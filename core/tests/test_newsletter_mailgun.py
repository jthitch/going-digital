"""Tests for Mailgun newsletter sync and unsubscribe webhook."""
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.mailgun import verify_webhook_signature
from core.newsletter_sync import (
    mark_customer_unsubscribed,
    member_payload_for_customer,
    member_vars_for_customer,
)
from core.views_mailgun_webhook import MailgunNewsletterWebhookView


class MemberVarsTests(SimpleTestCase):
    def test_guest_without_name_still_builds_vars(self):
        customer = SimpleNamespace(
            pk=42,
            firstname='',
            lastname='',
            email='guest@example.com',
        )
        vars_dict = member_vars_for_customer(
            customer,
            region_ids=[3, 1],
            region_names=['South East', 'London'],
        )
        self.assertEqual(vars_dict['customer_id'], '42')
        self.assertEqual(vars_dict['first_name'], '')
        self.assertEqual(vars_dict['last_name'], '')
        self.assertEqual(vars_dict['region_ids'], '3,1')
        self.assertEqual(vars_dict['regions'], 'South East,London')

    def test_member_payload_allows_blank_name(self):
        customer = SimpleNamespace(
            pk=7,
            firstname='',
            lastname='',
            email='anon@example.com',
        )
        with patch(
            'core.newsletter_sync.region_ids_for_customer',
            return_value=[],
        ):
            payload = member_payload_for_customer(customer, region_ids=[], region_names_by_id={})
        self.assertEqual(payload['address'], 'anon@example.com')
        self.assertEqual(payload['name'], '')
        self.assertEqual(payload['vars']['regions'], '')
        self.assertTrue(payload['subscribed'])


class WebhookSignatureTests(SimpleTestCase):
    @override_settings(MAILGUN_API_KEY='test-key', MAILGUN_WEBHOOK_SIGNING_KEY='')
    def test_valid_signature(self):
        timestamp = '1710000000'
        token = 'abc123'
        expected = hmac.new(
            b'test-key',
            f'{timestamp}{token}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        self.assertTrue(verify_webhook_signature(timestamp, token, expected))
        self.assertFalse(verify_webhook_signature(timestamp, token, 'nope'))


class MarkUnsubscribedTests(SimpleTestCase):
    @patch('core.newsletter_sync.Customer.objects')
    def test_sets_newsletter_zero(self, customer_objects):
        customer = MagicMock(pk=9, newsletter=1)
        customer_objects.filter.return_value.first.return_value = customer
        result = mark_customer_unsubscribed('pat@example.com')
        self.assertIs(result, customer)
        self.assertEqual(customer.newsletter, 0)
        customer.save.assert_called_once()
        self.assertIn('newsletter', customer.save.call_args.kwargs['update_fields'])


@override_settings(
    MAILGUN_API_KEY='test-key',
    MAILGUN_NEWSLETTER_LIST='newsletter@mg.example.com',
    MAILGUN_WEBHOOK_SIGNING_KEY='test-key',
)
class MailgunWebhookViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = MailgunNewsletterWebhookView.as_view()

    def _signed_json(self, event, recipient):
        timestamp = '1710000000'
        token = 'tok'
        signature = hmac.new(
            b'test-key',
            f'{timestamp}{token}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        body = {
            'signature': {
                'timestamp': timestamp,
                'token': token,
                'signature': signature,
            },
            'event-data': {
                'event': event,
                'recipient': recipient,
            },
        }
        return json.dumps(body).encode('utf-8')

    @patch('core.views_mailgun_webhook.remove_customer_from_mailgun')
    @patch('core.views_mailgun_webhook.mark_customer_unsubscribed')
    def test_unsubscribe_event_updates_customer(self, mark_unsub, remove_member):
        mark_unsub.return_value = SimpleNamespace(pk=5)
        request = self.factory.post(
            '/newsletter/mailgun/webhook/',
            data=self._signed_json('unsubscribed', 'pat@example.com'),
            content_type='application/json',
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        mark_unsub.assert_called_once_with('pat@example.com')
        remove_member.assert_called_once_with('pat@example.com')

    @patch('core.views_mailgun_webhook.mark_customer_unsubscribed')
    def test_invalid_signature_rejected(self, mark_unsub):
        body = {
            'signature': {
                'timestamp': '1',
                'token': 't',
                'signature': 'bad',
            },
            'event-data': {'event': 'unsubscribed', 'recipient': 'a@b.com'},
        }
        request = self.factory.post(
            '/newsletter/mailgun/webhook/',
            data=json.dumps(body).encode('utf-8'),
            content_type='application/json',
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)
        mark_unsub.assert_not_called()
