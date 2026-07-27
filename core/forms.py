"""Forms for gd_user admin."""
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
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


def _sync_user_venues(user, venue_pks, editor_id=None):
    """Assign/unassign gd_venue.user_id for this user (same link as Venue admin User field)."""
    from courses.models import Venue

    venue_pks = set(venue_pks)
    now = timezone.now()
    currently = set(
        Venue.objects.filter(user_id=user.pk).values_list('pk', flat=True)
    )
    to_remove = currently - venue_pks
    to_add = venue_pks - currently
    if to_remove:
        Venue.objects.filter(pk__in=to_remove, user_id=user.pk).update(
            user_id=None,
            updatedby_id=editor_id,
            updated_at=now,
        )
    if to_add:
        Venue.objects.filter(pk__in=to_add).update(
            user_id=user.pk,
            updatedby_id=editor_id,
            updated_at=now,
        )


class VenueMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Venue labels include location for disambiguation in the dual-list widget."""

    def label_from_instance(self, obj):
        name = obj.venue_name or f'Venue #{obj.pk}'
        loc = (obj.location or '').strip()
        return f'{name} ({loc})' if loc else name


def _venue_assignment_queryset(include_user_id=None):
    """Active venues, plus any already assigned to this user (even if inactive)."""
    from courses.models import Venue
    from django.db.models import Q

    qs = Venue.objects.filter(active=1)
    if include_user_id:
        qs = Venue.objects.filter(Q(active=1) | Q(user_id=include_user_id))
    return qs.order_by('venue_name', 'id')


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
    venues = VenueMultipleChoiceField(
        queryset=None,
        required=False,
        label='Venues',
        help_text=(
            'Venues assigned to this user (same as setting User on each venue). '
            'Selecting a venue already assigned elsewhere will move it to this user.'
        ),
        widget=FilteredSelectMultiple('venues', is_stacked=False),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
        field_classes = {}
        exclude = ['password']

    class Media:
        css = {'all': ('admin/css/widgets.css',)}
        js = (
            'admin/js/jquery.init.js',
            'admin/js/core.js',
            'admin/js/SelectBox.js',
            'admin/js/SelectFilter2.js',
        )

    def __init__(self, *args, can_assign_venues=False, **kwargs):
        from courses.models import Region, RegionUser, Venue

        self.can_assign_venues = can_assign_venues
        super().__init__(*args, **kwargs)
        self.fields.pop('password', None)
        self.fields['regions'].queryset = Region.objects.filter(active=1).order_by('region_name')
        if self.instance.pk:
            region_ids = RegionUser.objects.filter(user_id=self.instance.pk).values_list(
                'region_id', flat=True
            )
            self.fields['regions'].initial = Region.objects.filter(pk__in=region_ids)

        if can_assign_venues:
            self.fields['venues'].queryset = _venue_assignment_queryset(
                include_user_id=self.instance.pk if self.instance.pk else None
            )
            if self.instance.pk:
                self.fields['venues'].initial = Venue.objects.filter(user_id=self.instance.pk)
        else:
            self.fields.pop('venues', None)

    def save(self, commit=True):
        # Admin calls save(commit=False) then obj.save(); region/venue sync in UserAdmin.save_model.
        return super().save(commit=commit)

    def sync_regions(self, user):
        if 'regions' not in self.cleaned_data or not user.pk:
            return
        region_pks = [r.pk for r in self.cleaned_data['regions']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_regions(user, region_pks, editor_id=editor_id)

    def sync_venues(self, user):
        if not self.can_assign_venues or 'venues' not in self.cleaned_data or not user.pk:
            return
        venue_pks = [v.pk for v in self.cleaned_data['venues']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_venues(user, venue_pks, editor_id=editor_id)


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
    venues = VenueMultipleChoiceField(
        queryset=None,
        required=False,
        label='Venues',
        help_text=(
            'Venues assigned to this user (same as setting User on each venue). '
            'Selecting a venue already assigned elsewhere will move it to this user.'
        ),
        widget=FilteredSelectMultiple('venues', is_stacked=False),
    )

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = (
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
        )

    class Media:
        css = {'all': ('admin/css/widgets.css',)}
        js = (
            'admin/js/jquery.init.js',
            'admin/js/core.js',
            'admin/js/SelectBox.js',
            'admin/js/SelectFilter2.js',
        )

    def __init__(self, *args, can_assign_venues=False, **kwargs):
        from courses.models import Region

        self.can_assign_venues = can_assign_venues
        super().__init__(*args, **kwargs)
        self.fields['regions'].queryset = Region.objects.filter(active=1).order_by('region_name')
        if can_assign_venues:
            self.fields['venues'].queryset = _venue_assignment_queryset()
        else:
            self.fields.pop('venues', None)

    def save(self, commit=True):
        return super().save(commit=commit)

    def sync_regions(self, user):
        if 'regions' not in self.cleaned_data or not user.pk:
            return
        region_pks = [r.pk for r in self.cleaned_data['regions']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_regions(user, region_pks, editor_id=editor_id)

    def sync_venues(self, user):
        if not self.can_assign_venues or 'venues' not in self.cleaned_data or not user.pk:
            return
        venue_pks = [v.pk for v in self.cleaned_data['venues']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_venues(user, venue_pks, editor_id=editor_id)


class GdUserPasswordResetForm(PasswordResetForm):
    """Password reset for gd_user (uses active column, not is_active field)."""

    def get_users(self, email):
        active_users = User.objects.filter(email__iexact=email, active=1)
        email_field = User.get_email_field_name()
        for user in active_users:
            if user.has_usable_password() and (getattr(user, email_field) or '').strip().casefold() == email.casefold():
                yield user
