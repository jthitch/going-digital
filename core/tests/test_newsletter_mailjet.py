"""Tests for Mailjet newsletter sync and unsubscribe webhook."""
import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.mailjet import verify_webhook_token
from core.newsletter_sync import (
    mark_customer_unsubscribed,
    member_payload_for_customer,
    contact_properties_for_customer,
)
from core.views_mailjet_webhook import MailjetNewsletterWebhookView


class ContactPropertiesTests(SimpleTestCase):
    def test_guest_without_name_still_builds_properties(self):
        created = datetime(2022, 2, 26, 12, 0, 0, tzinfo=timezone.utc)
        customer = SimpleNamespace(
            pk=42,
            firstname='',
            lastname='',
            email='guest@example.com',
            created_at=created,
            registered_at=None,
            newsletter=1,
        )
        props = contact_properties_for_customer(
            customer,
            region_ids=[3, 1],
            region_names=['South East', 'London'],
        )
        self.assertEqual(props['customer_id'], '42')
        self.assertEqual(props['firstname'], '')
        self.assertEqual(props['lastname'], '')
        self.assertEqual(props['region_ids'], '3,1')
        self.assertEqual(props['regions'], 'South East,London')
        self.assertEqual(props['created_at'], '2022-02-26T12:00:00Z')
        self.assertIs(props['newsletter'], True)

    def test_created_at_falls_back_to_registered_at(self):
        customer = SimpleNamespace(
            pk=1,
            firstname='A',
            lastname='B',
            email='a@b.com',
            created_at=None,
            registered_at=date(2022, 2, 26),
            newsletter=1,
        )
        props = contact_properties_for_customer(customer, region_ids=[], region_names=[])
        self.assertEqual(props['created_at'], '2022-02-26T00:00:00Z')

    def test_newsletter_false_when_opted_out(self):
        customer = SimpleNamespace(
            pk=1,
            firstname='A',
            lastname='B',
            email='a@b.com',
            created_at=None,
            registered_at=None,
            newsletter=0,
        )
        props = contact_properties_for_customer(customer, region_ids=[], region_names=[])
        self.assertIs(props['newsletter'], False)

    def test_created_at_omitted_when_missing(self):
        customer = SimpleNamespace(
            pk=1,
            firstname='A',
            lastname='B',
            email='a@b.com',
            created_at=None,
            registered_at=None,
            newsletter=1,
        )
        props = contact_properties_for_customer(customer, region_ids=[], region_names=[])
        self.assertNotIn('created_at', props)

    def test_member_payload_allows_blank_name(self):
        customer = SimpleNamespace(
            pk=7,
            firstname='',
            lastname='',
            email='anon@example.com',
            created_at=None,
            registered_at=None,
            newsletter=1,
        )
        with patch(
            'core.newsletter_sync.region_ids_for_customer',
            return_value=[],
        ):
            payload = member_payload_for_customer(
                customer,
                region_ids=[],
                region_names_by_id={},
            )
        self.assertEqual(payload['Email'], 'anon@example.com')
        self.assertEqual(payload['Name'], '')
        self.assertEqual(payload['Properties']['regions'], '')
        self.assertNotIn('created_at', payload['Properties'])
        self.assertIs(payload['Properties']['newsletter'], True)

class WebhookTokenTests(SimpleTestCase):
    @override_settings(MAILJET_WEBHOOK_TOKEN='')
    def test_blank_token_allows_any(self):
        self.assertTrue(verify_webhook_token(''))
        self.assertTrue(verify_webhook_token('anything'))

    @override_settings(MAILJET_WEBHOOK_TOKEN='secret')
    def test_requires_matching_token(self):
        self.assertTrue(verify_webhook_token('secret'))
        self.assertFalse(verify_webhook_token('nope'))
        self.assertFalse(verify_webhook_token(''))


class MarkUnsubscribedTests(SimpleTestCase):
    @patch('core.newsletter_sync.Customer.objects')
    def test_sets_newsletter_zero_on_all_matching_rows(self, customer_objects):
        customer = MagicMock(pk=9, newsletter=1)
        qs = MagicMock()
        qs.first.return_value = customer
        qs.filter.return_value.update.return_value = 2
        customer_objects.filter.return_value = qs

        result = mark_customer_unsubscribed('pat@example.com')

        self.assertIs(result, customer)
        customer_objects.filter.assert_called_once_with(email__iexact='pat@example.com')
        qs.filter.assert_called_once_with(newsletter=1)
        qs.filter.return_value.update.assert_called_once()
        update_kwargs = qs.filter.return_value.update.call_args.kwargs
        self.assertEqual(update_kwargs['newsletter'], 0)
        self.assertIn('updated_at', update_kwargs)


@override_settings(
    MAILJET_API_KEY='pub',
    MAILJET_API_SECRET='priv',
    MAILJET_NEWSLETTER_LIST_ID='99',
    MAILJET_WEBHOOK_TOKEN='secret',
)
class MailjetWebhookViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = MailjetNewsletterWebhookView.as_view()

    @patch('core.views_mailjet_webhook.remove_customer_from_mailjet')
    @patch('core.views_mailjet_webhook.mark_customer_unsubscribed')
    def test_unsub_event_updates_customer(self, mark_unsub, remove_member):
        mark_unsub.return_value = SimpleNamespace(pk=5)
        body = json.dumps([{
            'event': 'unsub',
            'email': 'pat@example.com',
            'mj_list_id': 99,
        }]).encode('utf-8')
        request = self.factory.post(
            '/newsletter/mailjet/webhook/?token=secret',
            data=body,
            content_type='application/json',
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        mark_unsub.assert_called_once_with('pat@example.com')
        remove_member.assert_called_once_with('pat@example.com')

    @patch('core.views_mailjet_webhook.mark_customer_unsubscribed')
    def test_invalid_token_rejected(self, mark_unsub):
        body = json.dumps([{
            'event': 'unsub',
            'email': 'a@b.com',
        }]).encode('utf-8')
        request = self.factory.post(
            '/newsletter/mailjet/webhook/?token=wrong',
            data=body,
            content_type='application/json',
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)
        mark_unsub.assert_not_called()
