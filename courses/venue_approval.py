"""Venue approval helpers for admin UI."""
from django.urls import reverse

from courses.region_scope import user_has_full_region_access

VENUE_APPROVAL_PENDING = 'pending'
VENUE_APPROVAL_APPROVED = 'approved'
VENUE_APPROVAL_REJECTED = 'rejected'
VENUE_APPROVAL_NOT_SUBMITTED = 'not_submitted'

VENUE_APPROVAL_DECISION_CHOICES = (
    (VENUE_APPROVAL_PENDING, 'Pending approval'),
    (VENUE_APPROVAL_APPROVED, 'Approved'),
    (VENUE_APPROVAL_REJECTED, 'Rejected'),
    (VENUE_APPROVAL_NOT_SUBMITTED, 'Not submitted'),
)


def venue_approval_state(venue):
    """Return the single approval decision key for a venue (or defaults)."""
    if venue is None or not getattr(venue, 'pk', None):
        return VENUE_APPROVAL_NOT_SUBMITTED
    if venue.approved == 1:
        return VENUE_APPROVAL_APPROVED
    if venue.rejected == 1:
        return VENUE_APPROVAL_REJECTED
    if venue.approval_requested == 1:
        return VENUE_APPROVAL_PENDING
    return VENUE_APPROVAL_NOT_SUBMITTED


def apply_venue_approval_decision(venue, decision, *, editor_user_id=None, reject_reason=None, now=None):
    """
    Map a single approval decision onto the legacy 0/1 venue flags.

    Leaves DB columns in place; admins no longer edit the flags independently.
    """
    from django.utils import timezone

    if now is None:
        now = timezone.now()

    was_approved = venue.pk and venue.approved == 1

    if decision == VENUE_APPROVAL_APPROVED:
        venue.approved = 1
        venue.rejected = 0
        venue.reject_reason = None
        venue.approval_requested = 0
        if not was_approved:
            venue.approvedby_id = editor_user_id
            venue.approved_at = now
        return

    if decision == VENUE_APPROVAL_REJECTED:
        venue.approved = 0
        venue.rejected = 1
        venue.approval_requested = 0
        venue.reject_reason = (reject_reason or '').strip() or None
        return

    if decision == VENUE_APPROVAL_PENDING:
        venue.approved = 0
        venue.rejected = 0
        venue.reject_reason = None
        venue.approval_requested = 1
        if not venue.approval_requested_at:
            venue.approval_requested_at = now
            venue.approval_requested_by_id = editor_user_id
        return

    # not_submitted
    venue.approved = 0
    venue.rejected = 0
    venue.reject_reason = None
    venue.approval_requested = 0


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


CONTENT_CHANGE_APPLY = 'apply'
CONTENT_CHANGE_REJECT = 'reject'
CONTENT_CHANGE_LEAVE = ''

CONTENT_CHANGE_DECISION_CHOICES = (
    (CONTENT_CHANGE_LEAVE, 'Leave pending'),
    (CONTENT_CHANGE_APPLY, 'Approve & publish content'),
    (CONTENT_CHANGE_REJECT, 'Reject content changes'),
)

VENUE_CONTENT_FIELD_NAMES = (
    'content_title',
    'strapline',
    'main_content',
    'sub_content',
    'meta_title',
    'meta_description',
    'meta_keywords',
)


def live_venue_content_values(venue):
    content = venue.get_content() if venue else None
    if not content:
        return {name: '' for name in VENUE_CONTENT_FIELD_NAMES}
    return {name: getattr(content, name, None) or '' for name in VENUE_CONTENT_FIELD_NAMES}


def content_values_from_mapping(data):
    return {name: (data.get(name) or '') for name in VENUE_CONTENT_FIELD_NAMES}


def get_venue_content_change_request(venue):
    if not venue or not getattr(venue, 'pk', None):
        return None
    from courses.models import VenueContentChangeRequest

    try:
        return venue.content_change_request
    except VenueContentChangeRequest.DoesNotExist:
        return None


def pending_content_change_venues_queryset():
    from courses.models import Venue, VenueContentChangeRequest

    return Venue.objects.filter(
        content_change_request__status=VenueContentChangeRequest.STATUS_PENDING,
    ).order_by('-content_change_request__requested_at', '-id')


def pending_content_change_count():
    return pending_content_change_venues_queryset().count()


def pending_content_changes_changelist_url():
    return reverse('admin:courses_venue_changelist') + '?content_change=pending'


def content_change_status_label(venue):
    request = get_venue_content_change_request(venue)
    if not request:
        return 'No pending content changes'
    if request.status == request.STATUS_PENDING:
        return 'Content changes awaiting approval'
    if request.status == request.STATUS_REJECTED:
        reason = (request.reject_reason or '').strip()
        if reason:
            return f'Content changes rejected: {reason}'
        return 'Content changes rejected'
    return request.get_status_display()


def upsert_venue_content_change_request(venue, values, *, user_id=None):
    """Create/update a pending content change when values differ from live content."""
    from django.utils import timezone
    from courses.models import VenueContentChangeRequest

    values = content_values_from_mapping(values)
    live = live_venue_content_values(venue)
    existing = get_venue_content_change_request(venue)

    if values == live:
        if existing:
            existing.delete()
        return None

    defaults = {
        **values,
        'status': VenueContentChangeRequest.STATUS_PENDING,
        'reject_reason': '',
        'requested_by_id': user_id,
        'reviewed_by': None,
        'reviewed_at': None,
    }
    if existing:
        for key, value in defaults.items():
            setattr(existing, key, value)
        existing.requested_at = timezone.now()
        existing.save()
        return existing

    return VenueContentChangeRequest.objects.create(venue=venue, **defaults)


def apply_venue_content_change_request(venue, *, editor_user=None, now=None):
    """Publish pending content onto gd_content and clear the change request."""
    from django.utils import timezone
    from courses.models import Content

    if now is None:
        now = timezone.now()

    change = get_venue_content_change_request(venue)
    if not change:
        return False

    values = change.as_content_dict()
    user_id = getattr(editor_user, 'pk', None) or change.requested_by_id
    content = venue.get_content()
    if content:
        for name, value in values.items():
            setattr(content, name, value)
        content.updatedby_id = user_id
        content.updated_at = now
        content.save()
    else:
        content = Content.objects.create(
            content_title=values['content_title'] or venue.venue_name or '',
            header_content='',
            strapline=values['strapline'],
            main_content=values['main_content'],
            sub_content=values['sub_content'],
            footer_content='',
            meta_title=values['meta_title'],
            meta_description=values['meta_description'],
            meta_keywords=values['meta_keywords'],
            createdby_id=user_id,
            updatedby_id=user_id,
            created_at=now,
            updated_at=now,
        )
        venue.content_id = content.pk
        venue.save(update_fields=['content_id'])

    change.delete()
    return True


def reject_venue_content_change_request(venue, *, reject_reason='', editor_user=None, now=None):
    from django.utils import timezone
    from courses.models import VenueContentChangeRequest

    if now is None:
        now = timezone.now()

    change = get_venue_content_change_request(venue)
    if not change:
        return False

    change.status = VenueContentChangeRequest.STATUS_REJECTED
    change.reject_reason = (reject_reason or '').strip()
    change.reviewed_by = editor_user
    change.reviewed_at = now
    change.save(
        update_fields=['status', 'reject_reason', 'reviewed_by', 'reviewed_at'],
    )
    return True
