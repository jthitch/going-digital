"""Sign-in and sign-up forms for students (gd_customer)."""
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.customer_auth import authenticate_customer, customer_has_sign_in_password
from core.customer_service import get_or_create_customer_record
from core.models import Customer
from core.student_auth import (
    complete_customer_account,
    customer_needs_account_setup,
    link_bookings_to_customer,
    resolve_customer_for_email,
)


class StudentLoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'email',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'current-password',
        }),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.customer_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get('email') or '').strip()
        password = cleaned.get('password')
        if not email or not password:
            return cleaned

        customer = authenticate_customer(email, password)
        if customer is None:
            raise ValidationError('Invalid email or password.')
        if not customer.is_active:
            raise ValidationError('This account is inactive. Please contact us for help.')

        self.customer_cache = customer
        return cleaned

    def get_customer(self):
        return self.customer_cache


class StudentSignupForm(forms.Form):
    firstname = forms.CharField(
        label='First name',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'given-name',
        }),
    )
    lastname = forms.CharField(
        label='Last name',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'family-name',
        }),
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'email',
        }),
    )
    password1 = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'new-password',
        }),
    )
    password2 = forms.CharField(
        label='Confirm password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'new-password',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        customer = Customer.objects.filter(email__iexact=email).first()
        if customer and customer_has_sign_in_password(customer):
            raise ValidationError(
                'An account with this email already exists. Please sign in instead.'
            )
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')
        if password1:
            email = (cleaned.get('email') or '').strip().lower()
            validate_password(
                password1,
                Customer(
                    email=email,
                    firstname=cleaned.get('firstname', ''),
                    lastname=cleaned.get('lastname', ''),
                ),
            )
        return cleaned

    def save(self):
        email = self.cleaned_data['email']
        customer = Customer.objects.filter(email__iexact=email).first()
        created = False
        if not customer:
            customer, created = get_or_create_customer_record(
                email,
                self.cleaned_data['firstname'],
                self.cleaned_data['lastname'],
            )

        customer.firstname = self.cleaned_data['firstname']
        customer.lastname = self.cleaned_data['lastname']
        customer.active = 1
        customer.guest_account = 0
        customer.registered_at = timezone.now().date()
        customer.set_password(self.cleaned_data['password1'])
        customer.updated_at = timezone.now()
        customer.save()
        link_bookings_to_customer(customer)
        return customer, created


class CompleteAccountPasswordForm(forms.Form):
    """Set a password after booking to finish a guest student account."""

    email = forms.EmailField(
        widget=forms.HiddenInput(attrs={'class': 'booking-field-input'}),
    )
    password1 = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'new-password',
        }),
    )
    password2 = forms.CharField(
        label='Confirm password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'new-password',
        }),
    )

    def __init__(self, *args, setup=None, **kwargs):
        self.setup = setup or {}
        super().__init__(*args, **kwargs)
        if self.setup.get('email'):
            self.fields['email'].initial = self.setup['email']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        customer = resolve_customer_for_email(
            email,
            firstname=self.setup.get('firstname', ''),
            lastname=self.setup.get('lastname', ''),
        )
        if not customer:
            raise ValidationError('No account found for this email.')
        if not customer_needs_account_setup(customer):
            raise ValidationError(
                'This account already has a password. Please sign in instead.'
            )
        self.customer_cache = customer
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')
        customer = getattr(self, 'customer_cache', None)
        if password1 and customer:
            validate_password(
                password1,
                Customer(
                    email=customer.email,
                    firstname=self.setup.get('firstname') or customer.firstname,
                    lastname=self.setup.get('lastname') or customer.lastname,
                ),
            )
        return cleaned

    def save(self):
        customer = self.customer_cache
        return complete_customer_account(
            customer,
            self.cleaned_data['password1'],
            firstname=self.setup.get('firstname'),
            lastname=self.setup.get('lastname'),
        )


class CustomerPasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'email',
            'autofocus': True,
        }),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class CustomerPasswordResetConfirmForm(forms.Form):
    password1 = forms.CharField(
        label='New password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'new-password',
            'autofocus': True,
        }),
    )
    password2 = forms.CharField(
        label='Confirm new password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'new-password',
        }),
    )

    def __init__(self, *args, customer=None, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')
        if password1 and self.customer:
            validate_password(
                password1,
                Customer(
                    email=self.customer.email,
                    firstname=self.customer.firstname,
                    lastname=self.customer.lastname,
                ),
            )
        return cleaned

    def save(self):
        from core.customer_password_reset import clear_password_reset_token

        customer = self.customer
        customer.set_password(self.cleaned_data['password1'])
        customer.guest_account = 0
        customer.updated_at = timezone.now()
        customer.save(update_fields=['password', 'guest_account', 'updated_at'])
        clear_password_reset_token(customer)
        return customer


class BookingCameraForm(forms.Form):
    """Let a signed-in student update attendee and camera details for one booking."""

    student_first_name = forms.CharField(
        label='First name',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'given-name',
        }),
    )
    student_last_name = forms.CharField(
        label='Last name',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'booking-field-input',
            'autocomplete': 'family-name',
        }),
    )
    camera_make_choice = forms.ChoiceField(
        label='Camera make',
        required=False,
        widget=forms.Select(attrs={
            'class': 'booking-field-input booking-field-select',
            'data-camera-make': '',
        }),
    )
    camera_make_other = forms.CharField(
        label='Other make',
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'booking-field-input',
            'placeholder': 'Enter camera make',
            'autocomplete': 'off',
            'data-camera-make-other': '',
        }),
    )
    camera_model_choice = forms.ChoiceField(
        label='Camera model',
        required=False,
        widget=forms.Select(attrs={
            'class': 'booking-field-input booking-field-select',
            'data-camera-model': '',
        }),
    )
    camera_model_other = forms.CharField(
        label='Other model',
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'booking-field-input',
            'placeholder': 'Enter camera model',
            'autocomplete': 'off',
            'data-camera-model-other': '',
        }),
    )

    def __init__(self, booking, *args, **kwargs):
        from bookings.camera_catalog import (
            make_select_choices,
            model_select_choices,
            selection_from_stored,
        )

        self.booking = booking
        super().__init__(*args, **kwargs)
        self.fields['student_first_name'].initial = booking.student_first_name
        self.fields['student_last_name'].initial = booking.student_last_name

        selection = selection_from_stored(booking.camera_make, booking.camera_model)
        make_choice = self.data.get('camera_make_choice') if self.is_bound else selection['make_choice']
        self.fields['camera_make_choice'].choices = make_select_choices()
        self.fields['camera_model_choice'].choices = model_select_choices(make_choice or '')

        if not self.is_bound:
            self.fields['camera_make_choice'].initial = selection['make_choice']
            self.fields['camera_make_other'].initial = selection['make_other']
            self.fields['camera_model_choice'].initial = selection['model_choice']
            self.fields['camera_model_other'].initial = selection['model_other']
            self.fields['camera_model_choice'].widget.attrs['data-initial-model'] = selection['model_choice']
        else:
            self.fields['camera_model_choice'].widget.attrs['data-initial-model'] = (
                self.data.get('camera_model_choice') or ''
            )

    def clean(self):
        from bookings.camera_catalog import (
            resolve_camera_selection,
            validate_camera_selection,
        )

        cleaned = super().clean()
        errors = validate_camera_selection(
            cleaned.get('camera_make_choice'),
            cleaned.get('camera_make_other'),
            cleaned.get('camera_model_choice'),
            cleaned.get('camera_model_other'),
            required=not self.booking.loan_camera,
        )
        for field, message in errors.items():
            if field == 'camera_make':
                self.add_error('camera_make_choice', message)
            elif field == 'camera_model':
                self.add_error('camera_model_choice', message)
            else:
                self.add_error(None, message)

        make_name, model_name, _, _ = resolve_camera_selection(
            cleaned.get('camera_make_choice'),
            cleaned.get('camera_make_other'),
            cleaned.get('camera_model_choice'),
            cleaned.get('camera_model_other'),
        )
        cleaned['camera_make'] = make_name
        cleaned['camera_model'] = model_name
        return cleaned

    def save(self):
        from django.utils import timezone

        self.booking.camera_make = (self.cleaned_data.get('camera_make') or '').strip()
        self.booking.camera_model = (self.cleaned_data.get('camera_model') or '').strip()
        self.booking.student_first_name = (self.cleaned_data.get('student_first_name') or '').strip()
        self.booking.student_last_name = (self.cleaned_data.get('student_last_name') or '').strip()
        now = timezone.now()
        self.booking.attendee_details_collected_at = (
            self.booking.attendee_details_collected_at or now
        )
        self.booking.updated_at = now
        self.booking.save(update_fields=[
            'student_first_name',
            'student_last_name',
            'camera_make',
            'camera_model',
            'attendee_details_collected_at',
            'updated_at',
        ])
        return self.booking
