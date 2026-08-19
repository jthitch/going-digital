"""Payment gateway and basket helpers used by reports and legacy sync."""
from decimal import Decimal

from django.db import connection

STRIPE_GATEWAY_ID = 10
VOUCHER_GATEWAY_ID = 4
CASH_GATEWAY_ID = 6
CHEQUE_GATEWAY_ID = 5
BACS_GATEWAY_ID = 7
OTHER_GATEWAY_ID = 8

# Offline / paid-to-tutor gateways for franchisee report columns.
# gd_payment_gateway.manual_payment_option means "available when recording a
# payment in admin", not "counts as manual in reports" — WorldPay and Card Save
# have that flag set but are customer card payments.
MANUAL_REPORT_GATEWAY_IDS = frozenset({
    CHEQUE_GATEWAY_ID,
    CASH_GATEWAY_ID,
    BACS_GATEWAY_ID,
    OTHER_GATEWAY_ID,
})


def is_manual_report_gateway(gateway_id):
    """True when franchisee report should put the amount in Manual payment."""
    try:
        return int(gateway_id) in MANUAL_REPORT_GATEWAY_IDS
    except (TypeError, ValueError):
        return False


def load_payment_gateway_names():
    return {
        gateway_id: meta['name']
        for gateway_id, meta in load_payment_gateway_meta().items()
    }


def load_payment_gateway_meta():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, payment_gateway, internal_name,
                   transaction_percentage, manual_payment_option
            FROM gd_payment_gateway
            ORDER BY payment_gateway, internal_name
            """
        )
        return {
            row[0]: {
                'name': (row[1] or row[2] or f'Gateway #{row[0]}').strip(),
                'transaction_percentage': Decimal(str(row[3] or '0')),
                'manual_payment_option': int(row[4] or 0),
            }
            for row in cursor.fetchall()
        }


def load_basket_details(basket_ids):
    if not basket_ids:
        return {}
    ids = sorted({int(bid) for bid in basket_ids})
    placeholders = ','.join(['%s'] * len(ids))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, payment_gateway_id, gateway_transaction_code
            FROM gd_basket
            WHERE id IN ({placeholders})
            """,
            ids,
        )
        return {
            row[0]: {
                'payment_gateway_id': row[1],
                'gateway_transaction_code': (row[2] or '').strip(),
            }
            for row in cursor.fetchall()
        }


def gateway_id_for_booking(booking, basket_details):
    payment = booking.payment
    if not payment:
        return None

    metadata = dict(payment.metadata or {})
    if metadata.get('gift_voucher_basket_id'):
        return None

    basket_id = metadata.get('workshop_basket_id')
    if basket_id:
        try:
            basket = basket_details.get(int(basket_id))
            if basket:
                return basket['payment_gateway_id']
        except (TypeError, ValueError):
            pass

    if payment.intent_type == 'voucher_free':
        return VOUCHER_GATEWAY_ID

    if payment.intent_type == 'manual_tutor':
        try:
            return int(metadata.get('payment_gateway_id') or CASH_GATEWAY_ID)
        except (TypeError, ValueError):
            return CASH_GATEWAY_ID

    if metadata.get('payment_gateway_id'):
        try:
            return int(metadata['payment_gateway_id'])
        except (TypeError, ValueError):
            pass

    if payment.intent_type == 'checkout_session' and payment.status == 'succeeded':
        return STRIPE_GATEWAY_ID

    if payment.status == 'succeeded':
        return STRIPE_GATEWAY_ID

    return None


def gateway_name(gateway_id, gateway_names):
    if gateway_id and gateway_id in gateway_names:
        return gateway_names[gateway_id]
    if gateway_id:
        return f'Gateway #{gateway_id}'
    return 'Unknown'


def booking_basket_id(booking):
    payment = booking.payment
    if not payment:
        return None
    basket_id = (payment.metadata or {}).get('workshop_basket_id')
    if not basket_id:
        return None
    try:
        return int(basket_id)
    except (TypeError, ValueError):
        return None


def booking_transaction_id(booking, basket_details):
    basket_id = booking_basket_id(booking)
    if basket_id:
        basket = basket_details.get(basket_id) or {}
        txn = basket.get('gateway_transaction_code') or ''
        if txn:
            return txn
    payment = booking.payment
    if payment and payment.stripe_id:
        return payment.stripe_id
    return ''
