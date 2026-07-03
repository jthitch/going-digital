"""Franchisee booking report rows from gd_bookings_workshops (legacy) and synced tables (new site)."""
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from bookings.legacy_payment_gateway_report import _gd_booking_scope_clause
from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.legacy_report_queries import (
    filter_payment_gateway_queryset,
    gateway_id_from_name,
)
from bookings.models import ReportBookingByPaymentGateway, ReportBookingSummary
from bookings.report_payment_data import load_payment_gateway_meta


@dataclass
class FranchiseeSourceRow:
    booking_id: int
    payment_date: datetime | None
    payment_gateway_id: int | None
    payment_gateway: str
    manual_payment_option: int
    transaction_percentage: Decimal
    gateway_transaction_code: str
    amount_paid: Decimal
    amount_paid_by_voucher: Decimal
    amount_paid_by_promotional_voucher: Decimal
    vouchers_redeemed: str
    customer_firstname: str
    customer_lastname: str
    customer_email: str
    customer_phone: str
    course_name: str
    workshop_date: datetime | None
    workshop_id: int | None
    workshop_cost: Decimal
    venue_name: str
    places_booked: int
    franchisee_user_id: int | None
    franchisee_name: str


def _quantize(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def load_gd_booking_franchisee_rows(user, start_day, end_day, region_id=None, tutor_id=None):
    """
    Legacy line items via gd_bookings_workshops → gd_booking → gd_workshop.

    Franchisee from bw.workshop_user_id / workshop owner; venue from gd_venue.
    """
    scope_sql, scope_params = _gd_booking_scope_clause(user, region_id, tutor_id)
    sql = f"""
        SELECT
            b.id,
            b.created_at,
            b.payment_gateway_id,
            b.gateway_transaction_code,
            COALESCE(bw.amount_paid, b.amount_paid) AS amount_paid,
            COALESCE(bw.amount_paid_by_voucher, b.amount_paid_by_voucher) AS amount_paid_by_voucher,
            COALESCE(
                bw.amount_paid_by_promotional_voucher,
                b.amount_paid_by_promotional_voucher
            ) AS amount_paid_by_promotional_voucher,
            b.vouchers_redeemed,
            COALESCE(pg.payment_gateway, pg.internal_name, '') AS payment_gateway_name,
            COALESCE(pg.manual_payment_option, 0) AS manual_payment_option,
            COALESCE(pg.transaction_percentage, 0) AS transaction_percentage,
            c.firstname,
            c.lastname,
            c.email,
            c.contact_number,
            COALESCE(cr.course_name, '') AS course_name,
            w.date AS workshop_date,
            bw.workshop_id,
            w.cost AS workshop_cost,
            COALESCE(v.venue_name, '') AS venue_name,
            COALESCE(bw.workshop_user_id, w.user_id, w.createdby_id) AS franchisee_user_id,
            fu.firstname AS franchisee_firstname,
            fu.lastname AS franchisee_lastname
        FROM gd_bookings_workshops bw
        INNER JOIN gd_booking b ON b.id = bw.booking_id
        LEFT JOIN gd_workshop w ON w.id = bw.workshop_id
        LEFT JOIN gd_venue v ON v.id = w.venue_id
        LEFT JOIN gd_course cr ON cr.id = COALESCE(w.course_id, bw.course_id)
        LEFT JOIN gd_payment_gateway pg ON pg.id = b.payment_gateway_id
        LEFT JOIN gd_customer c ON c.id = b.customer_id
        LEFT JOIN gd_user fu ON fu.id = COALESCE(bw.workshop_user_id, w.user_id, w.createdby_id)
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
        ORDER BY franchisee_user_id, b.created_at DESC, b.id DESC, bw.id DESC
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
                created_at,
                payment_gateway_id,
                gateway_transaction_code,
                amount_paid,
                amount_paid_by_voucher,
                amount_paid_by_promotional_voucher,
                vouchers_redeemed,
                payment_gateway_name,
                manual_payment_option,
                transaction_percentage,
                firstname,
                lastname,
                email,
                contact_number,
                course_name,
                workshop_date,
                workshop_id,
                workshop_cost,
                venue_name,
                franchisee_user_id,
                franchisee_firstname,
                franchisee_lastname,
            ) = raw
            franchisee_name = (
                f'{(franchisee_firstname or "").strip()} {(franchisee_lastname or "").strip()}'
            ).strip()
            rows.append(
                FranchiseeSourceRow(
                    booking_id=int(booking_id),
                    payment_date=created_at,
                    payment_gateway_id=int(payment_gateway_id) if payment_gateway_id else None,
                    payment_gateway=(payment_gateway_name or '').strip() or 'Unknown',
                    manual_payment_option=int(manual_payment_option or 0),
                    transaction_percentage=_quantize(transaction_percentage),
                    gateway_transaction_code=(gateway_transaction_code or '').strip(),
                    amount_paid=_quantize(amount_paid),
                    amount_paid_by_voucher=_quantize(amount_paid_by_voucher),
                    amount_paid_by_promotional_voucher=_quantize(amount_paid_by_promotional_voucher),
                    vouchers_redeemed=(vouchers_redeemed or '').strip(),
                    customer_firstname=(firstname or '').strip(),
                    customer_lastname=(lastname or '').strip(),
                    customer_email=(email or '').strip(),
                    customer_phone=(contact_number or '').strip(),
                    course_name=(course_name or '').strip(),
                    workshop_date=workshop_date,
                    workshop_id=int(workshop_id) if workshop_id else None,
                    workshop_cost=_quantize(workshop_cost),
                    venue_name=(venue_name or '').strip(),
                    places_booked=1,
                    franchisee_user_id=int(franchisee_user_id) if franchisee_user_id else None,
                    franchisee_name=franchisee_name,
                ),
            )
    return rows


def load_new_site_franchisee_rows(user, start_dt, end_dt):
    """Rows synced to gd_report tables for new-site bookings."""
    pg_qs = ReportBookingByPaymentGateway.objects.filter(
        booking_date__gte=start_dt,
        booking_date__lt=end_dt,
        booking_id__gte=LEGACY_REPORT_BOOKING_ID_OFFSET,
    ).order_by('user_id', '-booking_date', '-booking_id')
    pg_qs = filter_payment_gateway_queryset(pg_qs, user)
    pg_rows = list(pg_qs)

    booking_ids = [row.booking_id for row in pg_rows]
    summary_by_booking = {
        row.booking_id: row
        for row in ReportBookingSummary.objects.filter(booking_id__in=booking_ids)
    }

    gateway_meta = load_payment_gateway_meta()
    gateway_names = {
        gateway_id: meta['name'] for gateway_id, meta in gateway_meta.items()
    }

    rows = []
    for pg_row in pg_rows:
        summary = summary_by_booking.get(pg_row.booking_id)
        gateway_id = gateway_id_from_name(pg_row.payment_gateway, gateway_names)
        meta = gateway_meta.get(gateway_id or 0, {})
        franchisee_name = ''
        if summary:
            franchisee_name = (summary.franchisee_name or '').strip()
        venue_name = (summary.venue_name or '').strip() if summary else ''

        rows.append(
            FranchiseeSourceRow(
                booking_id=pg_row.booking_id,
                payment_date=pg_row.booking_date,
                payment_gateway_id=gateway_id,
                payment_gateway=(pg_row.payment_gateway or '').strip() or 'Unknown',
                manual_payment_option=meta.get('manual_payment_option', 0),
                transaction_percentage=meta.get('transaction_percentage', Decimal('0.00')),
                gateway_transaction_code=(pg_row.gateway_transaction_code or '').strip(),
                amount_paid=_quantize(pg_row.amount_paid),
                amount_paid_by_voucher=_quantize(pg_row.amount_paid_by_voucher),
                amount_paid_by_promotional_voucher=_quantize(
                    pg_row.amount_paid_by_promotional_voucher,
                ),
                vouchers_redeemed=(pg_row.vouchers_redeemed or '').strip(),
                customer_firstname=(pg_row.customer_firstname or '').strip(),
                customer_lastname=(pg_row.customer_lastname or '').strip(),
                customer_email=(pg_row.customer_email or '').strip(),
                customer_phone='',
                course_name=(pg_row.course_name or '').strip(),
                workshop_date=pg_row.workshop_date,
                workshop_id=pg_row.workshop_id or None,
                workshop_cost=_quantize(pg_row.workshop_cost),
                venue_name=venue_name,
                places_booked=pg_row.places_booked or 1,
                franchisee_user_id=pg_row.user_id or None,
                franchisee_name=franchisee_name,
            ),
        )
    return rows


def franchisee_report_source_rows(user, start_date, end_date, region_id=None, tutor_id=None):
    """Merged legacy and new-site franchisee report rows."""
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

    legacy_rows = load_gd_booking_franchisee_rows(
        user,
        start_day,
        end_day,
        region_id=region_id,
        tutor_id=tutor_id,
    )
    new_rows = load_new_site_franchisee_rows(user, start_dt, end_dt)

    merged = legacy_rows + new_rows
    merged.sort(
        key=lambda row: (
            row.franchisee_user_id or 0,
            -(row.payment_date.timestamp() if row.payment_date else 0),
            -row.booking_id,
        ),
    )
    return merged
