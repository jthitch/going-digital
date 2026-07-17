from django.test import SimpleTestCase

from bookings.manual_booking import _normalize_phone, filter_workshops_for_manual_booking_picker


class ManualBookingHelpersTests(SimpleTestCase):
    def test_normalize_phone_strips_spaces(self):
        self.assertEqual(_normalize_phone('07565 716794'), '07565716794')
        self.assertEqual(_normalize_phone('+44 7700 900123'), '+447700900123')
        self.assertEqual(_normalize_phone(''), '')

    def test_manual_booking_workshop_filter_orders_today_then_older(self):
        class FakeQS:
            def filter(self, *args, **kwargs):
                self.filter_called = True
                return self

            def order_by(self, *args):
                self.order_args = args
                return self

        qs = FakeQS()
        result = filter_workshops_for_manual_booking_picker(qs)
        self.assertIs(result, qs)
        self.assertTrue(qs.filter_called)
        self.assertEqual(qs.order_args, ('-date', 'id'))

    def test_include_future_skips_date_filter(self):
        class FakeQS:
            def filter(self, *args, **kwargs):
                self.filter_called = True
                return self

            def order_by(self, *args):
                self.order_args = args
                return self

        qs = FakeQS()
        result = filter_workshops_for_manual_booking_picker(qs, include_future=True)
        self.assertIs(result, qs)
        self.assertFalse(getattr(qs, 'filter_called', False))
        self.assertEqual(qs.order_args, ('-date', 'id'))
