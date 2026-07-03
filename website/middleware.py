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

# Legacy site section renamed for SEO (301 everything under this prefix).
PHOTOGRAPHY_WORKSHOPS_PREFIX = '/photography-workshops'
PHOTOGRAPHY_COURSES_PREFIX = '/photography-courses'

# Paths that must not require the dev passcode (no browser session, e.g. Stripe CLI webhooks).
DEV_SITE_ACCESS_EXEMPT_PREFIXES = (
    '/payments/webhook/',
    '/robots.txt',
    '/llms.txt',
    '/sitemap.xml',
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


def _redirect_url_with_query(request, path):
    """Build redirect target path, preserving the query string."""
    if request.GET:
        qs = request.META.get('QUERY_STRING', '')
        return path + ('?' + qs if qs else '')
    return path


def _canonical_photography_courses_path(path):
    """
    Map /photography-workshops… to /photography-courses… with a trailing slash.
  """
    if path == PHOTOGRAPHY_WORKSHOPS_PREFIX:
        return f'{PHOTOGRAPHY_COURSES_PREFIX}/'
    if path.startswith(f'{PHOTOGRAPHY_WORKSHOPS_PREFIX}/'):
        new_path = PHOTOGRAPHY_COURSES_PREFIX + path[len(PHOTOGRAPHY_WORKSHOPS_PREFIX):]
        if new_path != f'{PHOTOGRAPHY_COURSES_PREFIX}/' and not new_path.endswith('/'):
            new_path += '/'
        return new_path
    return None


class PhotographyWorkshopsRedirectMiddleware(MiddlewareMixin):
    """
    301 redirect the legacy /photography-workshops/ section to /photography-courses/.
    Covers the list page, every course overview, and course-at-venue URLs in one hop
    (including paths with or without a trailing slash).
    """

    def process_request(self, request):
        new_path = _canonical_photography_courses_path(request.path)
        if not new_path:
            return None
        return HttpResponsePermanentRedirect(_redirect_url_with_query(request, new_path))


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
        new_path = redirect.new_path
        if not new_path.startswith('/') or new_path.startswith('//') or '://' in new_path:
            return None
        if redirect.permanent:
            return HttpResponsePermanentRedirect(_redirect_url_with_query(request, new_path))
        return HttpResponseRedirect(_redirect_url_with_query(request, new_path))
