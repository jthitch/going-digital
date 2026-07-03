"""Payment gateway report rows from gd_booking (legacy) and synced report table (new site)."""
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.legacy_report_queries import (
    _scoped_workshop_ids,
    filter_payment_gateway_queryset,
)
from bookings.models import ReportBookingByPaymentGateway
from courses.region_scope import user_has_full_region_access


@dataclass
class PaymentGatewaySourceRow:
    booking_id: int
    payment_date: datetime | None
    basket_id: int | None
    customer_firstname: str
    customer_lastname: str
    customer_email: str
    workshop_date: datetime | None
    workshop_id: int | None
    course_name: str
    places_booked: int
    workshop_cost: Decimal
    amount_paid: Decimal
    amount_paid_by_voucher: Decimal
    vouchers_redeemed: str
    payment_gateway: str
    gateway_transaction_code: str


def _quantize(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def _gd_booking_scope_clause(user, region_id=None, tutor_id=None):
    """Scope legacy rows via gd_bookings_workshops and gd_workshop."""
    if user_has_full_region_access(user) and not region_id and not tutor_id:
        return '', []

    clauses = []
    params = []

    if not user_has_full_region_access(user):
        clauses.append(
            '(bw.workshop_user_id = %s OR w.user_id = %s OR w.createdby_id = %s)',
        )
        params.extend([user.pk, user.pk, user.pk])

    workshop_ids = list(_scoped_workshop_ids(user, region_id, tutor_id, active_only=False))
    if workshop_ids:
        placeholders = ','.join(['%s'] * len(workshop_ids))
        clauses.append(f'bw.workshop_id IN ({placeholders})')
        params.extend(workshop_ids)
    elif region_id or tutor_id or not user_has_full_region_access(user):
        return ' AND 1=0', []

    if not clauses:
        return '', []

    return ' AND ' + ' AND '.join(clauses), params


def load_gd_booking_payment_gateway_rows(user, start_day, end_day, region_id=None, tutor_id=None):
    """
    Legacy line items via gd_bookings_workshops → gd_booking → gd_workshop.

    Payment and gateway from gd_booking; workshop date/price from gd_workshop.
    """
    scope_sql, scope_params = _gd_booking_scope_clause(user, region_id, tutor_id)
    sql = f"""
        SELECT
            b.id,
            b.basket_id,
            b.created_at,
            COALESCE(bw.amount_paid, b.amount_paid) AS amount_paid,
            COALESCE(bw.amount_paid_by_voucher, b.amount_paid_by_voucher) AS amount_paid_by_voucher,
            b.vouchers_redeemed,
            b.gateway_transaction_code,
            COALESCE(pg.payment_gateway, pg.internal_name, '') AS payment_gateway_name,
            c.firstname,
            c.lastname,
            c.email,
            COALESCE(cr.course_name, '') AS course_name,
            w.date AS workshop_date,
            bw.workshop_id,
            w.cost AS workshop_cost
        FROM gd_bookings_workshops bw
        INNER JOIN gd_booking b ON b.id = bw.booking_id
        LEFT JOIN gd_workshop w ON w.id = bw.workshop_id
        LEFT JOIN gd_course cr ON cr.id = COALESCE(w.course_id, bw.course_id)
        LEFT JOIN gd_payment_gateway pg ON pg.id = b.payment_gateway_id
        LEFT JOIN gd_customer c ON c.id = b.customer_id
        WHERE b.id < %s
          AND DATE(b.created_at) >= %s
          AND DATE(b.created_at) < %s
          AND (
                b.payment_confirmed = 1
                OR IFNULL(b.amount_paid, 0) > 0
                OR IFNULL(b.amount_paid_by_voucher, 0) > 0
                OR IFNULL(bw.amount_paid, 0) > 0
              )
        {scope_sql}
        ORDER BY b.created_at DESC, b.id DESC, bw.id DESC
    """
    params = [
        LEGACY_REPORT_BOOKING_ID_OFFSET,
        start_day,
        end_day,
        *scope_params,
    ]
    rows = []
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        for raw in cursor.fetchall():
            (
                booking_id,
                basket_id,
                created_at,
                amount_paid,
                amount_paid_by_voucher,
                vouchers_redeemed,
                gateway_transaction_code,
                payment_gateway_name,
                firstname,
                lastname,
                email,
                course_name,
                workshop_date,
                workshop_id,
                workshop_cost,
            ) = raw
            voucher_text = (vouchers_redeemed or '').strip()
            rows.append(
                PaymentGatewaySourceRow(
                    booking_id=int(booking_id),
                    payment_date=created_at,
                    basket_id=int(basket_id) if basket_id else None,
                    customer_firstname=(firstname or '').strip(),
                    customer_lastname=(lastname or '').strip(),
                    customer_email=(email or '').strip(),
                    workshop_date=workshop_date,
                    workshop_id=int(workshop_id) if workshop_id else None,
                    course_name=(course_name or '').strip(),
                    places_booked=1,
                    workshop_cost=_quantize(workshop_cost),
                    amount_paid=_quantize(amount_paid),
                    amount_paid_by_voucher=_quantize(amount_paid_by_voucher),
                    vouchers_redeemed=voucher_text or '0',
                    payment_gateway=(payment_gateway_name or '').strip() or 'Unknown',
                    gateway_transaction_code=(gateway_transaction_code or '').strip(),
                ),
            )
    return rows


def load_new_site_payment_gateway_rows(user, start_dt, end_dt):
    """Rows synced to gd_report__bookings_by_payment_gateway for new-site bookings."""
    qs = ReportBookingByPaymentGateway.objects.filter(
        booking_date__gte=start_dt,
        booking_date__lt=end_dt,
        booking_id__gte=LEGACY_REPORT_BOOKING_ID_OFFSET,
    ).order_by('-booking_date', '-booking_id')
    qs = filter_payment_gateway_queryset(qs, user)

    rows = []
    for row in qs:
        rows.append(
            PaymentGatewaySourceRow(
                booking_id=row.booking_id,
                payment_date=row.booking_date,
                basket_id=row.basket_id or None,
                customer_firstname=(row.customer_firstname or '').strip(),
                customer_lastname=(row.customer_lastname or '').strip(),
                customer_email=(row.customer_email or '').strip(),
                workshop_date=row.workshop_date,
                workshop_id=row.workshop_id or None,
                course_name=(row.course_name or '').strip(),
                places_booked=row.places_booked or 1,
                workshop_cost=_quantize(row.workshop_cost),
                amount_paid=_quantize(row.amount_paid),
                amount_paid_by_voucher=_quantize(row.amount_paid_by_voucher),
                vouchers_redeemed=(row.vouchers_redeemed or '').strip() or '0',
                payment_gateway=(row.payment_gateway or '').strip() or 'Unknown',
                gateway_transaction_code=(row.gateway_transaction_code or '').strip(),
            ),
        )
    return rows


def payment_gateway_report_source_rows(user, start_date, end_date, region_id=None, tutor_id=None):
    """Merged legacy (gd_booking) and new-site payment gateway report rows."""
    if isinstance(start_date, datetime):
        start_day = timezone.localdate(start_date)
    else:
        start_day = start_date
    if isinstance(end_date, datetime):
        end_day = timezone.localdate(end_date)
    else:
        end_day = end_date

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_day, time.min), tz)

    legacy_rows = load_gd_booking_payment_gateway_rows(
        user,
        start_day,
        end_day,
        region_id=region_id,
        tutor_id=tutor_id,
    )
    new_rows = load_new_site_payment_gateway_rows(user, start_dt, end_dt)

    merged = legacy_rows + new_rows
    merged.sort(
        key=lambda row: (
            -(row.payment_date.timestamp() if row.payment_date else 0),
            -row.booking_id,
        ),
    )
    return merged
