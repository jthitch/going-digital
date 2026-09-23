"""Mailjet webhook endpoints (newsletter unsubscribe)."""
from __future__ import annotations

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.mailjet import mailjet_configured, verify_webhook_token
from core.newsletter_sync import mark_customer_unsubscribed, remove_customer_from_mailjet

logger = logging.getLogger(__name__)


def _parse_events(request):
    """Mailjet posts a JSON array of event objects (or a single object)."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '[]')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return payload
    return None


def _event_email(event):
    email = str(event.get('email') or event.get('Email') or '').strip()
    if '<' in email and '>' in email:
        email = email.split('<', 1)[1].split('>', 1)[0].strip()
    return email


@method_decorator(csrf_exempt, name='dispatch')
class MailjetNewsletterWebhookView(View):
    """
    Honour Mailjet ``unsub`` events by clearing gd_customer.newsletter.

    Configure Mailjet Event tracking (unsub) to POST to this URL. Optionally
    append ``?token=...`` matching MAILJET_WEBHOOK_TOKEN.
    """

    def post(self, request):
        if not mailjet_configured():
            return HttpResponse(status=503)

        provided = (
            request.GET.get('token')
            or request.headers.get('X-Mailjet-Webhook-Token')
            or ''
        ).strip()
        if not verify_webhook_token(provided):
            logger.warning('Rejected Mailjet webhook with invalid token')
            return HttpResponse(status=403)

        events = _parse_events(request)
        if events is None:
            return HttpResponse(status=400)

        updated = []
        for event in events:
            event_type = str(event.get('event') or '').strip().lower()
            if event_type not in {'unsub', 'unsubscribed', 'unsubscribe'}:
                continue
            email = _event_email(event)
            if not email:
                continue
            customer = mark_customer_unsubscribed(email)
            try:
                remove_customer_from_mailjet(email)
            except Exception:
                logger.exception(
                    'Failed removing %s from Mailjet list after unsubscribe',
                    email,
                )
            updated.append({
                'email': email,
                'customer_id': customer.pk if customer else None,
            })

        return JsonResponse({'ok': True, 'updated': updated})
