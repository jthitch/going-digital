"""
Celery tasks for async email sending (optional - can use sync email for now).
"""
from django.core.mail import send_mail
from django.conf import settings
from bookings.models import Booking
from bookings.gift_voucher_basket import get_basket


def send_booking_confirmation_email(booking_id):
    """Send booking confirmation email."""
    try:
        booking = Booking.objects.get(id=booking_id)
        subject = f"Booking Confirmed: {booking.workshop.course.title if booking.workshop.course else 'Workshop'}"
        message = f"""
        Dear {booking.student_first_name} {booking.student_last_name},
        
        Your booking has been confirmed!
        
        Booking Reference: {booking.booking_reference}
            Course: {booking.workshop.course.title if booking.workshop.course else 'Workshop'}
            Date: {booking.workshop.start_date.strftime('%d %B %Y at %I:%M %p')}
            Location: {booking.workshop.venue.venue_address or booking.workshop.venue.name if booking.workshop.venue else 'TBC'}
        Price Paid: ${booking.price_paid}
        
        We look forward to seeing you!
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.student_email],
            fail_silently=False,
        )
    except Booking.DoesNotExist:
        pass


def send_gift_voucher_confirmation_email(basket_id, voucher_codes):
    """Send gift voucher purchase confirmation and voucher details to purchaser."""
    try:
        basket = get_basket(basket_id)
        if not basket or basket.get('basket_data', {}).get('type') != 'gift_voucher':
            return
        data = basket['basket_data']
        amount = data.get('amount', 0)
        quantity = data.get('quantity', 1)
        total = data.get('total', 0)
        purchaser_email = data.get('purchaser_email', '')
        if not purchaser_email:
            return

        codes_text = '\n'.join(f'  {code} (£{value})' for code, value in voucher_codes)

        subject = f"Your Going Digital Gift Voucher - {quantity} voucher(s)"
        message = f"""
Thank you for your gift voucher purchase!

Amount: £{amount} x {quantity} = £{total}

Your voucher code(s):
{codes_text}

The voucher(s) are valid for 9 months and can be used towards any of our photography courses. Present the code when booking.

If you have any questions, please contact us.
"""
        send_mail(
            subject,
            message.strip(),
            settings.DEFAULT_FROM_EMAIL,
            [purchaser_email],
            fail_silently=False,
        )
    except Exception:
        pass


def send_payment_success_email(booking_id):
    """Send payment success email."""
    # Similar to booking confirmation but can include payment receipt
    pass
