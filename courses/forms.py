"""
Custom forms for Course admin and contact.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django import forms
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from ckeditor.widgets import CKEditorWidget
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from core.models import User

from .display_images import workshop_gallery_image_ids
from .gd_image_upload import upload_help_text, validate_image_upload
from .workshop_duplicate import CLONED_FROM_WORKSHOP_INITIAL_KEY
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
    WorkshopGalleryImage,
    WorkshopType,
    COURSE_STATUS_CHOICES,
    COURSE_STATUS_DISPLAY_NAMES,
    LEVEL_DISPLAY_NAMES,
)


# Avoid rendering tens of thousands of <option> tags on the workshop change form.
_WORKSHOP_IMAGE_CHOICES_LIMIT = 250


def _image_owned_by_user(image, user_id):
    if not image or not user_id:
        return False
    return image.user_id == user_id or image.createdby_id == user_id


def _workshop_image_queryset(include_pks=None, owner_user_id=None):
    """Images for workshop picker; limited to images the current user uploaded."""
    include_pks = [pk for pk in (include_pks or []) if pk]
    qs = Image.objects.filter(active=1)
    if owner_user_id:
        qs = qs.filter(Q(user_id=owner_user_id) | Q(createdby_id=owner_user_id))
    qs = qs.order_by('-id')
    pks = list(qs.values_list('pk', flat=True)[:_WORKSHOP_IMAGE_CHOICES_LIMIT])
    for include_pk in include_pks:
        if include_pk not in pks:
            extra = Image.objects.filter(pk=include_pk).first()
            if extra and (not owner_user_id or _image_owned_by_user(extra, owner_user_id)):
                pks.insert(0, include_pk)
    pks = pks[:_WORKSHOP_IMAGE_CHOICES_LIMIT]
    return Image.objects.filter(pk__in=pks).order_by('-id')


def _workshop_image_option_label(obj):
    caption = obj.source_name or obj.file_name or f'Image #{obj.pk}'
    if not obj.url:
        return caption
    return format_html(
        '<span class="gd-workshop-image-option">'
        '<img src="{}" alt="" class="gd-workshop-image-thumb" loading="lazy">'
        '<span class="gd-workshop-image-caption">{}</span>'
        '</span>',
        obj.url,
        caption,
    )


def _sync_workshop_gallery(workshop, image_ids):
    """Replace workshop gallery links with the selected image ids (ordered)."""
    if not workshop or not workshop.pk:
        return

    ordered_ids = []
    seen = set()
    for image_id in image_ids or []:
        try:
            normalised = int(image_id)
        except (TypeError, ValueError):
            continue
        if normalised and normalised not in seen:
            seen.add(normalised)
            ordered_ids.append(normalised)

    existing = {
        int(link.image_id): link
        for link in WorkshopGalleryImage.objects.filter(workshop_id=workshop.pk)
    }
    keep = set()
    for order, image_id in enumerate(ordered_ids):
        keep.add(image_id)
        link = existing.get(image_id)
        if link:
            if link.display_order != order:
                link.display_order = order
                link.save(update_fields=['display_order'])
            continue
        link, _created = WorkshopGalleryImage.objects.get_or_create(
            workshop_id=workshop.pk,
            image_id=image_id,
            defaults={'display_order': order},
        )
        if link.display_order != order:
            link.display_order = order
            link.save(update_fields=['display_order'])
        existing[image_id] = link

    WorkshopGalleryImage.objects.filter(workshop_id=workshop.pk).exclude(
        image_id__in=keep,
    ).delete()


class WorkshopImagesModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Workshop image picker with thumbnail previews; select multiple."""

    widget = forms.CheckboxSelectMultiple(attrs={'class': 'gd-workshop-image-picker'})

    def label_from_instance(self, obj):
        return _workshop_image_option_label(obj)


def _legacy_01_checked(value):
    """Whether a legacy 0/1 (or boolean) value should show the toggle as on."""
    if value in (0, '0', False):
        return False
    if value in (1, '1', True):
        return True
    return False


def _local_datetime(dt):
    """Return a naive local datetime for admin date/time widgets."""
    if dt and timezone.is_aware(dt):
        return timezone.localtime(dt)
    return dt


def _assign_model_choice_fk(instance, cleaned_data, field_name, attr_name, *, zero_for_empty=False):
    """Set a legacy *_id column from a ModelChoiceField value."""
    value = cleaned_data.get(field_name)
    if value:
        setattr(instance, attr_name, value.pk)
    elif zero_for_empty:
        setattr(instance, attr_name, 0)
    else:
        setattr(instance, attr_name, None)


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


class HTML5SplitDateTimeWidget(forms.MultiWidget):
    """Native browser date/time pickers for workshop admin (no Django calendar JS)."""

    template_name = 'courses/widgets/workshop_split_datetime.html'

    def __init__(self, attrs=None):
        widgets = (
            forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'gd-workshop-date-input'},
            ),
            forms.TimeInput(
                format='%H:%M',
                attrs={'type': 'time', 'class': 'gd-workshop-time-input', 'step': '60'},
            ),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            value = _local_datetime(value)
            return [value.date(), value.time().replace(second=0, microsecond=0)]
        return [None, None]


class HTML5SplitDateTimeField(forms.SplitDateTimeField):
    """Workshop datetime using HTML5 date and time inputs."""

    widget = HTML5SplitDateTimeWidget
    input_date_formats = ['%Y-%m-%d']
    input_time_formats = ['%H:%M:%S', '%H:%M']


class VenuePostcodeLookupWidget(forms.TextInput):
    """Postcode field with a visible Look up control (JS wires the click handler)."""

    class Media:
        js = ('courses/js/admin-venue.js',)

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(self.attrs, attrs)
        css_class = final_attrs.get('class', '')
        final_attrs['class'] = f'{css_class} venue-postcode-lookup-input'.strip()
        input_html = super().render(name, value, final_attrs, renderer)
        return format_html(
            '<div class="venue-postcode-lookup-wrap">'
            '{}'
            '<button type="button" class="button venue-postcode-lookup-btn">Look up</button>'
            '</div>',
            input_html,
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
        required=False,
        label='Phone',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Optional phone number',
            'id': 'id_phone'
        })
    )
    order_number = forms.CharField(
        max_length=64,
        required=False,
        label='Order number',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Optional order or booking reference',
            'id': 'id_order_number',
            'autocomplete': 'off',
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
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox(attrs={'data-theme': 'light'}),
        label='Please verify you are not a robot'
    )


class UserNameModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that shows gd_user full name and email in the dropdown."""

    def label_from_instance(self, obj):
        name = (obj.get_full_name() or '').strip()
        email = (obj.email or '').strip()
        if name and email:
            return f'{name} ({email})'
        return name or email or f'User #{obj.pk}'


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
    from courses.venue_approval import (
        get_venue_content_change_request,
        live_venue_content_values,
    )

    if not instance or not getattr(instance, 'pk', None):
        return {}
    # Franchisee edits on approved venues load pending/rejected proposals first.
    change = get_venue_content_change_request(instance)
    if change and instance.approved == 1:
        return change.as_content_dict()
    if getattr(instance, 'content_id', None):
        try:
            instance = Venue.objects.get(pk=instance.pk)
        except Venue.DoesNotExist:
            return {}
    return live_venue_content_values(instance)


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

    approval_decision = forms.ChoiceField(
        choices=(),  # set in __init__ from venue_approval helpers
        required=True,
        label='Approval',
        help_text='Approve so franchisees can publish workshops at this venue.',
        widget=_venue_admin_select_widget(),
    )
    reject_reason = forms.CharField(
        required=False,
        label='Reject reason',
        help_text='Shown to the franchisee when the venue is rejected.',
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    content_change_decision = forms.ChoiceField(
        choices=(),
        required=False,
        label='Pending content changes',
        help_text='Approve to publish the franchisee\'s proposed content, or reject with a reason.',
        widget=_venue_admin_select_widget(),
    )
    content_change_reject_reason = forms.CharField(
        required=False,
        label='Content reject reason',
        help_text='Shown to the franchisee when content changes are rejected.',
        widget=forms.Textarea(attrs={'rows': 2}),
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
        help_text='When on, this venue can appear on the public site.',
        widget=BooleanToggleWidget(),
    )
    venue_region = forms.ModelChoiceField(
        queryset=Region.objects.filter(active=1).order_by('region_name'),
        required=False,
        empty_label='---------',
        label='Region',
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
    postcode_lookup = forms.CharField(
        required=False,
        label='Postcode lookup',
        help_text='Enter a UK postcode and click Look up to fill the address and map coordinates.',
        widget=VenuePostcodeLookupWidget(attrs={
            'placeholder': 'e.g. GL54 1AB',
            'autocomplete': 'postal-code',
        }),
    )
    add_document_to_booking_email = forms.BooleanField(
        required=False,
        label='Add to booking email',
        help_text='Attach this venue document to booking confirmation emails.',
        widget=BooleanToggleWidget(),
    )

    class Meta:
        model = Venue
        fields = [
            'active',
            'venue_region',
            'venue_user',
            'county',
            'venue_name',
            'slug',
            'venue_address',
            'location',
            'venue_telephone',
            'venue_url',
            'latitude',
            'longitude',
            'show_workshops',
            'created_at',
            'updated_at',
        ]
        widgets = {
            'venue_url': forms.TextInput(attrs={
                'placeholder': 'https://',
                'inputmode': 'url',
            }),
        }

    def __init__(self, *args, region_ids=None, franchisee_mode=False, editor_user_id=None, **kwargs):
        from courses.venue_approval import (
            CONTENT_CHANGE_DECISION_CHOICES,
            VENUE_APPROVAL_DECISION_CHOICES,
            get_venue_content_change_request,
            venue_approval_state,
        )

        self.region_ids = region_ids
        self.franchisee_mode = franchisee_mode
        self.editor_user_id = editor_user_id
        instance = kwargs.get('instance')
        self.content_only_mode = bool(
            franchisee_mode
            and instance
            and getattr(instance, 'pk', None)
            and instance.approved == 1
        )
        content_initial = venue_linked_content_initial(instance)
        if content_initial:
            initial = dict(kwargs.get('initial') or {})
            for name, value in content_initial.items():
                initial.setdefault(name, value)
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        if self.franchisee_mode:
            for name in (
                'venue_user',
                'active',
                'approval_decision',
                'content_change_decision',
                'content_change_reject_reason',
            ):
                self.fields.pop(name, None)
            if self.content_only_mode:
                for name in (
                    'venue_region',
                    'county',
                    'venue_name',
                    'slug',
                    'postcode_lookup',
                    'venue_address',
                    'location',
                    'venue_telephone',
                    'venue_url',
                    'latitude',
                    'longitude',
                    'show_workshops',
                    'add_document_to_booking_email',
                ):
                    self.fields.pop(name, None)
            elif region_ids is not None:
                region_qs = Region.objects.filter(active=1, pk__in=region_ids)
                if self.instance.pk and self.instance.region_id:
                    region_qs = Region.objects.filter(
                        Q(pk=self.instance.region_id) | Q(active=1, pk__in=region_ids)
                    )
                self.fields['venue_region'].queryset = region_qs.order_by('region_name')
                if len(region_ids) == 1 and not self.instance.pk:
                    self.fields['venue_region'].initial = self.fields['venue_region'].queryset.first()
        elif 'approval_decision' in self.fields:
            self.fields['approval_decision'].choices = VENUE_APPROVAL_DECISION_CHOICES
            if not self.is_bound:
                self.fields['approval_decision'].initial = venue_approval_state(self.instance)
            if 'reject_reason' in self.fields and self.instance.pk and not self.is_bound:
                self.fields['reject_reason'].initial = self.instance.reject_reason or ''
            change = get_venue_content_change_request(self.instance) if self.instance.pk else None
            if change and change.is_pending:
                self.fields['content_change_decision'].choices = CONTENT_CHANGE_DECISION_CHOICES
                if not self.is_bound:
                    self.fields['content_change_decision'].initial = ''
                    self.fields['content_change_reject_reason'].initial = change.reject_reason or ''
            else:
                self.fields.pop('content_change_decision', None)
                self.fields.pop('content_change_reject_reason', None)
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
        if self.instance.pk and self.instance.county_id and 'county' in self.fields:
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
        if self.instance.pk and self.instance.document_id and 'add_document_to_booking_email' in self.fields:
            from courses.venue_documents import venue_document_email_enabled

            self.fields['add_document_to_booking_email'].initial = venue_document_email_enabled(
                self.instance.pk,
            )
        elif 'add_document_to_booking_email' in self.fields:
            self.fields.pop('add_document_to_booking_email', None)

    def clean(self):
        from courses.venue_approval import (
            CONTENT_CHANGE_REJECT,
            VENUE_APPROVAL_REJECTED,
        )

        cleaned = super().clean()
        if self.franchisee_mode:
            return cleaned

        if 'approval_decision' in self.fields:
            decision = cleaned.get('approval_decision')
            reason = (cleaned.get('reject_reason') or '').strip()
            if decision == VENUE_APPROVAL_REJECTED and not reason:
                self.add_error(
                    'reject_reason',
                    'Enter a reject reason when setting approval to Rejected.',
                )
            elif decision != VENUE_APPROVAL_REJECTED:
                cleaned['reject_reason'] = ''
            else:
                cleaned['reject_reason'] = reason

        if 'content_change_decision' in self.fields:
            content_decision = cleaned.get('content_change_decision')
            if content_decision == CONTENT_CHANGE_REJECT:
                content_reason = (cleaned.get('content_change_reject_reason') or '').strip()
                if not content_reason:
                    self.add_error(
                        'content_change_reject_reason',
                        'Enter a reason when rejecting content changes.',
                    )
                else:
                    cleaned['content_change_reject_reason'] = content_reason
        return cleaned

    def save(self, commit=True):
        from django.utils import timezone
        from courses.venue_approval import (
            apply_venue_approval_decision,
            upsert_venue_content_change_request,
        )

        venue = super().save(commit=False)
        now = timezone.now()

        if self.content_only_mode:
            venue.updatedby_id = self.editor_user_id
            venue.updated_at = now
            if commit:
                venue.save(update_fields=['updatedby_id', 'updated_at'])
                upsert_venue_content_change_request(
                    venue,
                    self.cleaned_data,
                    user_id=self.editor_user_id,
                )
            return venue

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
            if not self.instance.pk:
                venue.status_id = 2
            venue_user = self.cleaned_data.get('venue_user')
            venue.user_id = venue_user.pk if venue_user else None
            apply_venue_approval_decision(
                venue,
                self.cleaned_data.get('approval_decision'),
                editor_user_id=self.editor_user_id,
                reject_reason=self.cleaned_data.get('reject_reason'),
                now=now,
            )
            venue.updatedby_id = self.editor_user_id
            venue.updated_at = now

        if commit:
            venue.save()
            self._save_content(venue)
            if venue.document_id and 'add_document_to_booking_email' in self.cleaned_data:
                from courses.venue_documents import set_venue_document_email_enabled

                set_venue_document_email_enabled(
                    venue.pk,
                    self.cleaned_data['add_document_to_booking_email'],
                )
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


class TutorAdminForm(forms.ModelForm):
    """Tutor admin: legacy 0/1 active as a boolean toggle."""

    active = forms.BooleanField(required=False, label='Active', widget=BooleanToggleWidget())

    class Meta:
        model = Tutor
        fields = ['firstname', 'lastname', 'email', 'telephone', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['firstname'].required = True
        self.fields['lastname'].required = True
        if self.instance.pk:
            self.fields['active'].initial = _legacy_01_checked(self.instance.active)
        else:
            self.fields['active'].initial = True

    def save(self, commit=True):
        tutor = super().save(commit=False)
        tutor.active = 1 if self.cleaned_data.get('active') else 0
        if commit:
            tutor.save()
        return tutor


class AssistantAdminForm(forms.ModelForm):
    """Assistant admin: legacy 0/1 active as a boolean toggle."""

    active = forms.BooleanField(required=False, label='Active', widget=BooleanToggleWidget())

    class Meta:
        model = Assistant
        fields = ['firstname', 'lastname', 'email', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['firstname'].required = True
        self.fields['lastname'].required = True
        if self.instance.pk:
            self.fields['active'].initial = _legacy_01_checked(self.instance.active)
        else:
            self.fields['active'].initial = True

    def save(self, commit=True):
        assistant = super().save(commit=False)
        assistant.active = 1 if self.cleaned_data.get('active') else 0
        if commit:
            assistant.save()
        return assistant


WORKSHOP_BYLINE_ADMIN_HELP = format_html(
    '<div class="gd-byline-help" role="note">'
    '<p class="gd-byline-help-lead">'
    '<i class="fas fa-info-circle" aria-hidden="true"></i> '
    'Where this appears on the public site</p>'
    '<ul>'
    '<li>the date and location cards on the course page</li>'
    '<li>the <strong>Workshop details</strong> tab on this workshop&rsquo;s page</li>'
    '</ul>'
    '<p>Include information specific to this workshop date and venue, for example '
    'start time, meeting point, parking, and what will be covered on the day.</p>'
    '</div>'
)


class WorkshopBylineWidget(CKEditorWidget):
    """CKEditor with byline instructions rendered above the input."""

    def render(self, name, value, attrs=None, renderer=None):
        editor = super().render(name, value, attrs, renderer)
        return mark_safe(f'{WORKSHOP_BYLINE_ADMIN_HELP}{editor}')


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
    open_dated = forms.BooleanField(
        required=False,
        label='Open dated',
        help_text='No fixed date — the tutor and student agree a date after booking (e.g. one-to-one tuition).',
        widget=BooleanToggleWidget(),
    )
    date = HTML5SplitDateTimeField(
        required=False,
        label='Start date and time',
    )
    end_at = HTML5SplitDateTimeField(
        required=False,
        label='End date and time',
        help_text='For multi-day courses, set the end date to the final day.',
    )
    strapline = forms.CharField(
        required=False,
        widget=CKEditorWidget(config_name='default'),
        label='Strapline',
    )
    byline = forms.CharField(
        required=False,
        widget=WorkshopBylineWidget(config_name='default'),
        label='Byline',
    )
    reminder_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        label='Reminder email notes',
        help_text=(
            'Optional notes included in the day-before reminder email as “Course notes”. '
            'The workshop byline above is also sent as “Workshop details”. '
            'Superusers can edit the shared intro and closing under Website → Workshop reminder email.'
        ),
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.filter(active=1).order_by('region_name'),
        required=False,
        empty_label='---------',
        label='Region',
    )
    tutor = forms.ModelChoiceField(
        queryset=Tutor.objects.filter(active=1).order_by('lastname', 'firstname'),
        required=False,
        empty_label='---------',
        label='Tutor',
    )
    assistant = forms.ModelChoiceField(
        queryset=Assistant.objects.filter(active=1).order_by('lastname', 'firstname'),
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
    images = WorkshopImagesModelMultipleChoiceField(
        queryset=Image.objects.none(),
        required=False,
        label='Display images',
        help_text='Select one or more of your uploaded images to show on the workshop page.',
    )
    image_upload = forms.ImageField(
        required=False,
        label='Upload image',
        help_text=upload_help_text(),
    )
    add_document_to_booking_email = forms.BooleanField(
        required=False,
        label='Add to booking email',
        help_text='Attach this venue document to booking confirmation emails.',
        widget=BooleanToggleWidget(),
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
            region_qs = Region.objects.filter(active=1, pk__in=region_ids).order_by('region_name')
            self.fields['region'].queryset = region_qs
            from .region_scope import filter_courses_for_workshop_picker

            include_course_ids = []
            if self.instance.pk:
                if self.instance.course_id:
                    include_course_ids.append(self.instance.course_id)
                if self.instance.alt_course_id:
                    include_course_ids.append(self.instance.alt_course_id)
            editor = None
            if self.editor_user_id:
                from core.models import User
                editor = User.objects.filter(pk=self.editor_user_id).first()
            course_base = Course.objects.filter(
                Q(region_id__isnull=True) | Q(region_id__in=region_ids)
            ).order_by('course_name')
            if editor:
                course_qs = filter_courses_for_workshop_picker(
                    course_base,
                    editor,
                    include_course_ids=include_course_ids,
                )
            else:
                course_qs = course_base
            self.fields['alt_course'].queryset = course_qs
            if 'course' in self.fields:
                self.fields['course'].queryset = course_qs
            if 'venue' in self.fields and editor:
                from .region_scope import filter_venues_for_workshop_picker

                self.fields['venue'].queryset = filter_venues_for_workshop_picker(
                    Venue.objects.all().order_by('venue_name'),
                    editor,
                )
            if len(region_ids) == 1 and not self.instance.pk:
                self.fields['region'].initial = region_qs.first()
        if self.instance.pk:
            self.fields['active'].initial = _legacy_01_checked(self.instance.active)
            self.fields['cameras_available'].initial = _legacy_01_checked(self.instance.cameras_available)
            self.fields['open_dated'].initial = _legacy_01_checked(self.instance.open_dated)
            if self.instance.date and 'date' not in self.initial and not self.instance.open_dated:
                self.fields['date'].initial = _local_datetime(self.instance.date)
            if self.instance.end_at and 'end_at' not in self.initial and not self.instance.open_dated:
                self.fields['end_at'].initial = _local_datetime(self.instance.end_at)
            elif (
                self.instance.date
                and 'end_at' not in self.initial
                and not self.instance.open_dated
                and not self.instance.end_at
            ):
                self.fields['end_at'].initial = _local_datetime(self.instance.get_end_date())
        else:
            if 'active' not in self.initial:
                self.fields['active'].initial = False if self.region_ids is not None else True
        gallery_ids = []
        if self.instance.pk:
            gallery_ids = workshop_gallery_image_ids(self.instance)
        image_qs = _workshop_image_queryset(
            include_pks=gallery_ids,
            owner_user_id=self.editor_user_id,
        )
        self.fields['images'].queryset = image_qs
        if gallery_ids:
            self.fields['images'].initial = gallery_ids
        if not image_qs.exists():
            self.fields['images'].help_text = (
                'You have not uploaded any images yet. Use Upload image below, '
                'then save and re-open this workshop to select them here.'
            )
        else:
            self.fields['images'].help_text = (
                'Only images you have uploaded are shown. '
                'Select one or more below, or upload a new file.'
            )
        self._set_initial_from_id('region', Region, 'region_id')
        self._set_initial_from_id('tutor', Tutor, 'tutor_id')
        self._set_initial_from_id('assistant', Assistant, 'assistant_id')
        self._set_initial_from_id('alt_course', Course, 'alt_course_id', skip_zero=True)
        self._set_initial_from_id('workshop_type', WorkshopType, 'workshop_type_id')
        tutor_qs = Tutor.objects.filter(active=1)
        current_tutor_id = self.instance.tutor_id if self.instance.pk else None
        if current_tutor_id:
            tutor_qs = Tutor.objects.filter(Q(pk=current_tutor_id) | Q(active=1))
        self.fields['tutor'].queryset = tutor_qs.order_by('lastname', 'firstname')
        assistant_qs = Assistant.objects.filter(active=1)
        current_assistant_id = self.instance.assistant_id if self.instance.pk else None
        if current_assistant_id:
            assistant_qs = Assistant.objects.filter(Q(pk=current_assistant_id) | Q(active=1))
        self.fields['assistant'].queryset = assistant_qs.order_by('lastname', 'firstname')
        venue = self.instance.venue if self.instance.pk and self.instance.venue_id else None
        if venue and venue.document_id:
            from courses.venue_documents import venue_document_email_enabled

            self.fields['add_document_to_booking_email'].initial = venue_document_email_enabled(
                venue.id,
            )
        else:
            self.fields.pop('add_document_to_booking_email', None)
        if 'image_upload' in self.fields:
            self.fields['image_upload'].widget.attrs.setdefault('accept', 'image/*')
        self._order_image_fields()

    def _order_image_fields(self):
        if 'images' not in self.fields or 'image_upload' not in self.fields:
            return
        order = list(self.fields.keys())
        order.remove('image_upload')
        order.insert(order.index('images') + 1, 'image_upload')
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
            if self.editor_user_id:
                from core.models import User
                from .region_scope import franchisee_course_blocked

                editor = User.objects.filter(pk=self.editor_user_id).first()
                if editor:
                    current_course_id = self.instance.course_id if self.instance.pk else None
                    current_alt_id = self.instance.alt_course_id if self.instance.pk else None
                    if (
                        course
                        and franchisee_course_blocked(editor, course)
                        and course.pk != current_course_id
                    ):
                        raise forms.ValidationError({
                            'course': 'You do not have permission to create workshops for this course.',
                        })
                    if (
                        alt
                        and franchisee_course_blocked(editor, alt)
                        and alt.pk != current_alt_id
                    ):
                        raise forms.ValidationError({
                            'alt_course': 'You do not have permission to use this course.',
                        })
            venue = cleaned.get('venue')
            if venue and self.editor_user_id:
                from core.models import User
                from .region_scope import filter_venues_for_workshop_picker

                editor = User.objects.filter(pk=self.editor_user_id).first()
                if editor and not filter_venues_for_workshop_picker(
                    Venue.objects.filter(pk=venue.pk),
                    editor,
                ).exists():
                    raise forms.ValidationError({
                        'venue': 'You cannot use this venue for workshops.',
                    })
            if cleaned.get('active') and venue and not venue_is_approved(venue):
                raise forms.ValidationError({
                    'active': (
                        'This workshop cannot be published until the venue is approved. '
                        'Add or select a venue under Venues and wait for administrator approval.'
                    ),
                })
        upload = cleaned.get('image_upload')
        if upload:
            try:
                validate_image_upload(upload)
            except DjangoValidationError as exc:
                raise forms.ValidationError({'image_upload': exc.messages[0]}) from exc

        open_dated = cleaned.get('open_dated')
        workshop_date = cleaned.get('date')
        workshop_end = cleaned.get('end_at')
        if open_dated and (workshop_date or workshop_end):
            errors = {}
            if workshop_date:
                errors['date'] = 'Clear the start date and time when marking a workshop as Open dated.'
            if workshop_end:
                errors['end_at'] = 'Clear the end date and time when marking a workshop as Open dated.'
            raise forms.ValidationError(errors)
        if not open_dated and not workshop_date:
            raise forms.ValidationError({
                'date': 'Set a start date and time, or tick Open dated.',
            })
        if not open_dated and workshop_date and not workshop_end:
            raise forms.ValidationError({
                'end_at': 'Set an end date and time.',
            })
        if workshop_date and workshop_end and workshop_end <= workshop_date:
            raise forms.ValidationError({
                'end_at': 'End date and time must be after the start.',
            })
        return cleaned

    def save(self, commit=True):
        workshop = super().save(commit=False)
        workshop.active = 1 if self.cleaned_data.get('active') else 0
        workshop.cameras_available = 1 if self.cleaned_data.get('cameras_available') else 0
        workshop.open_dated = 1 if self.cleaned_data.get('open_dated') else 0
        if workshop.open_dated:
            workshop.date = None
            workshop.end_at = None
        if not self.cleaned_data.get('cameras_available'):
            workshop.number_of_loan_cameras_available = 0
        for field_name, attr_name, zero in (
            ('region', 'region_id', False),
            ('tutor', 'tutor_id', False),
            ('assistant', 'assistant_id', False),
            ('alt_course', 'alt_course_id', True),
            ('workshop_type', 'workshop_type_id', False),
        ):
            _assign_model_choice_fk(
                workshop,
                self.cleaned_data,
                field_name,
                attr_name,
                zero_for_empty=zero,
            )
        if not self.instance.pk:
            duplicate_from = self.initial.get(CLONED_FROM_WORKSHOP_INITIAL_KEY)
            if duplicate_from:
                workshop.cloned_from_workshop_id = int(duplicate_from)
        selected_images = list(self.cleaned_data.get('images') or [])
        selected_ids = []
        seen = set()
        for image in selected_images:
            if image.pk not in seen:
                seen.add(image.pk)
                selected_ids.append(image.pk)
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
            if gd_image.pk not in seen:
                selected_ids.insert(0, gd_image.pk)
        workshop.image_id = selected_ids[0] if selected_ids else 0
        self._gallery_image_ids = selected_ids
        self._gallery_synced = False
        if commit:
            workshop.save()
            self.sync_gallery(workshop)
        venue = workshop.venue
        if (
            venue
            and venue.document_id
            and 'add_document_to_booking_email' in self.cleaned_data
        ):
            from courses.venue_documents import set_venue_document_email_enabled

            set_venue_document_email_enabled(
                venue.id,
                self.cleaned_data['add_document_to_booking_email'],
            )
        return workshop

    def sync_gallery(self, workshop):
        """Persist selected display images (admin saves the workshop with commit=False first)."""
        if not workshop or not workshop.pk or getattr(self, '_gallery_synced', False):
            return
        image_ids = getattr(self, '_gallery_image_ids', None)
        if image_ids is None:
            selected = self.cleaned_data.get('images') if getattr(self, 'cleaned_data', None) else None
            image_ids = [image.pk for image in (selected or [])]
        _sync_workshop_gallery(workshop, image_ids)
        self._gallery_synced = True


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
        range_fields = {
            'card_image_focus_x': {'min': 0, 'max': 100, 'step': 1},
            'card_image_focus_y': {'min': 0, 'max': 100, 'step': 1},
            'card_image_zoom': {'min': 100, 'max': 200, 'step': 5},
        }
        for name, attrs in range_fields.items():
            if name not in self.fields:
                continue
            widget_attrs = {
                'type': 'range',
                'class': 'course-card-image-range',
                'data-card-preview-input': name.replace('card_image_', ''),
            }
            widget_attrs.update(attrs)
            self.fields[name].widget = forms.NumberInput(attrs=widget_attrs)
            self.fields[name].widget.attrs.setdefault('style', 'width:100%;max-width:24rem;')
        slug = ''
        if self.is_bound:
            slug = self.data.get('slug', '')
        elif self.instance.pk:
            slug = self.instance.slug or ''
        if 'course_url' in self.fields:
            self.fields['course_url'].initial = self.course_url_path(slug)
        if 'region' in self.fields and self.instance.pk and self.instance.region_id:
            self.fields['region'].initial = Region.objects.filter(pk=self.instance.region_id).first()
        if 'status' in self.fields and not self.is_bound:
            status_id = self.instance.status_id if self.instance.pk else 2
            if status_id in COURSE_STATUS_DISPLAY_NAMES:
                self.fields['status'].initial = status_id
            elif status_id is not None:
                label = f'Status #{status_id}'
                self.fields['status'].choices = COURSE_STATUS_CHOICES + ((status_id, label),)
                self.fields['status'].initial = status_id
        content = getattr(self.instance, 'content', None) if self.instance.pk else None
        if content:
            content_initial = {
                'content_title': content.content_title,
                'strapline': content.strapline,
                'main_content': content.main_content,
                'sub_content': content.sub_content,
                'meta_title': content.meta_title,
                'meta_description': content.meta_description,
                'meta_keywords': content.meta_keywords,
            }
            for name, value in content_initial.items():
                if name in self.fields:
                    self.fields[name].initial = value

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
