from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from bookings.email_context import booking_confirmation_subject, bookings_confirmation_context


def _booking(pk, course_title, price='100.00', ref=None):
    course = SimpleNamespace(title=course_title)
    venue = SimpleNamespace(
        name='Studio',
        city='Bath',
        venue_address='1 High St',
        location='1 High St',
    )
    workshop = SimpleNamespace(
        course=course,
        venue=venue,
        tutor_id=None,
        start_date=None,
        get_absolute_url=lambda: f'/workshops/{pk}/',
    )
    return SimpleNamespace(
        id=pk,
        workshop=workshop,
        booking_reference=ref or f'REF{pk}',
        student_first_name='Ada',
        student_last_name='Lovelace',
        student_email='ada@example.com',
        student_phone='',
        special_requirements='',
        price_paid=Decimal(price),
        list_price=Decimal(price),
        voucher_code='',
        voucher_discount=Decimal('0.00'),
    )


class BookingConfirmationEmailContextTests(SimpleTestCase):
    def test_subject_for_single_booking(self):
        bookings = [_booking(1, 'Beginner DSLR')]
        self.assertEqual(
            booking_confirmation_subject(bookings),
            'Booking confirmed: Beginner DSLR',
        )

    def test_subject_for_two_different_courses(self):
        bookings = [
            _booking(1, 'Beginner DSLR'),
            _booking(2, 'Wildlife'),
        ]
        self.assertEqual(
            booking_confirmation_subject(bookings),
            'Booking confirmed: Beginner DSLR and Wildlife',
        )

    def test_subject_for_many_courses(self):
        bookings = [
            _booking(1, 'A'),
            _booking(2, 'B'),
            _booking(3, 'C'),
        ]
        self.assertEqual(
            booking_confirmation_subject(bookings),
            'Booking confirmed: 3 courses',
        )

    @patch('bookings.email_context.facebook_share_items_for_bookings', return_value=[])
    @patch('bookings.email_context.facebook_groups_context_for_bookings', return_value={
        'show_facebook_groups_cta': False,
        'going_digital_facebook_url': '',
        'local_facebook_groups': [],
        'local_facebook_group': None,
    })
    @patch('bookings.email_context.account_setup_from_bookings', return_value=None)
    @patch('bookings.email_context.site_url_for_booking', return_value='https://example.com')
    @patch('bookings.email_context.calendar_data_for_booking', return_value={
        'google_calendar_url': '',
        'outlook_calendar_url': '',
        'calendar_ics': '',
        'calendar_ics_filename': '',
    })
    def test_multi_booking_context_lists_items_and_total(self, *_mocks):
        bookings = [
            _booking(1, 'Beginner DSLR', '80.00'),
            _booking(2, 'Wildlife', '120.00'),
        ]
        context = bookings_confirmation_context(bookings)
        self.assertTrue(context['is_multi_booking'])
        self.assertEqual(context['booking_count'], 2)
        self.assertEqual(len(context['booking_items']), 2)
        self.assertEqual(context['total_price_paid'], Decimal('200.00'))
        self.assertEqual(context['booking_items'][0]['course_title'], 'Beginner DSLR')
        self.assertEqual(context['booking_items'][1]['course_title'], 'Wildlife')
