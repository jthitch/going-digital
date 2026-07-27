"""Admin changelist template helpers."""

from django import template

register = template.Library()

_IGNORED_CHANGE_LIST_KEYS = frozenset({'q', 'p', 'o', 'e', '_popup'})


@register.simple_tag
def changelist_filters_active(request):
    """True when the changelist has filter query params (not just search/pagination)."""
    if not getattr(request, 'GET', None):
        return False
    return any(key not in _IGNORED_CHANGE_LIST_KEYS for key in request.GET)


@register.simple_tag
def gd_changelist_emit_hidden_param(model_admin, param_name):
    """True when a hidden input should preserve this query param on submit."""
    if param_name == 'q':
        return False
    form_fields = getattr(model_admin, 'gd_changelist_form_field_params', ()) or ()
    return param_name not in form_fields
