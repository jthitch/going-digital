"""Newsletter signup API."""
import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from core.customer_service import subscribe_customer_to_newsletter
from core.forms_newsletter import NewsletterSubscribeForm


@method_decorator(csrf_protect, name='dispatch')
class NewsletterSubscribeView(View):
    def post(self, request):
        if request.content_type == 'application/json':
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            data = {'email': payload.get('email', '')}
        else:
            data = request.POST

        form = NewsletterSubscribeForm(data)
        if not form.is_valid():
            return JsonResponse(
                {'ok': False, 'errors': form.errors.get_json_data()},
                status=400,
            )

        try:
            subscribe_customer_to_newsletter(form.cleaned_data['email'])
        except ValueError as exc:
            return JsonResponse({'ok': False, 'message': str(exc)}, status=400)
        except ValidationError as exc:
            return JsonResponse(
                {'ok': False, 'message': exc.messages[0] if exc.messages else str(exc)},
                status=400,
            )

        return JsonResponse({
            'ok': True,
            'message': 'Thanks — you are subscribed to our newsletter.',
        })
