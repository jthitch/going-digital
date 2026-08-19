from datetime import date
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from bookings.forms_reports import MONTHS_CUSTOM, BookingReportFilterForm
from bookings.reports import _iter_months_between


class IterMonthsBetweenTests(SimpleTestCase):
    def test_custom_range_includes_partial_months(self):
        months = list(_iter_months_between(date(2024, 1, 15), date(2024, 3, 3)))
        self.assertEqual(months, [(2024, 1), (2024, 2), (2024, 3)])

    def test_months_back_preset(self):
        months = list(
            _iter_months_between(date(2024, 1, 1), date(2024, 6, 15), months_back=3)
        )
        self.assertEqual(months, [(2024, 4), (2024, 5), (2024, 6)])

    def test_single_month_custom_range(self):
        months = list(_iter_months_between(date(2024, 5, 1), date(2024, 5, 31)))
        self.assertEqual(months, [(2024, 5)])


class BookingReportFilterFormCustomPeriodTests(SimpleTestCase):
    def _form(self, data):
        user = MagicMock()
        empty = MagicMock()
        empty.order_by.return_value = empty
        empty.none.return_value = empty
        with (
            patch('bookings.forms_reports.report_filter_regions', return_value=empty),
            patch('bookings.forms_reports.report_filter_tutors', return_value=empty),
        ):
            return BookingReportFilterForm(user, data)

    def test_custom_requires_dates(self):
        form = self._form({'months': MONTHS_CUSTOM})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_custom_with_dates(self):
        form = self._form({
            'months': MONTHS_CUSTOM,
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_months_back())
        self.assertEqual(
            form.cleaned_custom_date_range(),
            (date(2024, 1, 1), date(2024, 6, 30)),
        )

    def test_preset_ignores_dates(self):
        form = self._form({
            'months': '12',
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_months_back(), 12)
        self.assertIsNone(form.cleaned_custom_date_range())

    def test_custom_rejects_inverted_range(self):
        form = self._form({
            'months': MONTHS_CUSTOM,
            'start_date': '2024-06-30',
            'end_date': '2024-01-01',
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())
