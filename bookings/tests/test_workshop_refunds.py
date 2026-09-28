"""Tests for recording refunds against workshop places."""
from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from bookings.workshop_refunds import WorkshopRefundError, record_workshop_refund
from courses.workshop_student_report import WorkshopStudentRow


def _call(**overrides):
    kwargs = {
        'workshop': SimpleNamespace(pk=10),
        'student_key': 'b:99',
        'amount': Decimal('85.00'),
        'refunded_on': date(2026, 9, 28),
        'method': 'bank_transfer',
        'reason': 'Student unwell',
    }
    kwargs.update(overrides)
    return record_workshop_refund(**kwargs)


class RecordRefundValidationTests(SimpleTestCase):
    def test_rejects_zero_amount(self):
        with self.assertRaises(WorkshopRefundError):
            _call(amount=Decimal('0'))

    def test_requires_reason(self):
        with self.assertRaises(WorkshopRefundError):
            _call(reason='  ')

    def test_rejects_unknown_method(self):
        with self.assertRaises(WorkshopRefundError):
            _call(method='paypal')

    def test_requires_one_student(self):
        with self.assertRaises(WorkshopRefundError):
            _call(student_key='nonsense')

    @patch('bookings.workshop_refunds.user_can_record_refund', return_value=False)
    def test_rejects_user_without_workshop_access(self, _perm):
        with self.assertRaises(WorkshopRefundError):
            _call(user=MagicMock(is_authenticated=True))


class RecordRefundNewBookingTests(SimpleTestCase):
    def _booking(self, **attrs):
        booking = MagicMock()
        booking.pk = 99
        booking.workshop_id = 10
        booking.status = 'confirmed'
        booking.booking_reference = 'ABC123'
        booking.student_first_name = 'Sam'
        booking.student_last_name = 'Jones'
        booking.student_email = 'sam@example.com'
        booking.price_paid = Decimal('100.00')
        booking.list_price = Decimal('100.00')
        for key, value in attrs.items():
            setattr(booking, key, value)
        return booking

    @patch('bookings.workshop_refunds.BookingRefund.objects')
    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    @patch('bookings.workshop_refunds.Booking.objects')
    def test_marks_booking_refunded_and_releases_place(
        self,
        booking_objects,
        workshop_objects,
        _atomic,
        adjust_places,
        refund_objects,
    ):
        workshop = SimpleNamespace(pk=10)
        workshop_objects.select_for_update.return_value.get.return_value = workshop
        booking = self._booking()
        booking_objects.select_for_update.return_value.filter.return_value.filter.return_value.first.return_value = booking

        _call(amount=Decimal('85.00'))

        self.assertEqual(booking.status, 'refunded')
        booking.save.assert_called_once_with(update_fields=['status', 'cancelled_at', 'updated_at'])
        adjust_places.assert_called_once_with(10, -1)
        created = refund_objects.create.call_args.kwargs
        self.assertEqual(created['booking'], booking)
        self.assertEqual(created['amount'], Decimal('85.00'))
        self.assertEqual(created['student_name'], 'Sam Jones')
        self.assertEqual(created['method'], 'bank_transfer')

    @patch('bookings.workshop_refunds.BookingRefund.objects')
    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    @patch('bookings.workshop_refunds.Booking.objects')
    def test_rejects_amount_over_price_paid(
        self,
        booking_objects,
        workshop_objects,
        _atomic,
        adjust_places,
        refund_objects,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)
        booking = self._booking()
        booking_objects.select_for_update.return_value.filter.return_value.filter.return_value.first.return_value = booking

        with self.assertRaises(WorkshopRefundError):
            _call(amount=Decimal('150.00'))

        booking.save.assert_not_called()
        adjust_places.assert_not_called()
        refund_objects.create.assert_not_called()

    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    @patch('bookings.workshop_refunds.Booking.objects')
    def test_rejects_unconfirmed_booking(
        self,
        booking_objects,
        workshop_objects,
        _atomic,
        adjust_places,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)
        booking = self._booking(status='cancelled')
        booking_objects.select_for_update.return_value.filter.return_value.filter.return_value.first.return_value = booking

        with self.assertRaises(WorkshopRefundError):
            _call()

        adjust_places.assert_not_called()

    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    @patch('bookings.workshop_refunds.Booking.objects')
    def test_rejects_booking_on_other_workshop(
        self,
        booking_objects,
        workshop_objects,
        _atomic,
        adjust_places,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)
        booking = self._booking(workshop_id=11)
        booking_objects.select_for_update.return_value.filter.return_value.filter.return_value.first.return_value = booking

        with self.assertRaises(WorkshopRefundError):
            _call()

        adjust_places.assert_not_called()


class RecordRefundLegacyTests(SimpleTestCase):
    def _row(self, attendee_id=77):
        return WorkshopStudentRow(
            first_name='Pat',
            last_name='Lee',
            email='pat@example.com',
            booking_reference='GD-55',
            legacy_booking_id=55,
            legacy_attendee_id=attendee_id,
        )

    @patch('bookings.workshop_refunds._write_legacy_line_refund')
    @patch('bookings.workshop_refunds._legacy_line_has_active_attendees', return_value=False)
    @patch('bookings.workshop_refunds._cancel_bridge', return_value=None)
    @patch('bookings.workshop_refunds._refund_legacy_attendee', return_value=300)
    @patch('bookings.workshop_refunds._legacy_rows_by_selection')
    @patch('bookings.workshop_refunds.BookingRefund.objects')
    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    def test_last_attendee_writes_legacy_line_refund(
        self,
        workshop_objects,
        _atomic,
        adjust_places,
        refund_objects,
        rows_by_selection,
        refund_attendee,
        _cancel_bridge,
        _has_active,
        write_line,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)
        rows_by_selection.return_value = ({77: self._row()}, {})
        refund_objects.filter.return_value.aggregate.return_value = {'total': Decimal('85.00')}

        _call(student_key='la:77')

        refund_attendee.assert_called_once_with(77, 10)
        created = refund_objects.create.call_args.kwargs
        self.assertEqual(created['legacy_attendee_id'], 77)
        self.assertEqual(created['legacy_bookings_workshops_id'], 300)
        write_line.assert_called_once_with(
            300, Decimal('85.00'), date(2026, 9, 28), 'Student unwell'
        )
        adjust_places.assert_called_once_with(10, -1)

    @patch('bookings.workshop_refunds._write_legacy_line_refund')
    @patch('bookings.workshop_refunds._legacy_line_has_active_attendees', return_value=True)
    @patch('bookings.workshop_refunds._cancel_bridge', return_value=None)
    @patch('bookings.workshop_refunds._refund_legacy_attendee', return_value=300)
    @patch('bookings.workshop_refunds._legacy_rows_by_selection')
    @patch('bookings.workshop_refunds.BookingRefund.objects')
    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    def test_attendee_with_siblings_keeps_line_active(
        self,
        workshop_objects,
        _atomic,
        adjust_places,
        refund_objects,
        rows_by_selection,
        _refund_attendee,
        _cancel_bridge,
        _has_active,
        write_line,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)
        rows_by_selection.return_value = ({77: self._row()}, {})

        _call(student_key='la:77')

        write_line.assert_not_called()
        adjust_places.assert_called_once_with(10, -1)

    @patch('bookings.workshop_refunds._write_legacy_line_refund')
    @patch('bookings.workshop_refunds._cancel_bridge', return_value=None)
    @patch('bookings.workshop_refunds._legacy_line_for_booking', return_value=400)
    @patch('bookings.workshop_refunds._legacy_rows_by_selection')
    @patch('bookings.workshop_refunds.BookingRefund.objects')
    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    def test_legacy_booking_line_writes_refund(
        self,
        workshop_objects,
        _atomic,
        adjust_places,
        refund_objects,
        rows_by_selection,
        line_for_booking,
        _cancel_bridge,
        write_line,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)
        rows_by_selection.return_value = ({}, {55: self._row(attendee_id=None)})
        refund_objects.filter.return_value.aggregate.return_value = {'total': Decimal('60.00')}

        _call(student_key='lb:55', amount=Decimal('60.00'))

        line_for_booking.assert_called_once_with(55, 10)
        write_line.assert_called_once_with(
            400, Decimal('60.00'), date(2026, 9, 28), 'Student unwell'
        )
        adjust_places.assert_called_once_with(10, -1)

    @patch('bookings.workshop_refunds._legacy_rows_by_selection', return_value=({}, {}))
    @patch('bookings.workshop_refunds._adjust_workshop_places_booked')
    @patch('bookings.workshop_refunds.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_refunds.Workshop.objects')
    def test_unknown_legacy_student_rejected(
        self,
        workshop_objects,
        _atomic,
        adjust_places,
        _rows,
    ):
        workshop_objects.select_for_update.return_value.get.return_value = SimpleNamespace(pk=10)

        with self.assertRaises(WorkshopRefundError):
            _call(student_key='la:999')

        adjust_places.assert_not_called()
