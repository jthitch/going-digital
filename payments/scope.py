"""Payment visibility for region-scoped franchisees."""
from django.db.models import Q

from courses.region_scope import (
    franchisee_owns_workshop,
    get_user_region_ids,
    user_has_full_region_access,
)


def filter_payments_for_user(queryset, user):
    """
    Franchisees see booking payments for workshops in their regions where they
    created the course or created/own the workshop schedule.
    """
    if user_has_full_region_access(user):
        return queryset
    region_ids = get_user_region_ids(user)
    if not region_ids:
        return queryset.none()
    return queryset.filter(
        booking__isnull=False,
        booking__workshop__region_id__in=region_ids,
    ).filter(
        Q(booking__workshop__user_id=user.pk)
        | Q(booking__workshop__createdby_id=user.pk)
    ).distinct()


def user_can_view_payment(user, payment):
    if user_has_full_region_access(user):
        return True
    booking = getattr(payment, 'booking', None)
    if not booking:
        return False
    workshop = booking.workshop
    if not workshop or not workshop.region_id:
        return False
    region_ids = get_user_region_ids(user) or []
    if workshop.region_id not in region_ids:
        return False
    return franchisee_owns_workshop(user, workshop)
