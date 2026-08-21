"""Shared Going Digital admin changelist: search-first UI and custom query params."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.db.models import Q
from django.utils.dateparse import parse_date

GD_SEARCH_FIRST_CHANGE_LIST_TEMPLATE = 'admin/gd/search_first_change_list.html'
GD_CHANGE_LIST_PAGE_SIZE = 50

# Shared date-range query keys (workshop, vouchers, etc.).
CHANGE_LIST_DATE_RANGE_PARAMS = ('date_from', 'date_to')


class GdChangeList(ChangeList):
    """Strip non-field query params before Django validates changelist lookups."""

    extra_query_params: frozenset[str] = frozenset()

    def get_filters_params(self, params=None):
        lookup_params = super().get_filters_params(params)
        for key in self.extra_query_params:
            lookup_params.pop(key, None)
        return lookup_params


def gd_change_list_class(extra_params):
    """Return a ChangeList subclass that ignores the given query-string keys."""

    extra = frozenset(extra_params)

    class _GdChangeList(GdChangeList):
        extra_query_params = extra

    return _GdChangeList


def parse_changelist_date(value):
    """Parse a YYYY-MM-DD query value into a date, or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return parse_date(text)


def parse_changelist_date_range(request):
    """
    Return (date_from, date_to) from request.GET, swapped if inverted.

    Missing/invalid values become None. Both None means no range selected.
    """
    get = getattr(request, 'GET', None)
    if not get:
        return None, None
    date_from = parse_changelist_date(get.get('date_from'))
    date_to = parse_changelist_date(get.get('date_to'))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def changelist_has_custom_date_range(request) -> bool:
    date_from, date_to = parse_changelist_date_range(request)
    return bool(date_from or date_to)


def apply_changelist_date_range(request, queryset, *, field, or_q=None):
    """
    Filter queryset by optional date_from / date_to on ``field``.

    ``field`` is a Django lookup path for a DateField or DateTimeField day
    (e.g. ``issue_date`` or ``date__date``). When ``or_q`` is set, rows matching
    that Q are kept even if outside the range (e.g. open-dated workshops).
    """
    date_from, date_to = parse_changelist_date_range(request)
    if not date_from and not date_to:
        return queryset

    range_query = Q()
    if date_from:
        range_query &= Q(**{f'{field}__gte': date_from})
    if date_to:
        range_query &= Q(**{f'{field}__lte': date_to})
    if or_q is not None:
        return queryset.filter(or_q | range_query)
    return queryset.filter(range_query)


class SearchFirstChangeListMixin:
    """
    Primary search bar + collapsible filters panel (see admin/gd/search_first_change_list.html).

    Set gd_changelist_extra_params for custom GET keys (e.g. show_all).
    Set gd_changelist_form_field_params for keys rendered as visible form inputs
    (excluded from duplicate hidden fields).
    Enable gd_changelist_show_date_range for the shared From/To date inputs;
    date_from/date_to are merged into extra/form params automatically.
    """

    change_list_template = GD_SEARCH_FIRST_CHANGE_LIST_TEMPLATE
    list_per_page = GD_CHANGE_LIST_PAGE_SIZE
    show_full_result_count = False
    gd_changelist_extra_params: tuple[str, ...] = ()
    gd_changelist_form_field_params: tuple[str, ...] = ()
    gd_changelist_show_date_range = False
    gd_changelist_date_field: str | None = None
    gd_changelist_date_range_hint = ''
    gd_changelist_date_range_id_prefix = 'gd'

    def resolved_gd_changelist_extra_params(self):
        params = list(self.gd_changelist_extra_params or ())
        if self.gd_changelist_show_date_range:
            for key in CHANGE_LIST_DATE_RANGE_PARAMS:
                if key not in params:
                    params.append(key)
        return tuple(params)

    def resolved_gd_changelist_form_field_params(self):
        params = list(self.gd_changelist_form_field_params or ())
        if self.gd_changelist_show_date_range:
            for key in CHANGE_LIST_DATE_RANGE_PARAMS:
                if key not in params:
                    params.append(key)
        return tuple(params)

    def get_changelist_date_range_or_q(self, request):
        """Optional Q ORed with the date range (override in subclasses)."""
        return None

    def get_changelist(self, request, **kwargs):
        extra = self.resolved_gd_changelist_extra_params()
        if extra:
            return gd_change_list_class(extra)
        return super().get_changelist(request, **kwargs)

    def lookup_allowed(self, lookup, value):
        if lookup in self.resolved_gd_changelist_extra_params():
            return True
        return super().lookup_allowed(lookup, value)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.gd_changelist_show_date_range and self.gd_changelist_date_field:
            qs = apply_changelist_date_range(
                request,
                qs,
                field=self.gd_changelist_date_field,
                or_q=self.get_changelist_date_range_or_q(request),
            )
        return qs


class GdActiveFilter(admin.SimpleListFilter):
    """Reusable active/inactive filter for legacy 0/1 integer fields."""

    title = 'Active'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Active'),
            ('0', 'Inactive'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == '1':
            return queryset.filter(active=1)
        if value == '0':
            return queryset.filter(active=0)
        return queryset
