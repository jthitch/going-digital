from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin.options import ModelAdmin
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from courses.region_scope import user_has_full_region_access

from .forms import GdUserChangeForm, GdUserCreationForm, GdUserPasswordResetForm
from .models import User


def _fieldsets_without_venues(fieldsets):
    stripped = []
    for title, opts in fieldsets:
        fields = opts.get('fields')
        if fields and 'venues' in fields:
            opts = {**opts, 'fields': tuple(f for f in fields if f != 'venues')}
        stripped.append((title, opts))
    return stripped


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model (gd_user)."""
    form = GdUserChangeForm
    add_form = GdUserCreationForm
    filter_horizontal = ()
    list_display = [
        'email',
        'firstname',
        'lastname',
        'get_user_type_display',
        'is_active',
        'password_reset_admin_link',
        'created_at',
    ]
    list_filter = ['user_type_id', 'active', 'created_at']
    search_fields = ['email', 'firstname', 'lastname']
    ordering = ['-created_at']
    actions = ['send_password_reset_email']
    readonly_fields = [
        'password_reset_link',
        'social_profile_links',
        'last_login',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        (None, {'fields': ('email', 'password_reset_link')}),
        ('Personal info', {'fields': ('firstname', 'lastname', 'telephone', 'mobile', 'company')}),
        ('Address', {
            'fields': ('address1', 'address2', 'town_city', 'postcode'),
        }),
        ('Social profiles', {
            'fields': ('facebook_url', 'twitter_url', 'linkedin_url', 'social_profile_links'),
        }),
        ('Permissions', {'fields': ('user_type_id', 'active', 'regions', 'venues')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'firstname',
                'lastname',
                'telephone',
                'mobile',
                'company',
                'address1',
                'address2',
                'town_city',
                'postcode',
                'user_type_id',
                'regions',
                'venues',
                'password1',
                'password2',
            ),
        }),
    )

    def get_urls(self):
        """Use core app URL name for password change (not auth_user_password_change)."""
        return [
            path(
                '<id>/password/',
                self.admin_site.admin_view(self.user_change_password),
                name='core_user_password_change',
            ),
        ] + ModelAdmin.get_urls(self)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            fieldsets = self.add_fieldsets
        else:
            fieldsets = self.fieldsets
        if user_has_full_region_access(request.user):
            return fieldsets
        return _fieldsets_without_venues(fieldsets)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        can_assign_venues = user_has_full_region_access(request.user)

        class UserFormWithVenueAccess(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs.setdefault('can_assign_venues', can_assign_venues)
                super().__init__(*args, **form_kwargs)

        UserFormWithVenueAccess.__name__ = form_class.__name__
        UserFormWithVenueAccess.__qualname__ = form_class.__qualname__
        return UserFormWithVenueAccess

    @admin.display(description='Profile links')
    def social_profile_links(self, obj):
        if not obj or not obj.pk:
            return '—'
        links = []
        for label, url in (
            ('Facebook', obj.facebook_url),
            ('Twitter / X', obj.twitter_url),
            ('LinkedIn', obj.linkedin_url),
        ):
            if url and url.strip():
                href = url.strip()
                if not href.startswith(('http://', 'https://')):
                    href = f'https://{href}'
                links.append(format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', href, label))
        if not links:
            return 'No social URLs set'
        return mark_safe(' &middot; '.join(links))

    def _password_change_url(self, obj):
        return reverse('admin:core_user_password_change', args=[obj.pk])

    @admin.display(description='Password')
    def password_reset_admin_link(self, obj):
        if not obj or not obj.pk:
            return '—'
        return format_html('<a href="{}">Reset password</a>', self._password_change_url(obj))

    @admin.display(description='Password reset')
    def password_reset_link(self, obj):
        if not obj or not obj.pk:
            return 'Save the user first, then you can reset their password.'
        return format_html(
            '<a class="button" href="{}">Reset password</a>',
            self._password_change_url(obj),
        )

    @admin.action(description='Email password reset link')
    def send_password_reset_email(self, request, queryset):
        sent = 0
        skipped = 0
        for user in queryset:
            email = (user.email or '').strip()
            if not email:
                skipped += 1
                continue
            form = GdUserPasswordResetForm({'email': email})
            if form.is_valid():
                form.save(request=request, use_https=request.is_secure())
                sent += 1
            else:
                skipped += 1
        if sent:
            self.message_user(
                request,
                f'Password reset email sent to {sent} user(s).',
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'Skipped {skipped} user(s) with no valid email.',
                messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        # gd_user.created_at/updated_at are nullable legacy columns (no auto_now).
        now = timezone.now()
        if obj.created_at is None:
            obj.created_at = now
        obj.updated_at = now
        if obj.user_type_id == 3 and not obj.is_franchisee:
            obj.is_franchisee = 1
        form._editor_id = request.user.id
        super().save_model(request, obj, form, change)
        if hasattr(form, 'sync_regions'):
            form.sync_regions(obj)
        if hasattr(form, 'sync_venues'):
            form.sync_venues(obj)
