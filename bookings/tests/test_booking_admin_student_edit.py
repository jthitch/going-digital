from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from bookings.admin import BookingAdmin
from bookings.models import Booking


class BookingAdminStudentEditTests(SimpleTestCase):
    def setUp(self):
        self.admin = BookingAdmin(Booking, AdminSite())
        self.booking = MagicMock(name='booking')

    def _request(self, *, full_access):
        user = SimpleNamespace(
            is_active=True,
            is_staff=True,
            is_superuser=full_access,
            is_authenticated=True,
        )
        request = MagicMock()
        request.user = user
        return request

    @patch('bookings.admin_mixins.user_has_full_region_access', return_value=True)
    @patch('bookings.admin.user_has_full_region_access', return_value=True)
    def test_superuser_can_edit_student_fields(self, *_mocks):
        request = self._request(full_access=True)
        readonly = self.admin.get_readonly_fields(request, obj=self.booking)
        for field in BookingAdmin.student_editable_fields:
            self.assertNotIn(field, readonly)
        self.assertIn('student_email', readonly)
        self.assertTrue(self.admin.has_change_permission(request, self.booking))

    @patch('bookings.admin_mixins.user_can_view_booking', return_value=True)
    @patch('bookings.admin.user_has_full_region_access', return_value=False)
    @patch('bookings.admin_mixins.user_has_full_region_access', return_value=False)
    def test_franchisee_can_edit_only_student_fields(self, *_mocks):
        request = self._request(full_access=False)
        readonly = self.admin.get_readonly_fields(request, obj=self.booking)
        for field in BookingAdmin.student_editable_fields:
            self.assertNotIn(field, readonly)
        self.assertIn('student_email', readonly)
        self.assertIn('status', readonly)
        self.assertIn('price_paid', readonly)
        self.assertTrue(self.admin.has_change_permission(request, self.booking))
