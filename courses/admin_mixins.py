"""Admin mixins for platform-admin-only and region-scoped franchisee access."""
from django.utils import timezone

from courses.region_scope import (
    filter_courses_for_user,
    filter_courses_for_workshop_picker,
    filter_venues_for_user,
    filter_venues_for_workshop_picker,
    filter_workshops_for_user,
    get_user_region_ids,
    user_can_access_venue,
    user_can_access_workshop,
    user_can_add_venue,
    user_can_change_venue,
    user_can_edit_venue_details,
    user_can_view_course,
    user_has_full_region_access,
    venue_is_approved,
)


class LegacyAuditAdminMixin:
    """
    Stamp legacy gd_* audit columns (createdby_id, updatedby_id, timestamps) on save.

    Subclasses may set audit_set_user_id_on_create = True to default user_id on create
    (Workshop admin). Override apply_legacy_audit_fields for bespoke audit rules.
    """

    audit_set_user_id_on_create = False

    def apply_legacy_audit_fields(self, request, obj, change):
        now = timezone.now()
        if not change:
            if hasattr(obj, 'createdby_id') and not obj.createdby_id:
                obj.createdby_id = request.user.id
            if hasattr(obj, 'created_at') and obj.created_at is None:
                obj.created_at = now
            if self.audit_set_user_id_on_create and hasattr(obj, 'user_id') and not obj.user_id:
                obj.user_id = request.user.id
        if hasattr(obj, 'updatedby_id'):
            obj.updatedby_id = request.user.id
        if hasattr(obj, 'updated_at'):
            obj.updated_at = now

    def save_model(self, request, obj, form, change):
        self.apply_legacy_audit_fields(request, obj, change)
        super().save_model(request, obj, form, change)


class PlatformAdminOnlyMixin:
    """Hide model from franchisees; super users and administrators only."""

    def has_module_permission(self, request):
        return user_has_full_region_access(request.user)

    def has_view_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)

    def has_add_permission(self, request):
        return user_has_full_region_access(request.user)

    def has_change_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)

    def has_delete_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)


class RegionScopedCourseAdminMixin:
    """Franchisees: view global + regional courses; no add/change/delete."""

    def get_queryset(self, request):
        return filter_courses_for_user(super().get_queryset(request), request.user)

    def has_module_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_module_permission(request)
        return bool(get_user_region_ids(request.user))

    def has_view_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_view_permission(request, obj)
        if obj is None:
            return bool(get_user_region_ids(request.user))
        return user_can_view_course(request.user, obj)

    def has_add_permission(self, request):
        return user_has_full_region_access(request.user)

    def has_change_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)

    def has_delete_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)


class RegionScopedWorkshopAdminMixin:
    """Franchisees: full workshop CRUD for their own workshops in assigned regions."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return filter_workshops_for_user(qs, request.user)

    def get_form(self, request, obj=None, **kwargs):
        region_ids = get_user_region_ids(request.user)
        form_class = super().get_form(request, obj, **kwargs)

        class RegionScopedWorkshopForm(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs.setdefault('region_ids', region_ids)
                form_kwargs.setdefault('editor_user_id', request.user.pk)
                super().__init__(*args, **form_kwargs)

        RegionScopedWorkshopForm.__name__ = form_class.__name__
        RegionScopedWorkshopForm.__qualname__ = form_class.__qualname__
        return RegionScopedWorkshopForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'course' and not user_has_full_region_access(request.user):
            include_ids = []
            object_id = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
            if object_id:
                workshop = self.model.objects.filter(pk=object_id).only('course_id').first()
                if workshop and workshop.course_id:
                    include_ids.append(workshop.course_id)
            kwargs['queryset'] = filter_courses_for_workshop_picker(
                kwargs.get('queryset', db_field.remote_field.model.objects.all()),
                request.user,
                include_course_ids=include_ids,
            )
        if db_field.name == 'venue' and not user_has_full_region_access(request.user):
            kwargs['queryset'] = filter_venues_for_workshop_picker(
                kwargs.get('queryset', db_field.remote_field.model.objects.all()),
                request.user,
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if request.path.endswith('/autocomplete/'):
            if queryset.model.__name__ == 'Course':
                queryset = filter_courses_for_workshop_picker(queryset, request.user)
            elif queryset.model.__name__ == 'Venue':
                queryset = filter_venues_for_workshop_picker(queryset, request.user)
        return queryset, use_distinct

    def has_module_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_module_permission(request)
        return bool(get_user_region_ids(request.user))

    def has_view_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_view_permission(request, obj)
        if obj is None:
            return bool(get_user_region_ids(request.user))
        return user_can_access_workshop(request.user, obj)

    def has_add_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_add_permission(request)
        return bool(get_user_region_ids(request.user))

    def has_change_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_change_permission(request, obj)
        if obj is None:
            return bool(get_user_region_ids(request.user))
        return user_can_access_workshop(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_delete_permission(request, obj)
        if obj is None:
            return bool(get_user_region_ids(request.user))
        return user_can_access_workshop(request.user, obj)


class RegionScopedVenueAdminMixin:
    """Franchisees: add and view only their own venues (pending approval); admins approve."""

    def get_queryset(self, request):
        return filter_venues_for_user(super().get_queryset(request), request.user)

    def _form_field_names_for_modelfactory(self):
        """Names that may be passed to modelform_factory (model + declared form fields)."""
        names = {f.name for f in self.model._meta.fields}
        if getattr(self, 'form', None) is not None:
            names.update(getattr(self.form, 'declared_fields', {}))
        return names

    def get_form(self, request, obj=None, **kwargs):
        fields = kwargs.get('fields')
        if fields is not None:
            allowed = self._form_field_names_for_modelfactory()
            kwargs['fields'] = [name for name in fields if name in allowed]
        region_ids = get_user_region_ids(request.user)
        franchisee_mode = not user_has_full_region_access(request.user)
        form_class = super().get_form(request, obj, **kwargs)

        class RegionScopedVenueForm(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs.setdefault('region_ids', region_ids)
                form_kwargs.setdefault('franchisee_mode', franchisee_mode)
                form_kwargs.setdefault('editor_user_id', request.user.pk)
                super().__init__(*args, **form_kwargs)

        RegionScopedVenueForm.__name__ = form_class.__name__
        RegionScopedVenueForm.__qualname__ = form_class.__qualname__
        return RegionScopedVenueForm

    def get_fieldsets(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().get_fieldsets(request, obj)
        if (
            obj
            and user_can_change_venue(request.user, obj)
            and not user_can_edit_venue_details(request.user, obj)
        ):
            approved_fieldsets = getattr(self, 'franchisee_approved_content_fieldsets', None)
            if approved_fieldsets is not None:
                return approved_fieldsets
        if (
            obj
            and user_can_access_venue(request.user, obj)
            and not user_can_change_venue(request.user, obj)
        ):
            view_fieldsets = getattr(self, 'franchisee_view_fieldsets', None)
            if view_fieldsets is not None:
                return view_fieldsets
        return getattr(self, 'franchisee_fieldsets', super().get_fieldsets(request, obj))

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not user_has_full_region_access(request.user):
            readonly = list(dict.fromkeys(
                readonly + ['approval_status', 'reject_reason', 'content_change_status'],
            ))
        return readonly

    def has_module_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_module_permission(request)
        return user_can_add_venue(request.user)

    def has_view_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_view_permission(request, obj)
        if obj is None:
            return user_can_add_venue(request.user)
        return user_can_access_venue(request.user, obj)

    def has_add_permission(self, request):
        if user_has_full_region_access(request.user):
            return super().has_add_permission(request)
        return user_can_add_venue(request.user)

    def has_change_permission(self, request, obj=None):
        if user_has_full_region_access(request.user):
            return super().has_change_permission(request, obj)
        if obj is None:
            return user_can_add_venue(request.user)
        return user_can_change_venue(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return user_has_full_region_access(request.user)
