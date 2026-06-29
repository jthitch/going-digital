"""Filter form for admin booking reports."""
from django import forms

from courses.models import Region, Tutor
from bookings.reports import report_filter_regions, report_filter_tutors


class BookingReportFilterForm(forms.Form):
    region = forms.ModelChoiceField(
        queryset=Region.objects.none(),
        required=False,
        empty_label='All regions',
        label='Region',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    tutor = forms.ModelChoiceField(
        queryset=Tutor.objects.none(),
        required=False,
        empty_label='All tutors',
        label='Tutor',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    months = forms.ChoiceField(
        choices=[
            (6, 'Last 6 months'),
            (12, 'Last 12 months'),
            (24, 'Last 24 months'),
        ],
        initial=12,
        label='Period',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['region'].queryset = report_filter_regions(user)
        region_id = None
        if self.is_bound:
            region_val = self.data.get('region') or self.initial.get('region')
            if region_val:
                try:
                    region_id = int(region_val)
                except (TypeError, ValueError):
                    region_id = None
        elif self.initial.get('region'):
            region_id = getattr(self.initial['region'], 'pk', self.initial['region'])
        self.fields['tutor'].queryset = report_filter_tutors(user, region_id=region_id)

    def cleaned_region_id(self):
        region = self.cleaned_data.get('region')
        return region.pk if region else None

    def cleaned_tutor_id(self):
        tutor = self.cleaned_data.get('tutor')
        return tutor.pk if tutor else None

    def cleaned_months_back(self):
        return int(self.cleaned_data.get('months') or 12)


class PaymentGatewayReportFilterForm(forms.Form):
    start_date = forms.DateField(
        label='Start date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    end_date = forms.DateField(
        label='End date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End date must be on or after the start date.')
        return cleaned
