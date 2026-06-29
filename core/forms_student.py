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
