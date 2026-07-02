"""Copy workshop settings for franchisees scheduling a repeat date."""

from courses.display_images import workshop_gallery_image_ids
from courses.models import Workshop
from courses.region_scope import user_can_access_workshop

DUPLICATE_FROM_PARAM = 'duplicate_from'
CLONED_FROM_WORKSHOP_INITIAL_KEY = 'cloned_from_workshop_id'

# Form initial keys that should be kept even when empty (e.g. cleared date on duplicate).
_DUPLICATE_EMPTY_ALLOWED_KEYS = frozenset({
    'date',
    'places_booked',
    'active',
    'open_dated',
    'cameras_available',
    'strapline',
    'byline',
    'comments',
    'reminder_message',
    'blurb',
    'cost',
    'deposit_required',
    'number_of_loan_cameras_available',
})


def parse_duplicate_from_pk(value):
    """Return a positive workshop pk from ?duplicate_from= or None."""
    try:
        pk = int(value)
    except (TypeError, ValueError):
        return None
    return pk if pk > 0 else None


def get_duplicate_source_workshop(request, *, prefetch_gallery=False):
    """
    Load the workshop referenced by ?duplicate_from= when the user may access it.
    Used by add-view messaging and change-form initial data.
    """
    from_pk = parse_duplicate_from_pk(request.GET.get(DUPLICATE_FROM_PARAM))
    if not from_pk:
        return None

    qs = Workshop.objects.filter(pk=from_pk)
    if prefetch_gallery:
        qs = qs.prefetch_related('gallery_images')
    qs = qs.select_related('course', 'venue')
    source = qs.first()
    if not source or not user_can_access_workshop(request.user, source):
        return None
    return source


def workshop_duplicate_initial(source: Workshop) -> dict:
    """
    Form initial data when duplicating a workshop.
    Copies content and logistics; clears date and bookings.
    """
    initial = {
        'course': source.course_id,
        'venue': source.venue_id,
        'region': source.region_id,
        'tutor': source.tutor_id,
        'assistant': source.assistant_id,
        'alt_course': source.alt_course_id if source.alt_course_id else None,
        'workshop_type': source.workshop_type_id,
        CLONED_FROM_WORKSHOP_INITIAL_KEY: source.pk,
        'cameras_available': bool(source.cameras_available),
        'number_of_loan_cameras_available': source.number_of_loan_cameras_available or 0,
        'cost': source.cost or 0,
        'deposit_required': source.deposit_required or 0,
        'max_places': source.max_places,
        'places_booked': 0,
        'strapline': source.strapline or '',
        'byline': source.byline or '',
        'comments': source.comments or '',
        'reminder_message': source.reminder_message or '',
        'blurb': source.blurb or '',
        'approve': source.approve,
        'active': bool(source.active),
        'open_dated': bool(source.open_dated),
        'date': None,
        'images': workshop_gallery_image_ids(source),
    }
    return {
        key: value
        for key, value in initial.items()
        if value is not None or key in _DUPLICATE_EMPTY_ALLOWED_KEYS
    }


def duplicate_workshop_querystring(source: Workshop) -> str:
    return f'{DUPLICATE_FROM_PARAM}={source.pk}'
