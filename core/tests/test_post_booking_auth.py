from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from core.views_student import (
    _prime_account_setup_email_from_booking_ref,
    _safe_next_url,
)


class SafeNextUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_allows_same_origin_path(self):
        request = self.factory.get('/account/login/', {'next': '/account/my-bookings/'})
        request.get_host = lambda: 'goingdigital.co.uk'
        self.assertEqual(
            _safe_next_url(request, '/fallback/'),
            '/account/my-bookings/',
        )

    def test_rejects_protocol_relative(self):
        request = self.factory.get('/account/login/', {'next': '//evil.example/phish'})
        request.get_host = lambda: 'goingdigital.co.uk'
        self.assertEqual(_safe_next_url(request, '/fallback/'), '/fallback/')

    def test_rejects_external_absolute(self):
        request = self.factory.get('/account/login/', {'next': 'https://evil.example/'})
        request.get_host = lambda: 'goingdigital.co.uk'
        self.assertEqual(_safe_next_url(request, '/fallback/'), '/fallback/')


class PrimeAccountSetupEmailTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, **params):
        request = self.factory.get('/account/post-booking/community/', params)
        request.session = {}
        return request

    @patch('payments.checkout_session_context.load_bookings_from_checkout_context', return_value=[])
    @patch('core.views_student.Booking.objects')
    def test_ref_alone_does_not_prime_session(self, booking_objects, _checkout):
        booking = SimpleNamespace(
            pk=1,
            booking_reference='ABCD1234',
            student_email='victim@example.com',
        )
        booking_objects.filter.return_value.first.return_value = booking
        request = self._request(ref='ABCD1234')

        _prime_account_setup_email_from_booking_ref(request)

        self.assertNotIn('account_setup_email', request.session)

    @patch('payments.checkout_session_context.load_bookings_from_checkout_context', return_value=[])
    @patch('core.views_student.Booking.objects')
    def test_ref_with_matching_email_primes_session(self, booking_objects, _checkout):
        booking = SimpleNamespace(
            pk=1,
            booking_reference='ABCD1234',
            student_email='student@example.com',
        )
        booking_objects.filter.return_value.first.return_value = booking
        request = self._request(ref='ABCD1234', email='student@example.com')

        _prime_account_setup_email_from_booking_ref(request)

        self.assertEqual(request.session.get('account_setup_email'), 'student@example.com')

    @patch('payments.checkout_session_context.load_bookings_from_checkout_context', return_value=[])
    @patch('core.views_student.Booking.objects')
    def test_ref_with_wrong_email_does_not_prime(self, booking_objects, _checkout):
        booking = SimpleNamespace(
            pk=1,
            booking_reference='ABCD1234',
            student_email='student@example.com',
        )
        booking_objects.filter.return_value.first.return_value = booking
        request = self._request(ref='ABCD1234', email='attacker@example.com')

        _prime_account_setup_email_from_booking_ref(request)

        self.assertNotIn('account_setup_email', request.session)

    @patch('core.views_student.Booking.objects')
    def test_checkout_session_booking_primes_session(self, booking_objects):
        booking = SimpleNamespace(
            pk=42,
            booking_reference='ABCD1234',
            student_email='student@example.com',
        )
        booking_objects.filter.return_value.first.return_value = booking
        checkout_booking = MagicMock(pk=42)
        request = self._request(ref='ABCD1234')

        with patch(
            'payments.checkout_session_context.load_bookings_from_checkout_context',
            return_value=[checkout_booking],
        ):
            _prime_account_setup_email_from_booking_ref(request)

        self.assertEqual(request.session.get('account_setup_email'), 'student@example.com')
