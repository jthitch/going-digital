from decimal import Decimal

from django.test import SimpleTestCase

from bookings.report_payment_data import (
    BACS_GATEWAY_ID,
    CASH_GATEWAY_ID,
    CHEQUE_GATEWAY_ID,
    OTHER_GATEWAY_ID,
    STRIPE_GATEWAY_ID,
    VOUCHER_GATEWAY_ID,
    is_manual_report_gateway,
)
from bookings.reports import _franchisee_payment_columns


WORLDPAY_GATEWAY_ID = 9
CARD_SAVE_GATEWAY_ID = 3


class ManualReportGatewayTests(SimpleTestCase):
    def test_offline_gateways_are_manual(self):
        for gateway_id in (
            CHEQUE_GATEWAY_ID,
            CASH_GATEWAY_ID,
            BACS_GATEWAY_ID,
            OTHER_GATEWAY_ID,
        ):
            self.assertTrue(is_manual_report_gateway(gateway_id))

    def test_card_gateways_are_not_manual(self):
        for gateway_id in (WORLDPAY_GATEWAY_ID, CARD_SAVE_GATEWAY_ID, STRIPE_GATEWAY_ID, 1, 2):
            self.assertFalse(is_manual_report_gateway(gateway_id))


class FranchiseePaymentColumnTests(SimpleTestCase):
    def test_worldpay_goes_to_customer_payment_despite_manual_flag(self):
        # Legacy DB has WorldPay.manual_payment_option=1; report must ignore it.
        gateway = {
            'name': 'WorldPay',
            'transaction_percentage': Decimal('2.50'),
            'manual_payment_option': 1,
        }
        columns = _franchisee_payment_columns(Decimal('100.00'), WORLDPAY_GATEWAY_ID, gateway)
        self.assertEqual(columns['customer_payment'], Decimal('100.00'))
        self.assertEqual(columns['manual_payment'], Decimal('0.00'))
        self.assertEqual(columns['transaction_fee'], Decimal('2.50'))

    def test_cash_goes_to_manual_payment(self):
        gateway = {
            'name': 'Cash',
            'transaction_percentage': Decimal('0'),
            'manual_payment_option': 0,
        }
        columns = _franchisee_payment_columns(Decimal('80.00'), CASH_GATEWAY_ID, gateway)
        self.assertEqual(columns['customer_payment'], Decimal('0.00'))
        self.assertEqual(columns['manual_payment'], Decimal('80.00'))
        self.assertEqual(columns['transaction_fee'], Decimal('0.00'))

    def test_voucher_zeros_both_payment_columns(self):
        gateway = {
            'name': 'Going Digital Voucher',
            'transaction_percentage': Decimal('2.55'),
            'manual_payment_option': 1,
        }
        columns = _franchisee_payment_columns(Decimal('50.00'), VOUCHER_GATEWAY_ID, gateway)
        self.assertEqual(columns['customer_payment'], Decimal('0.00'))
        self.assertEqual(columns['manual_payment'], Decimal('0.00'))
