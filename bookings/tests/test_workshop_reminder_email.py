from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from bookings.email_context import booking_reminder_context, booking_reminder_subject
from bookings.reminder_email import (
    bookings_due_reminder,
    reminder_target_date,
    send_due_workshop_reminders,
    send_workshop_reminder_email,
)


def _booking(
    pk,
    course_title,
    *,
    ref=None,
    tutor_id=None,
    reminder_message='',
    byline_plain='',
    start_date=None,
    open_dated=0,
    active=1,
    reminder_sent=False,
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
        tutor_id=tutor_id,
        start_date=start_date,
        open_dated=open_dated,
        active=active,
        reminder_message=reminder_message,
        byline_plain=byline_plain,
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
        reminder_email_sent_at=timezone.now() if reminder_sent else None,
        is_confirmed=is_confirmed,
        status='confirmed',
        save=MagicMock(),
    )
    return booking


class WorkshopReminderEmailContextTests(SimpleTestCase):
    @patch('bookings.email_context.reminder_email_copy', return_value={
        'intro': 'This is a friendly reminder that your photography course is tomorrow.',
        'closing': 'We look forward to seeing you tomorrow.',
    })
    @patch('bookings.tutor_contact.tutor_contact_for_booking', return_value={'mailto_url': 'mailto:tutor@example.com'})
    @patch('bookings.email_context.Tutor')
    @patch('bookings.email_context.site_url_for_booking', return_value='https://example.com')
    @patch('bookings.email_context.calendar_data_for_booking', return_value={
        'google_calendar_url': '',
        'outlook_calendar_url': '',
        'calendar_ics': '',
        'calendar_ics_filename': '',
    })
    @patch('bookings.email_context.franchisee_contract_details', return_value=None)
    def test_context_includes_notes_and_tutor_telephone(self, _contract, _cal, _site, tutor_model, _contact, _copy):
        start = datetime(2026, 8, 20, 10, 0)
        tutor = MagicMock()
        tutor.configure_mock(
            email='jane@example.com',
            telephone='07700 900123',
        )
        tutor.__str__.return_value = 'Jane Tutor'
        tutor_model.objects.filter.return_value.first.return_value = tutor
        booking = _booking(
            1,
            'Beginner DSLR',
            tutor_id=5,
            reminder_message='Bring your camera and a tripod.',
            byline_plain='Meet at the main entrance.',
            start_date=start,
        )
        context = booking_reminder_context(booking)

        self.assertEqual(context['course_title'], 'Beginner DSLR')
        self.assertEqual(context['tutor_name'], 'Jane Tutor')
        self.assertEqual(context['tutor_email'], 'jane@example.com')
        self.assertEqual(context['tutor_telephone'], '07700 900123')
        self.assertEqual(
            context['workshop_notes'],
            [
                ('Course notes', 'Bring your camera and a tripod.'),
                ('Workshop details', 'Meet at the main entrance.'),
            ],
        )
        self.assertIn('reminder_intro', context)
        self.assertIn('reminder_closing', context)

    def test_subject_includes_course_and_date(self):
        start = datetime(2026, 8, 20, 10, 0)
        booking = _booking(1, 'Beginner DSLR', start_date=start)
        self.assertEqual(
            booking_reminder_subject(booking),
            'Reminder: Beginner DSLR — Thursday 20 August',
        )


class WorkshopReminderSendTests(SimpleTestCase):
    @patch('bookings.reminder_email.booking_reminder_context', return_value={})
    @patch('bookings.reminder_email.send_html_email')
    @patch('bookings.reminder_email.timezone')
    def test_send_marks_booking_and_skips_already_sent(self, mock_timezone, send_mail, _context):
        sent_at = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)
        mock_timezone.now.return_value = sent_at
        booking = _booking(
            1,
            'Beginner DSLR',
            start_date=datetime(2026, 8, 20, 10, 0),
        )

        self.assertTrue(send_workshop_reminder_email(booking))
        send_mail.assert_called_once()
        self.assertEqual(booking.reminder_email_sent_at, sent_at)
        booking.save.assert_called_once_with(update_fields=['reminder_email_sent_at'])

        send_mail.reset_mock()
        booking.save.reset_mock()
        self.assertFalse(send_workshop_reminder_email(booking))
        send_mail.assert_not_called()
        booking.save.assert_not_called()

    def test_send_skips_open_dated_and_unconfirmed(self):
        open_dated = _booking(
            1,
            'Beginner DSLR',
            open_dated=1,
            start_date=datetime(2026, 8, 20, 10, 0),
        )
        unconfirmed = _booking(
            2,
            'Wildlife',
            is_confirmed=False,
            start_date=datetime(2026, 8, 20, 10, 0),
        )
        self.assertFalse(send_workshop_reminder_email(open_dated))
        self.assertFalse(send_workshop_reminder_email(unconfirmed))

    @patch('bookings.reminder_email.Booking')
    def test_bookings_due_reminder_builds_expected_query(self, booking_model):
        tomorrow = timezone.localdate() + timedelta(days=1)
        qs = MagicMock()
        booking_model.objects.filter.return_value.exclude.return_value.select_related.return_value.order_by.return_value = qs
        result = bookings_due_reminder()
        booking_model.objects.filter.assert_called_once_with(
            status='confirmed',
            payment__status='succeeded',
            reminder_email_sent_at__isnull=True,
            workshop__open_dated=0,
            workshop__active=1,
            workshop__date__date=tomorrow,
        )
        booking_model.objects.filter.return_value.exclude.return_value.select_related.return_value.order_by.assert_called_once_with('id')
        self.assertIs(result, qs)
        self.assertEqual(reminder_target_date(), tomorrow)

    @patch('bookings.reminder_email.bookings_due_reminder')
    @patch('bookings.reminder_email.send_workshop_reminder_email', side_effect=[True, False])
    def test_send_due_workshop_reminders_counts(self, _send_one, due_query):
        due_query.return_value.iterator.return_value = [_booking(1, 'A'), _booking(2, 'B')]
        counts = send_due_workshop_reminders(dry_run=True)
        self.assertEqual(counts['sent'], 1)
        self.assertEqual(counts['skipped'], 1)
        self.assertEqual(counts['failed'], 0)
