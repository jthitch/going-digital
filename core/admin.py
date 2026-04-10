from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserAdminForm(forms.ModelForm):
    """Use choice labels for user_type_id in admin form."""
    user_type_id = forms.TypedChoiceField(
        choices=[(1, 'Super User'), (2, 'Administrator'), (3, 'Franchisee')],
        coerce=int,
        required=False,
    )

    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model (gd_user)."""
    form = UserAdminForm
    filter_horizontal = ()
    list_display = ['email', 'firstname', 'lastname', 'get_user_type_display', 'is_active', 'created_at']
    list_filter = ['user_type_id', 'active', 'created_at']
    search_fields = ['email', 'firstname', 'lastname']
    ordering = ['-created_at']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('firstname', 'lastname', 'telephone', 'mobile')}),
        ('Permissions', {'fields': ('user_type_id', 'active')}),  # user_type_id shows as dropdown
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'firstname', 'lastname', 'password1', 'password2'),
        }),
    )
