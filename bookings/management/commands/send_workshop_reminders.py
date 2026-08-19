"""Send day-before workshop reminder emails to confirmed students."""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.reminder_email import reminder_target_date, send_due_workshop_reminders


class Command(BaseCommand):
    help = (
        'Email students a reminder one day before their workshop (course details, '
        'workshop notes, tutor contact). Safe to re-run — already-sent bookings are skipped.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log recipients without sending email or updating bookings.',
        )
        parser.add_argument(
            '--on-date',
            dest='on_date',
            help='Pretend today is this date (YYYY-MM-DD) when choosing workshops starting tomorrow.',
        )

    def handle(self, *args, **options):
        on_date = None
        raw = options.get('on_date')
        if raw:
            on_date = datetime.strptime(raw, '%Y-%m-%d').date()

        target = reminder_target_date(on_date=on_date)
        self.stdout.write(
            f'Sending reminders for workshops on {target.isoformat()} '
            f'(run date: {(on_date or timezone.localdate()).isoformat()})…'
        )

        counts = send_due_workshop_reminders(on_date=on_date, dry_run=options['dry_run'])
        prefix = 'Would send' if options['dry_run'] else 'Sent'
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix} {counts["sent"]} reminder(s); '
                f'{counts["skipped"]} skipped; {counts["failed"]} failed.'
            )
        )
