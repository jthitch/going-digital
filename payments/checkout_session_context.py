"""Persist checkout purchaser details until the payment success page loads."""
from bookings.models import Booking

CHECKOUT_SUCCESS_SESSION_KEY = 'checkout_success_context'


def store_checkout_success_context(request, bookings):
    """Remember booking ids and purchaser email before redirecting to Stripe."""
    booking_list = list(bookings)
    if not booking_list:
        return

    primary = booking_list[0]
    request.session[CHECKOUT_SUCCESS_SESSION_KEY] = {
        'booking_ids': [b.id for b in booking_list],
        'email': (primary.student_email or '').strip().lower(),
        'firstname': primary.student_first_name or '',
        'lastname': primary.student_last_name or '',
        'booking_reference': primary.booking_reference or '',
    }
    request.session.modified = True


def get_checkout_success_context(request):
    return request.session.get(CHECKOUT_SUCCESS_SESSION_KEY) or {}


def clear_checkout_success_context(request):
    if CHECKOUT_SUCCESS_SESSION_KEY in request.session:
        del request.session[CHECKOUT_SUCCESS_SESSION_KEY]
        request.session.modified = True


def load_bookings_from_checkout_context(request):
    data = get_checkout_success_context(request)
    booking_ids = data.get('booking_ids') or []
    if not booking_ids:
        return Booking.objects.none()
    return Booking.objects.filter(id__in=booking_ids).select_related(
        'workshop', 'workshop__course', 'workshop__venue', 'user',
    ).order_by('id')
