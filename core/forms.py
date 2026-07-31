"""Forms for gd_user admin."""
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.forms import (
    BaseUserCreationForm,
    PasswordResetForm,
    UserChangeForm,
)
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone

from .models import User


class RegionGroupedVenueWidget(forms.SelectMultiple):
    """Multi-select enhanced by region-grouped-venue.js into a dual list with collapsible regions."""

    class Media:
        css = {'all': ('admin/css/region-grouped-venue.css',)}
        js = ('admin/js/region-grouped-venue.js',)

    def __init__(self, verbose_name='venues', intro_text='', attrs=None):
        self.verbose_name = verbose_name
        self.intro_text = intro_text or ''
        self.region_by_value = {}
        self.venue_meta_by_value = {}
        attrs = dict(attrs or {})
        css = (attrs.get('class') or '').split()
        if 'gd-region-grouped-venue' not in css:
            css.append('gd-region-grouped-venue')
        attrs['class'] = ' '.join(css).strip()
        attrs['data-verbose-name'] = verbose_name
        super().__init__(attrs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs,
        )
        key = str(getattr(value, 'value', value))
        region = self.region_by_value.get(key)
        if region:
            option['attrs']['data-region'] = region
        meta = self.venue_meta_by_value.get(key)
        if meta:
            if meta.get('name'):
                option['attrs']['data-venue-name'] = meta['name']
            if meta.get('location'):
                option['attrs']['data-location'] = meta['location']
            if meta.get('owner'):
                option['attrs']['data-owner'] = meta['owner']
        return option

    def render(self, name, value, attrs=None, renderer=None):
        select_html = super().render(name, value, attrs, renderer)
        if self.intro_text:
            intro = format_html('<p class="help gd-venue-picker__intro">{}</p>', self.intro_text)
            return mark_safe(intro + select_html)
        return select_html


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
    """Assign/unassign gd_venue.user_id for this user (same link as Venue admin User field).

    Adding a venue that already has another owner moves primary ownership to this user.
    """
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


def _sync_user_workshop_access(user, venue_pks, editor_id=None):
    """Sync VenueWorkshopAccess grants for this user (workshop picker only, not ownership)."""
    from courses.models import VenueWorkshopAccess

    venue_pks = set(venue_pks)
    currently = set(
        VenueWorkshopAccess.objects.filter(user_id=user.pk).values_list('venue_id', flat=True)
    )
    to_remove = currently - venue_pks
    to_add = venue_pks - currently
    if to_remove:
        VenueWorkshopAccess.objects.filter(user_id=user.pk, venue_id__in=to_remove).delete()
    for venue_id in to_add:
        VenueWorkshopAccess.objects.get_or_create(
            venue_id=venue_id,
            user_id=user.pk,
            defaults={'granted_by_id': editor_id},
        )


def _sync_user_course_blocks(user, course_pks, editor_id=None):
    """Sync CourseWorkshopBlock deny-list for this franchisee."""
    from courses.models import CourseWorkshopBlock

    course_pks = set(course_pks)
    currently = set(
        CourseWorkshopBlock.objects.filter(user_id=user.pk).values_list('course_id', flat=True)
    )
    to_remove = currently - course_pks
    to_add = course_pks - currently
    if to_remove:
        CourseWorkshopBlock.objects.filter(user_id=user.pk, course_id__in=to_remove).delete()
    for course_id in to_add:
        CourseWorkshopBlock.objects.get_or_create(
            course_id=course_id,
            user_id=user.pk,
            defaults={'blocked_by_id': editor_id},
        )


def _course_block_queryset():
    """Active courses available to block for workshop creation."""
    from courses.models import Course

    return Course.objects.filter(active=True).order_by('course_name', 'id')


class VenueMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Venue picker with collapsible region groups; optional current-owner hint."""

    def __init__(self, *args, label_owned_by=False, exclude_owner_id=None, verbose_name='venues', help_above_widget=False, **kwargs):
        self.label_owned_by = label_owned_by
        self.exclude_owner_id = exclude_owner_id
        self._region_names = None
        self._owner_labels = None
        intro_text = ''
        if help_above_widget:
            intro_text = kwargs.pop('help_text', '') or ''
        widget = kwargs.get('widget')
        if widget is None:
            widget = RegionGroupedVenueWidget(verbose_name=verbose_name, intro_text=intro_text)
            kwargs['widget'] = widget
        elif isinstance(widget, RegionGroupedVenueWidget) and intro_text:
            widget.intro_text = intro_text
        if help_above_widget:
            kwargs['help_text'] = ''
        super().__init__(*args, **kwargs)

    def _ensure_label_caches(self):
        if self._region_names is not None:
            return
        from courses.models import Region

        venues = list(self.queryset)
        region_ids = {v.region_id for v in venues if v.region_id}
        self._region_names = (
            dict(Region.objects.filter(pk__in=region_ids).values_list('pk', 'region_name'))
            if region_ids
            else {}
        )
        self._owner_labels = {}
        if self.label_owned_by:
            owner_ids = {
                v.user_id
                for v in venues
                if v.user_id and v.user_id != self.exclude_owner_id
            }
            if owner_ids:
                for owner in User.objects.filter(pk__in=owner_ids).only(
                    'id', 'firstname', 'lastname', 'email',
                ):
                    self._owner_labels[owner.pk] = (
                        owner.get_full_name() or owner.email or f'user #{owner.pk}'
                    )

    def prepare_widget_grouping(self):
        """Attach region and display metadata to widget options."""
        self._region_names = None
        self._ensure_label_caches()
        region_by_value = {}
        venue_meta_by_value = {}
        for venue in self.queryset:
            key = str(venue.pk)
            region_by_value[key] = (
                (self._region_names.get(venue.region_id) or '').strip() or 'No region'
            )
            name = venue.venue_name or f'Venue #{venue.pk}'
            loc = (venue.location or '').strip()
            owner = ''
            if (
                self.label_owned_by
                and venue.user_id
                and venue.user_id != self.exclude_owner_id
            ):
                owner = self._owner_labels.get(venue.user_id) or ''
            venue_meta_by_value[key] = {
                'name': name,
                'location': loc,
                'owner': owner,
            }
        if isinstance(self.widget, RegionGroupedVenueWidget):
            self.widget.region_by_value = region_by_value
            self.widget.venue_meta_by_value = venue_meta_by_value

    def label_from_instance(self, obj):
        self._ensure_label_caches()
        name = obj.venue_name or f'Venue #{obj.pk}'
        loc = (obj.location or '').strip()
        return f'{name} ({loc})' if loc else name


def _venue_assignment_queryset(include_user_id=None):
    """Active venues (plus inactive ones already owned by include_user_id), ordered by region."""
    from courses.models import Region, Venue
    from django.db.models import CharField, OuterRef, Q, Subquery, Value
    from django.db.models.functions import Coalesce

    qs = Venue.objects.filter(active=1)
    if include_user_id:
        qs = Venue.objects.filter(Q(active=1) | Q(user_id=include_user_id))
    region_name = Region.objects.filter(pk=OuterRef('region_id')).values('region_name')[:1]
    return qs.annotate(
        _region_sort=Coalesce(
            Subquery(region_name, output_field=CharField()),
            Value(''),
        ),
    ).order_by('_region_sort', 'venue_name', 'id')


class GdUserSelfProfileForm(forms.ModelForm):
    """Franchisees editing their own gd_user row (contact details only)."""

    class Meta:
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
            'facebook_url',
            'twitter_url',
            'linkedin_url',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.setdefault('size', 50)


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
        label='Owned venues',
        verbose_name='owned venues',
        help_text=(
            'Primary venue owner (same as the User field on each venue). '
            'Selecting a venue already owned by another franchisee moves ownership to this user. '
            'To let someone run workshops at a venue without owning it, use '
            '“Workshop access venues” below (superusers only).'
        ),
        help_above_widget=True,
        label_owned_by=True,
    )
    workshop_access_venues = VenueMultipleChoiceField(
        queryset=None,
        required=False,
        label='Workshop access venues',
        verbose_name='workshop access venues',
        help_text=(
            'Venues this franchisee may use when creating workshops, without becoming the owner. '
            'Same grants as “Franchisees allowed to add workshops” on the venue page.'
        ),
    )
    blocked_courses = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label='Blocked courses',
        help_text=(
            'Courses this franchisee cannot select when creating workshops. '
            'All other region-eligible courses remain available by default. '
            'Existing workshops on a blocked course stay editable.'
        ),
        widget=FilteredSelectMultiple('blocked courses', is_stacked=False),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
        field_classes = {}
        exclude = ['password']

    class Media:
        css = {
            'all': (
                'admin/css/widgets.css',
                *RegionGroupedVenueWidget.Media.css.get('all', ()),
            ),
        }
        js = (
            'admin/js/jquery.init.js',
            'admin/js/core.js',
            'admin/js/SelectBox.js',
            'admin/js/SelectFilter2.js',
            *RegionGroupedVenueWidget.Media.js,
        )

    def __init__(self, *args, can_assign_venues=False, can_assign_workshop_access=False, **kwargs):
        from courses.models import Course, CourseWorkshopBlock, Region, RegionUser, Venue, VenueWorkshopAccess

        self.can_assign_venues = can_assign_venues
        self.can_assign_workshop_access = can_assign_workshop_access
        super().__init__(*args, **kwargs)
        self.fields.pop('password', None)
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.setdefault('size', 50)
        self.fields['regions'].queryset = Region.objects.filter(active=1).order_by('region_name')
        if self.instance.pk:
            region_ids = RegionUser.objects.filter(user_id=self.instance.pk).values_list(
                'region_id', flat=True
            )
            self.fields['regions'].initial = Region.objects.filter(pk__in=region_ids)

        if can_assign_venues:
            user_pk = self.instance.pk if self.instance.pk else None
            self.fields['venues'].exclude_owner_id = user_pk
            self.fields['venues'].queryset = _venue_assignment_queryset(include_user_id=user_pk)
            if user_pk:
                self.fields['venues'].initial = Venue.objects.filter(user_id=user_pk)
            self.fields['venues'].prepare_widget_grouping()
        else:
            self.fields.pop('venues', None)

        if can_assign_workshop_access:
            user_pk = self.instance.pk if self.instance.pk else None
            self.fields['workshop_access_venues'].queryset = _venue_assignment_queryset(
                include_user_id=user_pk,
            )
            if user_pk:
                granted_ids = VenueWorkshopAccess.objects.filter(user_id=user_pk).values_list(
                    'venue_id', flat=True,
                )
                self.fields['workshop_access_venues'].initial = Venue.objects.filter(
                    pk__in=granted_ids,
                )
            self.fields['workshop_access_venues'].prepare_widget_grouping()

            self.fields['blocked_courses'].queryset = _course_block_queryset()
            if user_pk:
                blocked_ids = CourseWorkshopBlock.objects.filter(user_id=user_pk).values_list(
                    'course_id', flat=True,
                )
                self.fields['blocked_courses'].initial = Course.objects.filter(pk__in=blocked_ids)
        else:
            self.fields.pop('workshop_access_venues', None)
            self.fields.pop('blocked_courses', None)

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

    def sync_workshop_access_venues(self, user):
        if (
            not self.can_assign_workshop_access
            or 'workshop_access_venues' not in self.cleaned_data
            or not user.pk
        ):
            return
        venue_pks = [v.pk for v in self.cleaned_data['workshop_access_venues']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_workshop_access(user, venue_pks, editor_id=editor_id)

    def sync_blocked_courses(self, user):
        if (
            not self.can_assign_workshop_access
            or 'blocked_courses' not in self.cleaned_data
            or not user.pk
        ):
            return
        course_pks = [c.pk for c in self.cleaned_data['blocked_courses']]
        editor_id = getattr(self, '_editor_id', None)
        _sync_user_course_blocks(user, course_pks, editor_id=editor_id)


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
        label='Owned venues',
        verbose_name='owned venues',
        help_text=(
            'Primary venue owner. Selecting a venue already owned by another franchisee '
            'moves ownership to this user.'
        ),
        help_above_widget=True,
        label_owned_by=True,
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
        css = RegionGroupedVenueWidget.Media.css
        js = RegionGroupedVenueWidget.Media.js

    def __init__(self, *args, can_assign_venues=False, can_assign_workshop_access=False, **kwargs):
        from courses.models import Region

        self.can_assign_venues = can_assign_venues
        self.can_assign_workshop_access = can_assign_workshop_access
        super().__init__(*args, **kwargs)
        self.fields['regions'].queryset = Region.objects.filter(active=1).order_by('region_name')
        if can_assign_venues:
            self.fields['venues'].queryset = _venue_assignment_queryset()
            self.fields['venues'].prepare_widget_grouping()
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
