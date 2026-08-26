"""Post-checkout attendee and camera details (before Facebook sharing)."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking


@dataclass
class AttendeePlaceForm:
    """One workshop place on the post-checkout details form."""

    booking: Booking
    place_number: int
    place_total: int
    is_primary: bool
    workshop_title: str
    workshop_date: str

    @property
    def booking_id(self):
        return getattr(self.booking, 'pk', None) or self.booking.id

    @property
    def show_name_fields(self):
        return not self.is_primary and self.place_total >= 2

    @property
    def camera_required(self):
        return not bool(self.booking.loan_camera)


def group_bookings_for_attendee_form(bookings):
    """
    Group confirmed bookings by workshop (creation order preserved).

    Each group is one workshop line from checkout; place 1 is the primary student.
    """
    groups = OrderedDict()
    for booking in sorted(bookings, key=lambda row: row.id):
        if booking.status == 'cancelled':
            continue
        groups.setdefault(booking.workshop_id, []).append(booking)
    return [places for places in groups.values() if places]


def build_attendee_place_forms(bookings):
    """Flatten grouped bookings into form rows for the template."""
    rows = []
    for places in group_bookings_for_attendee_form(bookings):
        workshop = places[0].workshop
        course = getattr(workshop, 'course', None) if workshop else None
        title = getattr(course, 'title', None) or getattr(course, 'course_name', None) or 'Workshop'
        if workshop and getattr(workshop, 'start_date', None):
            date_line = workshop.start_date.strftime('%d %B %Y')
        elif workshop and getattr(workshop, 'date', None):
            date_line = workshop.date.strftime('%d %B %Y')
        else:
            date_line = ''
        total = len(places)
        for index, booking in enumerate(places):
            rows.append(
                AttendeePlaceForm(
                    booking=booking,
                    place_number=index + 1,
                    place_total=total,
                    is_primary=index == 0,
                    workshop_title=title,
                    workshop_date=date_line,
                )
            )
    return rows


def bookings_need_attendee_details(bookings):
    """True when any confirmed booking still needs post-checkout details."""
    confirmed = [b for b in bookings if b.status != 'cancelled']
    if not confirmed:
        return False
    return any(not b.attendee_details_collected_at for b in confirmed)


def post_booking_community_url(*, ref='', email=''):
    from urllib.parse import urlencode

    url = reverse('account:post_booking_community')
    params = {}
    ref = (ref or '').strip()
    email = (email or '').strip()
    if ref:
        params['ref'] = ref
    if email:
        params['email'] = email
    if params:
        return f'{url}?{urlencode(params)}'
    return url


def post_booking_attendee_details_url(*, ref='', email=''):
    from urllib.parse import urlencode

    url = reverse('account:post_booking_attendee_details')
    params = {}
    ref = (ref or '').strip()
    email = (email or '').strip()
    if ref:
        params['ref'] = ref
    if email:
        params['email'] = email
    if params:
        return f'{url}?{urlencode(params)}'
    return url


def next_post_booking_step_url(bookings, *, ref='', email=''):
    """Attendee details first, then the Facebook community wizard."""
    if bookings_need_attendee_details(bookings):
        return post_booking_attendee_details_url(ref=ref, email=email)
    return post_booking_community_url(ref=ref, email=email)


def _field_value(post_data, suffix, booking_id):
    return (post_data.get(f'{suffix}_{booking_id}') or '').strip()


def validate_attendee_details_post(post_data, place_forms):
    """Return field errors keyed by ``field_bookingId``."""
    from bookings.camera_catalog import validate_camera_selection

    errors = {}
    for place in place_forms:
        booking_id = place.booking_id
        if place.show_name_fields:
            if not _field_value(post_data, 'student_first_name', booking_id):
                errors[f'student_first_name_{booking_id}'] = 'First name is required.'
            if not _field_value(post_data, 'student_last_name', booking_id):
                errors[f'student_last_name_{booking_id}'] = 'Last name is required.'
        camera_errors = validate_camera_selection(
            _field_value(post_data, 'camera_make_choice', booking_id),
            _field_value(post_data, 'camera_make_other', booking_id),
            _field_value(post_data, 'camera_model_choice', booking_id),
            _field_value(post_data, 'camera_model_other', booking_id),
            required=place.camera_required,
        )
        for field, message in camera_errors.items():
            errors[f'{field}_{booking_id}'] = message
    return errors


def save_attendee_details_from_post(post_data, place_forms):
    """Persist attendee/camera details and mark bookings complete."""
    from bookings.camera_catalog import resolve_camera_selection

    now = timezone.now()
    to_update = []
    for place in place_forms:
        booking = place.booking
        make_name, model_name, _, _ = resolve_camera_selection(
            _field_value(post_data, 'camera_make_choice', booking.pk),
            _field_value(post_data, 'camera_make_other', booking.pk),
            _field_value(post_data, 'camera_model_choice', booking.pk),
            _field_value(post_data, 'camera_model_other', booking.pk),
        )
        booking.camera_make = make_name
        booking.camera_model = model_name
        if place.show_name_fields:
            booking.student_first_name = _field_value(post_data, 'student_first_name', booking.pk)
            booking.student_last_name = _field_value(post_data, 'student_last_name', booking.pk)
        booking.attendee_details_collected_at = now
        booking.updated_at = now
        to_update.append(booking)

    if to_update:
        Booking.objects.bulk_update(
            to_update,
            [
                'camera_make',
                'camera_model',
                'student_first_name',
                'student_last_name',
                'attendee_details_collected_at',
                'updated_at',
            ],
        )


def posted_attendee_values(post_data, place_forms):
    """Repopulate the form after validation errors."""
    from bookings.camera_catalog import selection_from_stored

    by_booking = {}
    for place in place_forms:
        booking_id = place.booking_id
        stored = selection_from_stored(
            place.booking.camera_make,
            place.booking.camera_model,
        )
        by_booking[booking_id] = {
            'student_first_name': (
                _field_value(post_data, 'student_first_name', booking_id)
                or place.booking.student_first_name
            ),
            'student_last_name': (
                _field_value(post_data, 'student_last_name', booking_id)
                or place.booking.student_last_name
            ),
            'camera_make_choice': (
                _field_value(post_data, 'camera_make_choice', booking_id)
                or stored['make_choice']
            ),
            'camera_make_other': (
                _field_value(post_data, 'camera_make_other', booking_id)
                or stored['make_other']
            ),
            'camera_model_choice': (
                _field_value(post_data, 'camera_model_choice', booking_id)
                or stored['model_choice']
            ),
            'camera_model_other': (
                _field_value(post_data, 'camera_model_other', booking_id)
                or stored['model_other']
            ),
        }
    return by_booking


def field_errors_for_place(raw_errors, booking_id):
    """Map validation errors to template-friendly keys for one place."""
    prefix_map = {
        f'student_first_name_{booking_id}': 'student_first_name',
        f'student_last_name_{booking_id}': 'student_last_name',
        f'camera_make_{booking_id}': 'camera_make',
        f'camera_model_{booking_id}': 'camera_model',
    }
    mapped = {}
    for raw_key, message in raw_errors.items():
        friendly = prefix_map.get(raw_key)
        if friendly:
            mapped[friendly] = message
    return mapped


def initial_attendee_values(place):
    """Default form values for a place on GET."""
    from bookings.camera_catalog import selection_from_stored

    stored = selection_from_stored(place.booking.camera_make, place.booking.camera_model)
    return {
        'student_first_name': place.booking.student_first_name,
        'student_last_name': place.booking.student_last_name,
        'camera_make_choice': stored['make_choice'],
        'camera_make_other': stored['make_other'],
        'camera_model_choice': stored['model_choice'],
        'camera_model_other': stored['model_other'],
    }
