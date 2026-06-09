"""Render workshop customer list using the same table markup as Bookings admin changelist."""
from django.template.loader import render_to_string
from django.urls import reverse

from bookings.models import Booking
from bookings.scope import filter_bookings_for_user


def render_workshop_bookings_table(workshop, request):
    qs = (
        Booking.objects.filter(workshop_id=workshop.pk)
        .select_related('payment', 'workshop', 'workshop__course', 'workshop__venue')
        .order_by('-created_at')
    )
    if request:
        qs = filter_bookings_for_user(qs, request.user)

    bookings = list(qs)
    can_view = bool(request and request.user.has_perm('bookings.view_booking'))
    changelist_url = ''
    if can_view:
        changelist_url = (
            reverse('admin:bookings_booking_changelist')
            + f'?workshop__id__exact={workshop.pk}'
        )

    return render_to_string(
        'admin/courses/workshop/workshop_bookings_table.html',
        {
            'bookings': bookings,
            'booking_count': len(bookings),
            'can_view_booking': can_view,
            'bookings_changelist_url': changelist_url,
        },
        request=request,
    )
