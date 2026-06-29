"""gd_customer lookup and creation for bookings and vouchers."""
from django.utils import timezone

from core.models import Customer


def get_or_create_customer_record(email, firstname, lastname, phone=''):
    """
    Get or create a gd_customer row by email.
    Returns (customer, created).
    """
    firstname = (firstname or 'Customer').strip()
    lastname = (lastname or '').strip()
    if not lastname and firstname:
        parts = firstname.split(maxsplit=1)
        firstname = parts[0]
        lastname = parts[1] if len(parts) > 1 else ''

    email = (email or '').strip()
    if not email:
        raise ValueError('Email is required.')

    customer = Customer.objects.filter(email__iexact=email).first()
    if customer:
        updates = []
        if phone and not (customer.contact_number or '').strip():
            customer.contact_number = phone
            updates.append('contact_number')
        if firstname and not (customer.firstname or '').strip():
            customer.firstname = firstname
            updates.append('firstname')
        if lastname and not (customer.lastname or '').strip():
            customer.lastname = lastname
            updates.append('lastname')
        if updates:
            customer.updated_at = timezone.now()
            updates.append('updated_at')
            customer.save(update_fields=updates)
        return customer, False

    now = timezone.now()
    customer = Customer.objects.create(
        active=1,
        archived=0,
        guest_account=1,
        email=email,
        password='',
        firstname=firstname or 'Customer',
        lastname=lastname or '',
        contact_number=phone or '',
        newsletter=0,
        use_for_primary_booking=1,
        created_at=now,
        updated_at=now,
    )
    return customer, True


def get_or_create_customer(email, firstname, lastname, phone=''):
    """Legacy tuple API: (customer_id, created)."""
    customer, created = get_or_create_customer_record(email, firstname, lastname, phone)
    return customer.pk, created


def subscribe_customer_to_newsletter(email):
    """
    Opt a visitor into the newsletter on gd_customer.
    Creates a guest row (guest_account=1) or sets newsletter=1 on an existing row.
    Returns (customer, created).
    """
    email = (email or '').strip()
    if not email:
        raise ValueError('Email is required.')

    customer = Customer.objects.filter(email__iexact=email).first()
    now = timezone.now()

    if customer:
        update_fields = ['newsletter', 'updated_at']
        customer.newsletter = 1
        customer.updated_at = now
        if customer.archived:
            customer.archived = 0
            update_fields.append('archived')
        if customer.active != 1:
            customer.active = 1
            update_fields.append('active')
        customer.save(update_fields=update_fields)
        return customer, False

    customer = Customer.objects.create(
        active=1,
        archived=0,
        guest_account=1,
        email=email,
        password='',
        firstname='',
        lastname='',
        contact_number='',
        newsletter=1,
        use_for_primary_booking=0,
        created_at=now,
        updated_at=now,
    )
    return customer, True
