"""Tests for moving confirmed students between workshops."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from bookings.workshop_student_move import (
    WorkshopStudentMoveError,
    destination_has_capacity,
    move_workshop_students,
)


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


class MoveWorkshopStudentsValidationTests(SimpleTestCase):
    def test_rejects_same_workshop(self):
        workshop = SimpleNamespace(pk=1, active=1, course_id=5)
        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=workshop,
                destination=workshop,
                booking_ids=[1],
                send_confirmation_email=False,
            )

    def test_rejects_inactive_destination(self):
        source = SimpleNamespace(pk=1, active=1, course_id=5)
        dest = SimpleNamespace(pk=2, active=0, course_id=5)
        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=source,
                destination=dest,
                booking_ids=[1],
                send_confirmation_email=False,
            )

    def test_rejects_past_destination(self):
        from datetime import datetime, timezone as dt_timezone

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
                booking_ids=[1],
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
                booking_ids=[],
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
        booking_objects.select_for_update.return_value.filter.return_value.order_by.return_value = [
            booking,
        ]

        moved = move_workshop_students(
            source=source,
            destination=dest,
            booking_ids=[99],
            send_confirmation_email=True,
        )

        self.assertEqual(moved, [booking])
        self.assertEqual(booking.workshop, dest)
        booking.save.assert_called_once_with(update_fields=['workshop', 'updated_at'])
        adjust_places.assert_any_call(10, -1)
        adjust_places.assert_any_call(20, 1)
        send_email.assert_called_once_with(99)

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
        booking_objects.select_for_update.return_value.filter.return_value.order_by.return_value = [
            booking,
        ]

        with self.assertRaises(WorkshopStudentMoveError):
            move_workshop_students(
                source=source,
                destination=dest,
                booking_ids=[99],
                send_confirmation_email=True,
            )

        booking.save.assert_not_called()
        adjust_places.assert_not_called()
        send_email.assert_not_called()
