from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model."""
    list_display = ['username', 'email', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Information', {'fields': ('role', 'phone', 'date_of_birth')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Information', {'fields': ('role', 'phone', 'date_of_birth', 'email')}),
    )
