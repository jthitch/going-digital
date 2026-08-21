from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from bookings.email_context import booking_follow_up_context, booking_follow_up_subject
from bookings.follow_up_email import (
    bookings_due_follow_up,
    follow_up_target_date,
    send_due_workshop_follow_ups,
    send_workshop_follow_up_email,
)


def _booking(
    pk,
    course_title,
    *,
    ref=None,
    start_date=None,
    end_date=None,
    open_dated=0,
    active=1,
    follow_up_sent=False,
    follow_up_token='',
    email='ada@example.com',
    is_confirmed=True,
):
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
        start_date=start_date,
        end_date=end_date,
        open_dated=open_dated,
        active=active,
        get_end_date=lambda: end_date or start_date,
        get_absolute_url=lambda: f'/workshops/{pk}/',
    )
    booking = SimpleNamespace(
        id=pk,
        workshop=workshop,
        booking_reference=ref or f'REF{pk}',
        student_first_name='Ada',
        student_last_name='Lovelace',
        student_email=email,
        student_phone='',
        special_requirements='',
        price_paid=Decimal('100.00'),
        list_price=Decimal('100.00'),
        voucher_code='',
        voucher_discount=Decimal('0.00'),
        follow_up_email_sent_at=timezone.now() if follow_up_sent else None,
        follow_up_token=follow_up_token,
        is_confirmed=is_confirmed,
        status='confirmed',
        save=MagicMock(),
        refresh_from_db=MagicMock(),
    )
    return booking


class WorkshopFollowUpEmailContextTests(SimpleTestCase):
    @patch('bookings.email_context.follow_up_email_copy', return_value={
        'intro': 'We hope you enjoyed your photography course.',
        'closing': 'Thank you for learning with Going Digital.',
        'feedback_prompt': 'Tell us more.',
    })
    @patch('bookings.email_context.site_url_for_booking', return_value='https://example.com')
    @patch('bookings.email_context.calendar_data_for_booking', return_value={
        'google_calendar_url': '',
        'outlook_calendar_url': '',
        'calendar_ics': '',
        'calendar_ics_filename': '',
    })
    @patch('bookings.email_context.franchisee_contract_details', return_value=None)
    def test_context_includes_star_urls(self, _contract, _cal, _site, _copy):
        start = datetime(2026, 8, 19, 10, 0)
        booking = _booking(1, 'Beginner DSLR', start_date=start, follow_up_token='tok123')
        ctx = booking_follow_up_context(booking)
        self.assertEqual(ctx['follow_up_intro'], 'We hope you enjoyed your photography course.')
        self.assertEqual(ctx['course_title'], 'Beginner DSLR')
        self.assertEqual(
            ctx['star_urls'][5],
            'https://example.com/bookings/follow-up/tok123/rate/5/',
        )
        self.assertEqual(
            ctx['star_urls'][1],
            'https://example.com/bookings/follow-up/tok123/rate/1/',
        )
        self.assertIn('How was your Beginner DSLR course?', booking_follow_up_subject(booking))


class WorkshopFollowUpSendTests(SimpleTestCase):
    def test_target_date_is_yesterday(self):
        on_date = timezone.localdate()
        self.assertEqual(follow_up_target_date(on_date=on_date), on_date - timedelta(days=1))

    @patch('bookings.follow_up_email.booking_follow_up_context', return_value={})
    @patch('bookings.follow_up_email.send_html_email')
    @patch('bookings.follow_up_email.timezone')
    @patch('bookings.follow_up_email.ensure_follow_up_token', return_value='abc')
    def test_send_marks_sent_at(self, _token, tz, send_mail, _ctx):
        sent_at = timezone.now()
        tz.now.return_value = sent_at
        booking = _booking(1, 'Beginner DSLR', start_date=datetime(2026, 8, 19, 10, 0))
        self.assertTrue(send_workshop_follow_up_email(booking))
        self.assertEqual(booking.follow_up_email_sent_at, sent_at)
        booking.save.assert_called_with(update_fields=['follow_up_email_sent_at'])
        send_mail.assert_called_once()

    def test_send_skips_already_sent_and_open_dated(self):
        sent = _booking(1, 'X', follow_up_sent=True, start_date=datetime(2026, 8, 19, 10, 0))
        open_dated = _booking(2, 'Y', open_dated=1, start_date=datetime(2026, 8, 19, 10, 0))
        unconfirmed = _booking(
            3, 'Z', is_confirmed=False, start_date=datetime(2026, 8, 19, 10, 0),
        )
        self.assertFalse(send_workshop_follow_up_email(sent))
        self.assertFalse(send_workshop_follow_up_email(open_dated))
        self.assertFalse(send_workshop_follow_up_email(unconfirmed))

    @patch('bookings.follow_up_email.Booking')
    def test_due_queryset_filters(self, booking_model):
        qs = MagicMock()
        booking_model.objects.filter.return_value.annotate.return_value.filter.return_value.exclude.return_value.select_related.return_value.order_by.return_value = qs
        result = bookings_due_follow_up(on_date=timezone.localdate())
        self.assertIs(result, qs)
        booking_model.objects.filter.assert_called_once()
        kwargs = booking_model.objects.filter.call_args.kwargs
        self.assertEqual(kwargs['status'], 'confirmed')
        self.assertTrue(kwargs['follow_up_email_sent_at__isnull'])

    @patch('bookings.follow_up_email.bookings_due_follow_up')
    @patch('bookings.follow_up_email.send_workshop_follow_up_email', side_effect=[True, False])
    def test_send_due_counts(self, _send, due):
        due.return_value.iterator.return_value = [MagicMock(), MagicMock()]
        counts = send_due_workshop_follow_ups()
        self.assertEqual(counts['sent'], 1)
        self.assertEqual(counts['skipped'], 1)
        self.assertEqual(counts['failed'], 0)
        self.assertEqual(counts['recipients'], [])

    @patch('bookings.follow_up_email.bookings_due_follow_up')
    @patch('bookings.follow_up_email.send_workshop_follow_up_email', return_value=True)
    def test_send_due_dry_run_lists_recipients(self, _send, due):
        b1 = MagicMock(booking_reference='REF1', student_email='a@example.com')
        b2 = MagicMock(booking_reference='REF2', student_email='b@example.com')
        due.return_value.iterator.return_value = [b1, b2]
        counts = send_due_workshop_follow_ups(dry_run=True)
        self.assertEqual(counts['sent'], 2)
        self.assertEqual(
            counts['recipients'],
            [('REF1', 'a@example.com'), ('REF2', 'b@example.com')],
        )


class FollowUpRateRoutingTests(SimpleTestCase):
    @patch('bookings.follow_up_views.google_write_review_url', return_value='https://google.example/write')
    @patch('bookings.follow_up_views._record_rating')
    @patch('bookings.follow_up_views._booking_for_token')
    def test_five_stars_redirects_to_google(self, booking_for_token, record, _google):
        booking = MagicMock()
        booking.workshop_id = 1
        booking_for_token.return_value = booking
        from django.test import RequestFactory

        request = RequestFactory().get('/bookings/follow-up/tok/rate/5/')
        from bookings.follow_up_views import FollowUpRateView

        response = FollowUpRateView.as_view()(request, token='tok', rating=5)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://google.example/write')
        record.assert_called_once_with(booking, 5)

    @patch('bookings.follow_up_views._record_rating')
    @patch('bookings.follow_up_views._booking_for_token')
    def test_four_stars_redirects_to_feedback(self, booking_for_token, record):
        booking = MagicMock()
        booking.workshop_id = 1
        booking_for_token.return_value = booking
        from django.test import RequestFactory

        request = RequestFactory().get('/bookings/follow-up/tok/rate/4/')
        from bookings.follow_up_views import FollowUpRateView

        response = FollowUpRateView.as_view()(request, token='tok', rating=4)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/bookings/follow-up/tok/feedback/', response['Location'])
        record.assert_called_once_with(booking, 4)
