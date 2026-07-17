"""Create confirmed bookings for walk-up students who pay the tutor on the day."""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.report_payment_data import CASH_GATEWAY_ID
from core.customer_service import get_or_create_customer_record
from payments.checkout_completion import _increment_workshop_places_booked
from payments.models import Payment

logger = logging.getLogger(__name__)

MANUAL_TUTOR_INTENT = 'manual_tutor'


def filter_workshops_for_manual_booking_picker(queryset, include_future=False):
    """
    Workshops for the manual-booking picker.

    Default: today first, then older dates (1 week ago, 2 weeks ago, …).
    With include_future=True: all workshops, newest date first (future included).
    Open-dated workshops are always included.
    """
    from django.db.models import Q
    from django.utils import timezone

    if include_future:
        return queryset.order_by('-date', 'id')

    end = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=999999)
    return queryset.filter(
        Q(open_dated=1) | Q(date__isnull=True) | Q(date__lte=end)
    ).order_by('-date', 'id')


def _normalize_phone(phone):
    return ''.join(ch for ch in (phone or '') if ch.isdigit() or ch == '+')


def create_manual_booking(
    *,
    workshop,
    student_first_name,
    student_last_name,
    student_email,
    student_phone='',
    special_requirements='',
    loan_camera=False,
    price_paid=None,
    list_price=None,
    send_confirmation_email=True,
    created_by=None,
):
    """
    Create a confirmed booking paid directly to the tutor (cash / on-the-day).

    Returns the saved Booking.
    """
    if workshop is None:
        raise ValueError('Workshop is required.')

    first_name = (student_first_name or '').strip()
    last_name = (student_last_name or '').strip()
    email = (student_email or '').strip()
    if not first_name or not last_name or not email:
        raise ValueError('Student first name, last name, and email are required.')

    phone = _normalize_phone(student_phone)
    workshop_price = Decimal(str(workshop.price or 0))
    if list_price is None:
        list_price = workshop_price
    else:
        list_price = Decimal(str(list_price))
    if price_paid is None:
        price_paid = list_price
    else:
        price_paid = Decimal(str(price_paid))

    customer, _ = get_or_create_customer_record(
        email,
        first_name,
        last_name,
        phone=phone,
    )

    notes = (special_requirements or '').strip()
    created_by_id = getattr(created_by, 'pk', None) or created_by

    with transaction.atomic():
        payment = Payment.objects.create(
            user=None,
            intent_type=MANUAL_TUTOR_INTENT,
            stripe_id=f'manual-{uuid.uuid4().hex}',
            status='succeeded',
            amount=price_paid,
            currency='gbp',
            description=f'Manual booking — paid to tutor ({workshop})',
            metadata={
                'payment_method': 'paid_to_tutor',
                'payment_gateway_id': CASH_GATEWAY_ID,
                'manual_payment_option': 1,
                'created_by_id': created_by_id,
                'places_booked_applied': True,
                'confirmation_email_sent': bool(send_confirmation_email),
            },
            succeeded_at=timezone.now(),
            webhook_processed=True,
        )

        booking = Booking(
            workshop=workshop,
            customer=customer,
            payment=payment,
            student_first_name=first_name,
            student_last_name=last_name,
            student_email=email,
            student_phone=phone,
            special_requirements=notes,
            loan_camera=bool(loan_camera),
            list_price=list_price,
            price_paid=price_paid,
            status='confirmed',
        )
        booking.save()

        payment.metadata = {
            **dict(payment.metadata or {}),
            'booking_id': booking.pk,
        }
        payment.save(update_fields=['metadata', 'updated_at'])

        _increment_workshop_places_booked(workshop.pk, 1)

    try:
        from bookings.legacy_reports import sync_all_legacy_reports_for_booking

        sync_all_legacy_reports_for_booking(booking.pk)
    except Exception:
        logger.exception(
            'Failed to sync manual booking %s to legacy report tables',
            booking.pk,
        )

    if send_confirmation_email:
        try:
            from payments.tasks import send_booking_confirmation_email

            send_booking_confirmation_email(booking.pk)
        except Exception:
            logger.exception(
                'Failed to send confirmation email for manual booking %s',
                booking.pk,
            )
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(pk=payment.pk)
                meta = dict(payment.metadata or {})
                meta['confirmation_email_sent'] = False
                payment.metadata = meta
                payment.save(update_fields=['metadata', 'updated_at'])

    return booking
