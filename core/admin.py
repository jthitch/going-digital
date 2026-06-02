from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .forms import GdUserChangeForm, GdUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model (gd_user)."""
    form = GdUserChangeForm
    add_form = GdUserCreationForm
    filter_horizontal = ()
    list_display = ['email', 'firstname', 'lastname', 'get_user_type_display', 'is_active', 'created_at']
    list_filter = ['user_type_id', 'active', 'created_at']
    search_fields = ['email', 'firstname', 'lastname']
    ordering = ['-created_at']
    readonly_fields = ['password_reset_link', 'last_login', 'created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('email', 'password_reset_link')}),
        ('Personal info', {'fields': ('firstname', 'lastname', 'telephone', 'mobile')}),
        ('Permissions', {'fields': ('user_type_id', 'active', 'regions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    @admin.display(description='Password')
    def password_reset_link(self, obj):
        if not obj or not obj.pk:
            return 'Save the user first, then use the link below to set a password.'
        return format_html(
            '<a href="{}">Change password</a>',
            f'../../{obj.pk}/password/',
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
