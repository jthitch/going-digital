"""Sync opted-in gd_customer rows to the Mailjet newsletter contact list."""
from django.core.management.base import BaseCommand

from core.mailjet import mailjet_configured
from core.newsletter_sync import sync_newsletter_list


class Command(BaseCommand):
    help = (
        'Upsert gd_customer newsletter subscribers to the Mailjet contact list '
        '(with region properties) and remove list members who are no longer opted in.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count planned upserts/removals without writing to Mailjet.',
        )
        parser.add_argument(
            '--keep-extras',
            action='store_true',
            help='Do not remove Mailjet list members missing from gd_customer opt-ins.',
        )

    def handle(self, *args, **options):
        if not mailjet_configured():
            self.stderr.write(
                self.style.ERROR(
                    'Mailjet newsletter sync is not configured. '
                    'Set MAILJET_API_KEY, MAILJET_API_SECRET, and MAILJET_NEWSLETTER_LIST_ID.'
                )
            )
            return

        dry_run = options['dry_run']
        stats = sync_newsletter_list(
            dry_run=dry_run,
            remove_extras=not options['keep_extras'],
        )
        prefix = 'Would upsert' if dry_run else 'Upserted'
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix} {stats["upserted"]} contact(s); '
                f'removed {stats["removed"]}; '
                f'skipped {stats["skipped"]}; '
                f'errors {stats["errors"]}.'
            )
        )
