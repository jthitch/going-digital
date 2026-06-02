"""Patch admin index to supply dashboard context."""


def patch_admin_index():
    from django.contrib import admin

    from courses.dashboard_workshops import get_upcoming_workshops_dashboard_context
    from payments.dashboard_kpis import get_payment_kpis_dashboard_context

    original_index = admin.site.index

    def index(request, extra_context=None):
        context = dict(extra_context or {})
        context.update(get_payment_kpis_dashboard_context(request))
        context.update(get_upcoming_workshops_dashboard_context(request))
        return original_index(request, context)

    admin.site.index = index
