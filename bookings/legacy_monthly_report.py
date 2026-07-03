"""Monthly booking stats from gd_bookings_workshops (legacy) and synced tables (new site)."""
from decimal import Decimal

from django.db import connection
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce

from bookings.legacy_payment_gateway_report import _gd_booking_scope_clause
from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.legacy_report_queries import (
    _legacy_report_date_filter,
    filter_payment_gateway_queryset,
)
from bookings.models import ReportBookingByPaymentGateway


def _quantize(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def legacy_gd_booking_month_stats(user, start_day, end_day, region_id=None, tutor_id=None):
    """Aggregate bookings and income from gd_bookings_workshops for legacy gd_booking rows."""
    scope_sql, scope_params = _gd_booking_scope_clause(user, region_id, tutor_id)
    sql = f"""
        SELECT
            COUNT(bw.id) AS bookings,
            COALESCE(SUM(
                COALESCE(bw.amount_paid, b.amount_paid, 0)
                + COALESCE(bw.amount_paid_by_voucher, b.amount_paid_by_voucher, 0)
                + COALESCE(
                    bw.amount_paid_by_promotional_voucher,
                    b.amount_paid_by_promotional_voucher,
                    0
                  )
            ), 0) AS income
        FROM gd_bookings_workshops bw
        INNER JOIN gd_booking b ON b.id = bw.booking_id
        LEFT JOIN gd_workshop w ON w.id = bw.workshop_id
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
    """
    params = [
        LEGACY_REPORT_BOOKING_ID_OFFSET,
        start_day,
        end_day,
        *scope_params,
    ]
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        bookings, income = cursor.fetchone()

    return {
        'bookings': int(bookings or 0),
        'income': _quantize(income),
    }


def new_site_month_stats(user, start_day, end_day, region_id=None, tutor_id=None):
    """Aggregate bookings and income from synced payment-gateway report rows (new site)."""
    qs = ReportBookingByPaymentGateway.objects.filter(
        **_legacy_report_date_filter('booking_date', start_day, end_day),
        booking_id__gte=LEGACY_REPORT_BOOKING_ID_OFFSET,
    )
    qs = filter_payment_gateway_queryset(qs, user, region_id, tutor_id)
    stats = qs.aggregate(
        bookings=Count('id'),
        income=Coalesce(
            Sum(
                F('amount_paid')
                + F('amount_paid_by_voucher')
                + F('amount_paid_by_promotional_voucher'),
            ),
            Decimal('0.00'),
        ),
    )
    return {
        'bookings': int(stats['bookings'] or 0),
        'income': _quantize(stats['income']),
    }


def monthly_booking_stats(user, start_day, end_day, region_id=None, tutor_id=None):
    """
    Monthly booking count and income from gd_bookings_workshops (legacy) plus
    synced gd_report__bookings_by_payment_gateway rows (new site).
    """
    legacy = legacy_gd_booking_month_stats(
        user,
        start_day,
        end_day,
        region_id=region_id,
        tutor_id=tutor_id,
    )
    new_site = new_site_month_stats(
        user,
        start_day,
        end_day,
        region_id=region_id,
        tutor_id=tutor_id,
    )
    return {
        'bookings': legacy['bookings'] + new_site['bookings'],
        'income': legacy['income'] + new_site['income'],
    }
