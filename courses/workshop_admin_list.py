"""Workshop admin changelist: default scope, ordering, and list filters."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_date

# Default changelist: undated/open-dated, future, and roughly the last year (not full history).
WORKSHOP_CHANGE_LIST_LOOKBACK_DAYS = 365

# Query-string keys used by the workshop changelist UI (not model field lookups).
WORKSHOP_CHANGE_LIST_EXTRA_PARAMS = ('date_from', 'date_to', 'show_all')
WORKSHOP_CHANGE_LIST_FORM_FIELD_PARAMS = ('date_from', 'date_to')


def _parse_changelist_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return parse_date(text)


def workshop_changelist_has_custom_date_range(request) -> bool:
    get = getattr(request, 'GET', None)
    if not get:
        return False
    return bool(
        _parse_changelist_date(get.get('date_from'))
        or _parse_changelist_date(get.get('date_to'))
    )


def apply_workshop_custom_date_range(request, queryset):
    """
    Filter by optional date_from / date_to (calendar days on workshop start).

    Includes open-dated workshops plus any row whose start date falls in range.
    """
    get = getattr(request, 'GET', None)
    if not get:
        return queryset

    date_from = _parse_changelist_date(get.get('date_from'))
    date_to = _parse_changelist_date(get.get('date_to'))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    if not date_from and not date_to:
        return queryset

    range_query = Q()
    if date_from:
        range_query &= Q(date__date__gte=date_from)
    if date_to:
        range_query &= Q(date__date__lte=date_to)
    return queryset.filter(Q(open_dated=1) | range_query)


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
