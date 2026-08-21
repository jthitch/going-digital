"""Workshop admin changelist: default scope, ordering, and list filters."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone

from courses.admin_changelist import (
    CHANGE_LIST_DATE_RANGE_PARAMS,
    apply_changelist_date_range,
    changelist_has_custom_date_range,
)

# Default changelist: undated/open-dated, future, and roughly the last year (not full history).
WORKSHOP_CHANGE_LIST_LOOKBACK_DAYS = 365

# Query-string keys used by the workshop changelist UI (not model field lookups).
WORKSHOP_CHANGE_LIST_EXTRA_PARAMS = (*CHANGE_LIST_DATE_RANGE_PARAMS, 'show_all')
WORKSHOP_CHANGE_LIST_FORM_FIELD_PARAMS = CHANGE_LIST_DATE_RANGE_PARAMS


def workshop_changelist_has_custom_date_range(request) -> bool:
    return changelist_has_custom_date_range(request)


def apply_workshop_custom_date_range(request, queryset):
    """
    Filter by optional date_from / date_to (calendar days on workshop start).

    Includes open-dated workshops plus any row whose start date falls in range.
    """
    return apply_changelist_date_range(
        request,
        queryset,
        field='date__date',
        or_q=Q(open_dated=1),
    )


def is_workshop_changelist_request(request) -> bool:
    """True on the workshop admin list (not change form, CSV, autocomplete, etc.)."""
    path = (getattr(request, 'path', '') or '').rstrip('/')
    if path.endswith('/admin/courses/workshop'):
        return True
    match = getattr(request, 'resolver_match', None)
    return bool(match and match.url_name == 'courses_workshop_changelist')


def workshop_changelist_show_full_history(request) -> bool:
    """True when the user is searching, filtering by date scope, or asked for all rows."""
    params = getattr(request, 'GET', None)
    if not params:
        return False
    if (params.get('q') or '').strip():
        return True
    if params.get('show_all') == '1':
        return True
    if params.get('active') in ('0', '1'):
        return True
    if params.get('course__id__exact'):
        return True
    if params.get('tutor_id'):
        return True
    if params.get('region_id'):
        return True
    return workshop_changelist_has_custom_date_range(request)


def narrow_workshop_changelist(queryset, *, now=None):
    now = now or timezone.now()
    cutoff = now - timedelta(days=WORKSHOP_CHANGE_LIST_LOOKBACK_DAYS)
    return queryset.filter(
        Q(open_dated=1)
        | Q(date__isnull=True)
        | Q(date__gte=cutoff)
    )


def order_workshop_changelist(queryset):
    """Undated / open-dated first, then newest scheduled dates, then id."""
    return queryset.annotate(
        _gd_undated_first=Case(
            When(open_dated=1, then=Value(0)),
            When(date__isnull=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by('_gd_undated_first', F('date').desc(nulls_last=True), '-id')
