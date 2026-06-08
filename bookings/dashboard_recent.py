"""Recent bookings table for the admin dashboard."""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.utils.translation import gettext as _

from bookings.models import Booking
from bookings.scope import filter_bookings_for_user
from courses.region_scope import get_user_region_ids, user_has_full_region_access

RECENT_BOOKINGS_PAGE_SIZE = 10
BOOKINGS_PAGE_PARAM = 'bookings_page'


def get_recent_bookings_queryset(user):
    return filter_bookings_for_user(
        Booking.objects.select_related(
            'workshop__course',
            'workshop__venue',
            'payment',
        ),
        user,
    ).order_by('-created_at', '-id')


def _parse_page_number(raw, default=1):
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, number)


def get_recent_bookings_page(request):
    queryset = get_recent_bookings_queryset(request.user)
    paginator = Paginator(
        queryset,
        RECENT_BOOKINGS_PAGE_SIZE,
        allow_empty_first_page=True,
    )

    if paginator.count == 0:
        return paginator.page(1), paginator

    page_number = _parse_page_number(request.GET.get(BOOKINGS_PAGE_PARAM))
    page_number = min(page_number, paginator.num_pages)
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(1)
    return page, paginator


def get_recent_bookings_dashboard_context(request):
    user = request.user
    if not user.is_authenticated:
        return {'bookings_show': False}

    if not user_has_full_region_access(user) and not get_user_region_ids(user):
        return {'bookings_show': False}

    page, paginator = get_recent_bookings_page(request)
    query = request.GET.copy()
    base_path = request.path

    def build_page_url(num):
        num = int(num)
        q = query.copy()
        if num <= 1:
            q.pop(BOOKINGS_PAGE_PARAM, None)
        else:
            q[BOOKINGS_PAGE_PARAM] = str(num)
        qs = q.urlencode()
        return f'{base_path}?{qs}' if qs else base_path

    if user_has_full_region_access(user):
        panel_title = _('Recent bookings')
    else:
        panel_title = _('Your recent bookings')

    return {
        'bookings_show': True,
        'bookings_panel_title': panel_title,
        'bookings_can_change': user_has_full_region_access(user),
        'bookings_page': page,
        'bookings_paginator': paginator,
        'bookings_list': page.object_list,
        'bookings_has_other_pages': paginator.num_pages > 1,
        'bookings_prev_url': build_page_url(page.previous_page_number()) if page.has_previous() else None,
        'bookings_next_url': build_page_url(page.next_page_number()) if page.has_next() else None,
    }
