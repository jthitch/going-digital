"""Admin mixins for booking access control."""
from courses.region_scope import get_user_region_ids, user_has_full_region_access

from .scope import filter_bookings_for_user, user_can_view_booking


class RegionScopedBookingAdminMixin:
    """Franchisees: view-only bookings for their workshops."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return filter_bookings_for_user(qs, request.user).select_related(
            'workshop__course',
            'workshop__venue',
            'user',
            'payment',
        )

    def has_module_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_module_permission(request)
        return bool(get_user_region_ids(request.user))

    def has_view_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_view_permission(request, obj)
        if obj is None:
            return bool(get_user_region_ids(request.user))
        return user_can_view_booking(request.user, obj)

    def has_add_permission(self, request):
        return user_has_full_region_access(request.user)

    def has_change_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)

    def has_delete_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not user_has_full_region_access(request.user):
            return list(
                dict.fromkeys(
                    [f.name for f in self.model._meta.fields]
                    + [f.name for f in self.model._meta.many_to_many]
                    + readonly
                )
            )
        return readonly
