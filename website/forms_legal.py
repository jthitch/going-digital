from ckeditor.widgets import CKEditorWidget
from django import forms

from .models import LegalPage


class LegalPageAdminForm(forms.ModelForm):
    body = forms.CharField(widget=CKEditorWidget(config_name='legal'))

    class Meta:
        model = LegalPage
        fields = (
            'page_title',
            'browser_title',
            'meta_description',
            'meta_keywords',
            'body',
        )
