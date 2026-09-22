"""Sync opted-in gd_customer rows to the Mailgun newsletter mailing list."""
from django.core.management.base import BaseCommand

from core.mailgun import mailgun_configured
from core.newsletter_sync import sync_newsletter_list


class Command(BaseCommand):
    help = (
        'Upsert gd_customer newsletter subscribers to the Mailgun mailing list '
        '(with region vars) and remove list members who are no longer opted in.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count planned upserts/removals without writing to Mailgun.',
        )
        parser.add_argument(
            '--keep-extras',
            action='store_true',
            help='Do not delete Mailgun members who are missing from gd_customer opt-ins.',
        )

    def handle(self, *args, **options):
        if not mailgun_configured():
            self.stderr.write(
                self.style.ERROR(
                    'Mailgun newsletter sync is not configured. '
                    'Set MAILGUN_API_KEY and MAILGUN_NEWSLETTER_LIST.'
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
                f'{prefix} {stats["upserted"]} member(s); '
                f'removed {stats["removed"]}; '
                f'skipped {stats["skipped"]}; '
                f'errors {stats["errors"]}.'
            )
        )
