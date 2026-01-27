"""
Booking forms.
"""
from django import forms
from .models import Booking
from courses.models import CourseInstance


class BookingForm(forms.ModelForm):
    """Form for creating a booking."""
    
    class Meta:
        model = Booking
        fields = [
            'student_first_name',
            'student_last_name',
            'student_email',
            'student_phone',
            'special_requirements'
        ]
        widgets = {
            'special_requirements': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        self.course_instance = kwargs.pop('course_instance', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Pre-fill user information if available and user is authenticated
        if self.user and self.user.is_authenticated:
            self.fields['student_first_name'].initial = self.user.first_name or ''
            self.fields['student_last_name'].initial = self.user.last_name or ''
            self.fields['student_email'].initial = self.user.email or ''
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check if course instance is full
        if self.course_instance and self.course_instance.is_full:
            raise forms.ValidationError("This course is fully booked.")
        
        # Check if course instance enrollment is open
        if self.course_instance and not self.course_instance.enrollment_open:
            raise forms.ValidationError("Enrollment is not currently open for this course.")
        
        return cleaned_data
