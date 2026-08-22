"""Shared logic to mark a Stripe Checkout Session as paid in Django."""
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment


def _session_value(session, key, default=None):
    if isinstance(session, dict):
        return session.get(key, default)
    return getattr(session, key, default)


def stripe_metadata_dict(metadata):
    """Convert Stripe Checkout metadata (StripeObject or dict) to a plain dict."""
    if not metadata:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    try:
        return {key: metadata[key] for key in metadata.keys()}
    except (AttributeError, KeyError, TypeError):
        return {}


def checkout_session_is_paid(session):
    """True when Stripe reports the checkout session as successfully paid."""
    payment_status = _session_value(session, 'payment_status')
    status = _session_value(session, 'status')
    return payment_status == 'paid' or status == 'complete'


def complete_checkout_session(session, *, source='checkout.session.completed'):
    """
    Idempotently record payment success and run booking / gift-voucher side effects.
    Used by webhooks and the payment success page (local dev without Stripe CLI).
    """
    if not checkout_session_is_paid(session):
        return None

    session_id = _session_value(session, 'id')
    if not session_id:
        return None

    try:
        payment = Payment.objects.get(stripe_id=session_id)
    except Payment.DoesNotExist:
        return None

    already_recorded = payment.status == 'succeeded'
    now = timezone.now()

    if not already_recorded:
        payment.status = 'succeeded'
        payment.succeeded_at = now
        payment.last_webhook_event = source
        if source == 'checkout.session.completed':
            payment.webhook_processed = True
        payment.save(
            update_fields=[
                'status',
                'succeeded_at',
                'last_webhook_event',
                'webhook_processed',
                'updated_at',
            ]
        )

    metadata = payment.metadata or {}
    session_metadata = stripe_metadata_dict(_session_value(session, 'metadata'))
    if not metadata and session_metadata:
        metadata = session_metadata

    try:
        if 'gift_voucher_basket_id' in metadata:
            _complete_gift_voucher(metadata, session_id, payment)
        elif 'workshop_basket_id' in metadata:
            _complete_workshop_basket(metadata, payment)
        elif 'booking_id' in metadata:
            _complete_booking(metadata)
    except (Booking.DoesNotExist, KeyError, ValueError, TypeError):
        return payment

    return payment


def _complete_gift_voucher(metadata, session_id, payment):
    from bookings.gift_voucher_basket import (
        create_vouchers_from_basket,
        get_vouchers_for_basket,
        update_basket_gateway_transaction,
    )
    from payments.tasks import send_gift_voucher_confirmation_email

    basket_id = int(metadata['gift_voucher_basket_id'])
    update_basket_gateway_transaction(basket_id, session_id)

    voucher_codes = get_vouchers_for_basket(basket_id)
    if not voucher_codes:
        voucher_codes = create_vouchers_from_basket(basket_id, session_id)
    if not voucher_codes:
        return

    should_send_email = False
    payment_id = None

    with transaction.atomic():
        locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
        payment_id = locked_payment.pk
        pay_meta = dict(locked_payment.metadata or {})
        if not pay_meta.get('confirmation_email_sent'):
            pay_meta['confirmation_email_sent'] = True
            should_send_email = True
            locked_payment.metadata = pay_meta
            locked_payment.save(update_fields=['metadata', 'updated_at'])

    if should_send_email:
        try:
            send_gift_voucher_confirmation_email(basket_id, voucher_codes)
        except Exception:
            with transaction.atomic():
                locked_payment = Payment.objects.select_for_update().get(pk=payment_id)
                pay_meta = dict(locked_payment.metadata or {})
                pay_meta.pop('confirmation_email_sent', None)
                locked_payment.metadata = pay_meta
                locked_payment.save(update_fields=['metadata', 'updated_at'])
            raise


def _sync_legacy_report_for_booking(booking_id):
    """Best-effort legacy report row; must not fail checkout."""
    import logging

    from bookings.legacy_reports import sync_all_legacy_reports_for_booking

    logger = logging.getLogger(__name__)
    try:
        sync_all_legacy_reports_for_booking(booking_id)
    except Exception:
        logger.exception(
            'Failed to sync booking %s to legacy report tables',
            booking_id,
        )


def _increment_workshop_places_booked(workshop_id, places=1):
    """Increment gd_workshop.places_booked (NULL is treated as 0)."""
    if not workshop_id or places < 1:
        return
    from courses.models import Workshop

    Workshop.objects.filter(pk=workshop_id).update(
        places_booked=Coalesce(F('places_booked'), 0) + places,
    )


def _complete_workshop_basket(metadata, payment):
    """Create (if needed) and confirm bookings for a workshop basket payment."""
    from collections import Counter

    from core.models import Customer
    from payments.tasks import send_booking_confirmation_emails
    from bookings.workshop_basket import (
        create_confirmed_bookings_from_basket_data,
        get_workshop_basket,
        update_workshop_basket_booking_ids,
    )

    basket_id = int(metadata['workshop_basket_id'])
    booking_ids = metadata.get('booking_ids') or []
    if isinstance(booking_ids, str):
        booking_ids = [int(x) for x in booking_ids.split(',') if x.strip().isdigit()]
    else:
        booking_ids = [int(x) for x in booking_ids]

    basket = get_workshop_basket(basket_id)
    if not booking_ids and basket:
        booking_ids = [
            int(x) for x in (basket['basket_data'].get('booking_ids') or []) if str(x).isdigit()
        ]

    should_send_confirmation = False
    places_by_workshop = Counter()
    payment_id = payment.pk
    apply_places = False
    places_to_apply = {}

    with transaction.atomic():
        locked_payment = Payment.objects.select_for_update().get(pk=payment_id)
        pay_meta = dict(locked_payment.metadata or {})

        # Prefer ids already recorded on a prior completion (idempotent).
        meta_booking_ids = pay_meta.get('booking_ids') or []
        if isinstance(meta_booking_ids, str):
            meta_booking_ids = [
                int(x) for x in meta_booking_ids.split(',') if str(x).strip().isdigit()
            ]
        else:
            meta_booking_ids = [int(x) for x in meta_booking_ids if str(x).isdigit()]
        if meta_booking_ids:
            booking_ids = meta_booking_ids

        if not booking_ids:
            if not basket:
                return
            customer_id = basket.get('customer_id') or basket['basket_data'].get('customer_id')
            if not customer_id:
                return
            customer = Customer.objects.get(pk=customer_id)
            booking_ids = create_confirmed_bookings_from_basket_data(
                basket['basket_data'],
                customer,
                payment=locked_payment,
            )
            update_workshop_basket_booking_ids(basket_id, booking_ids)
            pay_meta['booking_ids'] = booking_ids
            pay_meta['workshop_basket_id'] = basket_id

        apply_places = not pay_meta.get('places_booked_applied')

        for booking_id in booking_ids:
            booking = Booking.objects.select_for_update().get(id=booking_id)
            if booking.payment_id != locked_payment.pk:
                booking.payment = locked_payment
                booking.save(update_fields=['payment', 'updated_at'])

            if booking.status != 'confirmed':
                booking.status = 'confirmed'
                booking.save(update_fields=['status', 'updated_at'])

            places_by_workshop[booking.workshop_id] += 1

            if not pay_meta.get('voucher_redeemed') and (
                booking.voucher_id or booking.discount_code_id
            ):
                from bookings.voucher_redemption import redeem_voucher_for_booking
                redeem_voucher_for_booking(booking)

        if not pay_meta.get('voucher_redeemed'):
            pay_meta['voucher_redeemed'] = True

        if not booking_ids:
            already_emailed = True
        else:
            already_emailed = bool(pay_meta.get('confirmation_email_sent')) or all(
                pay_meta.get(f'confirmation_email_sent_{booking_id}')
                for booking_id in booking_ids
            )
        if booking_ids and not already_emailed:
            should_send_confirmation = True
            pay_meta['confirmation_email_sent'] = True
            for booking_id in booking_ids:
                pay_meta[f'confirmation_email_sent_{booking_id}'] = True

        if apply_places:
            pay_meta['places_booked_applied'] = True
            places_to_apply = dict(places_by_workshop)

        locked_payment.metadata = pay_meta
        locked_payment.save(update_fields=['metadata', 'updated_at'])

    if apply_places:
        for workshop_id, count in places_to_apply.items():
            _increment_workshop_places_booked(workshop_id, count)

    if should_send_confirmation:
        try:
            send_booking_confirmation_emails(booking_ids)
        except Exception:
            with transaction.atomic():
                locked_payment = Payment.objects.select_for_update().get(pk=payment_id)
                pay_meta = dict(locked_payment.metadata or {})
                pay_meta.pop('confirmation_email_sent', None)
                for booking_id in booking_ids:
                    pay_meta.pop(f'confirmation_email_sent_{booking_id}', None)
                locked_payment.metadata = pay_meta
                locked_payment.save(update_fields=['metadata', 'updated_at'])
            raise

    for booking_id in booking_ids:
        _sync_legacy_report_for_booking(booking_id)


def _complete_booking(metadata):
    """Confirm booking once; increment places and send email at most once (webhook + success safe)."""
    from payments.tasks import send_booking_confirmation_email

    booking_id = int(metadata['booking_id'])
    should_increment_places = False
    should_send_email = False
    workshop_id = None
    payment_id = None

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(id=booking_id)
        payment = booking.payment
        if not payment:
            return

        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        payment_id = payment.pk
        pay_meta = dict(payment.metadata or {})

        if booking.status != 'confirmed':
            booking.status = 'confirmed'
            booking.save(update_fields=['status', 'updated_at'])

        if not pay_meta.get('places_booked_applied'):
            pay_meta['places_booked_applied'] = True
            should_increment_places = True
            workshop_id = booking.workshop_id

        if not pay_meta.get('confirmation_email_sent'):
            pay_meta['confirmation_email_sent'] = True
            should_send_email = True

        if not pay_meta.get('voucher_redeemed'):
            if booking.voucher_id or booking.discount_code_id:
                from bookings.voucher_redemption import redeem_voucher_for_booking
                redeem_voucher_for_booking(booking)
                pay_meta['voucher_id'] = booking.voucher_id
                pay_meta['discount_code_id'] = booking.discount_code_id
                pay_meta['voucher_code'] = booking.voucher_code
                pay_meta['voucher_discount'] = str(booking.voucher_discount)
            pay_meta['voucher_redeemed'] = True

        payment.metadata = pay_meta
        payment.save(update_fields=['metadata', 'updated_at'])

    if should_increment_places:
        _increment_workshop_places_booked(workshop_id)

    if should_send_email:
        try:
            send_booking_confirmation_email(booking_id)
        except Exception:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(pk=payment_id)
                pay_meta = dict(payment.metadata or {})
                pay_meta.pop('confirmation_email_sent', None)
                payment.metadata = pay_meta
                payment.save(update_fields=['metadata', 'updated_at'])
            raise

    _sync_legacy_report_for_booking(booking_id)
