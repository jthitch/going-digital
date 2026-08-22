"""Persist checkout purchaser details until the payment success page loads."""
from bookings.models import Booking

CHECKOUT_SUCCESS_SESSION_KEY = 'checkout_success_context'
AUTHORIZED_WORKSHOP_CHECKOUT_KEY = 'authorized_workshop_checkout'


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


def store_checkout_success_context_from_basket(request, basket_data):
    """Remember purchaser details when bookings are created only after payment."""
    items = basket_data.get('items') or []
    lead = items[0] if items else {}
    email = (
        basket_data.get('purchaser_email')
        or lead.get('student_email')
        or ''
    ).strip().lower()
    request.session[CHECKOUT_SUCCESS_SESSION_KEY] = {
        'booking_ids': list(basket_data.get('booking_ids') or []),
        'email': email,
        'firstname': lead.get('student_first_name') or '',
        'lastname': lead.get('student_last_name') or '',
        'booking_reference': '',
        'workshop_basket_id': basket_data.get('id'),
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


def authorize_workshop_checkout(request, *, basket_id=None, booking_ids=None):
    """
    Bind pending booking/basket checkout to the current browser session.

    Prevents IDOR access to /payments/checkout/<id>/ by guessing sequential ids.
    """
    booking_ids = [int(pk) for pk in (booking_ids or []) if pk]
    request.session[AUTHORIZED_WORKSHOP_CHECKOUT_KEY] = {
        'basket_id': basket_id,
        'booking_ids': booking_ids,
    }
    request.session.modified = True


def clear_authorized_workshop_checkout(request):
    if AUTHORIZED_WORKSHOP_CHECKOUT_KEY in request.session:
        del request.session[AUTHORIZED_WORKSHOP_CHECKOUT_KEY]
        request.session.modified = True


def _authorized_workshop_checkout(request):
    return request.session.get(AUTHORIZED_WORKSHOP_CHECKOUT_KEY) or {}


def is_booking_checkout_authorized(request, booking_id):
    try:
        booking_id = int(booking_id)
    except (TypeError, ValueError):
        return False
    return booking_id in _authorized_workshop_checkout(request).get('booking_ids', [])


def is_basket_checkout_authorized(request, basket_id):
    try:
        basket_id = int(basket_id)
    except (TypeError, ValueError):
        return False
    return _authorized_workshop_checkout(request).get('basket_id') == basket_id
