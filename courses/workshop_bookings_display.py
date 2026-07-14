"""Render workshop customer list using the same table markup as Bookings admin changelist."""
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.urls import reverse

from bookings.models import Booking
from bookings.scope import filter_bookings_for_user
from courses.region_scope import user_can_access_workshop, user_has_full_region_access
from courses.workshop_student_report import load_legacy_workshop_student_rows


def _legacy_booking_display(student):
    """Duck-typed booking row for the customers table template."""
    return SimpleNamespace(
        pk=None,
        booking_reference=student.booking_reference or '—',
        student_first_name=student.first_name,
        student_last_name=student.last_name,
        student_email=student.email,
        student_phone=student.phone,
        loan_camera=student.loan_camera,
        get_status_display=lambda s=student.status: s or '—',
        payment=None,
        voucher_code='',
        voucher_discount=None,
        price_paid=0,
        created_at=None,
        is_legacy=True,
    )


def render_workshop_bookings_table(workshop, request):
    qs = (
        Booking.objects.filter(workshop_id=workshop.pk)
        .select_related('payment', 'workshop', 'workshop__course', 'workshop__venue')
        .order_by('-created_at')
    )
    if request:
        qs = filter_bookings_for_user(qs, request.user)

    bookings = list(qs)
    for booking in bookings:
        booking.is_legacy = False

    if workshop and workshop.pk:
        for student in load_legacy_workshop_student_rows(workshop.pk):
            bookings.append(_legacy_booking_display(student))

    can_view = bool(request and request.user.has_perm('bookings.view_booking'))
    changelist_url = ''
    if can_view:
        changelist_url = (
            reverse('admin:bookings_booking_changelist')
            + f'?workshop__id__exact={workshop.pk}'
        )

    students_csv_url = ''
    if request and workshop and workshop.pk:
        if user_has_full_region_access(request.user) or user_can_access_workshop(
            request.user, workshop
        ):
            students_csv_url = reverse(
                'admin:courses_workshop_students_csv',
                args=[workshop.pk],
            )

    return render_to_string(
        'admin/courses/workshop/workshop_bookings_table.html',
        {
            'bookings': bookings,
            'booking_count': len(bookings),
            'can_view_booking': can_view,
            'bookings_changelist_url': changelist_url,
            'students_csv_url': students_csv_url,
        },
        request=request,
    )
