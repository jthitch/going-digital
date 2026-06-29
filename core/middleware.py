from django.utils.functional import SimpleLazyObject

from core.customer_auth import get_logged_in_customer


class CustomerAuthenticationMiddleware:
    """Attach request.customer from the student session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.customer = SimpleLazyObject(lambda: get_logged_in_customer(request))
        return self.get_response(request)
