"""Shared filters for upcoming and open-dated workshops."""
from django.db.models import Q
from django.utils import timezone

from .models import Workshop

OPEN_DATED_LABEL = 'Date by arrangement'


def workshop_is_open_dated(workshop):
    return bool(getattr(workshop, 'open_dated', 0))


def workshop_checkout_date_label(workshop):
    """Display date for checkout/Stripe; safe when workshop has no fixed date."""
    if workshop_is_open_dated(workshop):
        return OPEN_DATED_LABEL
    start = getattr(workshop, 'start_date', None) or getattr(workshop, 'date', None)
    if start:
        return start.strftime('%d %B %Y')
    return 'Date TBC'


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


def matching_workshop(instances, workshop_id=None):
    """
    Return the listed workshop whose pk matches ``workshop_id``, or None.

    Used to detect a valid deep-link before featuring / narrowing the list.
    """
    if workshop_id is None or workshop_id == '':
        return None
    try:
        workshop_id = int(workshop_id)
    except (TypeError, ValueError):
        return None
    for inst in instances or []:
        if inst.pk == workshop_id:
            return inst
    return None


def resolve_featured_workshop(instances, workshop_id=None):
    """
    Pick the workshop to feature on a course detail page.

    When ``workshop_id`` is present and matches a listed instance, use that
    (deep-link from venue/date cards). Otherwise use the first listed instance.
    """
    instances = list(instances or [])
    if not instances:
        return None
    matched = matching_workshop(instances, workshop_id)
    if matched is not None:
        return matched
    return instances[0]


def instances_for_workshop_param(instances, workshop_id=None):
    """
    When ``workshop_id`` matches a listed workshop, return only that workshop
    (deep-linked venue/date cards). Otherwise return the full list.
    """
    instances = list(instances or [])
    if not instances:
        return [], None
    matched = matching_workshop(instances, workshop_id)
    if matched is not None:
        return [matched], matched
    featured = resolve_featured_workshop(instances, workshop_id)
    return instances, featured
