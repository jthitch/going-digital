"""Outgoing email helpers (Mailjet SMTP via Django settings)."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _normalise_email(addr):
    return (addr or '').strip().lower()


def get_suppressed_recipients():
    return set(getattr(settings, 'EMAIL_SUPPRESS_RECIPIENTS', []) or [])


def filter_suppressed_recipients(addresses):
    """Drop addresses listed in EMAIL_SUPPRESS_RECIPIENTS (.env, comma-separated)."""
    suppressed = get_suppressed_recipients()
    if not suppressed:
        return [addr for addr in addresses if addr and str(addr).strip()]
    filtered = []
    removed = []
    for addr in addresses:
        if not addr or not str(addr).strip():
            continue
        if _normalise_email(addr) in suppressed:
            removed.append(addr)
            continue
        filtered.append(addr.strip())
    if removed:
        logger.info('Suppressed email recipient(s): %s', removed)
    return filtered


def send_html_email(
    *,
    to,
    subject,
    html_template,
    text_template=None,
    context=None,
    bcc=None,
    attachments=None,
    fail_silently=False,
):
    """
    Send multipart HTML + plain-text email.

    Mirrors legacy cf_send_mail(): primary recipients in ``to``, franchisees/staff in ``bcc``.
    """
    context = context or {}
    to = filter_suppressed_recipients(to)
    bcc = filter_suppressed_recipients(bcc or [])
    if not to:
        return 0

    html_body = render_to_string(html_template, context)
    if text_template:
        text_body = render_to_string(text_template, context)
    else:
        text_body = strip_tags(html_body)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        bcc=bcc or None,
    )
    msg.attach_alternative(html_body, 'text/html')

    for attachment in attachments or []:
        if len(attachment) == 2:
            filename, content = attachment
            mimetype = None
        else:
            filename, content, mimetype = attachment
        msg.attach(filename, content, mimetype)

    try:
        sent = msg.send(fail_silently=fail_silently)
        logger.info('Sent email "%s" to %s (bcc=%s)', subject, to, bcc)
        return sent
    except Exception:
        logger.exception('Failed to send email "%s" to %s', subject, to)
        if not fail_silently:
            raise
        return 0


def send_filtered_mail(subject, message, from_email, recipient_list, **kwargs):
    """Like django.core.mail.send_mail but honours EMAIL_SUPPRESS_RECIPIENTS."""
    from django.core.mail import send_mail

    recipient_list = filter_suppressed_recipients(recipient_list)
    if not recipient_list:
        logger.info('Skipped email "%s" — all recipients suppressed', subject)
        return 0
    return send_mail(subject, message, from_email, recipient_list, **kwargs)


def franchisee_emails_for_workshop(workshop):
    """Emails for workshop owner/creator, course creator, region franchisees, and tutor."""
    from core.models import User
    from courses.models import RegionUser, Tutor

    if not getattr(settings, 'EMAIL_FRANCHISEE_BCC_ENABLED', True):
        return []

    if not workshop:
        return []

    user_ids = set()
    if workshop.user_id:
        user_ids.add(workshop.user_id)
    if workshop.createdby_id:
        user_ids.add(workshop.createdby_id)
    if workshop.region_id:
        user_ids.update(
            RegionUser.objects.filter(region_id=workshop.region_id).values_list('user_id', flat=True)
        )

    course = getattr(workshop, 'course', None)
    if course is not None:
        course_createdby = getattr(course, 'createdby_id', None)
        if course_createdby:
            user_ids.add(course_createdby)

    emails = set()
    for uid in user_ids:
        user = User.objects.filter(pk=uid, active=1).first()
        if user and user.email:
            emails.add(user.email.strip().lower())

    if workshop.tutor_id:
        tutor = Tutor.objects.filter(pk=workshop.tutor_id).first()
        if tutor and tutor.email:
            emails.add(tutor.email.strip().lower())

    return filter_suppressed_recipients(sorted(emails))


def superuser_notification_emails():
    """Active Super Users (user_type_id=1) to BCC on booking confirmations."""
    if not getattr(settings, 'EMAIL_SUPERUSER_BCC_ENABLED', True):
        return []
    return server_error_recipient_emails()


def server_error_recipient_emails():
    """
    Active Super Users (user_type_id=1) who should receive production 500 alerts.
    Always on (not gated by EMAIL_SUPERUSER_BCC_ENABLED); still respects suppress list.
    """
    from core.models import User

    emails = []
    for user in User.objects.filter(active=1, user_type_id=1).exclude(email='').exclude(email__isnull=True):
        addr = (user.email or '').strip().lower()
        if addr:
            emails.append(addr)
    return filter_suppressed_recipients(sorted(set(emails)))


def booking_confirmation_bcc_emails(bookings, *, student_email=''):
    """
    BCC list for booking confirmations: franchisees/tutors/course creators + super users.
    Student address is excluded so they only appear in ``to``.
    """
    student_key = _normalise_email(student_email)
    bcc = []
    seen = set()

    for booking in bookings or []:
        for addr in franchisee_emails_for_workshop(getattr(booking, 'workshop', None)):
            key = _normalise_email(addr)
            if not key or key == student_key or key in seen:
                continue
            seen.add(key)
            bcc.append(addr.strip())

    for addr in superuser_notification_emails():
        key = _normalise_email(addr)
        if not key or key == student_key or key in seen:
            continue
        seen.add(key)
        bcc.append(addr.strip())

    return bcc
