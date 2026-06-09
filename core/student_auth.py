"""Student account helpers — booking linkage and password detection."""
from django.contrib.auth.hashers import identify_hasher
from django.db.models import Q

from bookings.models import Booking
from core.models import User


def is_django_password_hash(stored_hash):
    if not stored_hash:
        return False
    try:
        identify_hasher(stored_hash)
        return True
    except ValueError:
        return False


def is_legacy_bcrypt_hash(stored_hash):
    return bool(stored_hash) and stored_hash.startswith('$2')


def user_has_sign_in_password(user):
    """True if the account already has a password (Django hash or legacy bcrypt)."""
    stored = (user.password or '').strip()
    if not stored:
        return False
    if is_django_password_hash(stored) or is_legacy_bcrypt_hash(stored):
        return True
    return len(stored) > 0


def link_bookings_to_user(user):
    """Attach bookings booked with this email to the signed-in account."""
    if not user or not user.email:
        return 0
    return Booking.objects.filter(
        student_email__iexact=user.email.strip(),
    ).exclude(user_id=user.pk).update(user_id=user.pk)


def user_needs_account_setup(user):
    """True when the student should set a password to finish account creation."""
    if not user or not user.is_active:
        return False
    return not user_has_sign_in_password(user)


def resolve_student_user_for_email(email):
    if not email:
        return None
    return User.objects.filter(email__iexact=email.strip()).first()


def complete_student_account(user, password, *, firstname=None, lastname=None):
    """Set password and optional profile fields for a guest student account."""
    if user_has_sign_in_password(user):
        raise ValueError('This account already has a password. Please sign in instead.')

    if firstname:
        user.firstname = firstname
    if lastname:
        user.lastname = lastname
    user.active = 1
    user.set_password(password)
    user.save()
    link_bookings_to_user(user)
    return user


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

    user = primary.user or resolve_student_user_for_email(email)
    if not user or not user_needs_account_setup(user):
        return None

    firstname = primary.student_first_name or user.firstname or ''
    lastname = primary.student_last_name or user.lastname or ''
    if (user.firstname or '').strip().lower() == 'anonymous':
        firstname = primary.student_first_name or firstname
    if (user.lastname or '').strip().lower() == 'user':
        lastname = primary.student_last_name or lastname

    return {
        'email': email,
        'firstname': firstname,
        'lastname': lastname,
        'user': user,
        'booking_reference': primary.booking_reference,
    }


def payment_account_context_from_checkout_data(data, *, is_authenticated=False):
    """Build account CTA from session-stored checkout data when payment lookup fails."""
    if is_authenticated or not data:
        return None

    email = (data.get('email') or '').strip()
    if not email:
        return None

    user = resolve_student_user_for_email(email)
    base = {
        'email': email,
        'firstname': data.get('firstname') or (user.firstname if user else ''),
        'lastname': data.get('lastname') or (user.lastname if user else ''),
        'booking_reference': data.get('booking_reference') or '',
    }

    if user and user_needs_account_setup(user):
        setup = {
            'email': email,
            'firstname': base['firstname'],
            'lastname': base['lastname'],
            'user': user,
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

    user = primary.user or resolve_student_user_for_email(email)
    base = {
        'email': email,
        'firstname': primary.student_first_name or (user.firstname if user else ''),
        'lastname': primary.student_last_name or (user.lastname if user else ''),
        'booking_reference': primary.booking_reference,
    }

    if user and user_needs_account_setup(user):
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


def bookings_for_user(user):
    """Bookings owned by or booked under this student's email."""
    email = (user.email or '').strip()
    qs = Booking.objects.filter(user_id=user.pk)
    if email:
        qs = Booking.objects.filter(
            Q(user_id=user.pk) | Q(student_email__iexact=email),
        )
    return qs.select_related(
        'workshop',
        'workshop__course',
        'workshop__venue',
        'payment',
    ).distinct()
