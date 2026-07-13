from django.test import SimpleTestCase, override_settings

from bookings.calendar import _absolute_url


class AbsoluteUrlTests(SimpleTestCase):
    @override_settings(SITE_URL='https://staging.example.com')
    def test_absolute_url_without_site_base(self):
        """Regression: site_base=None must not raise UnboundLocalError."""
        self.assertEqual(
            _absolute_url('/account/my-bookings/'),
            'https://staging.example.com/account/my-bookings/',
        )

    def test_absolute_url_with_site_base(self):
        self.assertEqual(
            _absolute_url('/foo/', site_base='https://custom.example.com'),
            'https://custom.example.com/foo/',
        )
