from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


@override_settings(
    DEFAULT_FROM_EMAIL='noreply@example.com',
    EMAIL_SUPPRESS_RECIPIENTS=[],
    CONTACT_EMAIL='enquiries@goingdigital.co.uk',
)
class GiftVoucherConfirmationEmailTests(SimpleTestCase):
    def _basket(self):
        return {
            'basket_data': {
                'type': 'gift_voucher',
                'amount': 50,
                'quantity': 1,
                'total': 50,
                'purchaser_email': 'buyer@example.com',
            },
        }

    @patch('django.core.mail.EmailMessage')
    @patch('payments.tasks.get_basket')
    def test_bccs_office_inbox_excluding_purchaser(self, get_basket, email_message_cls):
        from payments.tasks import send_gift_voucher_confirmation_email

        get_basket.return_value = self._basket()
        msg = MagicMock()
        email_message_cls.return_value = msg

        ok = send_gift_voucher_confirmation_email(12, [('ABCD1234', 50)])

        self.assertTrue(ok)
        args, kwargs = email_message_cls.call_args
        self.assertEqual(args[0], 'Your Going Digital Gift Voucher - 1 voucher(s)')
        self.assertIn('ABCD1234', args[1])
        self.assertEqual(args[2], 'noreply@example.com')
        self.assertEqual(args[3], ['buyer@example.com'])
        self.assertEqual(kwargs['bcc'], ['enquiries@goingdigital.co.uk'])
        msg.send.assert_called_once_with(fail_silently=False)

    @patch('django.core.mail.EmailMessage')
    @patch('payments.tasks.get_basket')
    @override_settings(CONTACT_EMAIL='buyer@example.com')
    def test_no_bcc_when_office_is_purchaser(self, get_basket, email_message_cls):
        from payments.tasks import send_gift_voucher_confirmation_email

        get_basket.return_value = self._basket()
        msg = MagicMock()
        email_message_cls.return_value = msg

        ok = send_gift_voucher_confirmation_email(12, [('ABCD1234', 50)])

        self.assertTrue(ok)
        self.assertIsNone(email_message_cls.call_args.kwargs.get('bcc'))
        msg.send.assert_called_once_with(fail_silently=False)

    @patch('django.core.mail.EmailMessage')
    @patch('payments.tasks.get_basket')
    @override_settings(CONTACT_EMAIL='')
    def test_no_bcc_when_contact_email_empty(self, get_basket, email_message_cls):
        from payments.tasks import send_gift_voucher_confirmation_email

        get_basket.return_value = self._basket()
        msg = MagicMock()
        email_message_cls.return_value = msg

        ok = send_gift_voucher_confirmation_email(12, [('ABCD1234', 50)])

        self.assertTrue(ok)
        self.assertIsNone(email_message_cls.call_args.kwargs.get('bcc'))
        msg.send.assert_called_once_with(fail_silently=False)
