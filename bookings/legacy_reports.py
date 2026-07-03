"""Write confirmed bookings into legacy gd_report__* tables for reporting."""
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone

from bookings.models import (
    Booking,
    ReportBookingByCourse,
    ReportBookingByPaymentGateway,
    ReportBookingSummary,
    ReportUnpaidBooking,
)
from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.report_payment_data import (
    STRIPE_GATEWAY_ID,
    VOUCHER_GATEWAY_ID,
    booking_basket_id,
    booking_transaction_id,
    gateway_id_for_booking,
    gateway_name,
    load_basket_details,
    load_payment_gateway_names,
)
from courses.models import Region


def legacy_report_booking_id(booking):
    return LEGACY_REPORT_BOOKING_ID_OFFSET + int(booking.pk)


def legacy_report_bookings_workshops_id(booking):
    """Synthetic report key for unpaid bookings (new-site only)."""
    return legacy_report_booking_id(booking)


def _confirmed_booking(booking_or_id):
    booking_pk = booking_or_id.pk if isinstance(booking_or_id, Booking) else int(booking_or_id)
    return (
        Booking.objects.select_related(
            'payment',
            'customer',
            'workshop',
            'workshop__course',
            'workshop__venue',
        )
        .filter(pk=booking_pk, status='confirmed')
        .first()
    )


def _quantize_money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def _booking_datetime(booking):
    payment = booking.payment
    if payment and payment.succeeded_at:
        return payment.succeeded_at
    if payment and payment.created_at:
        return payment.created_at
    return booking.created_at or timezone.now()


def _workshop_datetime(workshop):
    if not workshop or not workshop.date:
        return None
    value = workshop.date
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _region_name(workshop):
    if not workshop or not workshop.region_id:
        return ''
    try:
        return Region.objects.get(pk=workshop.region_id).region_name or ''
    except Region.DoesNotExist:
        return ''


def _truncate(value, max_length=1000):
    text = (value or '').strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + '…'


def _workshop_user_id(workshop):
    if not workshop:
        return 0
    return workshop.user_id or workshop.createdby_id or 0


def _load_basket_device_types(basket_ids):
    if not basket_ids:
        return {}
    ids = sorted({int(bid) for bid in basket_ids})
    placeholders = ','.join(['%s'] * len(ids))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, device_type
            FROM gd_basket
            WHERE id IN ({placeholders})
            """,
            ids,
        )
        return {row[0]: (row[1] or '').strip() for row in cursor.fetchall()}


def _customer_fields(booking):
    if booking.customer:
        firstname = (booking.customer.firstname or booking.student_first_name or '').strip()
        lastname = (booking.customer.lastname or booking.student_last_name or '').strip()
        email = (booking.student_email or booking.customer.email or '').strip()
        customer_id = booking.customer_id or 0
    else:
        firstname = (booking.student_first_name or '').strip()
        lastname = (booking.student_last_name or '').strip()
        email = (booking.student_email or '').strip()
        customer_id = 0
    return {
        'customer_id': customer_id,
        'customer_firstname': _truncate(firstname, 1000),
        'customer_lastname': _truncate(lastname, 1000),
        'customer_email': _truncate(email, 1000),
    }


def _payment_amounts(booking, workshop_cost):
    voucher_amount = _quantize_money(booking.voucher_discount)
    price_paid = _quantize_money(booking.price_paid)
    payment = booking.payment

    if payment and payment.intent_type == 'voucher_free':
        return {
            'amount_paid': Decimal('0.00'),
            'amount_paid_by_voucher': voucher_amount or price_paid or workshop_cost,
            'amount_paid_by_promotional_voucher': Decimal('0.00'),
        }

    return {
        'amount_paid': price_paid,
        'amount_paid_by_voucher': voucher_amount if booking.voucher_code else Decimal('0.00'),
        'amount_paid_by_promotional_voucher': Decimal('0.00'),
    }


def build_legacy_course_report_row(booking):
    """Map a confirmed Booking to gd_report__bookings_by_course column values."""
    workshop = booking.workshop
    course = workshop.course if workshop else None
    venue = workshop.venue if workshop else None

    workshop_cost = booking.list_price
    if workshop_cost is None and workshop:
        workshop_cost = workshop.price

    return {
        'user_id': _workshop_user_id(workshop),
        'booking_id': legacy_report_booking_id(booking),
        'booking_date': _booking_datetime(booking),
        'booking_workshop_id': workshop.pk if workshop else 0,
        'workshop_date': _workshop_datetime(workshop),
        'course_name': _truncate(course.title if course else ''),
        'region_name': _truncate(_region_name(workshop)),
        'venue_name': _truncate(venue.venue_name if venue else ''),
        'places_booked': 1,
        'workshop_cost': _quantize_money(workshop_cost),
        'total_cost': _quantize_money(booking.price_paid),
    }


def build_legacy_payment_gateway_report_row(booking, *, basket_details=None, gateway_names=None):
    """Map a confirmed Booking to gd_report__bookings_by_payment_gateway column values."""
    workshop = booking.workshop
    course = workshop.course if workshop else None

    workshop_cost = booking.list_price
    if workshop_cost is None and workshop:
        workshop_cost = workshop.price
    workshop_cost = _quantize_money(workshop_cost)

    basket_details = basket_details if basket_details is not None else {}
    gateway_names = gateway_names if gateway_names is not None else load_payment_gateway_names()

    basket_id = booking_basket_id(booking) or 0
    gateway_id = gateway_id_for_booking(booking, basket_details)
    if gateway_id is None and booking.payment:
        if booking.payment.intent_type == 'voucher_free':
            gateway_id = VOUCHER_GATEWAY_ID
        elif booking.payment.status == 'succeeded':
            gateway_id = STRIPE_GATEWAY_ID

    amounts = _payment_amounts(booking, workshop_cost)
    device_types = _load_basket_device_types([basket_id] if basket_id else [])

    return {
        'user_id': _workshop_user_id(workshop),
        'booking_date': _booking_datetime(booking),
        'basket_id': basket_id,
        'booking_id': legacy_report_booking_id(booking),
        'bookings_workshops_id': legacy_report_bookings_workshops_id(booking),
        'workshop_date': _workshop_datetime(workshop),
        'workshop_id': workshop.pk if workshop else 0,
        'course_name': _truncate(course.title if course else ''),
        'places_booked': 1,
        'workshop_cost': workshop_cost,
        'vouchers_redeemed': _truncate((booking.voucher_code or '').strip() or '0'),
        'payment_gateway': _truncate(gateway_name(gateway_id, gateway_names)),
        'device_type': _truncate(device_types.get(basket_id, '')),
        'gateway_transaction_code': _truncate(
            booking_transaction_id(booking, basket_details),
        ),
        **_customer_fields(booking),
        **amounts,
    }


def _franchisee_name_for_workshop(workshop):
    if not workshop:
        return '', 0
    franchisee_id = workshop.user_id or workshop.createdby_id or 0
    if not franchisee_id:
        return '', 0
    from core.models import User

    try:
        user = User.objects.get(pk=franchisee_id, active=1)
        return _truncate(user.get_full_name(), 255), franchisee_id
    except User.DoesNotExist:
        return '', franchisee_id


def build_legacy_summary_report_row(booking):
    """Map a confirmed Booking to gd_report__bookings_summary column values."""
    workshop = booking.workshop
    course = workshop.course if workshop else None
    venue = workshop.venue if workshop else None

    workshop_cost = booking.list_price
    if workshop_cost is None and workshop:
        workshop_cost = workshop.price
    workshop_cost = _quantize_money(workshop_cost)

    amounts = _payment_amounts(booking, workshop_cost)
    franchisee_name, franchisee_id = _franchisee_name_for_workshop(workshop)
    promo = amounts['amount_paid_by_promotional_voucher']

    return {
        'user_id': _workshop_user_id(workshop),
        'course_name': _truncate(course.title if course else '', 255),
        'franchisee_name': franchisee_name,
        'franchisee_id': franchisee_id,
        'workshop_id': workshop.pk if workshop else 0,
        'bookings_workshops_id': legacy_report_bookings_workshops_id(booking),
        'workshop_date': _workshop_datetime(workshop),
        'venue_name': _truncate(venue.venue_name if venue else '', 255),
        'attendee_count': 1,
        'workshop_cost': workshop_cost,
        'booking_id': legacy_report_booking_id(booking),
        'vouchers_redeemed': _truncate((booking.voucher_code or '').strip() or '0'),
        'workshop_minus_promotional_discount': _quantize_money(workshop_cost - promo),
        **amounts,
    }


def build_legacy_unpaid_report_row(booking):
    """Map a pending Booking to gd_report__unpaid_bookings column values."""
    workshop = booking.workshop
    course = workshop.course if workshop else None
    venue = workshop.venue if workshop else None

    workshop_cost = booking.list_price
    if workshop_cost is None and workshop:
        workshop_cost = workshop.price
    workshop_cost = _quantize_money(workshop_cost)

    voucher_amount = _quantize_money(booking.voucher_discount)
    customer_name = _truncate(
        f'{booking.student_first_name} {booking.student_last_name}'.strip(),
    )

    return {
        'user_id': _workshop_user_id(workshop),
        'booking_date': booking.created_at or timezone.now(),
        'booking_workshop_id': legacy_report_bookings_workshops_id(booking),
        'customer_name': customer_name,
        'customer_email': _truncate(booking.student_email or ''),
        'customer_contact_number': _truncate(booking.student_phone or ''),
        'course_name': _truncate(course.title if course else ''),
        'workshop_date': _workshop_datetime(workshop),
        'venue_name': _truncate(venue.venue_name if venue else ''),
        'workshop_cost': workshop_cost,
        'places_booked': 1,
        'amount_paid': Decimal('0.00'),
        'amount_paid_by_voucher': voucher_amount if booking.voucher_code else Decimal('0.00'),
        'amount_paid_by_promotional_voucher': Decimal('0.00'),
        'amount_outstanding': _quantize_money(booking.price_paid),
    }


def sync_booking_to_legacy_course_report(booking_or_id):
    """Insert or update gd_report__bookings_by_course for a confirmed booking."""
    booking = _confirmed_booking(booking_or_id)
    if not booking:
        return None

    values = build_legacy_course_report_row(booking)
    with transaction.atomic():
        return ReportBookingByCourse.objects.update_or_create(
            booking_id=values['booking_id'],
            defaults=values,
        )


def sync_booking_to_legacy_payment_gateway_report(booking_or_id):
    """Insert or update gd_report__bookings_by_payment_gateway for a confirmed booking."""
    booking = _confirmed_booking(booking_or_id)
    if not booking:
        return None

    basket_id = booking_basket_id(booking)
    basket_details = load_basket_details([basket_id]) if basket_id else {}
    gateway_names = load_payment_gateway_names()
    values = build_legacy_payment_gateway_report_row(
        booking,
        basket_details=basket_details,
        gateway_names=gateway_names,
    )
    with transaction.atomic():
        return ReportBookingByPaymentGateway.objects.update_or_create(
            booking_id=values['booking_id'],
            defaults=values,
        )


def sync_booking_to_legacy_summary_report(booking_or_id):
    """Insert or update gd_report__bookings_summary for a confirmed booking."""
    booking = _confirmed_booking(booking_or_id)
    if not booking:
        return None

    values = build_legacy_summary_report_row(booking)
    with transaction.atomic():
        return ReportBookingSummary.objects.update_or_create(
            booking_id=values['booking_id'],
            defaults=values,
        )


def _pending_booking(booking_or_id):
    booking_pk = booking_or_id.pk if isinstance(booking_or_id, Booking) else int(booking_or_id)
    return (
        Booking.objects.select_related(
            'workshop',
            'workshop__course',
            'workshop__venue',
        )
        .filter(pk=booking_pk, status='pending')
        .first()
    )


def sync_booking_to_legacy_unpaid_report(booking_or_id):
    """Insert or update gd_report__unpaid_bookings for a pending booking."""
    booking = _pending_booking(booking_or_id)
    if not booking:
        return None

    values = build_legacy_unpaid_report_row(booking)
    with transaction.atomic():
        return ReportUnpaidBooking.objects.update_or_create(
            booking_workshop_id=values['booking_workshop_id'],
            defaults=values,
        )


def remove_legacy_unpaid_report_for_booking(booking_or_id):
    """Remove unpaid report row once a booking is paid or cancelled."""
    booking_pk = booking_or_id.pk if isinstance(booking_or_id, Booking) else int(booking_or_id)
    synthetic_id = LEGACY_REPORT_BOOKING_ID_OFFSET + int(booking_pk)
    ReportUnpaidBooking.objects.filter(booking_workshop_id=synthetic_id).delete()


def sync_booking_to_legacy_report(booking_or_id):
    """Backward-compatible alias for the course report sync."""
    return sync_booking_to_legacy_course_report(booking_or_id)


def sync_all_legacy_reports_for_booking(booking_or_id):
    """Sync confirmed booking rows into all legacy report tables."""
    remove_legacy_unpaid_report_for_booking(booking_or_id)
    course_result = sync_booking_to_legacy_course_report(booking_or_id)
    gateway_result = sync_booking_to_legacy_payment_gateway_report(booking_or_id)
    summary_result = sync_booking_to_legacy_summary_report(booking_or_id)
    return {
        'course': course_result,
        'payment_gateway': gateway_result,
        'summary': summary_result,
    }


def sync_bookings_to_legacy_reports(booking_ids):
    """Sync multiple confirmed bookings into legacy report tables."""
    counts = {
        'course_created': 0,
        'course_updated': 0,
        'gateway_created': 0,
        'gateway_updated': 0,
        'summary_created': 0,
        'summary_updated': 0,
        'unpaid_created': 0,
        'unpaid_updated': 0,
        'skipped': 0,
    }
    for booking_id in booking_ids:
        booking = Booking.objects.filter(pk=booking_id).only('status').first()
        if not booking:
            counts['skipped'] += 1
            continue
        if booking.status == 'pending':
            result = sync_booking_to_legacy_unpaid_report(booking_id)
            if not result:
                counts['skipped'] += 1
                continue
            _, was_created = result
            if was_created:
                counts['unpaid_created'] += 1
            else:
                counts['unpaid_updated'] += 1
            continue

        if booking.status != 'confirmed':
            counts['skipped'] += 1
            continue

        results = sync_all_legacy_reports_for_booking(booking_id)
        if not any(results.values()):
            counts['skipped'] += 1
            continue
        for key, result in results.items():
            if not result:
                continue
            _, was_created = result
            if was_created:
                counts[f'{key}_created'] += 1
            else:
                counts[f'{key}_updated'] += 1
    return counts
