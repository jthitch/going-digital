"""
Custom forms for Course admin and contact.
"""
from django import forms
from ckeditor.widgets import CKEditorWidget
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from .models import Content, Course


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


class CourseAdminForm(forms.ModelForm):
    """
    Course admin form with inline Content fields.
    Edit the linked Content's page content, meta, etc. directly when editing a course.
    """
    # Content fields (editable when course has content, or when creating new content)
    content_title = forms.CharField(required=False, max_length=1000, label='Content title')
    header_content = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Header content')
    strapline = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Strapline')
    main_content = forms.CharField(required=False, widget=CKEditorWidget(config_name='default'), label='Main content')
    sub_content = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}), label='Sub content')
    footer_content = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}), label='Footer content')
    meta_title = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Meta title')
    meta_description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Meta description')
    meta_keywords = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Meta keywords')

    class Meta:
        model = Course
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        content = getattr(self.instance, 'content', None) if self.instance.pk else None
        if content:
            self.fields['content_title'].initial = content.content_title
            self.fields['header_content'].initial = content.header_content
            self.fields['strapline'].initial = content.strapline
            self.fields['main_content'].initial = content.main_content
            self.fields['sub_content'].initial = content.sub_content
            self.fields['footer_content'].initial = content.footer_content
            self.fields['meta_title'].initial = content.meta_title
            self.fields['meta_description'].initial = content.meta_description
            self.fields['meta_keywords'].initial = content.meta_keywords

    def save(self, commit=True):
        course = super().save(commit=commit)
        # Content is saved via CourseAdmin.save_model (admin calls form.save(commit=False))
        if commit:
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
            content.header_content = self.cleaned_data.get('header_content') or ''
            content.strapline = self.cleaned_data.get('strapline') or ''
            content.main_content = self.cleaned_data.get('main_content') or ''
            content.sub_content = self.cleaned_data.get('sub_content') or ''
            content.footer_content = self.cleaned_data.get('footer_content') or ''
            content.meta_title = self.cleaned_data.get('meta_title') or ''
            content.meta_description = self.cleaned_data.get('meta_description') or ''
            content.meta_keywords = self.cleaned_data.get('meta_keywords') or ''
            content.updatedby_id = user_id
            content.updated_at = now
            content.save()
        elif self.cleaned_data.get('main_content') or self.cleaned_data.get('content_title'):
            content = Content.objects.create(
                content_title=self.cleaned_data.get('content_title') or course.course_name or '',
                header_content=self.cleaned_data.get('header_content') or '',
                strapline=self.cleaned_data.get('strapline') or '',
                main_content=self.cleaned_data.get('main_content') or '',
                sub_content=self.cleaned_data.get('sub_content') or '',
                footer_content=self.cleaned_data.get('footer_content') or '',
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
