"""Tests for legacy bridge bookings used by reminder/follow-up emails."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from bookings.legacy_workshop_emails import (
    confirmed_paid_or_legacy_q,
    ensure_legacy_bridge_bookings,
    legacy_preview_recipients,
)
from bookings.models import Booking
from courses.workshop_student_report import WorkshopStudentRow


class ConfirmedPaidOrLegacyQTests(SimpleTestCase):
    def test_q_includes_legacy_or_payment(self):
        q = confirmed_paid_or_legacy_q()
        children = q.children
        self.assertEqual(children[0], ('status', 'confirmed'))
        # Second child is an OR of payment / legacy ids
        self.assertEqual(len(children), 2)


class BookingIsConfirmedLegacyTests(SimpleTestCase):
    def test_legacy_bridge_confirmed_without_payment(self):
        booking = Booking(
            status='confirmed',
            payment=None,
            legacy_gd_booking_id=99,
            price_paid=Decimal('0.00'),
        )
        self.assertTrue(booking.is_legacy_bridge)
        self.assertTrue(booking.is_confirmed)

    def test_non_legacy_needs_payment(self):
        booking = Booking(
            status='confirmed',
            payment=None,
            price_paid=Decimal('0.00'),
        )
        self.assertFalse(booking.is_legacy_bridge)
        self.assertFalse(booking.is_confirmed)


class EnsureLegacyBridgeBookingsTests(SimpleTestCase):
    @patch('bookings.legacy_workshop_emails.Customer')
    @patch('bookings.legacy_workshop_emails.Booking')
    @patch('bookings.legacy_workshop_emails.load_legacy_workshop_student_rows')
    def test_creates_bridge_for_legacy_student(self, load_rows, booking_model, customer_model):
        workshop = SimpleNamespace(pk=18296)
        load_rows.return_value = [
            WorkshopStudentRow(
                first_name='Matthew',
                last_name='R',
                email='matthew@example.com',
                phone='07700900123',
                legacy_booking_id=555,
                legacy_attendee_id=777,
            ),
        ]

        def filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.exclude.return_value.values_list.return_value = []
            chained = MagicMock()
            chained.first.return_value = None
            m.filter.return_value = chained
            m.first.return_value = None
            m.exists.return_value = False
            return m

        booking_model.objects.filter.side_effect = filter_side_effect
        customer_model.objects.filter.return_value.first.return_value = None

        created = ensure_legacy_bridge_bookings([workshop])
        self.assertEqual(created, 1)
        booking_model.objects.create.assert_called_once()
        kwargs = booking_model.objects.create.call_args.kwargs
        self.assertEqual(kwargs['student_email'], 'matthew@example.com')
        self.assertEqual(kwargs['legacy_gd_booking_id'], 555)
        self.assertEqual(kwargs['legacy_attendee_id'], 777)
        self.assertEqual(kwargs['status'], 'confirmed')
        self.assertEqual(kwargs['booking_reference'], 'L18296-A777')

    @patch('bookings.legacy_workshop_emails.Booking')
    @patch('bookings.legacy_workshop_emails.load_legacy_workshop_student_rows')
    def test_skips_email_already_on_workshop(self, load_rows, booking_model):
        workshop = SimpleNamespace(pk=1)
        load_rows.return_value = [
            WorkshopStudentRow(
                email='ada@example.com',
                legacy_booking_id=1,
            ),
        ]

        def filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.exclude.return_value.values_list.return_value = ['ada@example.com']
            m.first.return_value = None
            return m

        booking_model.objects.filter.side_effect = filter_side_effect
        self.assertEqual(ensure_legacy_bridge_bookings([workshop]), 0)
        booking_model.objects.create.assert_not_called()


class LegacyPreviewRecipientsTests(SimpleTestCase):
    @patch('bookings.legacy_workshop_emails.Booking')
    @patch('bookings.legacy_workshop_emails.load_legacy_workshop_student_rows')
    def test_preview_lists_unbridged_legacy(self, load_rows, booking_model):
        workshop = SimpleNamespace(pk=10)
        load_rows.return_value = [
            WorkshopStudentRow(
                email='legacy@example.com',
                legacy_booking_id=3,
                legacy_attendee_id=None,
            ),
        ]
        booking_model.objects.filter.return_value.exclude.return_value.values_list.return_value = []
        pairs = legacy_preview_recipients([workshop])
        self.assertEqual(pairs, [('L10-B3', 'legacy@example.com')])
