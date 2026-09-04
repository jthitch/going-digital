"""
Email sending for payments (sync for now; can move to Celery later).
"""
import logging

from django.conf import settings
from bookings.email_context import (
    booking_confirmation_subject,
    bookings_confirmation_context,
)
from bookings.gift_voucher_basket import get_basket
from bookings.models import Booking
from core.mail import booking_confirmation_bcc_emails, send_html_email

logger = logging.getLogger(__name__)


def send_booking_confirmation_email(booking_id):
    """Send booking confirmation for a single booking id."""
    return send_booking_confirmation_emails([booking_id])


def send_booking_confirmation_emails(booking_ids):
    """
    Send one confirmation email covering all booking ids in a checkout.
    BCC franchisees/tutors for every workshop involved, plus the office inbox.
    """
    ids = [int(booking_id) for booking_id in booking_ids if booking_id]
    if not ids:
        return False

    bookings = list(
        Booking.objects.filter(id__in=ids)
        .select_related(
            'workshop',
            'workshop__course',
            'workshop__venue',
            'payment',
        )
        .order_by('id')
    )
    if not bookings:
        logger.warning('Bookings %s not found for confirmation email', ids)
        return False

    # Preserve checkout order when metadata provides an ordered id list.
    by_id = {booking.id: booking for booking in bookings}
    ordered = [by_id[booking_id] for booking_id in ids if booking_id in by_id]
    if not ordered:
        return False

    subject = booking_confirmation_subject(ordered)
    context = bookings_confirmation_context(ordered)

    student_email = ordered[0].student_email.strip()
    bcc = booking_confirmation_bcc_emails(ordered, student_email=student_email)

    attachments = []
    seen_filenames = set()
    from courses.venue_documents import booking_email_venue_document_attachment
    from courses.workshop_documents import booking_email_workshop_document_attachments

    for item in context['booking_items']:
        if item.get('calendar_ics'):
            filename = item['calendar_ics_filename']
            if filename not in seen_filenames:
                seen_filenames.add(filename)
                attachments.append((
                    filename,
                    item['calendar_ics'],
                    'text/calendar; method=PUBLISH; charset=UTF-8',
                ))

        workshop = item.get('workshop')
        if not workshop:
            continue

        venue_document = booking_email_venue_document_attachment(workshop)
        if venue_document:
            filename = venue_document[0]
            if filename not in seen_filenames:
                seen_filenames.add(filename)
                attachments.append(venue_document)

        for attachment in booking_email_workshop_document_attachments(workshop):
            filename = attachment[0]
            if filename in seen_filenames:
                continue
            seen_filenames.add(filename)
            attachments.append(attachment)

    send_html_email(
        to=[student_email],
        subject=subject,
        html_template='emails/booking_confirmation.html',
        text_template='emails/booking_confirmation.txt',
        context=context,
        bcc=bcc,
        attachments=attachments,
        fail_silently=False,
    )
    return True


def _format_voucher_codes(voucher_codes):
    """Accept (code, value) rows or bare code strings."""
    lines = []
    for item in voucher_codes:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            code, value = item[0], item[1]
        else:
            code, value = item, ''
        lines.append(f'  {code} (£{value})')
    return '\n'.join(lines)


def send_gift_voucher_confirmation_email(basket_id, voucher_codes):
    """Send gift voucher purchase confirmation to purchaser; BCC office inbox."""
    from django.core.mail import EmailMessage

    from core.mail import filter_suppressed_recipients, order_office_notification_emails

    basket = get_basket(basket_id)
    if not basket or basket.get('basket_data', {}).get('type') != 'gift_voucher':
        logger.warning('Gift voucher basket %s not found for confirmation email', basket_id)
        return False

    data = basket['basket_data']
    amount = data.get('amount', 0)
    quantity = data.get('quantity', 1)
    total = data.get('total', 0)
    purchaser_email = (data.get('purchaser_email') or '').strip()
    if not purchaser_email:
        logger.warning('No purchaser email on gift voucher basket %s', basket_id)
        return False

    if not voucher_codes:
        logger.warning('No voucher codes to email for basket %s', basket_id)
        return False

    recipients = filter_suppressed_recipients([purchaser_email])
    if not recipients:
        logger.warning('Purchaser email suppressed for gift voucher basket %s', basket_id)
        return False

    purchaser_key = purchaser_email.lower()
    bcc = [
        addr for addr in order_office_notification_emails()
        if addr and addr.strip().lower() != purchaser_key
    ]

    codes_text = _format_voucher_codes(voucher_codes)
    subject = f'Your Going Digital Gift Voucher - {quantity} voucher(s)'
    message = f"""
Thank you for your gift voucher purchase!

Amount: £{amount} x {quantity} = £{total}

Your voucher code(s):
{codes_text}

The voucher(s) are valid for 9 months and can be used towards any of our photography courses. Present the code when booking.

If you have any questions, please contact us.
"""
    msg = EmailMessage(
        subject,
        message.strip(),
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        bcc=bcc or None,
    )
    msg.send(fail_silently=False)
    logger.info(
        'Sent gift voucher confirmation for basket %s to %s (bcc=%s)',
        basket_id,
        recipients,
        bcc,
    )
    return True


def send_gift_voucher_card_email(basket_id, voucher_index, design_id, recipient_email):
    """Render and email a gift card PNG attachment."""
    from django.core.mail import EmailMessage

    from core.mail import filter_suppressed_recipients
    from payments.gift_voucher_cards import render_gift_voucher_card

    recipient_email = (recipient_email or '').strip()
    recipients = filter_suppressed_recipients([recipient_email])
    if not recipients:
        logger.warning('No recipient email for gift card on basket %s', basket_id)
        return False

    try:
        png_bytes, code = render_gift_voucher_card(basket_id, voucher_index, design_id)
    except Exception:
        logger.exception('Failed to render gift card for basket %s', basket_id)
        return False

    basket = get_basket(basket_id)
    data = basket.get('basket_data', {}) if basket else {}
    recipient_name = (data.get('recipient_name') or '').strip()
    subject = 'Your Going Digital gift voucher'
    if recipient_name:
        subject = f'Gift voucher for {recipient_name}'

    message = f"""
Your gift voucher is attached as an image you can print or forward.

Voucher code: {code}

The voucher is valid for 9 months and can be used towards any of our photography courses.

If you have any questions, please contact us.
""".strip()

    msg = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
    )
    msg.attach(f'gift-voucher-{code}.png', png_bytes, 'image/png')
    try:
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception('Failed to email gift card for basket %s', basket_id)
        return False
