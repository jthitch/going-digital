"""
Celery tasks for async email sending (optional - can use sync email for now).
"""
from django.core.mail import send_mail
from django.conf import settings
from bookings.models import Booking


def send_booking_confirmation_email(booking_id):
    """Send booking confirmation email."""
    try:
        booking = Booking.objects.get(id=booking_id)
        subject = f"Booking Confirmed: {booking.course_instance.course.title}"
        message = f"""
        Dear {booking.student_first_name} {booking.student_last_name},
        
        Your booking has been confirmed!
        
        Booking Reference: {booking.booking_reference}
        Course: {booking.course_instance.course.title}
        Date: {booking.course_instance.start_date.strftime('%B %d, %Y at %I:%M %p')}
        Location: {booking.course_instance.location.full_address}
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


def send_payment_success_email(booking_id):
    """Send payment success email."""
    # Similar to booking confirmation but can include payment receipt
    pass
