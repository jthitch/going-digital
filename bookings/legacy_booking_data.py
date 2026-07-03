"""Load legacy gd_booking rows for admin reports."""
from decimal import Decimal

from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.models import GdBooking
from core.models import Customer


def is_legacy_gd_booking_id(booking_id):
    """True when report booking_id refers to gd_booking (not new-site offset id)."""
    if booking_id is None:
        return False
    value = int(booking_id)
    return 0 < value < LEGACY_REPORT_BOOKING_ID_OFFSET


def load_gd_bookings(booking_ids):
    legacy_ids = sorted(
        {int(booking_id) for booking_id in booking_ids if is_legacy_gd_booking_id(booking_id)},
    )
    if not legacy_ids:
        return {}
    return GdBooking.objects.in_bulk(legacy_ids)


def load_gd_customers(customer_ids):
    ids = sorted({int(customer_id) for customer_id in customer_ids if customer_id})
    if not ids:
        return {}
    return Customer.objects.in_bulk(ids)


def workshop_id_from_course_report(booking_workshop_id):
    """
    booking_workshop_id on gd_report__bookings_by_course is gd_workshop.id.
    """
    if not booking_workshop_id:
        return None
    return int(booking_workshop_id)


def gd_booking_payment_date(gd_booking):
    if not gd_booking:
        return None
    return gd_booking.created_at


def gd_booking_customer_fields(gd_booking, customers_by_id):
    if not gd_booking or not gd_booking.customer_id:
        return {'name': '', 'email': '', 'phone': ''}
    customer = customers_by_id.get(gd_booking.customer_id)
    if not customer:
        return {'name': '', 'email': '', 'phone': ''}
    return {
        'name': f'{customer.firstname} {customer.lastname}'.strip(),
        'email': (customer.email or '').strip(),
        'phone': (customer.contact_number or '').strip(),
    }


def gd_booking_total_paid(gd_booking):
    if not gd_booking:
        return Decimal('0.00')
    return Decimal(gd_booking.amount_paid or 0).quantize(Decimal('0.01'))


def gd_booking_voucher_amount(gd_booking):
    if not gd_booking:
        return Decimal('0.00')
    return Decimal(gd_booking.amount_paid_by_voucher or 0).quantize(Decimal('0.01'))


def gd_booking_promotional_amount(gd_booking):
    if not gd_booking:
        return Decimal('0.00')
    return Decimal(gd_booking.amount_paid_by_promotional_voucher or 0).quantize(Decimal('0.01'))


def gd_booking_vouchers_redeemed(gd_booking):
    if not gd_booking:
        return ''
    return (gd_booking.vouchers_redeemed or '').strip()
