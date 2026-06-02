"""Shared logic to mark a Stripe Checkout Session as paid in Django."""
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment


def _session_value(session, key, default=None):
    if isinstance(session, dict):
        return session.get(key, default)
    return getattr(session, key, default)


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
        payment.webhook_processed = source == 'checkout.session.completed'
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
    session_metadata = _session_value(session, 'metadata') or {}
    if not metadata and session_metadata:
        metadata = dict(session_metadata)

    try:
        if 'gift_voucher_basket_id' in metadata:
            _complete_gift_voucher(metadata, session_id)
        elif 'booking_id' in metadata:
            _complete_booking(metadata)
    except (Booking.DoesNotExist, KeyError, ValueError, TypeError):
        return payment

    return payment


def _complete_gift_voucher(metadata, session_id):
    from bookings.gift_voucher_basket import (
        create_vouchers_from_basket,
        get_vouchers_for_basket,
        update_basket_gateway_transaction,
    )
    from payments.tasks import send_gift_voucher_confirmation_email

    basket_id = int(metadata['gift_voucher_basket_id'])
    update_basket_gateway_transaction(basket_id, session_id)

    if get_vouchers_for_basket(basket_id):
        return

    voucher_codes = create_vouchers_from_basket(basket_id, session_id)
    if voucher_codes:
        send_gift_voucher_confirmation_email(basket_id, voucher_codes)


def _increment_workshop_places_booked(workshop_id):
    """Increment gd_workshop.places_booked (NULL is treated as 0)."""
    if not workshop_id:
        return
    from courses.models import Workshop

    Workshop.objects.filter(pk=workshop_id).update(
        places_booked=Coalesce(F('places_booked'), 0) + 1,
    )


def _complete_booking(metadata):
    from payments.tasks import send_booking_confirmation_email, send_payment_success_email

    booking_id = int(metadata['booking_id'])
    booking = Booking.objects.select_related('payment').get(id=booking_id)
    payment = getattr(booking, 'payment', None)
    pay_meta = dict(payment.metadata or {}) if payment else {}

    newly_confirmed = booking.status != 'confirmed'
    if newly_confirmed:
        booking.status = 'confirmed'
        booking.save(update_fields=['status', 'updated_at'])

    if not pay_meta.get('places_booked_applied'):
        _increment_workshop_places_booked(booking.workshop_id)
        if payment:
            pay_meta['places_booked_applied'] = True
            payment.metadata = pay_meta
            payment.save(update_fields=['metadata', 'updated_at'])

    if newly_confirmed:
        send_booking_confirmation_email(booking.id)
        send_payment_success_email(booking.id)
