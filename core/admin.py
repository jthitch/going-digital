from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .forms import GdUserChangeForm, GdUserCreationForm, GdUserPasswordResetForm
from .models import User


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
        ('Personal info', {'fields': ('firstname', 'lastname', 'telephone', 'mobile')}),
        ('Social profiles', {
            'fields': ('facebook_url', 'twitter_url', 'linkedin_url', 'social_profile_links'),
        }),
        ('Permissions', {'fields': ('user_type_id', 'active', 'regions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

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

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'firstname', 'lastname', 'user_type_id', 'regions', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        form._editor_id = request.user.id
        super().save_model(request, obj, form, change)
        if hasattr(form, 'sync_regions'):
            form.sync_regions(obj)
