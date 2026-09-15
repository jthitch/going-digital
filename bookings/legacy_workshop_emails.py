"""Bridge legacy gd_booking attendees into bookings for reminder/follow-up emails."""
from __future__ import annotations

import logging
import re
import secrets
from decimal import Decimal

from django.db.models import Q
from django.db.models.functions import Coalesce, TruncDate

from bookings.models import Booking
from core.models import Customer
from courses.models import Workshop
from courses.workshop_student_report import load_legacy_workshop_student_rows

logger = logging.getLogger(__name__)

_PHONE_OK = re.compile(r'^\+?1?\d{9,15}$')


def confirmed_paid_or_legacy_q():
    """Bookings eligible for reminder/follow-up: Stripe-paid or legacy bridge."""
    return Q(status='confirmed') & (
        Q(payment__status='succeeded')
        | Q(legacy_gd_booking_id__isnull=False)
        | Q(legacy_attendee_id__isnull=False)
    )


def workshops_starting_on(target_date):
    return Workshop.objects.filter(
        active=1,
        open_dated=0,
        date__date=target_date,
    )


def workshops_ending_on(target_date):
    return (
        Workshop.objects.filter(active=1, open_dated=0)
        .annotate(
            workshop_end_day=TruncDate(Coalesce('end_at', 'date')),
        )
        .filter(workshop_end_day=target_date)
    )


def _safe_phone(raw):
    phone = (raw or '').strip()
    if phone and _PHONE_OK.match(phone):
        return phone
    return ''


def _bridge_reference(workshop_id, *, attendee_id=None, booking_id=None):
    if attendee_id:
        return f'L{workshop_id}-A{attendee_id}'
    if booking_id:
        return f'L{workshop_id}-B{booking_id}'
    return f'L{workshop_id}-X'


def _existing_bridge(workshop_id, row):
    qs = Booking.objects.filter(workshop_id=workshop_id)
    if row.legacy_attendee_id:
        return qs.filter(legacy_attendee_id=row.legacy_attendee_id).first()
    if row.legacy_booking_id:
        return qs.filter(
            legacy_gd_booking_id=row.legacy_booking_id,
            legacy_attendee_id__isnull=True,
        ).first()
    return None


def ensure_legacy_bridge_bookings(workshops):
    """
    Create confirmed Booking rows for paid legacy students on these workshops.

    Skips emails already covered by a new-site booking on the same workshop.
    Returns the number of bridge rows created.
    """
    created = 0
    for workshop in workshops:
        if not workshop or not workshop.pk:
            continue
        try:
            rows = load_legacy_workshop_student_rows(workshop.pk)
        except Exception:
            logger.exception(
                'Failed loading legacy students for workshop %s',
                workshop.pk,
            )
            continue

        covered_emails = {
            (email or '').strip().lower()
            for email in Booking.objects.filter(workshop_id=workshop.pk)
            .exclude(Q(student_email='') | Q(student_email__isnull=True))
            .values_list('student_email', flat=True)
        }

        for row in rows:
            email = (row.email or '').strip()
            if not email:
                continue
            email_key = email.lower()
            if email_key in covered_emails:
                continue
            if _existing_bridge(workshop.pk, row):
                covered_emails.add(email_key)
                continue
            if not row.legacy_booking_id and not row.legacy_attendee_id:
                continue

            ref = _bridge_reference(
                workshop.pk,
                attendee_id=row.legacy_attendee_id,
                booking_id=row.legacy_booking_id,
            )
            if Booking.objects.filter(booking_reference=ref).exists():
                ref = f'{ref}-{secrets.token_hex(3)}'

            customer = Customer.objects.filter(email__iexact=email).first()
            Booking.objects.create(
                workshop=workshop,
                customer=customer,
                user=None,
                payment=None,
                student_first_name=(row.first_name or '')[:100] or 'Guest',
                student_last_name=(row.last_name or '')[:100] or 'Student',
                student_email=email[:254],
                student_phone=_safe_phone(row.phone),
                special_requirements=(row.special_requirements or '')[:],
                loan_camera=bool(row.loan_camera),
                camera_make=(row.camera_make or '')[:120],
                camera_model=(row.camera_model or '')[:120],
                status='confirmed',
                booking_reference=ref,
                list_price=Decimal('0.00'),
                price_paid=Decimal('0.00'),
                legacy_gd_booking_id=row.legacy_booking_id,
                legacy_attendee_id=row.legacy_attendee_id,
            )
            covered_emails.add(email_key)
            created += 1
            logger.info(
                'Created legacy bridge booking %s for workshop %s (%s)',
                ref,
                workshop.pk,
                email,
            )
    return created


def legacy_preview_recipients(workshops, *, already_listed_emails=()):
    """
    (booking_reference, email) pairs for paid legacy students not already listed.

    Used by --dry-run so we do not create bridge Booking rows.
    """
    listed = {(e or '').strip().lower() for e in already_listed_emails if e}
    out = []
    for workshop in workshops:
        if not workshop or not workshop.pk:
            continue
        try:
            rows = load_legacy_workshop_student_rows(workshop.pk)
        except Exception:
            logger.exception(
                'Failed loading legacy students for workshop %s (dry-run)',
                workshop.pk,
            )
            continue
        covered = {
            (email or '').strip().lower()
            for email in Booking.objects.filter(workshop_id=workshop.pk)
            .exclude(Q(student_email='') | Q(student_email__isnull=True))
            .values_list('student_email', flat=True)
        }
        for row in rows:
            email = (row.email or '').strip()
            if not email:
                continue
            key = email.lower()
            if key in listed or key in covered:
                continue
            if not row.legacy_booking_id and not row.legacy_attendee_id:
                continue
            ref = _bridge_reference(
                workshop.pk,
                attendee_id=row.legacy_attendee_id,
                booking_id=row.legacy_booking_id,
            )
            out.append((ref, email))
            listed.add(key)
    return out
