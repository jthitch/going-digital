"""
Middleware for website app.
"""
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from .models import Redirect


class RedirectMiddleware(MiddlewareMixin):
    """
    Check incoming request path against the Redirect table.
    If a matching active redirect exists, return 301 or 302 to the new path.
    """
    def process_request(self, request):
        path = request.path
        if not path.startswith('/'):
            return None
        try:
            redirect = Redirect.objects.filter(
                old_path=path,
                is_active=True
            ).first()
        except Exception:
            return None
        if redirect is None:
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
