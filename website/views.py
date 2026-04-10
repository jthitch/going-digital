"""
Website views (dev access gate, etc.).
"""
from django.conf import settings
from django import forms
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView

from .middleware import DEV_SITE_SESSION_KEY


class DevAccessForm(forms.Form):
    password = forms.CharField(
        label='Passcode',
        widget=forms.PasswordInput(
            attrs={'autocomplete': 'current-password', 'autofocus': True},
        ),
    )


class DevSiteAccessView(FormView):
    template_name = 'website/dev_site_access.html'
    form_class = DevAccessForm

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404()
        if not (getattr(settings, 'DEV_SITE_PASSWORD', None) or '').strip():
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.session.get(DEV_SITE_SESSION_KEY):
            return redirect(self._safe_next())
        return super().get(request, *args, **kwargs)

    def _safe_next(self):
        request = self.request
        next_url = request.GET.get('next') or '/'
        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        return '/'

    def form_valid(self, form):
        entered = form.cleaned_data['password']
        expected = settings.DEV_SITE_PASSWORD
        if not constant_time_compare(entered, expected):
            form.add_error('password', 'Incorrect passcode')
            return self.form_invalid(form)
        self.request.session[DEV_SITE_SESSION_KEY] = True
        return HttpResponseRedirect(self._safe_next_post())

    def _safe_next_post(self):
        request = self.request
        next_url = (
            request.POST.get('next')
            or request.GET.get('next')
            or '/'
        )
        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        return '/'
