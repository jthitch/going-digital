"""Session-based student authentication against gd_customer."""
from functools import wraps

from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect
from django.urls import reverse

from core.models import Customer, User
from core.password_utils import (
    hash_needs_upgrade,
    is_django_password_hash,
    is_legacy_bcrypt_hash,
    verify_password_against_hash,
)

CUSTOMER_SESSION_KEY = 'customer_id'


def customer_has_sign_in_password(customer):
    stored = (customer.password or '').strip()
    if stored and (is_django_password_hash(stored) or is_legacy_bcrypt_hash(stored)):
        return True
    legacy_user = legacy_student_user_for_email(customer.email)
    if not legacy_user:
        return False
    legacy_stored = (legacy_user.password or '').strip()
    return bool(
        legacy_stored
        and (is_django_password_hash(legacy_stored) or is_legacy_bcrypt_hash(legacy_stored))
    )


def legacy_student_user_for_email(email):
    """
    gd_user row for a student (not staff) with the same email.
    Used when passwords were stored on gd_user before gd_customer auth.
    """
    if not email:
        return None
    user = User.objects.filter(email__iexact=email.strip()).first()
    if not user or user.user_type_id in (1, 2, 3):
        return None
    return user


def _upgrade_customer_password(customer, raw_password, stored_hash):
    stored_hash = (stored_hash or '').strip()
    if hash_needs_upgrade(stored_hash):
        customer.set_password(raw_password)
    elif stored_hash and not (customer.password or '').strip():
        customer.password = stored_hash
    customer.guest_account = 0
    from django.utils import timezone
    customer.updated_at = timezone.now()
    customer.save(update_fields=['password', 'guest_account', 'updated_at'])


def authenticate_customer(email, password):
    """Verify student credentials against gd_customer (and legacy gd_user fallback)."""
    if not email or not password:
        return None

    email = email.strip()
    customer = Customer.objects.filter(email__iexact=email).first()

    if customer is not None and not customer.is_active:
        return None

    if customer is not None:
        stored = (customer.password or '').strip()
        if stored and verify_password_against_hash(password, stored):
            if hash_needs_upgrade(stored):
                _upgrade_customer_password(customer, password, stored)
            return customer

    legacy_user = legacy_student_user_for_email(email)
    if legacy_user:
        legacy_stored = (legacy_user.password or '').strip()
        if legacy_stored and verify_password_against_hash(password, legacy_stored):
            if customer is None:
                from core.customer_service import get_or_create_customer_record
                customer, _ = get_or_create_customer_record(
                    email,
                    legacy_user.firstname,
                    legacy_user.lastname,
                )
            _upgrade_customer_password(customer, password, legacy_stored)
            return customer

    make_password(password, hasher='pbkdf2_sha256')
    return None


def get_logged_in_customer(request):
    customer_id = request.session.get(CUSTOMER_SESSION_KEY)
    if not customer_id:
        return None
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return None
    if not customer.is_active:
        return None
    return customer


def is_customer_authenticated(request):
    return get_logged_in_customer(request) is not None


def login_customer(request, customer):
    request.session[CUSTOMER_SESSION_KEY] = customer.pk
    request.session.modified = True
    from django.utils import timezone
    customer.last_login_date = timezone.now().date()
    customer.updated_at = timezone.now()
    customer.save(update_fields=['last_login_date', 'updated_at'])


def logout_customer(request):
    request.session.pop(CUSTOMER_SESSION_KEY, None)
    request.session.modified = True


def customer_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_customer_authenticated(request):
            login_url = reverse('account:login')
            return redirect(f'{login_url}?next={request.path}')
        return view_func(request, *args, **kwargs)
    return wrapper
