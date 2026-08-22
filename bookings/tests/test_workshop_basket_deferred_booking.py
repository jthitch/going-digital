from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase

from bookings.workshop_basket import (
    build_place_specs_from_basket,
    prepare_checkout_from_session,
    session_basket_from_data,
)
from payments.checkout_completion import _complete_workshop_basket


def _workshop(pk, price='100.00', *, is_full=False, enrollment_open=True, spaces=10):
    return SimpleNamespace(
        pk=pk,
        price=Decimal(price),
        is_full=is_full,
        enrollment_open=enrollment_open,
        spaces_available=spaces,
    )


def _basket_item(workshop_id, quantity=1, **overrides):
    item = {
        'id': 'item1',
        'workshop_id': workshop_id,
        'quantity': quantity,
        'student_first_name': 'Ada',
        'student_last_name': 'Lovelace',
        'student_email': 'ada@example.com',
        'student_phone': '',
        'special_requirements': '',
        'loan_cameras': 0,
        'unit_price': '100.00',
    }
    item.update(overrides)
    return item


class BuildPlaceSpecsTests(SimpleTestCase):
    @patch('bookings.workshop_basket.load_workshops_for_basket')
    def test_expands_quantity_into_place_specs(self, load_workshops):
        workshop = _workshop(10)
        load_workshops.return_value = {10: workshop}
        basket = {
            'items': [_basket_item(10, quantity=2)],
            'voucher_discount': '0.00',
            'discount_eligible_workshop_ids': [],
        }

        specs = build_place_specs_from_basket(basket, validate_availability=False)

        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]['price_paid'], Decimal('100.00'))
        self.assertEqual(specs[1]['list_price'], Decimal('100.00'))
        self.assertIs(specs[0]['workshop'], workshop)

    @patch('bookings.workshop_basket.load_workshops_for_basket')
    def test_allocates_voucher_discount_across_places(self, load_workshops):
        workshop = _workshop(10, '50.00')
        load_workshops.return_value = {10: workshop}
        basket = {
            'items': [_basket_item(10, quantity=2, unit_price='50.00')],
            'voucher_id': 99,
            'voucher_code': 'GIFT50',
            'voucher_discount': '50.00',
            'discount_eligible_workshop_ids': [10],
        }

        specs = build_place_specs_from_basket(basket, validate_availability=False)

        self.assertEqual(len(specs), 2)
        self.assertEqual(sum(s['price_paid'] for s in specs), Decimal('50.00'))
        self.assertEqual(sum(s['voucher_discount'] for s in specs), Decimal('50.00'))
        self.assertEqual(specs[0]['voucher_id'], 99)


class PrepareCheckoutDeferredBookingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('payments.checkout_session_context.authorize_workshop_checkout')
    @patch('bookings.workshop_basket.clear_session_basket')
    @patch('bookings.workshop_basket.persist_workshop_basket', return_value=321)
    @patch('bookings.workshop_basket._resolve_customer')
    @patch('bookings.workshop_basket._validate_quantity_for_workshop')
    @patch('bookings.workshop_basket.load_workshops_for_basket')
    @patch('bookings.workshop_basket.get_session_basket')
    @patch('bookings.workshop_basket.Booking.objects')
    def test_prepare_checkout_does_not_create_bookings(
        self,
        booking_objects,
        get_basket,
        load_workshops,
        validate_qty,
        resolve_customer,
        persist_basket,
        clear_basket,
        authorize,
    ):
        workshop = _workshop(10)
        get_basket.return_value = {
            'items': [_basket_item(10)],
            'voucher_discount': '0.00',
            'discount_eligible_workshop_ids': [],
        }
        load_workshops.return_value = {10: workshop}
        customer = SimpleNamespace(pk=7, email='ada@example.com')
        resolve_customer.return_value = customer
        request = self.factory.post('/bookings/basket/checkout/')
        request.session = {}

        basket_id, resolved = prepare_checkout_from_session(request)

        self.assertEqual(basket_id, 321)
        self.assertIs(resolved, customer)
        booking_objects.create.assert_not_called()
        booking_objects.filter.assert_not_called()
        persist_basket.assert_called_once()
        # New signature: request, basket, customer (no booking_ids)
        self.assertEqual(persist_basket.call_args.args[2], customer)
        authorize.assert_called_once_with(request, basket_id=321)
        clear_basket.assert_called_once_with(request)


class CompleteWorkshopBasketCreatesBookingsTests(SimpleTestCase):
    @patch('payments.checkout_completion.transaction.atomic')
    @patch('payments.checkout_completion._sync_legacy_report_for_booking')
    @patch('payments.checkout_completion._increment_workshop_places_booked')
    @patch('payments.tasks.send_booking_confirmation_emails')
    @patch('bookings.workshop_basket.update_workshop_basket_booking_ids')
    @patch('bookings.workshop_basket.create_confirmed_bookings_from_basket_data')
    @patch('bookings.workshop_basket.get_workshop_basket')
    @patch('payments.checkout_completion.Payment.objects')
    @patch('payments.checkout_completion.Booking.objects')
    @patch('core.models.Customer.objects')
    def test_creates_confirmed_bookings_when_none_exist(
        self,
        customer_objects,
        booking_objects,
        payment_objects,
        get_basket,
        create_bookings,
        update_basket_ids,
        send_emails,
        increment_places,
        sync_legacy,
        atomic,
    ):
        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        payment = SimpleNamespace(pk=55, metadata={'workshop_basket_id': 9})
        locked_payment = SimpleNamespace(pk=55, metadata={})
        locked_payment.save = MagicMock()
        payment_objects.select_for_update.return_value.get.return_value = locked_payment

        get_basket.return_value = {
            'id': 9,
            'customer_id': 3,
            'basket_data': {
                'type': 'workshop_booking',
                'customer_id': 3,
                'items': [_basket_item(10)],
                'booking_ids': [],
            },
        }
        customer = SimpleNamespace(pk=3)
        customer_objects.get.return_value = customer
        create_bookings.return_value = [101]

        booking = SimpleNamespace(
            id=101,
            payment_id=55,
            workshop_id=10,
            status='confirmed',
            voucher_id=None,
            discount_code_id=None,
        )
        booking.save = MagicMock()
        booking_objects.select_for_update.return_value.get.return_value = booking

        _complete_workshop_basket({'workshop_basket_id': 9}, payment)

        create_bookings.assert_called_once()
        update_basket_ids.assert_called_once_with(9, [101])
        self.assertEqual(locked_payment.metadata['booking_ids'], [101])
        self.assertTrue(locked_payment.metadata['places_booked_applied'])
        self.assertTrue(locked_payment.metadata['confirmation_email_sent'])
        increment_places.assert_called_once_with(10, 1)
        send_emails.assert_called_once_with([101])
        sync_legacy.assert_called_once_with(101)

    @patch('payments.checkout_completion.transaction.atomic')
    @patch('payments.checkout_completion._sync_legacy_report_for_booking')
    @patch('payments.checkout_completion._increment_workshop_places_booked')
    @patch('payments.tasks.send_booking_confirmation_emails')
    @patch('bookings.workshop_basket.create_confirmed_bookings_from_basket_data')
    @patch('bookings.workshop_basket.get_workshop_basket')
    @patch('payments.checkout_completion.Payment.objects')
    @patch('payments.checkout_completion.Booking.objects')
    def test_idempotent_when_booking_ids_already_on_payment(
        self,
        booking_objects,
        payment_objects,
        get_basket,
        create_bookings,
        send_emails,
        increment_places,
        sync_legacy,
        atomic,
    ):
        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        payment = SimpleNamespace(pk=55, metadata={'workshop_basket_id': 9})
        locked_payment = SimpleNamespace(
            pk=55,
            metadata={
                'booking_ids': [101],
                'places_booked_applied': True,
                'confirmation_email_sent': True,
                'confirmation_email_sent_101': True,
                'voucher_redeemed': True,
            },
        )
        locked_payment.save = MagicMock()
        payment_objects.select_for_update.return_value.get.return_value = locked_payment
        get_basket.return_value = {
            'id': 9,
            'customer_id': 3,
            'basket_data': {'booking_ids': [101], 'items': []},
        }

        booking = SimpleNamespace(
            id=101,
            payment_id=55,
            workshop_id=10,
            status='confirmed',
            voucher_id=None,
            discount_code_id=None,
        )
        booking.save = MagicMock()
        booking_objects.select_for_update.return_value.get.return_value = booking

        _complete_workshop_basket({'workshop_basket_id': 9, 'booking_ids': [101]}, payment)

        create_bookings.assert_not_called()
        increment_places.assert_not_called()
        send_emails.assert_not_called()
        sync_legacy.assert_called_once_with(101)


class SessionBasketFromDataTests(SimpleTestCase):
    def test_normalizes_missing_fields(self):
        basket = session_basket_from_data({'items': []})
        self.assertEqual(basket['voucher_discount'], '0.00')
        self.assertEqual(basket['discount_eligible_workshop_ids'], [])

    @patch('bookings.workshop_basket.load_workshops_for_basket', return_value={})
    def test_missing_workshop_raises(self, _load):
        with self.assertRaises(ValidationError):
            build_place_specs_from_basket(
                {'items': [_basket_item(99)], 'voucher_discount': '0'},
                validate_availability=False,
            )
