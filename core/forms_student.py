"""Sign-in and sign-up forms for students."""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import User
from core.student_auth import (
    complete_student_account,
    link_bookings_to_user,
    resolve_student_user_for_email,
    user_has_sign_in_password,
    user_needs_account_setup,
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
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get('email') or '').strip()
        password = cleaned.get('password')
        if not email or not password:
            return cleaned

        user = authenticate(self.request, username=email, password=password)
        if user is None:
            raise ValidationError('Invalid email or password.')
        if not user.is_active:
            raise ValidationError('This account is inactive. Please contact us for help.')

        self.user_cache = user
        return cleaned

    def get_user(self):
        return self.user_cache


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
        try:
            user = User.objects.get(email__iexact=email)
            if user_has_sign_in_password(user):
                raise ValidationError(
                    'An account with this email already exists. Please sign in instead.'
                )
        except User.DoesNotExist:
            pass
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
                User(
                    email=email,
                    firstname=cleaned.get('firstname', ''),
                    lastname=cleaned.get('lastname', ''),
                ),
            )
        return cleaned

    def save(self):
        email = self.cleaned_data['email']
        now = timezone.now()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = User(
                email=email,
                firstname=self.cleaned_data['firstname'],
                lastname=self.cleaned_data['lastname'],
                active=1,
                user_type_id=None,
                created_at=now,
                updated_at=now,
            )
            user.set_password(self.cleaned_data['password1'])
            user.save()
            link_bookings_to_user(user)
            return user, True

        user.firstname = self.cleaned_data['firstname']
        user.lastname = self.cleaned_data['lastname']
        user.active = 1
        user.updated_at = now
        user.set_password(self.cleaned_data['password1'])
        user.save()
        link_bookings_to_user(user)
        return user, False


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
        user = resolve_student_user_for_email(email)
        if not user:
            raise ValidationError('No account found for this email.')
        if not user_needs_account_setup(user):
            raise ValidationError(
                'This account already has a password. Please sign in instead.'
            )
        self.user_cache = user
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')
        user = getattr(self, 'user_cache', None)
        if password1 and user:
            validate_password(
                password1,
                User(
                    email=user.email,
                    firstname=self.setup.get('firstname') or user.firstname,
                    lastname=self.setup.get('lastname') or user.lastname,
                ),
            )
        return cleaned

    def save(self):
        user = self.user_cache
        return complete_student_account(
            user,
            self.cleaned_data['password1'],
            firstname=self.setup.get('firstname'),
            lastname=self.setup.get('lastname'),
        )
