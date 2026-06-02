"""
Middleware for website app.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from urllib.parse import urlencode

from .models import Redirect

# Cache redirect lookups to avoid a DB query on every request (invalidated by TTL).
_REDIRECT_CACHE_PREFIX = 'redirect:v1'
_REDIRECT_CACHE_TTL = 300  # seconds
_REDIRECT_MISS = '__no_redirect__'

# Session flag when dev passcode is accepted (see DevSiteAccessMiddleware).
DEV_SITE_SESSION_KEY = 'dev_site_access_granted'

# Paths that must not require the dev passcode (no browser session, e.g. Stripe CLI webhooks).
DEV_SITE_ACCESS_EXEMPT_PREFIXES = (
    '/payments/webhook/',
)


class DevSiteAccessMiddleware(MiddlewareMixin):
    """
    When enabled and DEV_SITE_PASSWORD is set in the environment, require
    a one-time passcode (session) before serving any URL except static/media and /dev-access/.
    """
    def process_request(self, request):
        if not getattr(settings, 'DEV_SITE_ACCESS_ENABLED', settings.DEBUG):
            return None
        password = (getattr(settings, 'DEV_SITE_PASSWORD', None) or '').strip()
        if not password:
            return None
        if request.session.get(DEV_SITE_SESSION_KEY):
            return None
        path = request.path
        if path.startswith('/dev-access'):
            return None
        static_url = getattr(settings, 'STATIC_URL', '/static/') or '/static/'
        media_url = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'
        if path.startswith(static_url) or path.startswith(media_url):
            return None
        if path.startswith('/favicon'):
            return None
        for prefix in DEV_SITE_ACCESS_EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return None
        next_qs = urlencode({'next': request.get_full_path()})
        login_url = reverse('dev_site_access')
        return HttpResponseRedirect(f'{login_url}?{next_qs}')


class RedirectMiddleware(MiddlewareMixin):
    """
    Check incoming request path against the Redirect table.
    If a matching active redirect exists, return 301 or 302 to the new path.
    """
    def process_request(self, request):
        path = request.path
        if not path.startswith('/'):
            return None
        cache_key = f'{_REDIRECT_CACHE_PREFIX}:{path}'
        try:
            cached = cache.get(cache_key)
            if cached == _REDIRECT_MISS:
                return None
            if cached is not None:
                redirect = cached
            else:
                redirect = Redirect.objects.filter(
                    old_path=path,
                    is_active=True,
                ).first()
                cache.set(
                    cache_key,
                    redirect if redirect is not None else _REDIRECT_MISS,
                    _REDIRECT_CACHE_TTL,
                )
                if redirect is None:
                    return None
        except Exception:
            return None
        # Preserve query string if new_path is relative
        if redirect.new_path.startswith('/') and request.GET:
            qs = request.META.get('QUERY_STRING', '')
            new_url = redirect.new_path + ('?' + qs if qs else '')
        else:
            new_url = redirect.new_path
        if redirect.permanent:
            return HttpResponsePermanentRedirect(new_url)
        return HttpResponseRedirect(new_url)
