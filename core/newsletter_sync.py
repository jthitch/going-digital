"""Sync gd_customer newsletter opt-ins to a Mailgun mailing list with region vars."""
from __future__ import annotations

import logging
from collections import defaultdict

from django.db import connection
from django.utils import timezone

from bookings.models import Booking
from core.mailgun import (
    MailgunError,
    delete_list_member,
    ensure_newsletter_list,
    iter_list_members,
    mailgun_configured,
    upsert_list_member,
    upsert_list_members_bulk,
)
from core.models import Customer
from courses.models import Region

logger = logging.getLogger(__name__)

_BOOKING_STATUSES = ('pending', 'confirmed', 'completed')
_BULK_CHUNK = 100


def newsletter_customers_queryset():
    """Active customers opted into the newsletter."""
    return (
        Customer.objects.filter(newsletter=1, active=1)
        .exclude(archived=1)
        .exclude(email='')
        .exclude(email__isnull=True)
        .order_by('id')
    )


def _region_names_by_id(region_ids):
    if not region_ids:
        return {}
    return {
        int(pk): (name or '').strip()
        for pk, name in Region.objects.filter(pk__in=region_ids).values_list(
            'pk', 'region_name'
        )
    }


def region_ids_for_customers(customer_ids):
    """
    Map customer_id -> sorted unique workshop region ids from new + legacy bookings.
    """
    region_map = defaultdict(set)
    if not customer_ids:
        return region_map

    id_list = [int(pk) for pk in customer_ids]

    for customer_id, region_id in (
        Booking.objects.filter(
            customer_id__in=id_list,
            status__in=_BOOKING_STATUSES,
            workshop__region_id__isnull=False,
        )
        .exclude(workshop__region_id=0)
        .values_list('customer_id', 'workshop__region_id')
        .distinct()
    ):
        if customer_id and region_id:
            region_map[int(customer_id)].add(int(region_id))

    # Legacy gd_booking → workshop region (paid / non-refunded lines).
    placeholders = ','.join(['%s'] * len(id_list))
    legacy_sql = f"""
        SELECT DISTINCT b.customer_id, w.region_id
        FROM gd_booking b
        INNER JOIN gd_bookings_workshops bw ON bw.booking_id = b.id
        INNER JOIN gd_workshop w ON w.id = bw.workshop_id
        WHERE b.customer_id IN ({placeholders})
          AND w.region_id IS NOT NULL
          AND w.region_id <> 0
          AND IFNULL(bw.refund_amount, 0) = 0
          AND (
              bw.payment_complete = 1
              OR b.payment_confirmed = 1
              OR IFNULL(bw.amount_paid, 0) > 0
              OR IFNULL(b.amount_paid, 0) > 0
              OR IFNULL(bw.amount_paid_by_voucher, 0) > 0
              OR IFNULL(b.amount_paid_by_voucher, 0) > 0
          )
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(legacy_sql, id_list)
            for customer_id, region_id in cursor.fetchall():
                if customer_id and region_id:
                    region_map[int(customer_id)].add(int(region_id))
    except Exception:
        logger.exception('Failed loading legacy regions for newsletter sync')

    return region_map


def region_ids_for_customer(customer):
    if not customer or not customer.pk:
        return []
    return sorted(region_ids_for_customers([customer.pk]).get(int(customer.pk), set()))


def member_vars_for_customer(customer, region_ids=None, region_names=None):
    """Mailgun member vars (all string values). Guests may have blank names."""
    if region_ids is None:
        region_ids = region_ids_for_customer(customer)
    region_ids = [int(rid) for rid in region_ids if rid]
    if region_names is None:
        names_by_id = _region_names_by_id(region_ids)
        region_names = [names_by_id[rid] for rid in region_ids if names_by_id.get(rid)]
    else:
        region_names = [name for name in region_names if name]

    return {
        'customer_id': str(customer.pk or ''),
        'first_name': (customer.firstname or '').strip(),
        'last_name': (customer.lastname or '').strip(),
        'region_ids': ','.join(str(rid) for rid in region_ids),
        'regions': ','.join(region_names),
    }


def member_display_name(customer):
    return f'{(customer.firstname or "").strip()} {(customer.lastname or "").strip()}'.strip()


def member_payload_for_customer(customer, *, region_ids=None, region_names_by_id=None):
    email = (customer.email or '').strip()
    if not email:
        return None
    if region_ids is None:
        region_ids = region_ids_for_customer(customer)
    region_ids = sorted({int(rid) for rid in region_ids if rid})
    if region_names_by_id is None:
        region_names_by_id = _region_names_by_id(region_ids)
    names = [region_names_by_id[rid] for rid in region_ids if region_names_by_id.get(rid)]
    return {
        'address': email,
        'name': member_display_name(customer),
        'vars': member_vars_for_customer(
            customer,
            region_ids=region_ids,
            region_names=names,
        ),
        'subscribed': True,
    }


def upsert_customer_to_mailgun(customer):
    """
    Best-effort upsert of one opted-in customer.

    Returns True on success, False when Mailgun is not configured.
    Raises MailgunError on API failure.
    """
    if not mailgun_configured():
        return False
    if not customer or int(getattr(customer, 'newsletter', 0) or 0) != 1:
        return False
    if int(getattr(customer, 'active', 0) or 0) != 1:
        return False
    if int(getattr(customer, 'archived', 0) or 0) == 1:
        return False

    payload = member_payload_for_customer(customer)
    if not payload:
        return False
    ensure_newsletter_list()
    upsert_list_member(
        email=payload['address'],
        name=payload['name'],
        vars_dict=payload['vars'],
        subscribed=True,
    )
    return True


def remove_customer_from_mailgun(email):
    """Best-effort delete of a list member. Missing members are ignored."""
    if not mailgun_configured():
        return False
    email = (email or '').strip()
    if not email:
        return False
    try:
        delete_list_member(email)
        return True
    except MailgunError as exc:
        if exc.status_code == 404:
            return False
        raise


def mark_customer_unsubscribed(email):
    """
    Honour a Mailgun unsubscribe: set gd_customer.newsletter=0 when a row exists.

    Returns the updated Customer, or None if no matching row.
    """
    email = (email or '').strip()
    if not email:
        return None
    customer = Customer.objects.filter(email__iexact=email).first()
    if not customer:
        logger.info('Mailgun unsubscribe for unknown email %s', email)
        return None
    if int(customer.newsletter or 0) == 0:
        return customer
    customer.newsletter = 0
    customer.updated_at = timezone.now()
    customer.save(update_fields=['newsletter', 'updated_at'])
    logger.info('Set newsletter=0 for customer %s after Mailgun unsubscribe', customer.pk)
    return customer


def sync_newsletter_list(*, dry_run=False, remove_extras=True, ensure_list=True):
    """
    Full sync of opted-in customers to the Mailgun newsletter list.

    Returns a stats dict: upserted, removed, skipped, errors, dry_run.
    """
    stats = {
        'upserted': 0,
        'removed': 0,
        'skipped': 0,
        'errors': 0,
        'dry_run': bool(dry_run),
        'configured': mailgun_configured(),
    }
    if not mailgun_configured():
        return stats

    customers = list(newsletter_customers_queryset())
    customer_ids = [c.pk for c in customers]
    regions_by_customer = region_ids_for_customers(customer_ids)
    all_region_ids = {
        rid for region_ids in regions_by_customer.values() for rid in region_ids
    }
    region_names_by_id = _region_names_by_id(all_region_ids)

    payloads = []
    subscribed_emails = set()
    for customer in customers:
        email = (customer.email or '').strip().lower()
        if not email:
            stats['skipped'] += 1
            continue
        subscribed_emails.add(email)
        payload = member_payload_for_customer(
            customer,
            region_ids=regions_by_customer.get(int(customer.pk), set()),
            region_names_by_id=region_names_by_id,
        )
        if payload:
            payloads.append(payload)

    if dry_run:
        stats['upserted'] = len(payloads)
        if remove_extras:
            # Count extras without calling delete.
            try:
                if ensure_list:
                    ensure_newsletter_list()
                extras = 0
                for member in iter_list_members():
                    addr = (member.get('address') or '').strip().lower()
                    if addr and addr not in subscribed_emails:
                        extras += 1
                stats['removed'] = extras
            except MailgunError:
                logger.exception('Dry-run could not list Mailgun members')
                stats['errors'] += 1
        return stats

    try:
        if ensure_list:
            ensure_newsletter_list()
    except MailgunError:
        logger.exception('Failed ensuring Mailgun newsletter list')
        stats['errors'] += 1
        return stats

    for start in range(0, len(payloads), _BULK_CHUNK):
        chunk = payloads[start:start + _BULK_CHUNK]
        try:
            upsert_list_members_bulk(chunk)
            stats['upserted'] += len(chunk)
        except MailgunError:
            logger.exception('Bulk Mailgun upsert failed; falling back to single members')
            for member in chunk:
                try:
                    upsert_list_member(
                        email=member['address'],
                        name=member.get('name') or '',
                        vars_dict=member.get('vars'),
                        subscribed=True,
                    )
                    stats['upserted'] += 1
                except MailgunError:
                    stats['errors'] += 1
                    logger.exception(
                        'Failed upserting Mailgun member %s',
                        member.get('address'),
                    )

    if remove_extras:
        try:
            for member in iter_list_members():
                addr = (member.get('address') or '').strip()
                if not addr:
                    continue
                if addr.lower() in subscribed_emails:
                    continue
                try:
                    delete_list_member(addr)
                    stats['removed'] += 1
                except MailgunError as exc:
                    if exc.status_code == 404:
                        continue
                    stats['errors'] += 1
                    logger.exception('Failed removing Mailgun member %s', addr)
        except MailgunError:
            stats['errors'] += 1
            logger.exception('Failed listing Mailgun members for cleanup')

    return stats
