"""Mailgun webhook endpoints (newsletter unsubscribe)."""
from __future__ import annotations

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.mailgun import mailgun_configured, verify_webhook_signature
from core.newsletter_sync import mark_customer_unsubscribed, remove_customer_from_mailgun

logger = logging.getLogger(__name__)


def _extract_signature_parts(payload, post_data):
    """Support classic form posts and JSON event webhooks."""
    if isinstance(payload, dict):
        signature = payload.get('signature') or {}
        if isinstance(signature, dict) and signature:
            return (
                str(signature.get('timestamp') or ''),
                str(signature.get('token') or ''),
                str(signature.get('signature') or ''),
            )
    return (
        str(post_data.get('timestamp') or ''),
        str(post_data.get('token') or ''),
        str(post_data.get('signature') or ''),
    )


def _extract_event_and_recipient(payload, post_data):
    event = ''
    recipient = ''
    if isinstance(payload, dict):
        event_data = payload.get('event-data') or payload.get('event_data') or {}
        if isinstance(event_data, dict):
            event = str(event_data.get('event') or '').strip().lower()
            recipient = str(event_data.get('recipient') or '').strip()
            if not recipient:
                message = event_data.get('message') or {}
                headers = message.get('headers') or {}
                if isinstance(headers, dict):
                    recipient = str(headers.get('to') or '').strip()
        if not event:
            event = str(payload.get('event') or '').strip().lower()
        if not recipient:
            recipient = str(payload.get('recipient') or '').strip()

    if not event:
        event = str(post_data.get('event') or '').strip().lower()
    if not recipient:
        recipient = str(post_data.get('recipient') or '').strip()
    return event, recipient


@method_decorator(csrf_exempt, name='dispatch')
class MailgunNewsletterWebhookView(View):
    """
    Honour Mailgun unsubscribe events by clearing gd_customer.newsletter.

    Configure Mailgun to POST unsubscribed events to this URL. Signature is
    verified with MAILGUN_WEBHOOK_SIGNING_KEY (or MAILGUN_API_KEY).
    """

    def post(self, request):
        if not mailgun_configured():
            return HttpResponse(status=503)

        payload = None
        content_type = (request.content_type or '').lower()
        if 'application/json' in content_type:
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
            except (json.JSONDecodeError, UnicodeDecodeError):
                return HttpResponse(status=400)

        post_data = request.POST
        timestamp, token, signature = _extract_signature_parts(payload, post_data)
        if not verify_webhook_signature(timestamp, token, signature):
            logger.warning('Rejected Mailgun webhook with invalid signature')
            return HttpResponse(status=403)

        event, recipient = _extract_event_and_recipient(payload, post_data)
        # List unsubscribes and permanent unsubscribes both clear local opt-in.
        if event not in {'unsubscribed', 'unsubscribe'}:
            return JsonResponse({'ok': True, 'ignored': True, 'event': event})

        if not recipient:
            return JsonResponse({'ok': False, 'message': 'Missing recipient'}, status=400)

        # Prefer the bare email if Mailgun sends "Name <email>".
        if '<' in recipient and '>' in recipient:
            recipient = recipient.split('<', 1)[1].split('>', 1)[0].strip()

        customer = mark_customer_unsubscribed(recipient)
        # Ensure they are off the list even if Mailgun only flipped subscribed=no.
        try:
            remove_customer_from_mailgun(recipient)
        except Exception:
            logger.exception('Failed removing %s from Mailgun list after unsubscribe', recipient)

        return JsonResponse({
            'ok': True,
            'email': recipient,
            'customer_id': customer.pk if customer else None,
        })
