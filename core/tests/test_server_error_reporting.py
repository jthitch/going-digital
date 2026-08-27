from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.logging_handlers import SuperuserEmailHandler
from core.mail import server_error_recipient_emails, superuser_notification_emails


class ServerErrorRecipientEmailsTests(SimpleTestCase):
    @override_settings(EMAIL_SUPPRESS_RECIPIENTS=[])
    @patch('core.models.User.objects')
    def test_returns_active_superuser_emails(self, user_objects):
        user_objects.filter.return_value.exclude.return_value.exclude.return_value = [
            SimpleNamespace(email='admin@example.com'),
            SimpleNamespace(email='ops@example.com'),
        ]
        self.assertEqual(
            server_error_recipient_emails(),
            ['admin@example.com', 'ops@example.com'],
        )

    @override_settings(EMAIL_SUPPRESS_RECIPIENTS=['admin@example.com'])
    @patch('core.models.User.objects')
    def test_respects_suppress_list(self, user_objects):
        user_objects.filter.return_value.exclude.return_value.exclude.return_value = [
            SimpleNamespace(email='admin@example.com'),
            SimpleNamespace(email='ops@example.com'),
        ]
        self.assertEqual(server_error_recipient_emails(), ['ops@example.com'])

    @override_settings(EMAIL_SUPERUSER_BCC_ENABLED=False, EMAIL_SUPPRESS_RECIPIENTS=[])
    @patch('core.mail.server_error_recipient_emails', return_value=['admin@example.com'])
    def test_booking_bcc_still_respects_toggle(self, _mocked):
        self.assertEqual(superuser_notification_emails(), [])


class SuperuserEmailHandlerTests(SimpleTestCase):
    @override_settings(
        DEFAULT_FROM_EMAIL='noreply@example.com',
        SERVER_EMAIL='errors@example.com',
        EMAIL_SUBJECT_PREFIX='[GD] ',
    )
    @patch('core.logging_handlers.EmailMultiAlternatives')
    @patch('core.mail.server_error_recipient_emails', return_value=['admin@example.com'])
    def test_sends_to_superusers(self, _recipients, mail_cls):
        handler = SuperuserEmailHandler(include_html=True)
        handler.connection = MagicMock(return_value=MagicMock())
        mail = MagicMock()
        mail_cls.return_value = mail

        handler.send_mail('Internal Server Error: /boom/', 'Traceback…', html_message='<p>err</p>')

        mail_cls.assert_called_once()
        kwargs = mail_cls.call_args.kwargs
        self.assertEqual(kwargs['to'], ['admin@example.com'])
        self.assertEqual(kwargs['from_email'], 'errors@example.com')
        self.assertTrue(kwargs['subject'].startswith('[GD] '))
        mail.attach_alternative.assert_called_once_with('<p>err</p>', 'text/html')
        mail.send.assert_called_once_with(fail_silently=True)

    @patch('core.logging_handlers.EmailMultiAlternatives')
    @patch('core.mail.server_error_recipient_emails', return_value=[])
    def test_skips_when_no_recipients(self, _recipients, mail_cls):
        handler = SuperuserEmailHandler()
        handler.send_mail('Error', 'body')
        mail_cls.assert_not_called()
