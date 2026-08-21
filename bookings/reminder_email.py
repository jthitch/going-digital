"""
Day-before workshop reminder emails for confirmed bookings.

Ops: run daily — `python manage.py send_workshop_reminders`
(optional `--dry-run`, `--on-date YYYY-MM-DD`).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from bookings.email_context import booking_reminder_context, booking_reminder_subject
from bookings.models import Booking
from core.mail import send_html_email

logger = logging.getLogger(__name__)


def reminder_target_date(*, on_date=None):
    """Workshop start calendar date that triggers a reminder when run on `on_date`."""
    return (on_date or timezone.localdate()) + timedelta(days=1)


def bookings_due_reminder(*, on_date=None):
    """
    Confirmed, paid bookings for fixed-date workshops starting on the reminder target date.
    """
    target = reminder_target_date(on_date=on_date)
    return (
        Booking.objects.filter(
            status='confirmed',
            payment__status='succeeded',
            reminder_email_sent_at__isnull=True,
            workshop__open_dated=0,
            workshop__active=1,
            workshop__date__date=target,
        )
        .exclude(Q(student_email='') | Q(student_email__isnull=True))
        .select_related(
            'workshop',
            'workshop__course',
            'workshop__venue',
            'payment',
        )
        .order_by('id')
    )


def send_workshop_reminder_email(booking, *, dry_run=False):
    """
    Send one day-before reminder to the student. Marks reminder_email_sent_at on success.
    """
    if booking.reminder_email_sent_at:
        return False

    workshop = booking.workshop
    if not workshop or workshop.open_dated or not workshop.start_date:
        return False

    if not booking.is_confirmed:
        return False

    student_email = (booking.student_email or '').strip()
    if not student_email:
        return False

    if dry_run:
        logger.info(
            'Dry run: would send workshop reminder for booking %s to %s',
            booking.booking_reference,
            student_email,
        )
        return True

    context = booking_reminder_context(booking)
    send_html_email(
        to=[student_email],
        subject=booking_reminder_subject(booking),
        html_template='emails/workshop_reminder.html',
        text_template='emails/workshop_reminder.txt',
        context=context,
        fail_silently=False,
    )
    booking.reminder_email_sent_at = timezone.now()
    booking.save(update_fields=['reminder_email_sent_at'])
    return True


def send_due_workshop_reminders(*, on_date=None, dry_run=False):
    """
    Send reminders for all bookings due on the target workshop date.

    Returns counts: sent, skipped, failed, and (when dry_run) recipients as
    (booking_reference, student_email) pairs for bookings that would be emailed.
    """
    sent = skipped = failed = 0
    recipients = []
    for booking in bookings_due_reminder(on_date=on_date).iterator(chunk_size=100):
        try:
            if send_workshop_reminder_email(booking, dry_run=dry_run):
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
                'Failed to send workshop reminder for booking %s',
                booking.booking_reference,
            )
    return {
        'sent': sent,
        'skipped': skipped,
        'failed': failed,
        'target_date': reminder_target_date(on_date=on_date),
        'recipients': recipients,
    }
