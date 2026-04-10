"""
Gift voucher basket service - integrates with legacy gd_basket, gd_customer, gd_voucher.
Creates basket on form submit, creates vouchers on successful payment.
"""
import json
import random
import string
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.utils import timezone


# Legacy constants from gd_voucher_type and gd_payment_gateway
VOUCHER_TYPE_GIFT = 1  # gift voucher type id
STRIPE_GATEWAY_NAME = 'Stripe'


def parse_device_and_browser(user_agent):
    """Parse User-Agent for device_type and browser. Returns (device_type, browser)."""
    ua = (user_agent or '').lower()
    device = 'desktop'
    if 'mobile' in ua and 'tablet' not in ua and 'ipad' not in ua:
        device = 'mobile'
    elif 'tablet' in ua or 'ipad' in ua:
        device = 'tablet'

    browser = 'unknown'
    if 'edg/' in ua or 'edge/' in ua:
        browser = 'Edge'
    elif 'opr/' in ua or 'opera' in ua:
        browser = 'Opera'
    elif 'firefox' in ua or 'fxios' in ua:
        browser = 'Firefox'
    elif 'samsungbrowser' in ua:
        browser = 'Samsung Browser'
    elif 'chrome' in ua and 'chromium' not in ua:
        browser = 'Chrome'
    elif 'safari' in ua and 'chrome' not in ua:
        browser = 'Safari'
    elif 'msie' in ua or 'trident' in ua:
        browser = 'Internet Explorer'

    return device, browser


def get_stripe_gateway_id():
    """Get Stripe payment gateway id, inserting if needed (MySQL / MariaDB)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM gd_payment_gateway WHERE internal_name = %s",
            [STRIPE_GATEWAY_NAME.lower()]
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        now = timezone.now().isoformat()
        cursor.execute(
            """
            INSERT INTO gd_payment_gateway
            (show_enabled, enabled, editable, manual_payment_option, payment_gateway, internal_name,
             transaction_percentage, description, created_at, updated_at)
            VALUES (1, 1, 0, 0, %s, %s, 0, 'Stripe payment gateway', %s, %s)
            """,
            [STRIPE_GATEWAY_NAME, STRIPE_GATEWAY_NAME.lower(), now, now]
        )
        return cursor.lastrowid


def get_or_create_customer(email, firstname, lastname, phone=''):
    """Get or create gd_customer by email. Returns (customer_id, created)."""
    firstname = (firstname or 'Customer').strip()
    lastname = (lastname or '').strip()
    if not lastname and firstname:
        parts = firstname.split(maxsplit=1)
        firstname = parts[0]
        lastname = parts[1] if len(parts) > 1 else ''

    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM gd_customer WHERE email = %s", [email])
        row = cursor.fetchone()
        if row:
            return row[0], False

        now = timezone.now().isoformat()
        cursor.execute(
            """
            INSERT INTO gd_customer
            (active, archived, guest_account, email, firstname, lastname, contact_number,
             newsletter, use_for_primary_booking, created_at, updated_at)
            VALUES (1, 0, 0, %s, %s, %s, %s, 0, 1, %s, %s)
            """,
            [email, firstname or 'Customer', lastname or '', phone or '', now, now]
        )
        return cursor.lastrowid, True


def create_gift_voucher_basket(customer_id, user_id, amount, quantity, total,
                               purchaser_name, purchaser_email, purchaser_phone='',
                               recipient_name='', gift_message='',
                               device_type='', browser=''):
    """
    Create gd_basket record for gift voucher purchase.
    basket_data stores JSON with order details for webhook to create vouchers.
    Returns basket_id.
    """
    gateway_id = get_stripe_gateway_id()
    checksum = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    basket_data = json.dumps({
        'type': 'gift_voucher',
        'amount': float(amount),
        'quantity': int(quantity),
        'total': float(total),
        'user_id': user_id,
        'purchaser_name': purchaser_name,
        'purchaser_email': purchaser_email,
        'purchaser_phone': purchaser_phone or '',
        'recipient_name': recipient_name or '',
        'gift_message': gift_message or '',
    })

    now = timezone.now().isoformat()
    device_type = device_type or ''
    browser = browser or ''
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO gd_basket
            (customer_id, payment_gateway_id, checksum, basket_data, basket_total,
             discount_total, transaction_total, device_type, browser, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s)
            """,
            [customer_id, gateway_id, checksum, basket_data, float(total), float(total),
             device_type, browser, now, now]
        )
        return cursor.lastrowid


def update_basket_gateway_transaction(basket_id, gateway_transaction_code):
    """Update gd_basket with Stripe session/transaction ID after successful payment."""
    if not gateway_transaction_code:
        return
    now = timezone.now().isoformat()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE gd_basket
            SET gateway_transaction_code = %s, updated_at = %s
            WHERE id = %s
            """,
            [gateway_transaction_code, now, basket_id]
        )


def get_vouchers_for_basket(basket_id):
    """Get voucher codes created for this basket (after webhook has run)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT voucher_code, value FROM gd_voucher WHERE basket_id = %s ORDER BY id",
            [basket_id]
        )
        return cursor.fetchall()


def get_basket(basket_id):
    """Fetch basket by id. Returns dict or None."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, customer_id, basket_data, basket_total FROM gd_basket WHERE id = %s",
            [basket_id]
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'customer_id': row[1],
            'basket_data': json.loads(row[2] or '{}'),
            'basket_total': row[3],
        }


def generate_voucher_code():
    """Generate unique gift voucher code (GIFT- + 8 alphanumeric)."""
    prefix = 'GIFT-'
    while True:
        code = prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM gd_voucher WHERE voucher_code = %s", [code])
            if not cursor.fetchone():
                return code


def create_vouchers_from_basket(basket_id, stripe_session_id):
    """
    Create gd_voucher records from paid basket. Called by webhook.
    Returns list of created voucher codes.
    """
    basket = get_basket(basket_id)
    if not basket or basket.get('basket_data', {}).get('type') != 'gift_voucher':
        return []

    data = basket['basket_data']
    amount = Decimal(str(data['amount']))
    quantity = int(data['quantity'])
    user_id = data.get('user_id')
    purchaser_email = data.get('purchaser_email', '')
    recipient_name = data.get('recipient_name', '').strip()
    email = purchaser_email
    if recipient_name:
        pass

    issue_date = date.today()
    expiry_date = issue_date + timedelta(days=9 * 30)  # 9 months
    gateway_id = get_stripe_gateway_id()
    voucher_type_id = VOUCHER_TYPE_GIFT
    now = timezone.now().isoformat()

    codes = []
    with connection.cursor() as cursor:
        for _ in range(quantity):
            code = generate_voucher_code()
            cursor.execute(
                """
                INSERT INTO gd_voucher
                (basket_id, active, voucher_type_id, use_once, user_id, customer_id,
                 actioned, email, issue_date, expiry_date, value, voucher_code,
                 amount_claimed, payment_gateway_id, gateway_transaction_code, created_at, updated_at)
                VALUES (%s, 1, %s, 0, %s, %s, 0, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s)
                """,
                [
                    basket_id,
                    voucher_type_id,
                    user_id or None,
                    basket['customer_id'],
                    email,
                    issue_date.isoformat(),
                    expiry_date.isoformat(),
                    float(amount),
                    code,
                    gateway_id,
                    stripe_session_id,
                    now,
                    now,
                ]
            )
            codes.append(code)

    return codes
