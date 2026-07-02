"""Shared filters for upcoming and open-dated workshops."""
from django.db.models import Q
from django.utils import timezone

from .models import Workshop

OPEN_DATED_LABEL = 'Date by arrangement'


def workshop_is_open_dated(workshop):
    return bool(getattr(workshop, 'open_dated', 0))


def bookable_workshop_visibility_q(*, now=None):
    """
    Workshops visible on the public site: active and either open-dated or scheduled ahead.
    """
    now = now or timezone.now()
    return Q(active=1) & (Q(open_dated=1) | Q(date__gte=now))


def bookable_workshops_queryset(*, now=None, course_active=True):
    qs = Workshop.objects.all()
    if course_active:
        qs = qs.filter(course__active=True)
    return qs.filter(bookable_workshop_visibility_q(now=now))


def apply_workshop_list_date_range(queryset, dt_from=None, dt_to=None):
    """
    Apply course-list date filters. Open-dated workshops always match any date range.
    """
    if dt_from:
        queryset = queryset.filter(Q(open_dated=1) | Q(date__gte=dt_from))
    if dt_to:
        queryset = queryset.filter(Q(open_dated=1) | Q(date__lte=dt_to))
    return queryset


def bookable_workshop_ordering():
    """Open-dated first, then earliest scheduled date."""
    return ('-open_dated', 'date')
