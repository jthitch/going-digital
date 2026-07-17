from django.test import SimpleTestCase

from bookings.admin_booking_list import (
    _status_clause_legacy,
    filters_from_request,
)


class AdminBookingListFiltersTests(SimpleTestCase):
    def test_filters_from_request_workshop(self):
        request = type('R', (), {'GET': {'workshop__id__exact': '42', 'q': ' jane '}})()
        filters = filters_from_request(request)
        self.assertEqual(filters['workshop_id'], 42)
        self.assertEqual(filters['search'], 'jane')

    def test_legacy_completed_status_excludes(self):
        sql, params = _status_clause_legacy('completed')
        self.assertIn('1=0', sql)
        self.assertEqual(params, [])
