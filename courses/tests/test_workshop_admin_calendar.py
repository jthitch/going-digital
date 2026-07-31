from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from courses.workshop_admin_calendar import (
    _parse_year_month,
    _shift_month,
    _workshop_days,
    build_workshop_calendar_context,
)


class WorkshopAdminCalendarHelpersTests(SimpleTestCase):
    def test_parse_year_month_defaults_on_bad_input(self):
        today = date(2026, 7, 15)
        self.assertEqual(_parse_year_month(None, None, today=today), (2026, 7))
        self.assertEqual(_parse_year_month('x', '2', today=today), (2026, 7))
        self.assertEqual(_parse_year_month('2026', '13', today=today), (2026, 7))

    def test_parse_year_month_valid(self):
        self.assertEqual(_parse_year_month('2025', '3', today=date(2026, 1, 1)), (2025, 3))

    def test_shift_month_across_year(self):
        self.assertEqual(_shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(_shift_month(2026, 12, 1), (2027, 1))

    def test_workshop_days_multi_day_clipped_to_month(self):
        workshop = SimpleNamespace(
            date=datetime(2026, 7, 30, 10, 0, 0),
            get_end_date=lambda: datetime(2026, 8, 2, 16, 0, 0),
        )
        days = _workshop_days(workshop, date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(days, [date(2026, 7, 30), date(2026, 7, 31)])


class WorkshopAdminCalendarContextTests(SimpleTestCase):
    @patch('courses.workshop_admin_calendar.reverse', return_value='/admin/courses/workshop/calendar/')
    def test_builds_weeks_and_places_workshop(self, _reverse):
        request = MagicMock(GET={'year': '2026', 'month': '7'})
        workshop = SimpleNamespace(
            pk=42,
            active=1,
            open_dated=0,
            date=datetime(2026, 7, 10, 9, 30, 0),
            end_at=datetime(2026, 7, 10, 16, 0, 0),
            course=SimpleNamespace(course_name='Get Off Auto'),
            venue=SimpleNamespace(venue_name='Cardiff'),
            get_end_date=lambda: datetime(2026, 7, 10, 16, 0, 0),
        )

        class FakeQS(list):
            def filter(self, *args, **kwargs):
                if kwargs.get('open_dated') == 1:
                    return FakeQS([])
                return FakeQS([workshop])

            def select_related(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def count(self):
                return len(self)

        context = build_workshop_calendar_context(request, FakeQS())
        self.assertEqual(context['calendar_year'], 2026)
        self.assertEqual(context['calendar_month'], 7)
        self.assertEqual(context['calendar_workshop_count'], 1)
        self.assertIn('/admin/courses/workshop/calendar/', context['calendar_prev_url'])

        found = False
        for week in context['calendar_weeks']:
            for day in week:
                if day['date'] == date(2026, 7, 10):
                    self.assertEqual(len(day['workshops']), 1)
                    self.assertEqual(day['workshops'][0]['id'], 42)
                    self.assertEqual(day['workshops'][0]['time_label'], '09:30')
                    found = True
        self.assertTrue(found)
