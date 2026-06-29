"""Newsletter subscription."""
from django import forms


class NewsletterSubscribeForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'newsletter-modal__input',
            'autocomplete': 'email',
            'placeholder': 'Enter your email address',
            'required': True,
        }),
    )
