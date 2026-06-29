"""Student account helpers — gd_customer booking linkage and password detection."""
from django.db.models import Q
from django.utils import timezone

from bookings.models import Booking
from core.customer_auth import customer_has_sign_in_password
from core.customer_service import get_or_create_customer_record
from core.models import Customer


def link_bookings_to_customer(customer):
    """Attach bookings booked with this email to the signed-in customer."""
    if not customer or not customer.email:
        return 0
    return Booking.objects.filter(
        student_email__iexact=customer.email.strip(),
    ).exclude(customer_id=customer.pk).update(customer_id=customer.pk)


def customer_needs_account_setup(customer):
    """True when the student should set a password to finish account creation."""
    if not customer or not customer.is_active:
        return False
    return not customer_has_sign_in_password(customer)


def resolve_customer_for_email(email, *, firstname='', lastname='', phone=''):
    if not email:
        return None
    customer = Customer.objects.filter(email__iexact=email.strip()).first()
    if customer:
        return customer
    if firstname or lastname or phone:
        customer, _ = get_or_create_customer_record(email, firstname, lastname, phone)
        return customer
    return None


def complete_customer_account(customer, password, *, firstname=None, lastname=None):
    """Set password and profile fields on gd_customer (not gd_user)."""
    if customer_has_sign_in_password(customer):
        raise ValueError('This account already has a password. Please sign in instead.')

    if firstname:
        customer.firstname = firstname
    if lastname:
        customer.lastname = lastname
    customer.active = 1
    customer.guest_account = 0
    customer.registered_at = timezone.now().date()
    customer.set_password(password)
    customer.updated_at = timezone.now()
    customer.save()
    link_bookings_to_customer(customer)
    return customer


def account_setup_from_bookings(bookings):
    """
    Build account-setup context from confirmed booking(s).
    Returns dict or None when setup is not offered.
    """
    booking_list = list(bookings or [])
    if not booking_list:
        return None

    primary = booking_list[0]
    email = (primary.student_email or '').strip()
    if not email:
        return None

    customer = (
        primary.customer
        or resolve_customer_for_email(
            email,
            firstname=primary.student_first_name,
            lastname=primary.student_last_name,
            phone=primary.student_phone or '',
        )
    )
    if not customer or not customer_needs_account_setup(customer):
        return None

    firstname = primary.student_first_name or customer.firstname or ''
    lastname = primary.student_last_name or customer.lastname or ''

    return {
        'email': email,
        'firstname': firstname,
        'lastname': lastname,
        'customer': customer,
        'booking_reference': primary.booking_reference,
    }


def payment_account_context_from_checkout_data(data, *, is_authenticated=False):
    """Build account CTA from session-stored checkout data when payment lookup fails."""
    if is_authenticated or not data:
        return None

    email = (data.get('email') or '').strip()
    if not email:
        return None

    customer = resolve_customer_for_email(
        email,
        firstname=data.get('firstname', ''),
        lastname=data.get('lastname', ''),
    )
    base = {
        'email': email,
        'firstname': data.get('firstname') or (customer.firstname if customer else ''),
        'lastname': data.get('lastname') or (customer.lastname if customer else ''),
        'booking_reference': data.get('booking_reference') or '',
    }

    if customer and customer_needs_account_setup(customer):
        setup = {
            'email': email,
            'firstname': base['firstname'],
            'lastname': base['lastname'],
            'customer': customer,
            'booking_reference': base['booking_reference'],
        }
        return {**base, 'mode': 'setup', 'setup': setup}

    return {**base, 'mode': 'sign_in'}


def payment_account_context_from_bookings(bookings, *, is_authenticated=False):
    """
    Account CTA for the payment success page.
    Returns setup form context, or a sign-in prompt when a password already exists.
    """
    if is_authenticated:
        return None

    booking_list = list(bookings or [])
    if not booking_list:
        return None

    primary = booking_list[0]
    email = (primary.student_email or '').strip()
    if not email:
        return None

    customer = primary.customer or resolve_customer_for_email(
        email,
        firstname=primary.student_first_name,
        lastname=primary.student_last_name,
        phone=primary.student_phone or '',
    )
    base = {
        'email': email,
        'firstname': primary.student_first_name or (customer.firstname if customer else ''),
        'lastname': primary.student_last_name or (customer.lastname if customer else ''),
        'booking_reference': primary.booking_reference,
    }

    if customer and customer_needs_account_setup(customer):
        setup = account_setup_from_bookings(booking_list)
        if setup:
            return {
                **base,
                'mode': 'setup',
                'setup': setup,
            }

    return {
        **base,
        'mode': 'sign_in',
    }


def bookings_for_customer(customer):
    """Bookings owned by or booked under this student's email."""
    email = (customer.email or '').strip()
    qs = Booking.objects.filter(customer_id=customer.pk)
    if email:
        qs = Booking.objects.filter(
            Q(customer_id=customer.pk) | Q(student_email__iexact=email),
        )
    return qs.select_related(
        'workshop',
        'workshop__course',
        'workshop__venue',
        'payment',
    ).distinct()


def customer_can_view_booking(request, booking):
    """
    True when a signed-in student owns the booking, or the browser session
    still has post-checkout access for that booking's email.
    """
    from core.customer_auth import is_customer_authenticated

    if is_customer_authenticated(request):
        customer = request.customer
        return bookings_for_customer(customer).filter(pk=booking.pk).exists()

    student_email = (booking.student_email or '').strip().lower()
    if not student_email:
        return False

    from payments.checkout_session_context import (
        get_checkout_success_context,
        load_bookings_from_checkout_context,
    )

    checkout_bookings = load_bookings_from_checkout_context(request)
    if any(item.pk == booking.pk for item in checkout_bookings):
        return True

    session_email = (request.session.get('account_setup_email') or '').strip().lower()
    checkout_email = (get_checkout_success_context(request).get('email') or '').strip().lower()
    return student_email in {session_email, checkout_email}
