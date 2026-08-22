"""Monthly booking and workshop reports for the admin."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import connection
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from bookings.models import Booking
from bookings.legacy_franchisee_report import franchisee_report_source_rows
from bookings.legacy_payment_gateway_report import payment_gateway_report_source_rows
from bookings.legacy_report_queries import (
    gateway_id_from_name,
    legacy_display_booking_id,
    legacy_row_payment_date,
    legacy_row_workshop_date,
)
from bookings.legacy_monthly_report import monthly_booking_stats
from bookings.report_payment_data import (
    STRIPE_GATEWAY_ID,
    VOUCHER_GATEWAY_ID,
    booking_basket_id as _booking_basket_id,
    booking_transaction_id as _booking_transaction_id,
    gateway_id_for_booking as _gateway_id_for_booking,
    gateway_name as _gateway_name,
    is_manual_report_gateway,
    load_basket_details as _load_basket_details,
    load_payment_gateway_meta,
    load_payment_gateway_names,
)
from bookings.scope import filter_bookings_for_user
from courses.models import Region, Tutor, Workshop
from courses.region_scope import (
    filter_regions_for_user,
    filter_workshops_for_user,
    get_user_region_ids,
    user_has_full_region_access,
)


@dataclass
class MonthlyReportRow:
    label: str
    year: int
    month: int
    bookings: int
    income: Decimal
    courses_scheduled: int
    future_courses: int
    places_booked: int
    places_capacity: int
    percent_sold: Decimal | None

    @property
    def is_future_month(self):
        today = timezone.localdate()
        return (self.year, self.month) > (today.year, today.month)


@dataclass
class PaymentGatewayBookingRow:
    payment_date: date | None
    basket_id: int | None
    booking_ref: int
    customer_name: str
    customer_email: str
    workshop_date: date | None
    workshop_id: int | None
    course_name: str
    places_booked: int
    workshop_price: Decimal
    gift_voucher_code: str
    gift_voucher_amount: Decimal | None
    promotion_code: str
    payment_gateway: str
    total_paid: Decimal
    transaction_id: str


@dataclass
class FranchiseeBookingRow:
    franchisee_name: str
    payment_date: date | None
    customer_name: str
    customer_email: str
    customer_phone: str
    customer_location: str
    customer_postcode: str
    booking_ref: int
    workshop_date: date | None
    workshop_id: int | None
    course_name: str
    workshop_cost: Decimal
    venue_name: str
    places_booked: int
    gift_voucher_value: Decimal
    gift_voucher_transaction_fee: Decimal
    promotional_discount: Decimal
    promotional_vouchers_redeemed: str
    payment_method: str
    customer_payment: Decimal
    manual_payment: Decimal
    transaction_fee: Decimal
    transaction_code: str
    customer_payment_plus_voucher: Decimal
    total_paid: Decimal


@dataclass
class RefundReportRow:
    refund_id: int
    franchisee_name: str
    refund_amount: Decimal
    refund_date: datetime
    refund_reason: str


@dataclass
class GiftVoucherPurchasedRow:
    date_issued: date | None
    voucher_id: int
    customer_email: str
    gift_voucher_code: str
    value: Decimal
    expiry_date: date | None
    payment_gateway: str
    gateway_transaction_code: str
    customer_name: str
    purchased_basket_id: str
    claimed_by: str
    claimed_date: date | None
    amount_claimed: Decimal
    redeemed_basket_id: str


def user_can_view_payment_gateway_report(user):
    """Bookings by payment gateway is for platform super users / administrators."""
    return user_can_view_reports(user) and user_has_full_region_access(user)


def user_can_view_franchisee_booking_report(user):
    """Bookings by franchisee is for platform super users / administrators."""
    return user_can_view_payment_gateway_report(user)


def user_can_view_refunds_report(user):
    """Refunds report is for platform super users / administrators."""
    return user_can_view_payment_gateway_report(user)


def user_can_view_gift_voucher_purchased_report(user):
    """Gift voucher purchased report is for platform super users / administrators."""
    return user_can_view_payment_gateway_report(user)


def user_can_view_reports(user):
    if not user.is_authenticated or not user.is_staff:
        return False
    if user_has_full_region_access(user):
        return True
    return bool(get_user_region_ids(user))


def _month_start(year, month):
    return date(year, month, 1)


def _next_month_start(year, month):
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _aware_range(start_day, end_day):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end = timezone.make_aware(datetime.combine(end_day, time.min), tz)
    return start, end


def _iter_months(months_back):
    """Yield (year, month) from oldest to newest, inclusive of current month."""
    today = timezone.localdate()
    return _iter_months_between(
        _month_start(today.year, today.month),
        today,
        months_back=months_back,
    )


def _iter_months_between(start_day, end_day, *, months_back=None):
    """
    Yield (year, month) from oldest to newest.

    If months_back is set, walk that many months ending at end_day's month
    (used for preset periods). Otherwise include every month from start_day
    through end_day inclusive.
    """
    if months_back is not None:
        year, month = end_day.year, end_day.month
        months = []
        for _ in range(months_back):
            months.append((year, month))
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        return reversed(months)

    year, month = start_day.year, start_day.month
    end_year, end_month = end_day.year, end_day.month
    months = []
    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _booking_queryset(user, region_id=None, tutor_id=None):
    qs = Booking.objects.filter(status='confirmed').select_related('workshop')
    qs = filter_bookings_for_user(qs, user)
    if region_id:
        qs = qs.filter(workshop__region_id=region_id)
    if tutor_id:
        qs = qs.filter(workshop__tutor_id=tutor_id)
    return qs


def _workshop_queryset(user, region_id=None, tutor_id=None):
    qs = Workshop.objects.filter(active=1)
    qs = filter_workshops_for_user(qs, user)
    if region_id:
        qs = qs.filter(region_id=region_id)
    if tutor_id:
        qs = qs.filter(tutor_id=tutor_id)
    return qs


def report_filter_regions(user):
    return filter_regions_for_user(
        Region.objects.filter(active=1).order_by('region_name'),
        user,
    )


def report_filter_tutors(user, region_id=None):
    workshop_qs = _workshop_queryset(user, region_id=region_id)
    tutor_ids = (
        workshop_qs.exclude(tutor_id__isnull=True)
        .values_list('tutor_id', flat=True)
        .distinct()
    )
    return Tutor.objects.filter(pk__in=tutor_ids, active=1).order_by(
        'lastname', 'firstname',
    )


def build_monthly_report(
    user,
    *,
    region_id=None,
    tutor_id=None,
    months_back=12,
    start_date=None,
    end_date=None,
):
    """Build monthly rows for bookings, income, courses and % sold (legacy + new site)."""
    from django.utils.formats import date_format

    rows = []
    now = timezone.now()

    if start_date is not None and end_date is not None:
        month_pairs = _iter_months_between(start_date, end_date)
    else:
        month_pairs = _iter_months(months_back)

    for year, month in month_pairs:
        month_start = _month_start(year, month)
        month_end = _next_month_start(year, month)
        workshop_start, workshop_end = _aware_range(month_start, month_end)

        booking_stats = monthly_booking_stats(
            user,
            month_start,
            month_end,
            region_id=region_id,
            tutor_id=tutor_id,
        )

        workshops_qs = _workshop_queryset(user, region_id, tutor_id).filter(
            date__gte=workshop_start,
            date__lt=workshop_end,
        )
        workshop_stats = workshops_qs.aggregate(
            courses=Count('id'),
            future_courses=Count('id', filter=Q(date__gte=now)),
            booked=Coalesce(Sum('places_booked'), 0),
            capacity=Coalesce(Sum('max_places'), 0),
        )

        places_booked = int(workshop_stats['booked'] or 0)
        places_capacity = int(workshop_stats['capacity'] or 0)
        if places_capacity > 0:
            percent_sold = (
                Decimal(places_booked) / Decimal(places_capacity) * Decimal('100')
            ).quantize(Decimal('0.1'))
        else:
            percent_sold = None

        label = date_format(month_start, format='F Y')
        rows.append(
            MonthlyReportRow(
                label=label,
                year=year,
                month=month,
                bookings=booking_stats['bookings'] or 0,
                income=booking_stats['income'] or Decimal('0.00'),
                courses_scheduled=workshop_stats['courses'] or 0,
                future_courses=workshop_stats['future_courses'] or 0,
                places_booked=places_booked,
                places_capacity=places_capacity,
                percent_sold=percent_sold,
            )
        )

    return rows


def report_totals(rows):
    total_bookings = sum(row.bookings for row in rows)
    total_income = sum((row.income for row in rows), Decimal('0.00'))
    total_courses = sum(row.courses_scheduled for row in rows)
    total_future = sum(row.future_courses for row in rows)
    total_booked = sum(row.places_booked for row in rows)
    total_capacity = sum(row.places_capacity for row in rows)
    if total_capacity > 0:
        overall_pct = (
            Decimal(total_booked) / Decimal(total_capacity) * Decimal('100')
        ).quantize(Decimal('0.1'))
    else:
        overall_pct = None
    return {
        'bookings': total_bookings,
        'income': total_income,
        'courses_scheduled': total_courses,
        'future_courses': total_future,
        'percent_sold': overall_pct,
    }


def _inclusive_end_day(end_day):
    """Treat end_date as inclusive by using start of the following day."""
    return end_day + timedelta(days=1)


def _workshop_date(workshop):
    if not workshop or not workshop.date:
        return None
    value = workshop.date
    if hasattr(value, 'date'):
        return value.date()
    return value


def _booking_payment_date(booking):
    payment = booking.payment
    if not payment:
        return timezone.localdate(booking.created_at)
    if payment.succeeded_at:
        return timezone.localdate(payment.succeeded_at)
    return timezone.localdate(payment.created_at or booking.created_at)


def _payment_gateway_booking_queryset(user, start_dt, end_dt):
    return (
        _booking_queryset(user)
        .select_related('payment', 'workshop', 'workshop__course', 'customer')
        .filter(
            Q(payment__succeeded_at__gte=start_dt, payment__succeeded_at__lt=end_dt)
            | Q(
                payment__succeeded_at__isnull=True,
                payment__status='succeeded',
                created_at__gte=start_dt,
                created_at__lt=end_dt,
            )
        )
        .order_by('-payment__succeeded_at', '-created_at')
    )


def build_payment_gateway_report(user, start_date, end_date):
    """Line-item bookings from gd_booking (legacy) and synced rows (new site)."""
    end_exclusive = _inclusive_end_day(end_date)
    source_rows = payment_gateway_report_source_rows(user, start_date, end_exclusive)

    rows = []
    total_paid = Decimal('0.00')
    for row in source_rows:
        voucher_code = (row.vouchers_redeemed or '').strip() or '0'
        voucher_amount = row.amount_paid_by_voucher or Decimal('0.00')
        price_paid = row.amount_paid or Decimal('0.00')
        total_paid += price_paid

        customer_name = f'{row.customer_firstname} {row.customer_lastname}'.strip()
        rows.append(
            PaymentGatewayBookingRow(
                payment_date=legacy_row_payment_date(row.payment_date),
                basket_id=row.basket_id,
                booking_ref=legacy_display_booking_id(row.booking_id),
                customer_name=customer_name,
                customer_email=(row.customer_email or '').strip(),
                workshop_date=legacy_row_workshop_date(row.workshop_date),
                workshop_id=row.workshop_id,
                course_name=(row.course_name or '').strip(),
                places_booked=row.places_booked or 1,
                workshop_price=row.workshop_cost or Decimal('0.00'),
                gift_voucher_code=voucher_code,
                gift_voucher_amount=voucher_amount if voucher_code != '0' else None,
                promotion_code='0',
                payment_gateway=(row.payment_gateway or '').strip() or 'Unknown',
                total_paid=price_paid,
                transaction_id=(row.gateway_transaction_code or '').strip(),
            )
        )

    return rows, {
        'bookings': len(rows),
        'income': total_paid,
    }


def _quantize_money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def _gateway_transaction_fee(amount, gateway_meta):
    amount = Decimal(amount or 0)
    if amount <= 0:
        return Decimal('0.00')
    percentage = gateway_meta.get('transaction_percentage', Decimal('0'))
    if percentage <= 0:
        return Decimal('0.00')
    return _quantize_money(amount * percentage / Decimal('100'))


def _load_franchisee_names(user_ids):
    if not user_ids:
        return {}
    from core.models import User

    return {
        user.pk: user.get_full_name()
        for user in User.objects.filter(pk__in=user_ids, active=1)
    }


def _franchisee_payment_columns(amount_paid, gateway_id, gateway_meta):
    """
    Split amount into customer vs manual columns for the franchisee report.

    Online gateways (WorldPay, Stripe, PayPal, etc.) stay in customer payment
    even when gd_payment_gateway.manual_payment_option is set.
    """
    customer_payment = _quantize_money(amount_paid)

    if is_manual_report_gateway(gateway_id):
        return {
            'customer_payment': Decimal('0.00'),
            'manual_payment': customer_payment,
            'transaction_fee': Decimal('0.00'),
        }
    if gateway_id == VOUCHER_GATEWAY_ID:
        return {
            'customer_payment': Decimal('0.00'),
            'manual_payment': Decimal('0.00'),
            'transaction_fee': Decimal('0.00'),
        }
    return {
        'customer_payment': customer_payment,
        'manual_payment': Decimal('0.00'),
        'transaction_fee': _gateway_transaction_fee(customer_payment, gateway_meta),
    }


def _gift_voucher_transaction_fee(gift_voucher_value, gateway_meta_by_id):
    """
    Fee on gift-voucher value uses the Going Digital Voucher gateway rate.

    Applies whenever a gift voucher amount is present — including mixed
    Stripe/WorldPay + voucher payments — not only pure voucher gateways.
    """
    value = _quantize_money(gift_voucher_value)
    if value <= 0:
        return Decimal('0.00')
    voucher_gateway = gateway_meta_by_id.get(VOUCHER_GATEWAY_ID, {})
    return _gateway_transaction_fee(value, voucher_gateway)


def build_franchisee_booking_report(user, start_date, end_date):
    """Line-item franchisee bookings via gd_bookings_workshops (legacy) and synced rows (new site)."""
    gateway_meta = load_payment_gateway_meta()
    gateway_names = {
        gateway_id: meta['name'] for gateway_id, meta in gateway_meta.items()
    }
    end_exclusive = _inclusive_end_day(end_date)
    source_rows = franchisee_report_source_rows(user, start_date, end_exclusive)

    missing_franchisee_ids = {
        row.franchisee_user_id
        for row in source_rows
        if not row.franchisee_name and row.franchisee_user_id
    }
    franchisee_names = _load_franchisee_names(missing_franchisee_ids)

    rows = []
    total_paid = Decimal('0.00')
    for row in source_rows:
        gateway_id = row.payment_gateway_id
        if not gateway_id:
            gateway_id = gateway_id_from_name(row.payment_gateway, gateway_names)
        gateway = gateway_meta.get(gateway_id or 0, {})

        payment_method = (row.payment_gateway or '').strip() or 'Unknown'
        workshop_cost = _quantize_money(row.workshop_cost)
        gift_voucher_value = _quantize_money(row.amount_paid_by_voucher)
        promotional_discount = _quantize_money(row.amount_paid_by_promotional_voucher)
        promotional_vouchers_redeemed = (row.vouchers_redeemed or '').strip()
        if promotional_vouchers_redeemed in ('', '0', 'NULL'):
            promotional_vouchers_redeemed = ''

        columns = _franchisee_payment_columns(row.amount_paid, gateway_id, gateway)
        customer_payment = columns['customer_payment']
        manual_payment = columns['manual_payment']
        transaction_fee = columns['transaction_fee']
        if gateway_id == VOUCHER_GATEWAY_ID:
            gift_voucher_value = gift_voucher_value or workshop_cost
        elif gift_voucher_value > 0 and customer_payment == 0:
            # Fully voucher-funded rows sometimes synced as Stripe when the basket
            # still had a card gateway id; show voucher as the payment method.
            voucher_meta = gateway_meta.get(VOUCHER_GATEWAY_ID, {})
            payment_method = (voucher_meta.get('name') or '').strip() or payment_method

        gift_voucher_transaction_fee = _gift_voucher_transaction_fee(
            gift_voucher_value,
            gateway_meta,
        )

        customer_payment_plus_voucher = _quantize_money(
            customer_payment + gift_voucher_value,
        )
        net_total = _quantize_money(
            customer_payment_plus_voucher
            - transaction_fee
            - gift_voucher_transaction_fee,
        )
        total_paid += net_total

        franchisee_name = row.franchisee_name
        if not franchisee_name and row.franchisee_user_id:
            franchisee_name = franchisee_names.get(row.franchisee_user_id, '')

        customer_name = f'{row.customer_firstname} {row.customer_lastname}'.strip()

        rows.append(
            FranchiseeBookingRow(
                franchisee_name=franchisee_name,
                payment_date=legacy_row_payment_date(row.payment_date),
                customer_name=customer_name,
                customer_email=(row.customer_email or '').strip(),
                customer_phone=(row.customer_phone or '').strip(),
                customer_location='',
                customer_postcode='',
                booking_ref=legacy_display_booking_id(row.booking_id),
                workshop_date=legacy_row_workshop_date(row.workshop_date),
                workshop_id=row.workshop_id,
                course_name=(row.course_name or '').strip(),
                workshop_cost=workshop_cost,
                venue_name=(row.venue_name or '').strip(),
                places_booked=row.places_booked or 1,
                gift_voucher_value=gift_voucher_value,
                gift_voucher_transaction_fee=gift_voucher_transaction_fee,
                promotional_discount=promotional_discount,
                promotional_vouchers_redeemed=promotional_vouchers_redeemed,
                payment_method=payment_method,
                customer_payment=customer_payment,
                manual_payment=manual_payment,
                transaction_fee=transaction_fee,
                transaction_code=(row.gateway_transaction_code or '').strip(),
                customer_payment_plus_voucher=customer_payment_plus_voucher,
                total_paid=net_total,
            )
        )

    return rows, {
        'bookings': len(rows),
        'income': total_paid,
    }


def _format_franchisee_name(firstname, lastname):
    return f'{(firstname or "").strip()} {(lastname or "").strip()}'.strip()


def _localize_legacy_datetime(value):
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def format_refund_datetime(value):
    localized = _localize_legacy_datetime(value)
    if not localized:
        return ''
    return localized.strftime('%d/%m/%Y %H:%M')


def build_refunds_report(user, start_date, end_date):
    """Refunds recorded against legacy workshop bookings in a date range."""
    end_exclusive = _inclusive_end_day(end_date)
    start_dt, end_dt = _aware_range(start_date, end_exclusive)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT bw.id, bw.refund_amount, bw.refund_date, bw.refund_reason,
                   u.firstname, u.lastname
            FROM gd_bookings_workshops bw
            LEFT JOIN gd_user u ON u.id = bw.workshop_user_id
            WHERE bw.refund_amount > 0
              AND bw.refund_date IS NOT NULL
              AND bw.refund_date >= %s
              AND bw.refund_date < %s
            ORDER BY bw.refund_date DESC, bw.id DESC
            """,
            [start_dt, end_dt],
        )
        raw_rows = cursor.fetchall()

    rows = []
    total_amount = Decimal('0.00')
    for refund_id, refund_amount, refund_date, refund_reason, firstname, lastname in raw_rows:
        amount = _quantize_money(refund_amount)
        total_amount += amount
        rows.append(
            RefundReportRow(
                refund_id=refund_id,
                franchisee_name=_format_franchisee_name(firstname, lastname),
                refund_amount=amount,
                refund_date=_localize_legacy_datetime(refund_date),
                refund_reason=(refund_reason or '').strip(),
            )
        )

    return rows, {
        'refunds': len(rows),
        'amount': total_amount,
    }


GIFT_VOUCHER_TYPE_ID = 1


def _format_report_date(value):
    if not value:
        return ''
    if hasattr(value, 'date') and callable(value.date) and not isinstance(value, date):
        value = value.date()
    return value.strftime('%d/%m/%Y')


def _load_redeemed_basket_ids(voucher_ids, claimed_booking_by_voucher):
    if not voucher_ids:
        return {}

    redeem_baskets = {}
    bookings = Booking.objects.filter(voucher_id__in=voucher_ids).select_related('payment')
    for booking in bookings:
        if not booking.payment or not booking.voucher_id:
            continue
        basket_id = (booking.payment.metadata or {}).get('workshop_basket_id')
        if basket_id:
            redeem_baskets[booking.voucher_id] = int(basket_id)

    remaining = {
        booking_id: voucher_id
        for voucher_id, booking_id in claimed_booking_by_voucher.items()
        if voucher_id not in redeem_baskets and booking_id
    }
    if not remaining:
        return redeem_baskets

    legacy_ids = sorted(remaining.keys())
    placeholders = ','.join(['%s'] * len(legacy_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, basket_id
            FROM gd_booking
            WHERE id IN ({placeholders})
            """,
            legacy_ids,
        )
        for booking_id, basket_id in cursor.fetchall():
            voucher_id = remaining.get(booking_id)
            if voucher_id and basket_id:
                redeem_baskets[voucher_id] = int(basket_id)

    return redeem_baskets


def build_gift_voucher_purchased_report(user, start_date, end_date):
    """Gift vouchers issued in a date range."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT v.id, v.issue_date, v.email, v.voucher_code, v.value, v.expiry_date,
                   v.payment_gateway_id, v.gateway_transaction_code, v.basket_id,
                   v.claimed_by_customer_id, v.claimed_date, v.amount_claimed,
                   v.claimed_on_booking_id,
                   pg.payment_gateway,
                   pc.firstname, pc.lastname,
                   cc.firstname, cc.lastname
            FROM gd_voucher v
            LEFT JOIN gd_payment_gateway pg ON pg.id = v.payment_gateway_id
            LEFT JOIN gd_customer pc ON pc.id = v.customer_id
            LEFT JOIN gd_customer cc ON cc.id = v.claimed_by_customer_id
            WHERE v.voucher_type_id = %s
              AND v.issue_date >= %s
              AND v.issue_date <= %s
            ORDER BY v.issue_date DESC, v.id DESC
            """,
            [GIFT_VOUCHER_TYPE_ID, start_date, end_date],
        )
        raw_rows = cursor.fetchall()

    voucher_ids = [row[0] for row in raw_rows]
    claimed_booking_by_voucher = {
        row[0]: row[12]
        for row in raw_rows
        if row[12]
    }
    redeemed_basket_ids = _load_redeemed_basket_ids(voucher_ids, claimed_booking_by_voucher)

    rows = []
    total_value = Decimal('0.00')
    total_claimed = Decimal('0.00')
    for (
        voucher_id,
        issue_date,
        email,
        voucher_code,
        value,
        expiry_date,
        payment_gateway_id,
        gateway_transaction_code,
        basket_id,
        claimed_by_customer_id,
        claimed_date,
        amount_claimed,
        claimed_on_booking_id,
        payment_gateway,
        purchaser_first,
        purchaser_last,
        claimed_first,
        claimed_last,
    ) in raw_rows:
        voucher_value = _quantize_money(value)
        claimed_amount = _quantize_money(amount_claimed)
        total_value += voucher_value
        total_claimed += claimed_amount

        purchaser_name = _format_franchisee_name(purchaser_first, purchaser_last)
        if not purchaser_name:
            purchaser_name = 'N/A'

        claimed_by = _format_franchisee_name(claimed_first, claimed_last)
        if not claimed_by_customer_id or not claimed_by:
            claimed_by = 'N/A'

        redeemed_basket = redeemed_basket_ids.get(voucher_id)
        rows.append(
            GiftVoucherPurchasedRow(
                date_issued=issue_date,
                voucher_id=voucher_id,
                customer_email=(email or '').strip(),
                gift_voucher_code=(voucher_code or '').strip(),
                value=voucher_value,
                expiry_date=expiry_date,
                payment_gateway=(payment_gateway or '').strip() or 'N/A',
                gateway_transaction_code=(gateway_transaction_code or '').strip(),
                customer_name=purchaser_name,
                purchased_basket_id=str(basket_id) if basket_id else 'N/A',
                claimed_by=claimed_by,
                claimed_date=claimed_date,
                amount_claimed=claimed_amount,
                redeemed_basket_id=str(redeemed_basket) if redeemed_basket else '',
            )
        )

    return rows, {
        'vouchers': len(rows),
        'value': total_value,
        'claimed': total_claimed,
    }


def default_payment_gateway_date_range():
    today = timezone.localdate()
    first_of_this_month = today.replace(day=1)
    last_of_previous_month = first_of_this_month - timedelta(days=1)
    first_of_previous_month = last_of_previous_month.replace(day=1)
    return first_of_previous_month, last_of_previous_month


def iter_monthly_report_csv(rows, totals):
    yield [
        'Month',
        'Bookings',
        'Income',
        'Courses scheduled',
        'Future courses',
        '% sold',
    ]
    for row in rows:
        yield [
            row.label,
            row.bookings,
            row.income,
            row.courses_scheduled,
            row.future_courses,
            f'{row.percent_sold}%' if row.percent_sold is not None else '',
        ]
    if totals:
        yield [
            'Total',
            totals['bookings'],
            totals['income'],
            totals['courses_scheduled'],
            totals['future_courses'],
            f"{totals['percent_sold']}%" if totals['percent_sold'] is not None else '',
        ]


def iter_payment_gateway_report_csv(rows):
    yield [
        'Payment date',
        'Basket id',
        'Booking ref',
        'Customer name',
        'Customer email',
        'Workshop date',
        'Workshop id',
        'Course',
        'Places booked',
        'Workshop price',
        'Gift voucher code',
        'Gift voucher amount',
        'Promotion code',
        'Payment gateway',
        'Total paid',
        'Transaction id',
    ]
    for row in rows:
        yield [
            row.payment_date.strftime('%d/%m/%Y') if row.payment_date else '',
            row.basket_id or '',
            row.booking_ref,
            row.customer_name,
            row.customer_email,
            row.workshop_date.strftime('%d/%m/%Y') if row.workshop_date else '',
            row.workshop_id or '',
            row.course_name,
            row.places_booked,
            row.workshop_price,
            row.gift_voucher_code,
            row.gift_voucher_amount if row.gift_voucher_amount is not None else '',
            row.promotion_code,
            row.payment_gateway,
            row.total_paid,
            row.transaction_id,
        ]


def iter_franchisee_booking_report_csv(rows):
    yield [
        'Franchisee',
        'Payment Date',
        'Customer Name',
        'Customer Email',
        'Customer Phone',
        'Customer Location',
        'Customer Postcode',
        'Booking Ref',
        'Workshop Date',
        'Workshop Id',
        'Course',
        'Workshop Cost',
        'Venue',
        'Places Booked',
        'Gift Voucher Value',
        'Gift Voucher Transaction Fee',
        'Promotional Discount',
        'Promotional Vouchers Redeemed',
        'Payment Method',
        'Customer Payment',
        'Manual Payment',
        'Transaction Fee',
        'Transaction Code',
        'Customer Payment + Gift Voucher',
        'Total Paid',
    ]
    for row in rows:
        yield [
            row.franchisee_name,
            row.payment_date.strftime('%d/%m/%Y') if row.payment_date else '',
            row.customer_name,
            row.customer_email,
            row.customer_phone,
            row.customer_location,
            row.customer_postcode,
            row.booking_ref,
            row.workshop_date.strftime('%d/%m/%Y') if row.workshop_date else '',
            row.workshop_id or '',
            row.course_name,
            row.workshop_cost,
            row.venue_name,
            row.places_booked,
            row.gift_voucher_value,
            row.gift_voucher_transaction_fee,
            row.promotional_discount,
            row.promotional_vouchers_redeemed,
            row.payment_method,
            row.customer_payment,
            row.manual_payment,
            row.transaction_fee,
            row.transaction_code,
            row.customer_payment_plus_voucher,
            row.total_paid,
        ]


def iter_refunds_report_csv(rows):
    yield [
        'ID',
        'Franchisee Name',
        'Refund Amount',
        'Refund Date',
        'Refund Reason',
    ]
    for row in rows:
        yield [
            row.refund_id,
            row.franchisee_name,
            row.refund_amount,
            format_refund_datetime(row.refund_date),
            row.refund_reason,
        ]


def iter_gift_voucher_purchased_report_csv(rows):
    yield [
        'Date Issued',
        'Id',
        'Customer Email Address',
        'Gift Voucher Code',
        'Value',
        'Expiry Date',
        'Payment Gateway',
        'Gateway Transaction Code',
        'Customer Name',
        'Purchased Basket Id',
        'Claimed By',
        'Claimed Date',
        'Amount Claimed',
        'Redeemed Basket Id',
    ]
    for row in rows:
        yield [
            _format_report_date(row.date_issued),
            row.voucher_id,
            row.customer_email,
            row.gift_voucher_code,
            row.value,
            _format_report_date(row.expiry_date),
            row.payment_gateway,
            row.gateway_transaction_code,
            row.customer_name,
            row.purchased_basket_id,
            row.claimed_by,
            _format_report_date(row.claimed_date) if row.claimed_date else 'N/A',
            row.amount_claimed,
            row.redeemed_basket_id,
        ]
