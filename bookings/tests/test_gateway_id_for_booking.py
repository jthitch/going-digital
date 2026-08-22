from types import SimpleNamespace

from django.test import SimpleTestCase

from bookings.report_payment_data import (
    STRIPE_GATEWAY_ID,
    VOUCHER_GATEWAY_ID,
    gateway_id_for_booking,
)


class GatewayIdForBookingTests(SimpleTestCase):
    def test_voucher_free_wins_over_basket_stripe_gateway(self):
        payment = SimpleNamespace(
            intent_type='voucher_free',
            status='succeeded',
            metadata={'workshop_basket_id': 32544},
        )
        booking = SimpleNamespace(payment=payment)
        basket_details = {
            32544: {
                'payment_gateway_id': STRIPE_GATEWAY_ID,
                'gateway_transaction_code': '',
            },
        }
        self.assertEqual(
            gateway_id_for_booking(booking, basket_details),
            VOUCHER_GATEWAY_ID,
        )

    def test_checkout_session_uses_basket_gateway(self):
        payment = SimpleNamespace(
            intent_type='checkout_session',
            status='succeeded',
            metadata={'workshop_basket_id': 99},
        )
        booking = SimpleNamespace(payment=payment)
        basket_details = {
            99: {
                'payment_gateway_id': STRIPE_GATEWAY_ID,
                'gateway_transaction_code': 'cs_test',
            },
        }
        self.assertEqual(
            gateway_id_for_booking(booking, basket_details),
            STRIPE_GATEWAY_ID,
        )
