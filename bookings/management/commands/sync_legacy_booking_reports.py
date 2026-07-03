"""Backfill legacy gd_report__* booking tables from bookings on the new site."""
from django.core.management.base import BaseCommand

from bookings.legacy_reports import sync_all_legacy_reports_for_booking, sync_booking_to_legacy_unpaid_report
from bookings.models import Booking


class Command(BaseCommand):
    help = (
        'Write bookings into gd_report__bookings_by_course, '
        'gd_report__bookings_by_payment_gateway, gd_report__bookings_summary, '
        'and gd_report__unpaid_bookings. Safe to re-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--since',
            help='Only bookings created on/after YYYY-MM-DD (optional).',
        )

    def handle(self, *args, **options):
        qs = Booking.objects.filter(
            status__in=['confirmed', 'pending'],
        ).order_by('id')
        since = options.get('since')
        if since:
            qs = qs.filter(created_at__date__gte=since)

        counts = {
            'course_created': 0,
            'course_updated': 0,
            'gateway_created': 0,
            'gateway_updated': 0,
            'summary_created': 0,
            'summary_updated': 0,
            'unpaid_created': 0,
            'unpaid_updated': 0,
            'skipped': 0,
        }

        for booking in qs.iterator(chunk_size=200):
            if booking.status == 'pending':
                result = sync_booking_to_legacy_unpaid_report(booking)
                if not result:
                    counts['skipped'] += 1
                    continue
                _, was_created = result
                if was_created:
                    counts['unpaid_created'] += 1
                else:
                    counts['unpaid_updated'] += 1
                continue

            results = sync_all_legacy_reports_for_booking(booking)
            if not any(results.values()):
                counts['skipped'] += 1
                continue
            for key, result in results.items():
                if not result:
                    continue
                _, was_created = result
                if was_created:
                    counts[f'{key}_created'] += 1
                else:
                    counts[f'{key}_updated'] += 1

        self.stdout.write(
            self.style.SUCCESS(
                'Synced legacy report rows: '
                f'course {counts["course_created"]} created / {counts["course_updated"]} updated; '
                f'payment gateway {counts["gateway_created"]} created / '
                f'{counts["gateway_updated"]} updated; '
                f'summary {counts["summary_created"]} created / {counts["summary_updated"]} updated; '
                f'unpaid {counts["unpaid_created"]} created / {counts["unpaid_updated"]} updated; '
                f'{counts["skipped"]} skipped.'
            )
        )
