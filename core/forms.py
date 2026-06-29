"""Forms for gd_user admin."""
from django import forms
from django.contrib.auth.forms import (
    BaseUserCreationForm,
    PasswordResetForm,
    UserChangeForm,
)
from django.utils import timezone

from .models import User


def _sync_user_regions(user, region_pks, editor_id=None):
    """Replace gd_region_user rows for this user."""
    from courses.models import RegionUser

    RegionUser.objects.filter(user_id=user.pk).delete()
    now = timezone.now()
    for region_id in region_pks:
        RegionUser.objects.create(
            user_id=user.pk,
            region_id=region_id,
            createdby_id=editor_id,
            updatedby_id=editor_id,
            created_at=now,
            updated_at=now,
        )
    if len(region_pks) == 1:
        user.region_id = region_pks[0]
    elif not region_pks:
        user.region_id = None
    user.save(update_fields=['region_id'])


class GdUserChangeForm(UserChangeForm):
    """Change form without password hash display (reset link is on the admin page)."""

    user_type_id = forms.TypedChoiceField(
        choices=[(1, 'Super User'), (2, 'Administrator'), (3, 'Franchisee')],
        coerce=int,
        required=False,
        label='User type',
    )
    regions = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label='Regions',
        help_text='Franchise regions this user can access (gd_region_user).',
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
        field_classes = {}
        exclude = ['password']

    def __init__(self, *args, **kwargs):
        from courses.models import Region, RegionUser

        super().__init__(*args, **kwargs)
        self.fields.pop('password', None)
        self.fields['regions'].queryset = Region.objects.filter(active=1).order_by('region_name')
        if self.instance.pk:
            region_ids = RegionUser.objects.filter(user_id=self.instance.pk).values_list(
                'region_id', flat=True
            )
            self.fields['regions'].initial = Region.objects.filter(pk__in=region_ids)

    def save(self, commit=True):
        # Admin calls save(commit=False) then obj.save(); region sync runs in UserAdmin.save_model.
        return super().save(commit=commit)

    def sync_regions(self, user):
        if 'regions' not in self.cleaned_data or not user.pk:
            return
        region_pks = [r.pk for r in self.cleaned_data['regions']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_regions(user, region_pks, editor_id=editor_id)


class GdUserCreationForm(BaseUserCreationForm):
    """Create user with hashed password (never store plain text in gd_user.password)."""

    user_type_id = forms.TypedChoiceField(
        choices=[(1, 'Super User'), (2, 'Administrator'), (3, 'Franchisee')],
        coerce=int,
        required=False,
        initial=3,
        label='User type',
    )
    regions = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label='Regions',
        help_text='Franchise regions this user can access (gd_region_user).',
    )

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('email', 'firstname', 'lastname', 'user_type_id')

    def __init__(self, *args, **kwargs):
        from courses.models import Region

        super().__init__(*args, **kwargs)
        self.fields['regions'].queryset = Region.objects.filter(active=1).order_by('region_name')

    def save(self, commit=True):
        return super().save(commit=commit)

    def sync_regions(self, user):
        if 'regions' not in self.cleaned_data or not user.pk:
            return
        region_pks = [r.pk for r in self.cleaned_data['regions']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_regions(user, region_pks, editor_id=editor_id)


class GdUserPasswordResetForm(PasswordResetForm):
    """Password reset for gd_user (uses active column, not is_active field)."""

    def get_users(self, email):
        active_users = User.objects.filter(email__iexact=email, active=1)
        email_field = User.get_email_field_name()
        for user in active_users:
            if user.has_usable_password() and (getattr(user, email_field) or '').strip().casefold() == email.casefold():
                yield user
