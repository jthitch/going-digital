"""
Custom forms for Course admin.
"""
from django import forms
from .models import Course


class CourseAdminForm(forms.ModelForm):
    """
    Custom form for Course admin that converts newline-separated
    text input to JSON array for what_youll_learn field.
    """
    what_youll_learn_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 60}),
        help_text="Enter each learning outcome on a new line. Example:\nLearn aperture\nUnderstand composition\nMaster lighting",
        label="What You'll Learn (one per line)"
    )
    
    class Meta:
        model = Course
        fields = '__all__'
        # Exclude the original JSON field from the form
        exclude = ['what_youll_learn']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert JSON array to newline-separated text for display
        if self.instance and self.instance.pk:
            what_youll_learn = self.instance.what_youll_learn
            if isinstance(what_youll_learn, list):
                self.initial['what_youll_learn_text'] = '\n'.join(what_youll_learn)
            else:
                self.initial['what_youll_learn_text'] = ''
        else:
            self.initial['what_youll_learn_text'] = ''
    
    def clean_what_youll_learn_text(self):
        """Convert newline-separated text to JSON array."""
        text = self.cleaned_data.get('what_youll_learn_text', '')
        if not text:
            return []
        # Split by newlines, strip whitespace, and filter out empty lines
        items = [line.strip() for line in text.split('\n') if line.strip()]
        return items
    
    def save(self, commit=True):
        """Convert the text input to JSON array before saving."""
        instance = super().save(commit=False)
        # Get the cleaned text input and convert to list
        items = self.cleaned_data.get('what_youll_learn_text', [])
        instance.what_youll_learn = items
        if commit:
            instance.save()
        return instance
