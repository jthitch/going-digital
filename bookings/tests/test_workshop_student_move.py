"""Tests for moving confirmed students between workshops."""
from contextlib import nullcontext
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from bookings.workshop_student_move import (
    WorkshopStudentMoveError,
    _parse_student_keys,
    destination_has_capacity,
    legacy_student_selection_key,
    move_workshop_students,
)
from courses.workshop_student_report import WorkshopStudentRow


class DestinationHasCapacityTests(SimpleTestCase):
    def test_unlimited_when_max_places_zero(self):
        dest = SimpleNamespace(max_places=0, places_booked=99)
        self.assertTrue(destination_has_capacity(dest, 5))

    def test_enough_space(self):
        dest = SimpleNamespace(max_places=10, places_booked=7)
        self.assertTrue(destination_has_capacity(dest, 3))
        self.assertFalse(destination_has_capacity(dest, 4))

    def test_null_places_booked_treated_as_zero(self):
        dest = SimpleNamespace(max_places=2, places_booked=None)
        self.assertTrue(destination_has_capacity(dest, 2))
        self.assertFalse(destination_has_capacity(dest, 3))


class ParseStudentKeysTests(SimpleTestCase):
    def test_parses_booking_legacy_and_plain_ids(self):
        booking_ids, attendees, legacy_bookings = _parse_student_keys(
            ['b:10', 'la:20', 'lb:30', '40', 'b:10']
        )
        self.assertEqual(booking_ids, [10, 40])
        self.assertEqual(attendees, [20])
        self.assertEqual(legacy_bookings, [30])


class LegacySelectionKeyTests(SimpleTestCase):
    def test_prefers_attendee_id(self):
        row = WorkshopStudentRow(legacy_booking_id=5, legacy_attendee_id=9)
        self.assertEqual(legacy_student_selection_key(row), 'la:9')

    def test_falls_back_to_booking_id(self):
        row = WorkshopStudentRow(legacy_booking_id=5, legacy_attendee_id=None)
        self.assertEqual(legacy_student_selection_key(row), 'lb:5')


class MoveWorkshopStudentsValidationTests(SimpleTestCase):
    def test_rejects_same_workshop(self):
        workshop = SimpleNamespace(pk=1, active=1, course_id=5)
        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=workshop,
                destination=workshop,
                student_keys=['b:1'],
                send_confirmation_email=False,
            )

    def test_rejects_inactive_destination(self):
        source = SimpleNamespace(pk=1, active=1, course_id=5)
        dest = SimpleNamespace(pk=2, active=0, course_id=5)
        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=source,
                destination=dest,
                student_keys=['b:1'],
                send_confirmation_email=False,
            )

    def test_rejects_past_destination(self):
        source = SimpleNamespace(pk=1, active=1, course_id=5)
        dest = SimpleNamespace(
            pk=2,
            active=1,
            course_id=9,
            open_dated=0,
            date=datetime(2020, 1, 1, tzinfo=dt_timezone.utc),
            start_date=datetime(2020, 1, 1, tzinfo=dt_timezone.utc),
        )
        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=source,
                destination=dest,
                student_keys=['b:1'],
                send_confirmation_email=False,
            )

    def test_rejects_empty_selection(self):
        source = SimpleNamespace(pk=1, active=1, course_id=5)
        dest = SimpleNamespace(
            pk=2,
            active=1,
            course_id=5,
            open_dated=1,
            date=None,
            start_date=None,
        )
        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=source,
                destination=dest,
                student_keys=[],
                send_confirmation_email=False,
            )


class MoveWorkshopStudentsActionTests(SimpleTestCase):
    @patch('payments.tasks.send_booking_confirmation_email')
    @patch('bookings.workshop_student_move._adjust_workshop_places_booked')
    @patch('bookings.workshop_student_move.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_student_move.Workshop.objects')
    @patch('bookings.workshop_student_move.Booking.objects')
    def test_moves_bookings_adjusts_places_and_emails(
        self,
        booking_objects,
        workshop_objects,
        _atomic,
        adjust_places,
        send_email,
    ):
        source = SimpleNamespace(pk=10, active=1, course_id=5)
        dest = SimpleNamespace(
            pk=20,
            active=1,
            course_id=5,
            max_places=8,
            places_booked=2,
            open_dated=1,
            date=None,
            start_date=None,
        )
        workshop_objects.select_for_update.return_value.get.return_value = dest

        booking = MagicMock()
        booking.pk = 99
        booking.workshop_id = 10
        booking.status = 'confirmed'
        booking.booking_reference = 'ABC'
        booking_objects.select_for_update.return_value.filter.return_value.filter.return_value.order_by.return_value = [
            booking,
        ]

        moved = move_workshop_students(
            source=source,
            destination=dest,
            student_keys=['b:99'],
            send_confirmation_email=True,
        )

        self.assertEqual(moved, [booking])
        self.assertEqual(booking.workshop, dest)
        booking.save.assert_called_once_with(update_fields=['workshop', 'updated_at'])
        adjust_places.assert_any_call(10, -1)
        adjust_places.assert_any_call(20, 1)
        send_email.assert_called_once_with(99)

    @patch('bookings.workshop_student_move.movable_legacy_student_rows')
    @patch('bookings.legacy_workshop_emails.get_or_create_legacy_bridge')
    @patch('bookings.workshop_student_move._move_legacy_attendee')
    @patch('payments.tasks.send_booking_confirmation_email')
    @patch('bookings.workshop_student_move._adjust_workshop_places_booked')
    @patch('bookings.workshop_student_move.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_student_move.Workshop.objects')
    def test_moves_legacy_attendee_and_emails_bridge(
        self,
        workshop_objects,
        _atomic,
        adjust_places,
        send_email,
        move_attendee,
        get_bridge,
        load_legacy,
    ):
        source = SimpleNamespace(pk=10, active=1, course_id=5)
        dest = SimpleNamespace(
            pk=20,
            active=1,
            course_id=7,
            max_places=8,
            places_booked=1,
            open_dated=1,
            date=None,
            start_date=None,
        )
        workshop_objects.select_for_update.return_value.get.return_value = dest
        load_legacy.return_value = [
            WorkshopStudentRow(
                first_name='Pat',
                last_name='Lee',
                email='pat@example.com',
                legacy_booking_id=55,
                legacy_attendee_id=77,
            ),
        ]
        bridge = MagicMock(pk=500)
        get_bridge.return_value = bridge

        moved = move_workshop_students(
            source=source,
            destination=dest,
            student_keys=['la:77'],
            send_confirmation_email=True,
        )

        move_attendee.assert_called_once_with(77, 10, 20)
        get_bridge.assert_called_once()
        adjust_places.assert_any_call(10, -1)
        adjust_places.assert_any_call(20, 1)
        send_email.assert_called_once_with(500)
        self.assertEqual(moved, [bridge])

    @patch('payments.tasks.send_booking_confirmation_email')
    @patch('bookings.workshop_student_move._adjust_workshop_places_booked')
    @patch('bookings.workshop_student_move.transaction.atomic', return_value=nullcontext())
    @patch('bookings.workshop_student_move.Workshop.objects')
    @patch('bookings.workshop_student_move.Booking.objects')
    def test_capacity_error_skips_email(
        self,
        booking_objects,
        workshop_objects,
        _atomic,
        adjust_places,
        send_email,
    ):
        source = SimpleNamespace(pk=10, active=1, course_id=5)
        dest = SimpleNamespace(
            pk=20,
            active=1,
            course_id=5,
            max_places=2,
            places_booked=2,
            open_dated=1,
            date=None,
            start_date=None,
        )
        workshop_objects.select_for_update.return_value.get.return_value = dest

        booking = MagicMock()
        booking.pk = 99
        booking.workshop_id = 10
        booking.status = 'confirmed'
        booking.booking_reference = 'ABC'
        booking_objects.select_for_update.return_value.filter.return_value.filter.return_value.order_by.return_value = [
            booking,
        ]

        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=source,
                destination=dest,
                student_keys=['b:99'],
                send_confirmation_email=True,
            )

        booking.save.assert_not_called()
        adjust_places.assert_not_called()
        send_email.assert_not_called()
