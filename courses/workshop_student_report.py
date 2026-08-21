"""Workshop student attendance report (CSV download for franchisees/admins)."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.db import connection
from django.http import HttpResponse
from django.utils.text import slugify

from bookings.models import Booking
from bookings.scope import filter_bookings_for_user


ATTENDING_STATUSES = ('pending', 'confirmed', 'completed')


# Legacy gd_booking_status ids used on gd_bookings_workshops_attendees.
_LEGACY_STATUS_CANCELLED = 3
_LEGACY_STATUS_REFUNDED = 4

_PAID_BOOKING_SQL = """
    (
        bw.payment_complete = 1
        OR b.payment_confirmed = 1
        OR IFNULL(bw.amount_paid, 0) > 0
        OR IFNULL(b.amount_paid, 0) > 0
        OR IFNULL(bw.amount_paid_by_voucher, 0) > 0
        OR IFNULL(b.amount_paid_by_voucher, 0) > 0
    )
"""


@dataclass
class WorkshopStudentRow:
    """Normalised student line for new-site and legacy workshop bookings."""

    first_name: str = ''
    last_name: str = ''
    email: str = ''
    phone: str = ''
    address1: str = ''
    address2: str = ''
    town_city: str = ''
    postcode: str = ''
    special_requirements: str = ''
    loan_camera: bool = False
    camera_make: str = ''
    camera_model: str = ''
    booking_reference: str = ''
    status: str = ''
    created_at: Optional[datetime] = None


def _customer_field(customer, *attrs):
    if not customer:
        return ''
    for attr in attrs:
        value = getattr(customer, attr, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def _row_from_new_booking(booking):
    customer = booking.customer
    phone = (booking.student_phone or '').strip() or _customer_field(customer, 'contact_number')
    return WorkshopStudentRow(
        first_name=booking.student_first_name or '',
        last_name=booking.student_last_name or '',
        email=booking.student_email or '',
        phone=phone,
        address1=_customer_field(customer, 'address1', 'address'),
        address2=_customer_field(customer, 'address2'),
        town_city=_customer_field(customer, 'town_city'),
        postcode=_customer_field(customer, 'postcode'),
        special_requirements=(booking.special_requirements or '').strip(),
        loan_camera=bool(booking.loan_camera),
        camera_make=(booking.camera_make or '').strip(),
        camera_model=(booking.camera_model or '').strip(),
        booking_reference=booking.booking_reference or '',
        status=(
            booking.get_status_display()
            if hasattr(booking, 'get_status_display')
            else (booking.status or '')
        ),
        created_at=getattr(booking, 'created_at', None),
    )


def _text(value):
    return (str(value).strip() if value is not None else '')


def _legacy_status(payment_complete, refund_amount, status_label=None):
    label = _text(status_label)
    if label:
        return label
    refund = Decimal(str(refund_amount or 0))
    if refund > 0:
        return 'Refunded'
    if int(payment_complete or 0) == 1:
        return 'Confirmed'
    return 'Pending'


def _legacy_booking_reference(unique_code, booking_id, attendee_id=None):
    ref = _text(unique_code)
    if ref:
        return ref
    if booking_id:
        return f'LEGACY-{booking_id}'
    if attendee_id:
        return f'LEGACY-A{attendee_id}'
    return 'LEGACY'


def load_legacy_workshop_student_rows(workshop_id):
    """
    Students attending this workshop via legacy gd_bookings_workshops_attendees.

    Attendee name/camera/loan fields come from the attendees table; email/phone
    and address come from gd_customer on the linked gd_booking. Falls back to
    gd_bookings_workshops + gd_customer when a paid line has no attendee rows.
    """
    attendee_sql = f"""
        SELECT
            a.id AS attendee_id,
            COALESCE(a.booking_id, bw.booking_id) AS booking_id,
            bw.unique_code,
            bw.payment_complete,
            bw.refund_amount,
            a.comments,
            bw.message,
            bw.additional_information,
            a.firstname,
            a.lastname,
            c.email,
            c.contact_number,
            c.address1,
            c.address,
            c.address2,
            c.town_city,
            c.postcode,
            a.loan_camera_required,
            a.camera_make,
            a.camera_model,
            a.created_at,
            bs.status AS booking_status
        FROM gd_bookings_workshops_attendees a
        LEFT JOIN gd_booking_status bs ON bs.id = a.booking_status_id
        LEFT JOIN gd_bookings_workshops bw ON bw.id = a.bookings_workshops_id
        LEFT JOIN gd_booking b ON b.id = COALESCE(a.booking_id, bw.booking_id)
        LEFT JOIN gd_customer c ON c.id = b.customer_id
        WHERE a.workshop_id = %s
          AND IFNULL(a.active, 1) = 1
          AND IFNULL(a.booking_status_id, 1) NOT IN (
              {_LEGACY_STATUS_CANCELLED}, {_LEGACY_STATUS_REFUNDED}
          )
          AND IFNULL(bw.refund_amount, 0) = 0
          AND {_PAID_BOOKING_SQL}
        ORDER BY a.lastname, a.firstname, a.id
    """
    fallback_sql = f"""
        SELECT
            b.id AS booking_id,
            bw.unique_code,
            bw.payment_complete,
            bw.refund_amount,
            bw.message,
            bw.additional_information,
            c.firstname,
            c.lastname,
            c.email,
            c.contact_number,
            c.address1,
            c.address,
            c.address2,
            c.town_city,
            c.postcode,
            bw.created_at
        FROM gd_bookings_workshops bw
        INNER JOIN gd_booking b ON b.id = bw.booking_id
        LEFT JOIN gd_customer c ON c.id = b.customer_id
        WHERE bw.workshop_id = %s
          AND IFNULL(bw.refund_amount, 0) = 0
          AND {_PAID_BOOKING_SQL}
          AND NOT EXISTS (
              SELECT 1
              FROM gd_bookings_workshops_attendees a
              WHERE a.bookings_workshops_id = bw.id
                AND IFNULL(a.active, 1) = 1
          )
        ORDER BY c.lastname, c.firstname, b.id, bw.id
    """
    rows = []
    with connection.cursor() as cursor:
        cursor.execute(attendee_sql, [workshop_id])
        for raw in cursor.fetchall():
            (
                attendee_id,
                booking_id,
                unique_code,
                payment_complete,
                refund_amount,
                comments,
                message,
                additional_information,
                firstname,
                lastname,
                email,
                contact_number,
                address1,
                address,
                address2,
                town_city,
                postcode,
                loan_camera_required,
                camera_make,
                camera_model,
                created_at,
                booking_status,
            ) = raw
            special = (
                _text(comments)
                or _text(message)
                or _text(additional_information)
            )
            rows.append(
                WorkshopStudentRow(
                    first_name=_text(firstname),
                    last_name=_text(lastname),
                    email=_text(email),
                    phone=_text(contact_number),
                    address1=_text(address1) or _text(address),
                    address2=_text(address2),
                    town_city=_text(town_city),
                    postcode=_text(postcode),
                    special_requirements=special,
                    loan_camera=bool(int(loan_camera_required or 0)),
                    camera_make=_text(camera_make),
                    camera_model=_text(camera_model),
                    booking_reference=_legacy_booking_reference(
                        unique_code, booking_id, attendee_id=attendee_id
                    ),
                    status=_legacy_status(
                        payment_complete,
                        refund_amount,
                        status_label=booking_status,
                    ),
                    created_at=created_at,
                )
            )

        cursor.execute(fallback_sql, [workshop_id])
        for raw in cursor.fetchall():
            (
                booking_id,
                unique_code,
                payment_complete,
                refund_amount,
                message,
                additional_information,
                firstname,
                lastname,
                email,
                contact_number,
                address1,
                address,
                address2,
                town_city,
                postcode,
                created_at,
            ) = raw
            special = _text(message) or _text(additional_information)
            rows.append(
                WorkshopStudentRow(
                    first_name=_text(firstname),
                    last_name=_text(lastname),
                    email=_text(email),
                    phone=_text(contact_number),
                    address1=_text(address1) or _text(address),
                    address2=_text(address2),
                    town_city=_text(town_city),
                    postcode=_text(postcode),
                    special_requirements=special,
                    loan_camera=False,
                    booking_reference=_legacy_booking_reference(
                        unique_code, booking_id
                    ),
                    status=_legacy_status(payment_complete, refund_amount),
                    created_at=created_at,
                )
            )
    return rows


def load_new_workshop_student_rows(workshop, user=None):
    qs = (
        Booking.objects.filter(
            workshop_id=workshop.pk,
            status__in=ATTENDING_STATUSES,
        )
        .select_related('customer')
        .order_by('student_last_name', 'student_first_name', 'id')
    )
    if user is not None:
        qs = filter_bookings_for_user(qs, user)
    return [_row_from_new_booking(booking) for booking in qs]


def load_workshop_student_rows(workshop, user=None):
    """Merge new-site and legacy students for this workshop."""
    rows = load_new_workshop_student_rows(workshop, user=user)
    if workshop and workshop.pk:
        rows.extend(load_legacy_workshop_student_rows(workshop.pk))
    rows.sort(key=lambda row: (row.last_name.lower(), row.first_name.lower(), row.email.lower()))
    return rows


def _format_workshop_date(workshop):
    if not workshop:
        return ''
    if getattr(workshop, 'is_open_dated', False):
        return 'Open dated'
    start = getattr(workshop, 'start_date', None) or getattr(workshop, 'date', None)
    if not start:
        return ''
    return start.strftime('%d %B %Y')


def _format_workshop_time(workshop):
    if not workshop or getattr(workshop, 'is_open_dated', False):
        return ''
    start = getattr(workshop, 'start_date', None) or getattr(workshop, 'date', None)
    if not start:
        return ''
    return start.strftime('%H:%M')


def _course_name(workshop):
    if not workshop or not workshop.course_id:
        return ''
    course = workshop.course
    return (getattr(course, 'course_name', None) or getattr(course, 'title', None) or '').strip()


def _venue_name(workshop):
    if not workshop or not workshop.venue_id:
        return ''
    venue = workshop.venue
    return (getattr(venue, 'venue_name', None) or getattr(venue, 'name', None) or '').strip()


def _student_csv_row(workshop, student: WorkshopStudentRow):
    return [
        _course_name(workshop),
        _format_workshop_date(workshop),
        _format_workshop_time(workshop),
        _venue_name(workshop),
        student.first_name,
        student.last_name,
        student.email,
        student.phone,
        student.address1,
        student.address2,
        student.town_city,
        student.postcode,
        student.special_requirements,
        'Yes' if student.loan_camera else '',
        student.camera_make,
        student.camera_model,
        student.booking_reference,
        student.status,
    ]


CSV_HEADERS = [
    'Course',
    'Workshop date',
    'Workshop time',
    'Venue',
    'First name',
    'Last name',
    'Email',
    'Phone',
    'Address line 1',
    'Address line 2',
    'Town / city',
    'Postcode',
    'Special requirements',
    'Loan camera',
    'Camera make',
    'Camera model',
    'Booking reference',
    'Status',
]


def iter_workshop_student_report_rows(workshop, students):
    yield CSV_HEADERS
    for student in students:
        if not isinstance(student, WorkshopStudentRow):
            student = _row_from_new_booking(student)
        yield _student_csv_row(workshop, student)


def workshop_student_report_filename(workshop):
    course = slugify(_course_name(workshop)) or 'workshop'
    date_part = 'open-dated'
    start = getattr(workshop, 'start_date', None) or getattr(workshop, 'date', None)
    if start and not getattr(workshop, 'is_open_dated', False):
        date_part = start.strftime('%Y-%m-%d')
    workshop_id = workshop.pk or 'new'
    raw = f'students-{course}-{date_part}-w{workshop_id}.csv'
    return re.sub(r'[^a-zA-Z0-9._-]+', '-', raw)


def build_workshop_student_csv_response(workshop, user=None):
    students = load_workshop_student_rows(workshop, user=user)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="{workshop_student_report_filename(workshop)}"'
    )
    response.write('\ufeff')
    writer = csv.writer(response)
    for row in iter_workshop_student_report_rows(workshop, students):
        writer.writerow(row)
    return response
