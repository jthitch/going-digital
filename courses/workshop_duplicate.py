"""Copy workshop settings for franchisees scheduling a repeat date."""

from courses.models import Workshop


def workshop_duplicate_initial(source: Workshop) -> dict:
    """
    Form initial data when duplicating a workshop.
    Copies content and logistics; clears date and bookings.
    """
    gallery_ids = list(
        source.gallery_images.order_by('display_order', 'id').values_list('image_id', flat=True)
    )
    if not gallery_ids and source.image_id:
        gallery_ids = [source.image_id]

    initial = {
        'course': source.course_id,
        'venue': source.venue_id,
        'region': source.region_id,
        'tutor': source.tutor_id,
        'assistant': source.assistant_id,
        'alt_course': source.alt_course_id if source.alt_course_id else None,
        'workshop_type': source.workshop_type_id,
        'cloned_from_workshop': source.pk,
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
        'date': None,
        'images': gallery_ids,
    }
    return {key: value for key, value in initial.items() if value is not None or key in {
        'date', 'places_booked', 'active', 'cameras_available', 'strapline', 'byline',
        'comments', 'reminder_message', 'blurb', 'cost', 'deposit_required',
        'number_of_loan_cameras_available',
    }}


def duplicate_workshop_querystring(source: Workshop) -> str:
    return f'duplicate_from={source.pk}'
