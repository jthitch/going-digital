"""Logging handlers for production error alerts."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.log import AdminEmailHandler


class SuperuserEmailHandler(AdminEmailHandler):
    """
    Like Django's AdminEmailHandler, but emails active Super Users from gd_user
    (user_type_id=1) instead of settings.ADMINS.
    """

    def send_mail(self, subject, message, *args, **kwargs):
        try:
            from core.mail import server_error_recipient_emails

            recipients = server_error_recipient_emails()
        except Exception:
            recipients = []

        if not recipients:
            return

        from_email = getattr(settings, 'SERVER_EMAIL', None) or settings.DEFAULT_FROM_EMAIL
        mail = EmailMultiAlternatives(
            subject=f'{settings.EMAIL_SUBJECT_PREFIX}{subject}',
            body=message,
            from_email=from_email,
            to=recipients,
            connection=self.connection(),
        )
        html_message = kwargs.get('html_message')
        if self.include_html and html_message:
            mail.attach_alternative(html_message, 'text/html')
        mail.send(fail_silently=True)
