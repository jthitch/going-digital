"""Upcoming workshops for the admin dashboard."""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.utils import timezone
from django.utils.translation import gettext as _

from django.db.models import Q

from courses.models import Workshop
from courses.region_scope import filter_workshops_for_user, user_has_full_region_access
from courses.workshop_querysets import bookable_workshop_ordering

UPCOMING_WORKSHOPS_PAGE_SIZE = 10
UPCOMING_PAGE_PARAM = 'upcoming_page'


def get_upcoming_workshops_queryset(user):
    now = timezone.now()
    qs = filter_workshops_for_user(
        Workshop.objects.select_related('course', 'venue'),
        user,
    )
    return qs.filter(
        active=1,
    ).filter(
        Q(open_dated=1) | Q(date__isnull=False, date__gte=now),
    ).order_by(*bookable_workshop_ordering(), 'id')


def _parse_page_number(raw, default=1):
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, number)


def get_upcoming_workshops_page(request):
    queryset = get_upcoming_workshops_queryset(request.user)
    paginator = Paginator(
        queryset,
        UPCOMING_WORKSHOPS_PAGE_SIZE,
        allow_empty_first_page=True,
    )

    if paginator.count == 0:
        return paginator.page(1), paginator

    page_number = _parse_page_number(request.GET.get(UPCOMING_PAGE_PARAM))
    page_number = min(page_number, paginator.num_pages)
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(1)
    return page, paginator


def get_upcoming_workshops_dashboard_context(request):
    if not request.user.is_authenticated:
        return {'upcoming_show': False}

    page, paginator = get_upcoming_workshops_page(request)
    query = request.GET.copy()
    base_path = request.path

    def build_page_url(num):
        num = int(num)
        q = query.copy()
        if num <= 1:
            q.pop(UPCOMING_PAGE_PARAM, None)
        else:
            q[UPCOMING_PAGE_PARAM] = str(num)
        qs = q.urlencode()
        return f'{base_path}?{qs}' if qs else base_path

    if user_has_full_region_access(request.user):
        panel_title = _('Upcoming workshops')
    else:
        panel_title = _('Your upcoming workshops')

    return {
        'upcoming_show': True,
        'upcoming_panel_title': panel_title,
        'upcoming_page': page,
        'upcoming_paginator': paginator,
        'upcoming_workshops': page.object_list,
        'upcoming_has_other_pages': paginator.num_pages > 1,
        'upcoming_prev_url': build_page_url(page.previous_page_number()) if page.has_previous() else None,
        'upcoming_next_url': build_page_url(page.next_page_number()) if page.has_next() else None,
    }
