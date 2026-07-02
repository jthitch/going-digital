"""Password reset tokens and email for gd_customer accounts."""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.mail import send_html_email
from core.models import Customer

logger = logging.getLogger(__name__)

RESET_TOKEN_MAX_AGE = getattr(settings, 'CUSTOMER_PASSWORD_RESET_TIMEOUT', 15 * 60)


def _reset_token_age():
    return timedelta(seconds=RESET_TOKEN_MAX_AGE)


def generate_reset_token():
    return secrets.token_urlsafe(32)[:99]


def issue_password_reset_token(customer):
    token = generate_reset_token()
    customer.password_reset_token = token
    customer.last_reset_password_date = timezone.now()
    customer.updated_at = timezone.now()
    customer.save(update_fields=[
        'password_reset_token',
        'last_reset_password_date',
        'updated_at',
    ])
    return token


def clear_password_reset_token(customer):
    customer.password_reset_token = None
    customer.updated_at = timezone.now()
    customer.save(update_fields=['password_reset_token', 'updated_at'])


def customer_for_reset_token(token):
    token = (token or '').strip()
    if not token:
        return None

    customer = Customer.objects.filter(password_reset_token=token).first()
    if not customer or not customer.is_active:
        return None

    issued_at = customer.last_reset_password_date
    if not issued_at:
        return None
    if timezone.now() - issued_at > _reset_token_age():
        return None

    if not secrets.compare_digest(customer.password_reset_token or '', token):
        return None

    return customer


def eligible_for_password_reset(customer):
    if not customer or not customer.is_active:
        return False
    return bool((customer.email or '').strip())


def send_customer_password_reset_email(customer, request=None):
    token = issue_password_reset_token(customer)
    reset_path = f'/account/password-reset/confirm/{token}/'
    if request is not None:
        reset_url = request.build_absolute_uri(reset_path)
    else:
        site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
        reset_url = f'{site_url}{reset_path}'

    context = {
        'customer': customer,
        'reset_url': reset_url,
        'site_url': getattr(settings, 'SITE_URL', ''),
        'contact_email': getattr(settings, 'CONTACT_EMAIL', ''),
    }
    send_html_email(
        to=[customer.email.strip()],
        subject='Reset your Going Digital password',
        html_template='emails/password_reset.html',
        text_template='emails/password_reset.txt',
        context=context,
        fail_silently=False,
    )
    logger.info('Sent password reset email to %s', customer.email)
