"""
Day-after workshop follow-up emails with star-rating links.

Ops: run daily — `python manage.py send_workshop_follow_ups`
(optional `--dry-run`, `--on-date YYYY-MM-DD`).
"""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.db.models import Q
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from bookings.email_context import booking_follow_up_context, booking_follow_up_subject
from bookings.models import Booking
from core.mail import send_html_email

logger = logging.getLogger(__name__)


def follow_up_target_date(*, on_date=None):
    """Workshop end calendar date that triggers a follow-up when run on `on_date`."""
    return (on_date or timezone.localdate()) - timedelta(days=1)


def ensure_follow_up_token(booking):
    """Assign a unique follow-up token if missing; return the token."""
    token = (booking.follow_up_token or '').strip()
    if token:
        return token
    for _ in range(8):
        candidate = secrets.token_urlsafe(24)
        if not Booking.objects.filter(follow_up_token=candidate).exists():
            booking.follow_up_token = candidate
            booking.save(update_fields=['follow_up_token'])
            return candidate
    raise RuntimeError('Could not allocate a unique follow-up token.')


def bookings_due_follow_up(*, on_date=None):
    """
    Confirmed, paid bookings for fixed-date workshops that ended on the target date.
    """
    target = follow_up_target_date(on_date=on_date)
    return (
        Booking.objects.filter(
            status='confirmed',
            payment__status='succeeded',
            follow_up_email_sent_at__isnull=True,
            workshop__open_dated=0,
            workshop__active=1,
        )
        .annotate(
            workshop_end_day=TruncDate(
                Coalesce('workshop__end_at', 'workshop__date'),
            ),
        )
        .filter(workshop_end_day=target)
        .exclude(Q(student_email='') | Q(student_email__isnull=True))
        .select_related(
            'workshop',
            'workshop__course',
            'workshop__venue',
            'payment',
        )
        .order_by('id')
    )


def send_workshop_follow_up_email(booking, *, dry_run=False):
    """
    Send one day-after follow-up with star ratings. Marks follow_up_email_sent_at on success.
    """
    if booking.follow_up_email_sent_at:
        return False

    workshop = booking.workshop
    if not workshop or workshop.open_dated:
        return False
    if not workshop.get_end_date() and not workshop.start_date:
        return False

    if not booking.is_confirmed:
        return False

    student_email = (booking.student_email or '').strip()
    if not student_email:
        return False

    if dry_run:
        logger.info(
            'Dry run: would send workshop follow-up for booking %s to %s',
            booking.booking_reference,
            student_email,
        )
        return True

    ensure_follow_up_token(booking)
    booking.refresh_from_db(fields=['follow_up_token'])
    context = booking_follow_up_context(booking)
    send_html_email(
        to=[student_email],
        subject=booking_follow_up_subject(booking),
        html_template='emails/workshop_follow_up.html',
        text_template='emails/workshop_follow_up.txt',
        context=context,
        fail_silently=False,
    )
    booking.follow_up_email_sent_at = timezone.now()
    booking.save(update_fields=['follow_up_email_sent_at'])
    return True


def send_due_workshop_follow_ups(*, on_date=None, dry_run=False):
    """
    Send follow-ups for all bookings whose workshop ended on the target date.

    Returns counts: sent, skipped, failed, and (when dry_run) recipients as
    (booking_reference, student_email) pairs for bookings that would be emailed.
    """
    sent = skipped = failed = 0
    recipients = []
    for booking in bookings_due_follow_up(on_date=on_date).iterator(chunk_size=100):
        try:
            if send_workshop_follow_up_email(booking, dry_run=dry_run):
                sent += 1
                if dry_run:
                    recipients.append((
                        booking.booking_reference,
                        (booking.student_email or '').strip(),
                    ))
            else:
                skipped += 1
        except Exception:
            failed += 1
            logger.exception(
                'Failed to send workshop follow-up for booking %s',
                booking.booking_reference,
            )
    return {
        'sent': sent,
        'skipped': skipped,
        'failed': failed,
        'target_date': follow_up_target_date(on_date=on_date),
        'recipients': recipients,
    }
