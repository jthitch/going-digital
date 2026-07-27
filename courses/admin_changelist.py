"""Shared Going Digital admin changelist: search-first UI and custom query params."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList

GD_SEARCH_FIRST_CHANGE_LIST_TEMPLATE = 'admin/gd/search_first_change_list.html'
GD_CHANGE_LIST_PAGE_SIZE = 50


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


class SearchFirstChangeListMixin:
    """
    Primary search bar + collapsible filters panel (see admin/gd/search_first_change_list.html).

    Set gd_changelist_extra_params for custom GET keys (e.g. workshop date range).
    Set gd_changelist_form_field_params for keys rendered as visible form inputs
    (excluded from duplicate hidden fields).
    """

    change_list_template = GD_SEARCH_FIRST_CHANGE_LIST_TEMPLATE
    list_per_page = GD_CHANGE_LIST_PAGE_SIZE
    show_full_result_count = False
    gd_changelist_extra_params: tuple[str, ...] = ()
    gd_changelist_form_field_params: tuple[str, ...] = ()

    def get_changelist(self, request, **kwargs):
        if self.gd_changelist_extra_params:
            return gd_change_list_class(self.gd_changelist_extra_params)
        return super().get_changelist(request, **kwargs)

    def lookup_allowed(self, lookup, value):
        if lookup in self.gd_changelist_extra_params:
            return True
        return super().lookup_allowed(lookup, value)


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
