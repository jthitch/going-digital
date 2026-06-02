"""Venue approval helpers for admin UI."""
from django.urls import reverse

from courses.region_scope import user_has_full_region_access


def pending_venues_queryset():
    from courses.models import Venue

    return Venue.objects.filter(
        approval_requested=1,
        approved=0,
        rejected=0,
    ).order_by('-approval_requested_at', '-id')


def pending_venue_count():
    return pending_venues_queryset().count()


def pending_venues_changelist_url():
    return reverse('admin:courses_venue_changelist') + '?approval_state=pending'


def user_sees_pending_venue_alerts(user):
    return user_has_full_region_access(user)
