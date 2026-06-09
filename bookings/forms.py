"""
Booking forms.
"""
from django import forms
from .models import Booking
from courses.models import Workshop


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
        super().__init__(*args, **kwargs)
        
        # Pre-fill user information if available and user is authenticated
        if self.user and self.user.is_authenticated:
            self.fields['student_first_name'].initial = self.user.first_name or ''
            self.fields['student_last_name'].initial = self.user.last_name or ''
            self.fields['student_email'].initial = self.user.email or ''
    
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
                raise forms.ValidationError(
                    f'Only {available} place(s) available on this course.'
                )

        return cleaned_data
