"""Unified admin booking list: new-site `bookings` + legacy `gd_bookings_workshops`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import connection
from django.urls import reverse

from bookings.legacy_payment_gateway_report import _gd_booking_scope_clause
from bookings.legacy_report_constants import LEGACY_REPORT_BOOKING_ID_OFFSET
from bookings.legacy_report_queries import _scoped_workshop_ids
from courses.region_scope import user_has_full_region_access


@dataclass
class AdminBookingListRow:
    source: str  # 'new' | 'legacy'
    row_id: int
    booking_reference: str
    student_first_name: str
    student_last_name: str
    student_email: str
    course_name: str
    workshop_date: datetime | None
    status: str
    payment_status: str
    voucher_code: str
    voucher_discount: Decimal | None
    price_paid: Decimal
    loan_camera: bool
    created_at: datetime | None

    @property
    def change_url(self):
        if self.source != 'new':
            return ''
        return reverse('admin:bookings_booking_change', args=[self.row_id])


def _text(value):
    return (str(value).strip() if value is not None else '')


def _quantize(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def _parse_int(raw):
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _new_booking_scope_clause(user):
    if user_has_full_region_access(user):
        return '', []
    workshop_ids = list(_scoped_workshop_ids(user, active_only=False))
    if not workshop_ids:
        return ' AND 1=0', []
    placeholders = ','.join(['%s'] * len(workshop_ids))
    return f' AND b.workshop_id IN ({placeholders})', list(workshop_ids)


def _legacy_paid_clause():
    return """
      AND (
            bw.payment_complete = 1
            OR b.payment_confirmed = 1
            OR IFNULL(bw.amount_paid, 0) > 0
            OR IFNULL(b.amount_paid, 0) > 0
            OR IFNULL(bw.amount_paid_by_voucher, 0) > 0
            OR IFNULL(b.amount_paid_by_voucher, 0) > 0
            OR IFNULL(bw.refund_amount, 0) > 0
          )
    """


def _legacy_status_expr():
    return """
      CASE
        WHEN IFNULL(bw.refund_amount, 0) > 0 THEN 'cancelled'
        WHEN bw.payment_complete = 1 OR b.payment_confirmed = 1 THEN 'confirmed'
        ELSE 'pending'
      END
    """


def _search_clause_new(search):
    if not search:
        return '', []
    like = f'%{search}%'
    return (
        """
          AND (
                b.booking_reference LIKE %s
                OR b.student_first_name LIKE %s
                OR b.student_last_name LIKE %s
                OR b.student_email LIKE %s
                OR b.voucher_code LIKE %s
                OR c.course_name LIKE %s
              )
        """,
        [like, like, like, like, like, like],
    )


def _search_clause_legacy(search):
    if not search:
        return '', []
    like = f'%{search}%'
    return (
        """
          AND (
                bw.unique_code LIKE %s
                OR cust.firstname LIKE %s
                OR cust.lastname LIKE %s
                OR cust.email LIKE %s
                OR b.vouchers_redeemed LIKE %s
                OR cr.course_name LIKE %s
                OR CAST(b.id AS CHAR) LIKE %s
              )
        """,
        [like, like, like, like, like, like, like],
    )


def _status_clause_new(status):
    if not status:
        return '', []
    return ' AND b.status = %s', [status]


def _status_clause_legacy(status):
    if not status:
        return '', []
    if status == 'cancelled':
        return ' AND IFNULL(bw.refund_amount, 0) > 0', []
    if status == 'confirmed':
        return (
            ' AND IFNULL(bw.refund_amount, 0) = 0'
            ' AND (bw.payment_complete = 1 OR b.payment_confirmed = 1)',
            [],
        )
    if status == 'pending':
        return (
            ' AND IFNULL(bw.refund_amount, 0) = 0'
            ' AND IFNULL(bw.payment_complete, 0) = 0'
            ' AND IFNULL(b.payment_confirmed, 0) = 0',
            [],
        )
    if status == 'completed':
        # Legacy had no completed equivalent; exclude.
        return ' AND 1=0', []
    return '', []


def _workshop_clause_new(workshop_id):
    if workshop_id is None:
        return '', []
    return ' AND b.workshop_id = %s', [workshop_id]


def _workshop_clause_legacy(workshop_id):
    if workshop_id is None:
        return '', []
    return ' AND bw.workshop_id = %s', [workshop_id]


def _course_clause_new(course_id):
    if course_id is None:
        return '', []
    return ' AND w.course_id = %s', [course_id]


def _course_clause_legacy(course_id):
    if course_id is None:
        return '', []
    return ' AND COALESCE(w.course_id, bw.course_id) = %s', [course_id]


def _venue_clause_new(venue_id):
    if venue_id is None:
        return '', []
    return ' AND w.venue_id = %s', [venue_id]


def _venue_clause_legacy(venue_id):
    if venue_id is None:
        return '', []
    return ' AND w.venue_id = %s', [venue_id]


def filters_from_request(request):
    """Parse common BookingAdmin changelist GET filters for the unified query."""
    get = request.GET
    return {
        'search': (get.get('q') or '').strip(),
        'workshop_id': _parse_int(get.get('workshop__id__exact') or get.get('workshop__id')),
        'status': (get.get('status__exact') or get.get('status') or '').strip() or None,
        'course_id': _parse_int(
            get.get('workshop__course__id__exact')
            or get.get('workshop__course__id')
        ),
        'venue_id': _parse_int(
            get.get('workshop__venue__id__exact')
            or get.get('workshop__venue__id')
        ),
        'year': _parse_int(get.get('created_at__year')),
        'month': _parse_int(get.get('created_at__month')),
        'day': _parse_int(get.get('created_at__day')),
        'created_gte': (get.get('created_at__gte') or '').strip() or None,
        'created_lt': (get.get('created_at__lt') or '').strip() or None,
    }


def _date_clause(alias_created, *, year=None, month=None, day=None, created_gte=None, created_lt=None):
    clauses = []
    params = []
    if created_gte:
        clauses.append(f'{alias_created} >= %s')
        params.append(created_gte)
    if created_lt:
        clauses.append(f'{alias_created} < %s')
        params.append(created_lt)
    if year:
        clauses.append(f'YEAR({alias_created}) = %s')
        params.append(year)
    if month:
        clauses.append(f'MONTH({alias_created}) = %s')
        params.append(month)
    if day:
        clauses.append(f'DAY({alias_created}) = %s')
        params.append(day)
    if not clauses:
        return '', []
    return ' AND ' + ' AND '.join(clauses), params


def _new_select_sql(user, filters):
    scope_sql, scope_params = _new_booking_scope_clause(user)
    search_sql, search_params = _search_clause_new(filters['search'])
    status_sql, status_params = _status_clause_new(filters['status'])
    workshop_sql, workshop_params = _workshop_clause_new(filters['workshop_id'])
    course_sql, course_params = _course_clause_new(filters['course_id'])
    venue_sql, venue_params = _venue_clause_new(filters['venue_id'])
    date_sql, date_params = _date_clause(
        'b.created_at',
        year=filters['year'],
        month=filters['month'],
        day=filters['day'],
        created_gte=filters.get('created_gte'),
        created_lt=filters.get('created_lt'),
    )
    sql = f"""
        SELECT
            'new' AS source,
            b.id AS row_id,
            b.booking_reference,
            b.student_first_name,
            b.student_last_name,
            b.student_email,
            COALESCE(c.course_name, '') AS course_name,
            w.date AS workshop_date,
            b.status,
            CASE
                WHEN p.id IS NULL THEN ''
                WHEN p.intent_type = 'manual_tutor' THEN 'Paid to tutor'
                ELSE COALESCE(p.status, '')
            END AS payment_status,
            COALESCE(b.voucher_code, '') AS voucher_code,
            b.voucher_discount,
            b.price_paid,
            IFNULL(b.loan_camera, 0) AS loan_camera,
            b.created_at
        FROM bookings b
        LEFT JOIN gd_workshop w ON w.id = b.workshop_id
        LEFT JOIN gd_course c ON c.id = w.course_id
        LEFT JOIN payments p ON p.id = b.payment_id
        WHERE 1=1
        {scope_sql}
        {workshop_sql}
        {course_sql}
        {venue_sql}
        {status_sql}
        {search_sql}
        {date_sql}
    """
    params = [
        *scope_params,
        *workshop_params,
        *course_params,
        *venue_params,
        *status_params,
        *search_params,
        *date_params,
    ]
    return sql, params


def _legacy_select_sql(user, filters):
    scope_sql, scope_params = _gd_booking_scope_clause(user)
    search_sql, search_params = _search_clause_legacy(filters['search'])
    status_sql, status_params = _status_clause_legacy(filters['status'])
    workshop_sql, workshop_params = _workshop_clause_legacy(filters['workshop_id'])
    course_sql, course_params = _course_clause_legacy(filters['course_id'])
    venue_sql, venue_params = _venue_clause_legacy(filters['venue_id'])
    date_sql, date_params = _date_clause(
        'COALESCE(bw.created_at, b.created_at)',
        year=filters['year'],
        month=filters['month'],
        day=filters['day'],
        created_gte=filters.get('created_gte'),
        created_lt=filters.get('created_lt'),
    )
    status_expr = _legacy_status_expr()
    paid_sql = _legacy_paid_clause()
    sql = f"""
        SELECT
            'legacy' AS source,
            bw.id AS row_id,
            COALESCE(NULLIF(bw.unique_code, ''), CONCAT('LEGACY-', b.id)) AS booking_reference,
            COALESCE(cust.firstname, '') AS student_first_name,
            COALESCE(cust.lastname, '') AS student_last_name,
            COALESCE(cust.email, '') AS student_email,
            COALESCE(cr.course_name, '') AS course_name,
            w.date AS workshop_date,
            {status_expr} AS status,
            COALESCE(pg.payment_gateway, pg.internal_name, '') AS payment_status,
            COALESCE(b.vouchers_redeemed, '') AS voucher_code,
            COALESCE(bw.amount_paid_by_voucher, b.amount_paid_by_voucher, 0) AS voucher_discount,
            COALESCE(bw.amount_paid, b.amount_paid, 0) AS price_paid,
            0 AS loan_camera,
            COALESCE(bw.created_at, b.created_at) AS created_at
        FROM gd_bookings_workshops bw
        INNER JOIN gd_booking b ON b.id = bw.booking_id
        LEFT JOIN gd_workshop w ON w.id = bw.workshop_id
        LEFT JOIN gd_course cr ON cr.id = COALESCE(w.course_id, bw.course_id)
        LEFT JOIN gd_customer cust ON cust.id = b.customer_id
        LEFT JOIN gd_payment_gateway pg ON pg.id = b.payment_gateway_id
        WHERE b.id < %s
        {paid_sql}
        {scope_sql}
        {workshop_sql}
        {course_sql}
        {venue_sql}
        {status_sql}
        {search_sql}
        {date_sql}
    """
    params = [
        LEGACY_REPORT_BOOKING_ID_OFFSET,
        *scope_params,
        *workshop_params,
        *course_params,
        *venue_params,
        *status_params,
        *search_params,
        *date_params,
    ]
    return sql, params


_STATUS_LABELS = {
    'pending': 'Pending Payment',
    'confirmed': 'Confirmed',
    'cancelled': 'Cancelled',
    'completed': 'Completed',
}

_PAYMENT_LABELS = {
    'succeeded': 'Succeeded',
    'pending': 'Pending',
    'failed': 'Failed',
    'cancelled': 'Cancelled',
    'refunded': 'Refunded',
}


def _row_from_sql(raw):
    (
        source,
        row_id,
        booking_reference,
        student_first_name,
        student_last_name,
        student_email,
        course_name,
        workshop_date,
        status,
        payment_status,
        voucher_code,
        voucher_discount,
        price_paid,
        loan_camera,
        created_at,
    ) = raw
    status_key = _text(status)
    payment_key = _text(payment_status)
    return AdminBookingListRow(
        source=_text(source),
        row_id=int(row_id),
        booking_reference=_text(booking_reference) or '—',
        student_first_name=_text(student_first_name),
        student_last_name=_text(student_last_name),
        student_email=_text(student_email),
        course_name=_text(course_name),
        workshop_date=workshop_date,
        status=_STATUS_LABELS.get(status_key, status_key or '—'),
        payment_status=_PAYMENT_LABELS.get(payment_key, payment_key or '—'),
        voucher_code=_text(voucher_code),
        voucher_discount=_quantize(voucher_discount) if voucher_discount else None,
        price_paid=_quantize(price_paid),
        loan_camera=bool(loan_camera),
        created_at=created_at,
    )


def count_unified_admin_bookings(user, filters):
    new_sql, new_params = _new_select_sql(user, filters)
    legacy_sql, legacy_params = _legacy_select_sql(user, filters)
    sql = f"""
        SELECT
            (SELECT COUNT(*) FROM ({new_sql}) AS new_rows)
          + (SELECT COUNT(*) FROM ({legacy_sql}) AS legacy_rows)
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [*new_params, *legacy_params])
        return int(cursor.fetchone()[0] or 0)


def load_unified_admin_bookings(user, filters, *, limit=100, offset=0):
    new_sql, new_params = _new_select_sql(user, filters)
    legacy_sql, legacy_params = _legacy_select_sql(user, filters)
    sql = f"""
        SELECT * FROM (
            {new_sql}
            UNION ALL
            {legacy_sql}
        ) AS booking_rows
        ORDER BY created_at DESC, source ASC, row_id DESC
        LIMIT %s OFFSET %s
    """
    params = [*new_params, *legacy_params, int(limit), int(offset)]
    rows = []
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        for raw in cursor.fetchall():
            rows.append(_row_from_sql(raw))
    return rows
