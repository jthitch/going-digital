"""
Booking forms.
"""
from decimal import Decimal

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError

from .models import Booking, DiscountCode
from .workshop_basket import (
    loan_cameras_reserved_in_basket,
    places_available_message,
    validate_loan_cameras_requested,
)


class BookingForm(forms.ModelForm):
    """Form for adding a workshop line to the booking basket."""

    quantity = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=1,
        label='Number of places',
        widget=forms.NumberInput(attrs={
            'class': 'basket-qty-input booking-qty-input',
            'min': 1,
            'max': 10,
            'inputmode': 'numeric',
        }),
    )
    
    class Meta:
        model = Booking
        fields = [
            'student_first_name',
            'student_last_name',
            'student_email',
            'student_phone',
            'special_requirements',
        ]
        widgets = {
            'student_first_name': forms.TextInput(attrs={
                'class': 'booking-field-input',
                'autocomplete': 'given-name',
            }),
            'student_last_name': forms.TextInput(attrs={
                'class': 'booking-field-input',
                'autocomplete': 'family-name',
            }),
            'student_email': forms.EmailInput(attrs={
                'class': 'booking-field-input',
                'autocomplete': 'email',
            }),
            'student_phone': forms.TextInput(attrs={
                'class': 'booking-field-input',
                'autocomplete': 'tel',
                'inputmode': 'tel',
            }),
            'special_requirements': forms.Textarea(attrs={
                'class': 'booking-field-input booking-field-textarea',
                'rows': 4,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.workshop = kwargs.pop('workshop', None)
        self.user = kwargs.pop('user', None)
        self.customer = kwargs.pop('customer', None)
        self.basket = kwargs.pop('basket', None)
        super().__init__(*args, **kwargs)

        if self.customer:
            self.fields['student_first_name'].initial = self.customer.firstname or ''
            self.fields['student_last_name'].initial = self.customer.lastname or ''
            self.fields['student_email'].initial = self.customer.email or ''
        elif self.user and self.user.is_authenticated:
            self.fields['student_first_name'].initial = self.user.first_name or ''
            self.fields['student_last_name'].initial = self.user.last_name or ''
            self.fields['student_email'].initial = self.user.email or ''

        if self.workshop and self.workshop.has_loan_cameras_available:
            quantity = self._current_quantity()
            max_loan = self._max_loan_cameras_for_quantity(quantity)
            self.fields['loan_cameras'] = forms.IntegerField(
                min_value=0,
                max_value=max_loan,
                initial=0,
                required=False,
                label='Loan cameras required',
                widget=forms.NumberInput(attrs={
                    'class': 'basket-qty-input booking-qty-input booking-loan-camera-input',
                    'min': 0,
                    'max': max_loan,
                    'inputmode': 'numeric',
                    'data-loan-camera-input': '1',
                }),
            )
    
    def _current_quantity(self):
        if self.is_bound:
            raw = self.data.get('quantity')
            if raw not in (None, ''):
                try:
                    return max(1, int(raw))
                except (TypeError, ValueError):
                    pass
        if 'quantity' in self.initial:
            return int(self.initial['quantity'] or 1)
        return int(self.fields['quantity'].initial or 1)

    def _max_loan_cameras_for_quantity(self, quantity):
        if not self.workshop or not self.workshop.has_loan_cameras_available:
            return 0
        reserved = loan_cameras_reserved_in_basket(
            self.basket or {},
            self.workshop.pk,
        )
        remaining = max(0, self.workshop.loan_cameras_remaining() - reserved)
        return max(0, min(int(quantity), remaining))

    def clean(self):
        cleaned_data = super().clean()
        
        quantity = cleaned_data.get('quantity', 1)

        if self.workshop and self.workshop.is_full:
            raise forms.ValidationError('This course is fully booked.')

        if self.workshop and not self.workshop.enrollment_open:
            raise forms.ValidationError('Enrollment is not currently open for this course.')

        if self.workshop:
            available = self.workshop.spaces_available
            if available is not None and quantity > available:
                self.add_error('quantity', places_available_message(available))

        if self.workshop and self.workshop.has_loan_cameras_available:
            try:
                cleaned_data['loan_cameras'] = validate_loan_cameras_requested(
                    self.workshop,
                    cleaned_data.get('loan_cameras', 0),
                    quantity,
                    basket=self.basket,
                )
            except ValidationError as exc:
                message = exc.messages[0] if exc.messages else str(exc)
                self.add_error('loan_cameras', message)
        else:
            cleaned_data['loan_cameras'] = 0

        return cleaned_data


class BasketCheckoutForm(forms.Form):
    """Basket proceed-to-payment — requires terms acceptance."""

    accept_terms = forms.BooleanField(
        required=True,
        error_messages={
            'required': 'You must accept the terms and conditions to proceed.',
        },
    )
    subscribe_newsletter = forms.BooleanField(
        required=False,
        label='Sign me up for seasonal newsletters and special offers',
    )


class ManualBookingAdminForm(forms.ModelForm):
    """Admin form for walk-up / paid-to-tutor bookings."""

    include_future_workshops = forms.BooleanField(
        required=False,
        initial=False,
        label='Include future workshops',
        help_text='By default the workshop search shows today and older dates. Tick this to also search upcoming workshops.',
    )
    send_confirmation_email = forms.BooleanField(
        required=False,
        initial=True,
        label='Send confirmation email',
        help_text='Email the student their booking confirmation and joining details.',
    )

    class Meta:
        model = Booking
        fields = [
            'workshop',
            'student_first_name',
            'student_last_name',
            'student_email',
            'student_phone',
            'special_requirements',
            'loan_camera',
            'list_price',
            'price_paid',
        ]
        widgets = {
            'special_requirements': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, workshop_base_queryset=None, **kwargs):
        from .manual_booking import filter_workshops_for_manual_booking_picker

        super().__init__(*args, **kwargs)
        self.fields['workshop'].help_text = (
            'The workshop this student is attending. Payment is recorded as paid to the tutor.'
        )
        self.fields['price_paid'].help_text = (
            'Amount paid to the tutor. Defaults to the workshop price if left blank.'
        )
        self.fields['list_price'].required = False
        self.fields['price_paid'].required = False
        self.fields['student_phone'].required = False

        include_future = False
        if self.is_bound:
            include_future = self.data.get('include_future_workshops') in (
                True, 'true', 'True', '1', 'on', 'yes',
            )
        if workshop_base_queryset is not None:
            self.fields['workshop'].queryset = filter_workshops_for_manual_booking_picker(
                workshop_base_queryset,
                include_future=include_future,
            )

    def clean_student_phone(self):
        phone = self.cleaned_data.get('student_phone') or ''
        return ''.join(ch for ch in phone if ch.isdigit() or ch == '+')

    def clean(self):
        cleaned = super().clean()
        workshop = cleaned.get('workshop')
        if not workshop:
            return cleaned
        workshop_price = workshop.price
        if cleaned.get('list_price') is None:
            cleaned['list_price'] = workshop_price
        if cleaned.get('price_paid') is None:
            cleaned['price_paid'] = cleaned.get('list_price') or workshop_price
        return cleaned


class DiscountCodeAdminForm(forms.ModelForm):
    workshops = forms.ModelMultipleChoiceField(
        queryset=DiscountCode._meta.get_field('workshops').related_model.objects.none(),
        required=True,
        widget=FilteredSelectMultiple('workshops', is_stacked=False),
        help_text='Select the workshops this code can be used on.',
    )

    class Meta:
        model = DiscountCode
        fields = [
            'code',
            'discount_type',
            'amount',
            'is_active',
            'expiry_date',
            'workshops',
            'notes',
        ]

    def __init__(self, *args, workshop_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        from courses.models import Workshop

        qs = workshop_queryset
        if qs is None:
            qs = Workshop.objects.select_related('course', 'venue').order_by('-date', 'id')
        self.fields['workshops'].queryset = qs
        self.fields['code'].help_text = 'Letters and numbers only. Stored in uppercase.'
        self.fields['amount'].help_text = (
            'For fixed amount enter pounds (e.g. 10 for £10 off). '
            'For percentage enter the percent (e.g. 10 for 10% off).'
        )
        self.fields['discount_type'].label = 'Discount type'

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise ValidationError('Enter a discount code.')
        if ' ' in code:
            raise ValidationError('Codes cannot contain spaces.')
        return code

    def clean(self):
        cleaned = super().clean()
        discount_type = cleaned.get('discount_type')
        amount = cleaned.get('amount')
        if amount is None:
            return cleaned
        if amount <= 0:
            self.add_error('amount', 'Amount must be greater than zero.')
        if discount_type == DiscountCode.DISCOUNT_PERCENT and amount > Decimal('100'):
            self.add_error('amount', 'Percentage cannot be more than 100.')
        workshops = cleaned.get('workshops')
        if workshops is not None and not workshops.exists():
            self.add_error('workshops', 'Select at least one workshop.')
        return cleaned
