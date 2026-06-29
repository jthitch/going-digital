from django import forms

from .models import NewsletterModalSettings


class NewsletterModalSettingsForm(forms.ModelForm):
    class Meta:
        model = NewsletterModalSettings
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        range_fields = {
            'desktop_focus_x': {'min': 0, 'max': 100, 'step': 1},
            'desktop_focus_y': {'min': 0, 'max': 100, 'step': 1},
            'desktop_zoom': {'min': 100, 'max': 200, 'step': 5},
            'mobile_focus_x': {'min': 0, 'max': 100, 'step': 1},
            'mobile_focus_y': {'min': 0, 'max': 100, 'step': 1},
            'mobile_zoom': {'min': 100, 'max': 200, 'step': 5},
        }
        for name, attrs in range_fields.items():
            if name not in self.fields:
                continue
            widget_attrs = {
                'type': 'range',
                'class': 'newsletter-modal-focus-range',
            }
            widget_attrs.update(attrs)
            self.fields[name].widget = forms.NumberInput(attrs=widget_attrs)
            self.fields[name].widget.attrs.setdefault(
                'style', 'width:100%;max-width:24rem;'
            )
