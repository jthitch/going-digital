"""
Custom forms for Course admin and contact.
"""
from django import forms
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html
from ckeditor.widgets import CKEditorWidget
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from core.models import User

from .models import (
    Content,
    Course,
    CourseCategory,
    CourseSkillLevel,
    Image,
    ImageCategory,
    ImageType,
    Assistant,
    County,
    Region,
    Tutor,
    Venue,
    Workshop,
    WorkshopType,
    COURSE_STATUS_CHOICES,
    COURSE_STATUS_DISPLAY_NAMES,
    LEVEL_DISPLAY_NAMES,
)


# Avoid rendering tens of thousands of <option> tags on the workshop change form.
_WORKSHOP_CLONE_CHOICES_LIMIT = 200
_WORKSHOP_IMAGE_CHOICES_LIMIT = 250


def _recent_workshops_queryset(exclude_pk=None, include_pk=None, owner_user_id=None):
    qs = Workshop.objects.select_related('course', 'venue').order_by('-date', '-id')
    if owner_user_id:
        qs = qs.filter(Q(user_id=owner_user_id) | Q(createdby_id=owner_user_id))
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    recent = list(qs[:_WORKSHOP_CLONE_CHOICES_LIMIT])
    pks = {w.pk for w in recent}
    if include_pk and include_pk not in pks:
        extra = Workshop.objects.select_related('course', 'venue').filter(pk=include_pk).first()
        if extra:
            recent.insert(0, extra)
    return Workshop.objects.filter(pk__in=[w.pk for w in recent]).order_by('-date', '-id')


def _workshop_image_queryset(include_pk=None):
    qs = Image.objects.filter(active=1).order_by('-id')
    if include_pk:
        qs = Image.objects.filter(Q(active=1) | Q(pk=include_pk)).order_by('-id')
    return qs[:_WORKSHOP_IMAGE_CHOICES_LIMIT]


CONTACT_REGION_CHOICES = [
    ('', 'Please select'),
    ('cotswolds', 'Cotswolds'),
    ('devon-cornwall', 'Devon & Cornwall'),
    ('east-anglia', 'East Anglia'),
    ('east-midlands', 'East Midlands'),
    ('east-of-england', 'East of England'),
    ('lake-district', 'Lake District'),
    ('lancashire', 'Lancashire'),
    ('london', 'London'),
    ('north-mid-wales', 'North and Mid Wales'),
    ('north-east', 'North East'),
    ('north-west', 'North West & North West Midlands'),
    ('scottish-highlands', 'Scottish Highlands & Islands'),
    ('south-coast', 'South & South Coast'),
    ('south-east', 'South East'),
    ('south-east-scotland', 'South East Scotland'),
    ('south-midlands', 'South Midlands'),
    ('south-west-scotland', 'South West Scotland'),
    ('west-england-south-wales', 'West of England & South Wales'),
    ('yorkshire', 'Yorkshire'),
    ('customer-services', 'Customer Services'),
]

def _legacy_01_checked(value):
    """Whether a legacy 0/1 (or boolean) value should show the toggle as on."""
    if value in (0, '0', False):
        return False
    if value in (1, '1', True):
        return True
    return False


class BooleanToggleWidget(forms.CheckboxInput):
    """AdminLTE/Jazzmin-style switch for legacy 0/1 integer fields."""

    def __init__(self, attrs=None):
        default_attrs = {'class': 'custom-control-input'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs, check_test=_legacy_01_checked)

    def render(self, name, value, attrs=None, renderer=None):
        value = _legacy_01_checked(value)
        html = super().render(name, value, attrs, renderer)
        input_id = (attrs or {}).get('id', f'id_{name}')
        return format_html(
            '<div class="custom-control custom-switch">{}'
            '<label class="custom-control-label" for="{}"></label>'
            '</div>',
            html,
            input_id,
        )


class CourseUrlHelpWidget(forms.Widget):
    """Read-only course URL preview for admin (no input box)."""

    def render(self, name, value, attrs=None, renderer=None):
        if value:
            return format_html(
                '<div class="help-block course-url-preview">{}</div>',
                value,
            )
        return format_html(
            '<div class="help-block course-url-preview">'
            'Enter a slug above to see the public course URL.'
            '</div>',
        )


VOUCHER_AMOUNT_CHOICES = [
    (5, '£5'),
    (10, '£10'),
    (20, '£20'),
    (25, '£25'),
    (50, '£50'),
    (75, '£75'),
    (100, '£100'),
    (200, '£200'),
    (250, '£250'),
]


class GiftVoucherRequestForm(forms.Form):
    """Form to request purchase of a gift voucher."""
    amount = forms.IntegerField(
        required=True,
        min_value=5,
        max_value=1000,
        label='Amount (£)',
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter amount',
            'min': 5,
            'max': 1000,
            'step': 1,
            'inputmode': 'numeric',
        })
    )
    quantity = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(1, 11)],
        coerce=int,
        required=True,
        label='Quantity',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your name',
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your email address',
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your phone number',
        })
    )
    recipient_name = forms.CharField(
        max_length=100,
        required=False,
        label='Recipient name (for gift message)',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Optional - who is the voucher for?',
        })
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Optional personal message for the recipient',
            'rows': 3,
        })
    )
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox(attrs={'data-theme': 'light'}),
        label='Please verify you are not a robot'
    )


class ContactForm(forms.Form):
    """Contact form for booking and workshop enquiries."""
    region = forms.ChoiceField(
        choices=CONTACT_REGION_CHOICES,
        required=True,
        label='Who would you like to contact?',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_region'})
    )
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Please enter your name',
            'id': 'id_name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Please enter your email address',
            'id': 'id_email'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Please enter your phone number',
            'id': 'id_phone'
        })
    )
    message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': "Don't forget to fill this in",
            'rows': 5,
            'id': 'id_message'
        })
    )
    security_answer = forms.IntegerField(
        required=True,
        label='Security question',
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Please answer this simple sum to proceed',
            'id': 'id_security_answer'
        })
    )

    def __init__(self, *args, security_question=None, expected_answer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.security_question = security_question or ''
        self.expected_answer = expected_answer
        if security_question:
            self.fields['security_answer'].label = f"Security question: what is {security_question} ?"

    def clean_security_answer(self):
        answer = self.cleaned_data.get('security_answer')
        if self.expected_answer is None:
            raise forms.ValidationError('Session expired. Please refresh the page and try again.')
        if answer != self.expected_answer:
            raise forms.ValidationError('Please answer the security question correctly.')
        return answer


class UserNameModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that shows gd_user full name in the dropdown."""

    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.email or f'User #{obj.pk}'


def _venue_admin_select_widget():
    """Native select — avoids Jazzmin Select2 mixing up options that share the same pk."""
    return forms.Select(attrs={'class': 'venue-admin-select'})


VENUE_CONTENT_FIELD_NAMES = (
    'content_title',
    'strapline',
    'main_content',
    'sub_content',
    'meta_title',
    'meta_description',
    'meta_keywords',
)


def venue_linked_content_initial(instance):
    """Initial values for gd_content fields on the venue admin form."""
    if not instance or not getattr(instance, 'pk', None):
        return {}
    if getattr(instance, 'content_id', None):
        try:
            instance = Venue.objects.get(pk=instance.pk)
        except Venue.DoesNotExist:
            return {}
    content = instance.get_content()
    if not content:
        return {}
    return {
        name: (getattr(content, name, None) or '')
        for name in VENUE_CONTENT_FIELD_NAMES
    }


def unique_venue_slug(source, *, exclude_pk=None):
    """Build a URL slug from venue name; append -2, -3, … if taken."""
    from django.utils.text import slugify

    base = slugify(source or '')[:255] or 'venue'
    slug = base
    n = 2
    while True:
        qs = Venue.objects.filter(slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        suffix = f'-{n}'
        slug = f'{base[: 255 - len(suffix)]}{suffix}'
        n += 1


class VenueAdminForm(forms.ModelForm):
    """Venue admin: legacy FKs as dropdowns; gd_content edited in Venue content fieldset."""

    approved = forms.BooleanField(
        required=False,
        label='Approved',
        widget=BooleanToggleWidget(),
    )
    content_title = forms.CharField(required=False, max_length=1000, label='Content title')
    strapline = forms.CharField(required=False, max_length=1000, label='Strapline')
    main_content = forms.CharField(
        required=False, widget=CKEditorWidget(config_name='default'), label='Main content',
    )
    sub_content = forms.CharField(
        required=False, widget=CKEditorWidget(config_name='default'), label='Sub content',
    )
    meta_title = forms.CharField(required=False, max_length=1000, label='Meta title')
    meta_description = forms.CharField(required=False, max_length=1000, label='Meta description')
    meta_keywords = forms.CharField(required=False, max_length=1000, label='Meta keywords')

    active = forms.BooleanField(
        required=False,
        label='Active',
        widget=BooleanToggleWidget(),
    )
    venue_region = forms.ModelChoiceField(
        queryset=Region.objects.filter(active=1).order_by('region_name'),
        required=False,
        empty_label='---------',
        label='Region',
        widget=_venue_admin_select_widget(),
    )
    status = forms.TypedChoiceField(
        choices=COURSE_STATUS_CHOICES,
        coerce=int,
        required=True,
        label='Status',
        widget=_venue_admin_select_widget(),
    )
    venue_user = UserNameModelChoiceField(
        queryset=User.objects.all().order_by('lastname', 'firstname'),
        required=False,
        empty_label='---------',
        label='User',
        widget=_venue_admin_select_widget(),
    )
    county = forms.ModelChoiceField(
        queryset=County.objects.filter(active=1).order_by('county'),
        required=False,
        empty_label='---------',
        label='County',
        widget=_venue_admin_select_widget(),
    )

    class Meta:
        model = Venue
        fields = [
            'active',
            'status',
            'venue_region',
            'venue_user',
            'county',
            'venue_name',
            'location',
            'slug',
            'venue_address',
            'venue_telephone',
            'venue_url',
            'latitude',
            'longitude',
            'show_workshops',
            'created_at',
            'updated_at',
        ]

    def __init__(self, *args, region_ids=None, franchisee_mode=False, editor_user_id=None, **kwargs):
        self.region_ids = region_ids
        self.franchisee_mode = franchisee_mode
        self.editor_user_id = editor_user_id
        instance = kwargs.get('instance')
        content_initial = venue_linked_content_initial(instance)
        if content_initial:
            initial = dict(kwargs.get('initial') or {})
            for name, value in content_initial.items():
                initial.setdefault(name, value)
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        if self.franchisee_mode:
            for name in ('venue_user', 'status', 'active', 'approved'):
                self.fields.pop(name, None)
            if region_ids is not None:
                region_qs = Region.objects.filter(active=1, pk__in=region_ids)
                if self.instance.pk and self.instance.region_id:
                    region_qs = Region.objects.filter(
                        Q(pk=self.instance.region_id) | Q(active=1, pk__in=region_ids)
                    )
                self.fields['venue_region'].queryset = region_qs.order_by('region_name')
                if len(region_ids) == 1 and not self.instance.pk:
                    self.fields['venue_region'].initial = self.fields['venue_region'].queryset.first()
        else:
            if self.instance.pk:
                self.fields['approved'].initial = _legacy_01_checked(self.instance.approved)
            else:
                self.fields['approved'].initial = False
        if 'active' in self.fields:
            if self.instance.pk:
                self.fields['active'].initial = _legacy_01_checked(self.instance.active)
            elif not self.franchisee_mode:
                self.fields['active'].initial = True
        if self.instance.pk and self.instance.region_id and 'venue_region' in self.fields:
            region = Region.objects.filter(pk=self.instance.region_id).first()
            if region:
                self.fields['venue_region'].initial = region
                if region.active != 1:
                    self.fields['venue_region'].queryset = (
                        Region.objects.filter(pk=region.pk)
                        | self.fields['venue_region'].queryset
                    ).order_by('region_name')
        if self.instance.pk and self.instance.county_id:
            county = County.objects.filter(pk=self.instance.county_id).first()
            if county:
                self.fields['county'].initial = county
                if county.active != 1:
                    self.fields['county'].queryset = (
                        County.objects.filter(pk=county.pk) | County.objects.filter(active=1)
                    ).order_by('county')
        if 'venue_user' in self.fields and self.instance.pk and self.instance.user_id:
            self.fields['venue_user'].initial = User.objects.filter(pk=self.instance.user_id).first()
        if content_initial:
            for name, value in content_initial.items():
                if name in self.fields:
                    self.fields[name].initial = value
        if 'status' in self.fields and not self.is_bound:
            status_id = self.instance.status_id if self.instance.pk else 2
            if status_id in COURSE_STATUS_DISPLAY_NAMES:
                self.fields['status'].initial = status_id
            elif status_id is not None:
                label = f'Status #{status_id}'
                self.fields['status'].choices = COURSE_STATUS_CHOICES + ((status_id, label),)
                self.fields['status'].initial = status_id

    def save(self, commit=True):
        from django.utils import timezone

        venue = super().save(commit=False)
        now = timezone.now()
        venue_region = self.cleaned_data.get('venue_region')
        venue.region_id = venue_region.pk if venue_region else None
        county = self.cleaned_data.get('county')
        venue.county_id = county.pk if county else None

        if not (venue.slug or '').strip() and (venue.venue_name or '').strip():
            venue.slug = unique_venue_slug(
                venue.venue_name,
                exclude_pk=venue.pk if venue.pk else None,
            )

        if self.franchisee_mode:
            venue.status_id = 2
            venue.updatedby_id = self.editor_user_id
            venue.updated_at = now
            if not self.instance.pk:
                venue.active = 0
                venue.approved = 0
                venue.rejected = 0
                venue.approval_requested = 1
                venue.user_id = self.editor_user_id
                venue.approval_requested_by_id = self.editor_user_id
                venue.approval_requested_at = now
                venue.createdby_id = self.editor_user_id
            elif venue.rejected == 1:
                venue.rejected = 0
                venue.approval_requested = 1
                venue.approval_requested_by_id = self.editor_user_id
                venue.approval_requested_at = now
                venue.reject_reason = None
        else:
            venue.active = 1 if self.cleaned_data.get('active') else 0
            venue.status_id = self.cleaned_data.get('status', 2)
            venue_user = self.cleaned_data.get('venue_user')
            venue.user_id = venue_user.pk if venue_user else None
            was_approved = self.instance.pk and self.instance.approved == 1
            venue.approved = 1 if self.cleaned_data.get('approved') else 0
            if venue.approved and not was_approved:
                venue.approvedby_id = self.editor_user_id
                venue.approved_at = now
                venue.rejected = 0
                venue.reject_reason = None
                venue.approval_requested = 0
            venue.updatedby_id = self.editor_user_id
            venue.updated_at = now

        if commit:
            venue.save()
            self._save_content(venue)
        return venue

    def _content_fields_in_post(self):
        if not self.is_bound:
            return True
        return any(name in self.data for name in VENUE_CONTENT_FIELD_NAMES)

    def _save_content(self, venue, request=None):
        """Update or create gd_content linked via venue.content_id."""
        from django.utils import timezone

        now = timezone.now()
        user_id = None
        if request and getattr(request, 'user', None):
            user_id = request.user.id
        elif self.editor_user_id:
            user_id = self.editor_user_id
        content = venue.get_content()
        if (
            self.franchisee_mode
            and content
            and not self._content_fields_in_post()
        ):
            return
        if content:
            content.content_title = self.cleaned_data.get('content_title') or ''
            content.strapline = self.cleaned_data.get('strapline') or ''
            content.main_content = self.cleaned_data.get('main_content') or ''
            content.sub_content = self.cleaned_data.get('sub_content') or ''
            content.meta_title = self.cleaned_data.get('meta_title') or ''
            content.meta_description = self.cleaned_data.get('meta_description') or ''
            content.meta_keywords = self.cleaned_data.get('meta_keywords') or ''
            content.updatedby_id = user_id
            content.updated_at = now
            content.save()
        elif self.cleaned_data.get('main_content') or self.cleaned_data.get('content_title'):
            content = Content.objects.create(
                content_title=self.cleaned_data.get('content_title') or venue.venue_name or '',
                header_content='',
                strapline=self.cleaned_data.get('strapline') or '',
                main_content=self.cleaned_data.get('main_content') or '',
                sub_content=self.cleaned_data.get('sub_content') or '',
                footer_content='',
                meta_title=self.cleaned_data.get('meta_title') or '',
                meta_description=self.cleaned_data.get('meta_description') or '',
                meta_keywords=self.cleaned_data.get('meta_keywords') or '',
                createdby_id=user_id,
                updatedby_id=user_id,
                created_at=now,
                updated_at=now,
            )
            venue.content_id = content.pk
            venue.save(update_fields=['content_id'])


class ImageAdminForm(forms.ModelForm):
    """Image admin: legacy integer FKs as labeled dropdowns."""

    image_type = forms.ModelChoiceField(
        queryset=ImageType.objects.filter(active=1).order_by('image_type'),
        required=False,
        empty_label='---------',
        label='Image type',
    )
    image_category = forms.ModelChoiceField(
        queryset=ImageCategory.objects.all().order_by('category'),
        required=False,
        empty_label='---------',
        label='Image category',
    )
    image_user = UserNameModelChoiceField(
        queryset=User.objects.all().order_by('lastname', 'firstname'),
        required=False,
        empty_label='---------',
        label='User',
    )
    active = forms.BooleanField(
        required=False,
        label='Active',
        widget=BooleanToggleWidget(),
    )

    class Meta:
        model = Image
        fields = '__all__'
        exclude = ['image_type_id', 'image_category_id', 'user_id', 'checksum', 'converted']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['active'].initial = _legacy_01_checked(self.instance.active)
        else:
            self.fields['active'].initial = True
        if self.instance.pk and self.instance.image_type_id:
            current = ImageType.objects.filter(pk=self.instance.image_type_id).first()
            if current:
                self.fields['image_type'].initial = current
                if current.active != 1:
                    self.fields['image_type'].queryset = (
                        ImageType.objects.filter(pk=current.pk)
                        | ImageType.objects.filter(active=1)
                    ).order_by('image_type')
        if self.instance.pk and self.instance.image_category_id:
            self.fields['image_category'].initial = ImageCategory.objects.filter(
                pk=self.instance.image_category_id
            ).first()
        if self.instance.pk and self.instance.user_id:
            self.fields['image_user'].initial = User.objects.filter(pk=self.instance.user_id).first()

    def save(self, commit=True):
        image = super().save(commit=False)
        image.active = 1 if self.cleaned_data.get('active') else 0
        image_type = self.cleaned_data.get('image_type')
        image.image_type_id = image_type.pk if image_type else None
        image_category = self.cleaned_data.get('image_category')
        image.image_category_id = image_category.pk if image_category else None
        image_user = self.cleaned_data.get('image_user')
        image.user_id = image_user.pk if image_user else None
        if commit:
            image.save()
        return image


class CourseSkillLevelAdminForm(forms.ModelForm):
    """Skill level admin: show Beginner, Intermediate, etc. instead of legacy numeric strings."""

    skill_level = forms.ChoiceField(
        choices=[(name, name) for name in LEVEL_DISPLAY_NAMES.values()],
        label='Skill level',
    )

    class Meta:
        model = CourseSkillLevel
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            display = LEVEL_DISPLAY_NAMES.get(self.instance.pk) or self.instance.skill_level
            if display in dict(self.fields['skill_level'].choices):
                self.fields['skill_level'].initial = display


class CourseCategoryAdminForm(forms.ModelForm):
    """Course category admin: legacy 0/1 flags as boolean toggles."""

    active = forms.BooleanField(required=False, label='Active', widget=BooleanToggleWidget())
    exclude_from_course_list = forms.BooleanField(
        required=False,
        label='Exclude from course list',
        widget=BooleanToggleWidget(),
    )

    class Meta:
        model = CourseCategory
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['active'].initial = _legacy_01_checked(self.instance.active)
            self.fields['exclude_from_course_list'].initial = _legacy_01_checked(
                self.instance.exclude_from_course_list
            )

    def save(self, commit=True):
        category = super().save(commit=False)
        category.active = 1 if self.cleaned_data.get('active') else 0
        category.exclude_from_course_list = 1 if self.cleaned_data.get('exclude_from_course_list') else 0
        if commit:
            category.save()
        return category


class WorkshopAdminForm(forms.ModelForm):
    """Workshop admin: legacy integer FKs as labeled dropdowns."""

    active = forms.BooleanField(
        required=False,
        label='Active',
        widget=BooleanToggleWidget(),
    )
    cameras_available = forms.BooleanField(
        required=False,
        label='Cameras available',
        widget=BooleanToggleWidget(),
    )
    strapline = forms.CharField(
        required=False,
        widget=CKEditorWidget(config_name='default'),
        label='Strapline',
    )
    byline = forms.CharField(
        required=False,
        widget=CKEditorWidget(config_name='default'),
        label='Byline',
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.filter(active=1).order_by('region_name'),
        required=False,
        empty_label='---------',
        label='Region',
    )
    tutor = forms.ModelChoiceField(
        queryset=Tutor.objects.all().order_by('lastname', 'firstname'),
        required=False,
        empty_label='---------',
        label='Tutor',
    )
    assistant = forms.ModelChoiceField(
        queryset=Assistant.objects.all().order_by('lastname', 'firstname'),
        required=False,
        empty_label='---------',
        label='Assistant',
    )
    alt_course = forms.ModelChoiceField(
        queryset=Course.objects.all().order_by('course_name'),
        required=False,
        empty_label='---------',
        label='Alt course',
    )
    workshop_type = forms.ModelChoiceField(
        queryset=WorkshopType.objects.all().order_by('workshop_type'),
        required=False,
        empty_label='---------',
        label='Workshop type',
    )
    cloned_from_workshop = forms.ModelChoiceField(
        queryset=Workshop.objects.none(),
        required=False,
        empty_label='---------',
        label='Cloned from workshop',
    )
    image = forms.ModelChoiceField(
        queryset=Image.objects.none(),
        required=False,
        empty_label='---------',
        label='Existing image',
        help_text='Pick a previously uploaded image, or upload a new file below.',
    )
    image_upload = forms.ImageField(
        required=False,
        label='Upload image',
        help_text='Optional. JPG, PNG, GIF, or WebP up to 10 MB.',
    )

    class Meta:
        model = Workshop
        fields = '__all__'
        exclude = [
            'region_id',
            'tutor_id',
            'assistant_id',
            'user_id',
            'alt_course_id',
            'workshop_type_id',
            'cloned_from_workshop_id',
            'createdby_id',
            'updatedby_id',
            'image_id',
            'sticky',
            'checksum',
        ]

    def __init__(self, *args, region_ids=None, editor_user_id=None, **kwargs):
        self.region_ids = region_ids
        self.editor_user_id = editor_user_id
        super().__init__(*args, **kwargs)
        if region_ids is not None:
            from django.db.models import Q

            region_qs = Region.objects.filter(active=1, pk__in=region_ids).order_by('region_name')
            self.fields['region'].queryset = region_qs
            course_qs = Course.objects.filter(
                Q(region_id__isnull=True) | Q(region_id__in=region_ids)
            ).order_by('course_name')
            self.fields['alt_course'].queryset = course_qs
            if 'course' in self.fields:
                self.fields['course'].queryset = course_qs
            if 'venue' in self.fields and self.editor_user_id:
                from core.models import User
                from .region_scope import filter_venues_for_workshop_picker, venue_is_approved

                editor = User.objects.filter(pk=self.editor_user_id).first()
                if editor:
                    self.fields['venue'].queryset = filter_venues_for_workshop_picker(
                        Venue.objects.all().order_by('venue_name'),
                        editor,
                    )
            if len(region_ids) == 1 and not self.instance.pk:
                self.fields['region'].initial = region_qs.first()
        if self.instance.pk:
            self.fields['active'].initial = _legacy_01_checked(self.instance.active)
            self.fields['cameras_available'].initial = _legacy_01_checked(self.instance.cameras_available)
        else:
            self.fields['active'].initial = False if self.region_ids is not None else True
        exclude_pk = self.instance.pk if self.instance.pk else None
        clone_include = self.instance.cloned_from_workshop_id if self.instance.pk else None
        clone_qs = _recent_workshops_queryset(
            exclude_pk=exclude_pk,
            include_pk=clone_include,
            owner_user_id=self.editor_user_id if region_ids is not None else None,
        )
        if region_ids is not None:
            clone_qs = clone_qs.filter(region_id__in=region_ids)
        self.fields['cloned_from_workshop'].queryset = clone_qs
        image_include = self.instance.image_id if self.instance.pk and self.instance.image_id else None
        self.fields['image'].queryset = _workshop_image_queryset(include_pk=image_include)
        self._set_initial_from_id('region', Region, 'region_id')
        self._set_initial_from_id('tutor', Tutor, 'tutor_id')
        self._set_initial_from_id('assistant', Assistant, 'assistant_id')
        self._set_initial_from_id('alt_course', Course, 'alt_course_id', skip_zero=True)
        self._set_initial_from_id('workshop_type', WorkshopType, 'workshop_type_id')
        self._set_initial_from_id('cloned_from_workshop', Workshop, 'cloned_from_workshop_id')
        self._set_initial_from_id('image', Image, 'image_id', skip_zero=True)
        if 'image_upload' in self.fields:
            self.fields['image_upload'].widget.attrs.setdefault('accept', 'image/*')
        self._order_image_fields()

    def _order_image_fields(self):
        if 'image' not in self.fields or 'image_upload' not in self.fields:
            return
        order = list(self.fields.keys())
        order.remove('image_upload')
        order.insert(order.index('image') + 1, 'image_upload')
        self.order_fields(order)

    def _set_initial_from_id(self, field_name, model, id_attr, skip_zero=False):
        if not self.instance.pk:
            return
        pk = getattr(self.instance, id_attr, None)
        if pk is None or (skip_zero and pk == 0):
            return
        obj = model.objects.filter(pk=pk).first()
        if obj and field_name in self.fields:
            self.fields[field_name].initial = obj

    def clean(self):
        from .region_scope import venue_is_approved

        cleaned = super().clean()
        if self.region_ids is not None:
            region = cleaned.get('region')
            if not region:
                raise forms.ValidationError({'region': 'Region is required.'})
            if region.pk not in self.region_ids:
                raise forms.ValidationError({'region': 'You are not assigned to this region.'})
            course = cleaned.get('course')
            if course and course.region_id and course.region_id not in self.region_ids:
                raise forms.ValidationError({'course': 'This course is not available in your regions.'})
            alt = cleaned.get('alt_course')
            if alt and alt.region_id and alt.region_id not in self.region_ids:
                raise forms.ValidationError({'alt_course': 'This course is not available in your regions.'})
            venue = cleaned.get('venue')
            if venue and venue.region_id and venue.region_id not in self.region_ids:
                raise forms.ValidationError({'venue': 'This venue is not in your regions.'})
            if cleaned.get('active') and venue and not venue_is_approved(venue):
                raise forms.ValidationError({
                    'active': (
                        'This workshop cannot be published until the venue is approved. '
                        'Add or select a venue under Venues and wait for administrator approval.'
                    ),
                })
        upload = cleaned.get('image_upload')
        if upload:
            from .gd_image_upload import ALLOWED_IMAGE_EXTENSIONS, MAX_UPLOAD_BYTES

            ext = '.' + upload.name.rsplit('.', 1)[-1].lower() if '.' in upload.name else ''
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise forms.ValidationError({
                    'image_upload': 'Unsupported image type. Use JPG, PNG, GIF, or WebP.',
                })
            if upload.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError({
                    'image_upload': 'Image must be 10 MB or smaller.',
                })
        return cleaned

    def save(self, commit=True):
        workshop = super().save(commit=False)
        workshop.active = 1 if self.cleaned_data.get('active') else 0
        workshop.cameras_available = 1 if self.cleaned_data.get('cameras_available') else 0
        region = self.cleaned_data.get('region')
        workshop.region_id = region.pk if region else None
        tutor = self.cleaned_data.get('tutor')
        workshop.tutor_id = tutor.pk if tutor else None
        assistant = self.cleaned_data.get('assistant')
        workshop.assistant_id = assistant.pk if assistant else None
        alt_course = self.cleaned_data.get('alt_course')
        workshop.alt_course_id = alt_course.pk if alt_course else 0
        workshop_type = self.cleaned_data.get('workshop_type')
        workshop.workshop_type_id = workshop_type.pk if workshop_type else None
        cloned = self.cleaned_data.get('cloned_from_workshop')
        workshop.cloned_from_workshop_id = cloned.pk if cloned else None
        upload = self.cleaned_data.get('image_upload')
        if upload:
            from .gd_image_upload import create_gd_image_from_upload

            course = self.cleaned_data.get('course')
            label = course.course_name if course else (workshop.course.course_name if workshop.course else '')
            gd_image = create_gd_image_from_upload(
                upload,
                user_id=self.editor_user_id,
                source_name=label,
                description=f'Workshop image: {label}'[:1000],
            )
            workshop.image_id = gd_image.pk
        else:
            image = self.cleaned_data.get('image')
            workshop.image_id = image.pk if image else 0
        if commit:
            workshop.save()
        return workshop


class CourseAdminForm(forms.ModelForm):
    """
    Course admin form with inline Content fields.
    Edit the linked Content's page content, meta, etc. directly when editing a course.
    """
    # Content fields (editable when course has content, or when creating new content)
    content_title = forms.CharField(required=False, max_length=1000, label='Content title')
    strapline = forms.CharField(required=False, max_length=1000, label='Strapline')
    main_content = forms.CharField(required=False, widget=CKEditorWidget(config_name='default'), label='Main content')
    sub_content = forms.CharField(required=False, widget=CKEditorWidget(config_name='default'), label='Sub content')
    meta_title = forms.CharField(required=False, max_length=1000, label='Meta title')
    meta_description = forms.CharField(required=False, max_length=1000, label='Meta description')
    meta_keywords = forms.CharField(required=False, max_length=1000, label='Meta keywords')
    region = forms.ModelChoiceField(
        queryset=Region.objects.filter(active=1).order_by('region_name'),
        required=False,
        empty_label='---------',
        label='Region',
    )
    status = forms.TypedChoiceField(
        choices=COURSE_STATUS_CHOICES,
        coerce=int,
        required=True,
        label='Status',
    )
    course_url = forms.CharField(
        required=False,
        label='Course URL',
        widget=CourseUrlHelpWidget(),
    )

    class Meta:
        model = Course
        fields = '__all__'
        exclude = ['region_id', 'status_id']

    @staticmethod
    def course_url_path(slug):
        slug = (slug or '').strip()
        if not slug:
            return ''
        return reverse('courses:course_detail', kwargs={'slug': slug})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        slug = ''
        if self.is_bound:
            slug = self.data.get('slug', '')
        elif self.instance.pk:
            slug = self.instance.slug or ''
        self.fields['course_url'].initial = self.course_url_path(slug)
        if self.instance.pk and self.instance.region_id:
            self.fields['region'].initial = Region.objects.filter(pk=self.instance.region_id).first()
        if not self.is_bound:
            status_id = self.instance.status_id if self.instance.pk else 2
            if status_id in COURSE_STATUS_DISPLAY_NAMES:
                self.fields['status'].initial = status_id
            elif status_id is not None:
                label = f'Status #{status_id}'
                self.fields['status'].choices = COURSE_STATUS_CHOICES + ((status_id, label),)
                self.fields['status'].initial = status_id
        content = getattr(self.instance, 'content', None) if self.instance.pk else None
        if content:
            self.fields['content_title'].initial = content.content_title
            self.fields['strapline'].initial = content.strapline
            self.fields['main_content'].initial = content.main_content
            self.fields['sub_content'].initial = content.sub_content
            self.fields['meta_title'].initial = content.meta_title
            self.fields['meta_description'].initial = content.meta_description
            self.fields['meta_keywords'].initial = content.meta_keywords

    def save(self, commit=True):
        course = super().save(commit=False)
        region = self.cleaned_data.get('region')
        course.region_id = region.pk if region else None
        course.status_id = self.cleaned_data.get('status', 2)
        if commit:
            course.save()
            self._save_content(course)
        return course

    def _save_content(self, course, request=None):
        """Update or create linked Content from form data. Called from admin save_model."""
        from django.utils import timezone
        now = timezone.now()
        user_id = request.user.id if request and request.user else None
        content = getattr(course, 'content', None)
        if content:
            content.content_title = self.cleaned_data.get('content_title') or ''
            content.strapline = self.cleaned_data.get('strapline') or ''
            content.main_content = self.cleaned_data.get('main_content') or ''
            content.sub_content = self.cleaned_data.get('sub_content') or ''
            content.meta_title = self.cleaned_data.get('meta_title') or ''
            content.meta_description = self.cleaned_data.get('meta_description') or ''
            content.meta_keywords = self.cleaned_data.get('meta_keywords') or ''
            content.updatedby_id = user_id
            content.updated_at = now
            content.save()
        elif self.cleaned_data.get('main_content') or self.cleaned_data.get('content_title'):
            content = Content.objects.create(
                content_title=self.cleaned_data.get('content_title') or course.course_name or '',
                header_content='',
                strapline=self.cleaned_data.get('strapline') or '',
                main_content=self.cleaned_data.get('main_content') or '',
                sub_content=self.cleaned_data.get('sub_content') or '',
                footer_content='',
                meta_title=self.cleaned_data.get('meta_title') or '',
                meta_description=self.cleaned_data.get('meta_description') or '',
                meta_keywords=self.cleaned_data.get('meta_keywords') or '',
                createdby_id=user_id,
                updatedby_id=user_id,
                created_at=now,
                updated_at=now,
            )
            course.content = content
            course.save(update_fields=['content'])
