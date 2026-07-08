from datetime import datetime

from django.test import SimpleTestCase

from courses.duration import (
    calendar_day_span,
    duration_hours_value,
    duration_iso8601,
    format_duration,
)


class DurationHelpersTests(SimpleTestCase):
    def test_single_day_hours(self):
        start = datetime(2026, 6, 1, 10, 0)
        end = datetime(2026, 6, 1, 16, 0)
        self.assertEqual(format_duration(start, end), '6 hours')
        self.assertEqual(duration_hours_value(start, end), 6)
        self.assertEqual(duration_iso8601(start, end), 'PT6H')

    def test_two_days_label(self):
        start = datetime(2026, 6, 1, 10, 0)
        end = datetime(2026, 6, 2, 16, 0)
        self.assertEqual(calendar_day_span(start, end), 2)
        self.assertEqual(format_duration(start, end), 'Two days')
        self.assertEqual(duration_hours_value(start, end), 0)
        self.assertEqual(duration_iso8601(start, end), 'P2D')

    def test_three_days_label(self):
        start = datetime(2026, 6, 1, 9, 0)
        end = datetime(2026, 6, 3, 17, 0)
        self.assertEqual(format_duration(start, end), 'Three days')

    def test_longer_multi_day(self):
        start = datetime(2026, 6, 1, 9, 0)
        end = datetime(2026, 6, 10, 17, 0)
        self.assertEqual(format_duration(start, end), '10 days')

    def test_one_hour_singular(self):
        start = datetime(2026, 6, 1, 10, 0)
        end = datetime(2026, 6, 1, 11, 0)
        self.assertEqual(format_duration(start, end), '1 hour')
