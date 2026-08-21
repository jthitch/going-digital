"""Send day-after workshop follow-up emails with star ratings."""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.follow_up_email import follow_up_target_date, send_due_workshop_follow_ups


class Command(BaseCommand):
    help = (
        'Email students a follow-up one day after their workshop ends, with 1–5 star links. '
        'Safe to re-run — already-sent bookings are skipped.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List recipients on stdout without sending email or updating bookings.',
        )
        parser.add_argument(
            '--on-date',
            dest='on_date',
            help='Pretend today is this date (YYYY-MM-DD) when choosing workshops that ended yesterday.',
        )

    def handle(self, *args, **options):
        on_date = None
        raw = options.get('on_date')
        if raw:
            on_date = datetime.strptime(raw, '%Y-%m-%d').date()

        target = follow_up_target_date(on_date=on_date)
        self.stdout.write(
            f'Sending follow-ups for workshops ending on {target.isoformat()} '
            f'(run date: {(on_date or timezone.localdate()).isoformat()})…'
        )

        dry_run = options['dry_run']
        counts = send_due_workshop_follow_ups(on_date=on_date, dry_run=dry_run)
        if dry_run:
            for ref, email in counts.get('recipients') or []:
                self.stdout.write(f'  {ref} → {email}')
        prefix = 'Would send' if dry_run else 'Sent'
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix} {counts["sent"]} follow-up(s); '
                f'{counts["skipped"]} skipped; {counts["failed"]} failed.'
            )
        )
