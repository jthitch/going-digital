"""Record refunds against workshop places (paid back outside the site)."""
from __future__ import annotations

import logging
from datetime import datetime, time
from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from bookings.models import Booking, BookingRefund
from bookings.workshop_student_move import (
    _legacy_rows_by_selection,
    _parse_student_keys,
    booking_selection_key,
    legacy_student_selection_key,
    movable_bookings_queryset,
    movable_legacy_student_rows,
)
from courses.models import Workshop
from courses.region_scope import user_can_access_workshop, user_has_full_region_access
from payments.checkout_completion import _adjust_workshop_places_booked

logger = logging.getLogger(__name__)

_LEGACY_STATUS_CANCELLED = 3
_LEGACY_STATUS_REFUNDED = 4


class WorkshopRefundError(Exception):
    """Validation or permission failure when recording a refund."""


def user_can_record_refund(user, workshop):
    if user is None or workshop is None:
        return False
    return user_has_full_region_access(user) or user_can_access_workshop(user, workshop)


def _booking_paid_amount(booking):
    paid = booking.price_paid if booking.price_paid is not None else Decimal('0.00')
    return Decimal(paid).quantize(Decimal('0.01'))


def _legacy_paid_amount(legacy_booking_id, workshop_id):
    """Best-effort paid amount for a legacy line (cash + voucher) to prefill the form."""
    if not legacy_booking_id:
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT IFNULL(bw.amount_paid, 0) + IFNULL(bw.amount_paid_by_voucher, 0)
            FROM gd_bookings_workshops bw
            WHERE bw.booking_id = %s
              AND bw.workshop_id = %s
            ORDER BY bw.id
            LIMIT 1
            """,
            [legacy_booking_id, workshop_id],
        )
        row = cursor.fetchone()
    if not row or row[0] is None:
        return None
    amount = Decimal(str(row[0])).quantize(Decimal('0.01'))
    return amount if amount > 0 else None


def refundable_student_choices(workshop):
    """
    Returns ``(choices, amounts)`` for the record-refund form.

    ``choices`` are ``(key, label)`` pairs; ``amounts`` maps key -> suggested
    refund amount string (the amount the student paid) where known.
    """
    choices = []
    amounts = {}
    if workshop is None or not workshop.pk:
        return choices, amounts

    for booking in movable_bookings_queryset(workshop):
        key = booking_selection_key(booking)
        name = f'{booking.student_first_name} {booking.student_last_name}'.strip()
        ref = booking.booking_reference or f'#{booking.pk}'
        paid = _booking_paid_amount(booking)
        email = booking.student_email or ''
        label = f'{name} — {email} ({ref}) — paid £{paid}' if email else f'{name} ({ref}) — paid £{paid}'
        choices.append((key, label))
        amounts[key] = str(paid)

    for row in movable_legacy_student_rows(workshop):
        key = legacy_student_selection_key(row)
        if not key:
            continue
        name = f'{row.first_name} {row.last_name}'.strip() or 'Legacy student'
        ref = row.booking_reference or key
        email = row.email or ''
        label = f'{name} — {email} ({ref}) [legacy]' if email else f'{name} ({ref}) [legacy]'
        choices.append((key, label))
        try:
            paid = _legacy_paid_amount(row.legacy_booking_id, workshop.pk)
        except Exception:
            logger.exception('Failed loading legacy paid amount for %s', key)
            paid = None
        if paid is not None:
            amounts[key] = str(paid)
    return choices, amounts


def has_refundable_students(workshop):
    if movable_bookings_queryset(workshop).exists():
        return True
    return any(legacy_student_selection_key(row) for row in movable_legacy_student_rows(workshop))


def _legacy_refund_datetime(refunded_on):
    """Naive local datetime for gd_bookings_workshops.refund_date."""
    if refunded_on == timezone.localdate():
        return timezone.localtime().replace(tzinfo=None, microsecond=0)
    return datetime.combine(refunded_on, time(12, 0))


def _cancel_bridge(workshop_id, row):
    from bookings.legacy_workshop_emails import _existing_bridge

    bridge = _existing_bridge(workshop_id, row)
    if bridge is None or bridge.status == 'refunded':
        return bridge
    bridge.status = 'refunded'
    bridge.cancelled_at = timezone.now()
    bridge.save(update_fields=['status', 'cancelled_at', 'updated_at'])
    return bridge


def _refund_legacy_attendee(attendee_id, workshop_id):
    """Mark the attendee refunded; returns gd_bookings_workshops.id (or None)."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT bookings_workshops_id
            FROM gd_bookings_workshops_attendees
            WHERE id = %s
              AND workshop_id = %s
              AND IFNULL(active, 1) = 1
              AND IFNULL(booking_status_id, 1) NOT IN (%s, %s)
            FOR UPDATE
            """,
            [attendee_id, workshop_id, _LEGACY_STATUS_CANCELLED, _LEGACY_STATUS_REFUNDED],
        )
        row = cursor.fetchone()
        if row is None:
            raise WorkshopRefundError(
                f'Legacy attendee #{attendee_id} is not on this workshop or is already refunded.'
            )
        cursor.execute(
            'UPDATE gd_bookings_workshops_attendees SET booking_status_id = %s WHERE id = %s',
            [_LEGACY_STATUS_REFUNDED, attendee_id],
        )
    return int(row[0]) if row[0] else None


def _legacy_line_has_active_attendees(bookings_workshops_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM gd_bookings_workshops_attendees
            WHERE bookings_workshops_id = %s
              AND IFNULL(active, 1) = 1
              AND IFNULL(booking_status_id, 1) NOT IN (%s, %s)
            LIMIT 1
            """,
            [bookings_workshops_id, _LEGACY_STATUS_CANCELLED, _LEGACY_STATUS_REFUNDED],
        )
        return cursor.fetchone() is not None


def _legacy_line_for_booking(legacy_booking_id, workshop_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM gd_bookings_workshops
            WHERE booking_id = %s
              AND workshop_id = %s
              AND IFNULL(refund_amount, 0) = 0
            ORDER BY id
            LIMIT 1
            FOR UPDATE
            """,
            [legacy_booking_id, workshop_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise WorkshopRefundError(
            f'Legacy booking #{legacy_booking_id} is not on this workshop or is already refunded.'
        )
    return int(row[0])


def _write_legacy_line_refund(bookings_workshops_id, amount, refunded_on, reason):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE gd_bookings_workshops
            SET refund_amount = %s,
                refund_date = %s,
                refund_reason = %s
            WHERE id = %s
            """,
            [amount, _legacy_refund_datetime(refunded_on), reason, bookings_workshops_id],
        )


def record_workshop_refund(
    *,
    workshop,
    student_key,
    amount,
    refunded_on,
    method,
    reason,
    user=None,
):
    """
    Record a refund for one student place on ``workshop`` and release the place.

    ``student_key`` uses ``b:<booking id>``, ``la:<attendee id>`` or ``lb:<gd_booking id>``.
    No money is moved: the refund is assumed to have been paid to the student directly.
    Returns the created BookingRefund.
    """
    if workshop is None or not workshop.pk:
        raise WorkshopRefundError('Workshop is required.')
    if user is not None and not user_can_record_refund(user, workshop):
        raise WorkshopRefundError('You cannot record refunds on this workshop.')

    amount = Decimal(str(amount or 0)).quantize(Decimal('0.01'))
    if amount <= 0:
        raise WorkshopRefundError('Refund amount must be greater than zero.')
    reason = (reason or '').strip()
    if not reason:
        raise WorkshopRefundError('Please enter a reason for the refund.')
    if refunded_on is None:
        refunded_on = timezone.localdate()
    valid_methods = {value for value, _label in BookingRefund.METHOD_CHOICES}
    if method not in valid_methods:
        raise WorkshopRefundError('Choose how the refund was paid.')

    new_ids, attendee_ids, legacy_booking_ids = _parse_student_keys([student_key])
    if len(new_ids) + len(attendee_ids) + len(legacy_booking_ids) != 1:
        raise WorkshopRefundError('Select one student to refund.')

    recorded_by = user if getattr(user, 'is_authenticated', False) else None

    with transaction.atomic():
        workshop = Workshop.objects.select_for_update().get(pk=workshop.pk)

        if new_ids:
            booking = (
                Booking.objects.select_for_update()
                .filter(pk=new_ids[0])
                .filter(legacy_gd_booking_id__isnull=True, legacy_attendee_id__isnull=True)
                .first()
            )
            if booking is None or booking.workshop_id != workshop.pk:
                raise WorkshopRefundError('That booking is not on this workshop.')
            if booking.status != 'confirmed':
                raise WorkshopRefundError(
                    f'Booking {booking.booking_reference} is not confirmed and cannot be refunded.'
                )
            max_amount = max(
                _booking_paid_amount(booking),
                Decimal(booking.list_price or 0).quantize(Decimal('0.01')),
            )
            if max_amount > 0 and amount > max_amount:
                raise WorkshopRefundError(
                    f'Refund £{amount} is more than the £{max_amount} paid for this booking.'
                )
            booking.status = 'refunded'
            booking.cancelled_at = timezone.now()
            booking.save(update_fields=['status', 'cancelled_at', 'updated_at'])
            refund = BookingRefund.objects.create(
                booking=booking,
                workshop=workshop,
                booking_reference=booking.booking_reference or '',
                student_name=f'{booking.student_first_name} {booking.student_last_name}'.strip(),
                student_email=booking.student_email or '',
                amount=amount,
                refunded_on=refunded_on,
                method=method,
                reason=reason,
                recorded_by=recorded_by,
            )
        else:
            by_attendee, by_booking = _legacy_rows_by_selection(workshop)
            if attendee_ids:
                row = by_attendee.get(attendee_ids[0])
                if row is None:
                    raise WorkshopRefundError(
                        f'Legacy attendee #{attendee_ids[0]} is not on this workshop.'
                    )
                bw_id = _refund_legacy_attendee(row.legacy_attendee_id, workshop.pk)
            else:
                row = by_booking.get(legacy_booking_ids[0])
                if row is None:
                    raise WorkshopRefundError(
                        f'Legacy booking #{legacy_booking_ids[0]} is not on this workshop.'
                    )
                bw_id = _legacy_line_for_booking(row.legacy_booking_id, workshop.pk)

            bridge = _cancel_bridge(workshop.pk, row)
            refund = BookingRefund.objects.create(
                booking=bridge,
                workshop=workshop,
                legacy_gd_booking_id=row.legacy_booking_id,
                legacy_attendee_id=row.legacy_attendee_id,
                legacy_bookings_workshops_id=bw_id,
                booking_reference=row.booking_reference or '',
                student_name=f'{row.first_name} {row.last_name}'.strip(),
                student_email=row.email or '',
                amount=amount,
                refunded_on=refunded_on,
                method=method,
                reason=reason,
                recorded_by=recorded_by,
            )

            # Legacy treats refund_amount > 0 as "whole line refunded", so only
            # write it once every attendee on a multi-place line is refunded.
            if bw_id and (
                legacy_booking_ids or not _legacy_line_has_active_attendees(bw_id)
            ):
                line_total = (
                    BookingRefund.objects.filter(legacy_bookings_workshops_id=bw_id)
                    .aggregate(total=Sum('amount'))['total']
                    or amount
                )
                _write_legacy_line_refund(bw_id, line_total, refunded_on, reason)

        _adjust_workshop_places_booked(workshop.pk, -1)

    return refund


class RecordRefundForm(forms.Form):
    student = forms.ChoiceField(choices=(), label='Student')
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        label='Amount refunded (£)',
        help_text='The amount actually paid back, e.g. the course fee minus any admin fee.',
    )
    refunded_on = forms.DateField(
        label='Date refunded',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    method = forms.ChoiceField(
        choices=BookingRefund.METHOD_CHOICES,
        initial=BookingRefund.METHOD_BANK_TRANSFER,
        label='How was it paid?',
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Reason',
    )

    def __init__(self, *args, workshop=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices, amounts = refundable_student_choices(workshop)
        self.student_amounts = amounts
        self.fields['student'].choices = [('', '— Select student —')] + choices
        if not self.is_bound:
            self.fields['refunded_on'].initial = timezone.localdate()
