"""Move confirmed students from one workshop to another (admin cancel/transfer)."""
from __future__ import annotations

import logging
import re

from django import forms
from django.db import connection, transaction

from bookings.models import Booking
from courses.models import Workshop
from courses.region_scope import filter_workshops_for_user, user_can_access_workshop
from courses.workshop_student_report import load_legacy_workshop_student_rows
from payments.checkout_completion import _adjust_workshop_places_booked

logger = logging.getLogger(__name__)

_BOOKING_KEY = re.compile(r'^b:(\d+)$')
_LEGACY_ATTENDEE_KEY = re.compile(r'^la:(\d+)$')
_LEGACY_BOOKING_KEY = re.compile(r'^lb:(\d+)$')


class WorkshopStudentMoveError(Exception):
    """Validation or permission failure when moving workshop students."""


def movable_bookings_queryset(workshop):
    """
    Confirmed new-site bookings on ``workshop`` that can be transferred.

    Excludes legacy bridge rows — those are moved via the legacy student list.
    """
    return (
        Booking.objects.filter(workshop_id=workshop.pk, status='confirmed')
        .filter(legacy_gd_booking_id__isnull=True, legacy_attendee_id__isnull=True)
        .select_related('workshop', 'workshop__course', 'workshop__venue')
        .order_by('student_last_name', 'student_first_name', 'id')
    )


def movable_legacy_student_rows(workshop):
    """Paid legacy students on ``workshop`` (attendee or booking-workshop lines)."""
    if not workshop or not workshop.pk:
        return []
    try:
        return load_legacy_workshop_student_rows(workshop.pk)
    except Exception:
        logger.exception('Failed loading legacy students for workshop %s', workshop.pk)
        return []


def legacy_student_selection_key(row):
    if row.legacy_attendee_id:
        return f'la:{int(row.legacy_attendee_id)}'
    if row.legacy_booking_id:
        return f'lb:{int(row.legacy_booking_id)}'
    return None


def booking_selection_key(booking):
    return f'b:{int(booking.pk)}'


def build_movable_student_choices(workshop):
    """(value, label) pairs for the move-students form."""
    choices = []
    for booking in movable_bookings_queryset(workshop):
        name = f'{booking.student_first_name} {booking.student_last_name}'.strip()
        ref = booking.booking_reference or f'#{booking.pk}'
        email = booking.student_email or ''
        label = f'{name} — {email} ({ref})' if email else f'{name} ({ref})'
        choices.append((booking_selection_key(booking), label))

    for row in movable_legacy_student_rows(workshop):
        key = legacy_student_selection_key(row)
        if not key:
            continue
        name = f'{row.first_name} {row.last_name}'.strip() or 'Legacy student'
        ref = row.booking_reference or key
        email = row.email or ''
        if email:
            label = f'{name} — {email} ({ref}) [legacy]'
        else:
            label = f'{name} ({ref}) [legacy]'
        choices.append((key, label))
    return choices


def has_movable_students(workshop):
    if movable_bookings_queryset(workshop).exists():
        return True
    return any(legacy_student_selection_key(row) for row in movable_legacy_student_rows(workshop))


def destination_workshops_queryset(source, user):
    """
    Active future workshops suitable as a transfer destination.

    Any course, excluding the source, scoped to the user. Open-dated workshops
    are included; dated workshops must start now or later.
    """
    from django.utils import timezone

    from courses.workshop_querysets import bookable_workshop_visibility_q

    now = timezone.now()
    qs = (
        Workshop.objects.filter(bookable_workshop_visibility_q(now=now))
        .exclude(pk=source.pk)
        .select_related('course', 'venue')
    )
    qs = filter_workshops_for_user(qs, user)
    return qs.order_by('date', 'id')


def destination_has_capacity(destination, places):
    """True when ``destination`` can accept ``places`` more confirmed students."""
    places = int(places or 0)
    if places < 1:
        return True
    max_p = int(destination.max_places or 0)
    if max_p <= 0:
        # No capacity limit configured.
        return True
    booked = int(destination.places_booked or 0)
    return (max_p - booked) >= places


def _destination_is_future(destination, *, now=None):
    """Open-dated or scheduled at/after ``now``."""
    from django.utils import timezone

    from courses.workshop_querysets import workshop_is_open_dated

    if workshop_is_open_dated(destination):
        return True
    start = getattr(destination, 'start_date', None) or getattr(destination, 'date', None)
    if not start:
        return False
    now = now or timezone.now()
    return start >= now


def _parse_student_keys(student_keys):
    booking_ids = []
    legacy_attendee_ids = []
    legacy_booking_ids = []
    for raw in student_keys or []:
        value = str(raw).strip()
        match = _BOOKING_KEY.match(value)
        if match:
            booking_ids.append(int(match.group(1)))
            continue
        match = _LEGACY_ATTENDEE_KEY.match(value)
        if match:
            legacy_attendee_ids.append(int(match.group(1)))
            continue
        match = _LEGACY_BOOKING_KEY.match(value)
        if match:
            legacy_booking_ids.append(int(match.group(1)))
            continue
        # Back-compat: plain booking primary keys from older forms.
        try:
            booking_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return (
        list(dict.fromkeys(booking_ids)),
        list(dict.fromkeys(legacy_attendee_ids)),
        list(dict.fromkeys(legacy_booking_ids)),
    )


def _legacy_rows_by_selection(workshop):
    by_attendee = {}
    by_booking = {}
    for row in movable_legacy_student_rows(workshop):
        if row.legacy_attendee_id:
            by_attendee[int(row.legacy_attendee_id)] = row
        elif row.legacy_booking_id:
            by_booking[int(row.legacy_booking_id)] = row
    return by_attendee, by_booking


def _move_legacy_attendee(attendee_id, source_id, destination_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE gd_bookings_workshops_attendees
            SET workshop_id = %s
            WHERE id = %s
              AND workshop_id = %s
              AND IFNULL(active, 1) = 1
            """,
            [destination_id, attendee_id, source_id],
        )
        if cursor.rowcount != 1:
            raise WorkshopStudentMoveError(
                f'Legacy attendee #{attendee_id} is not on this workshop or could not be moved.'
            )
        # Repoint the parent bookings_workshops line when no sibling attendees
        # remain on the source workshop for that line.
        cursor.execute(
            """
            UPDATE gd_bookings_workshops bw
            INNER JOIN gd_bookings_workshops_attendees a
                ON a.bookings_workshops_id = bw.id
            SET bw.workshop_id = %s
            WHERE a.id = %s
              AND bw.workshop_id = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM gd_bookings_workshops_attendees a2
                  WHERE a2.bookings_workshops_id = bw.id
                    AND a2.id <> %s
                    AND a2.workshop_id = %s
                    AND IFNULL(a2.active, 1) = 1
              )
            """,
            [destination_id, attendee_id, source_id, attendee_id, source_id],
        )


def _move_legacy_booking_workshop(legacy_booking_id, source_id, destination_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE gd_bookings_workshops
            SET workshop_id = %s
            WHERE booking_id = %s
              AND workshop_id = %s
              AND IFNULL(refund_amount, 0) = 0
            """,
            [destination_id, legacy_booking_id, source_id],
        )
        if cursor.rowcount < 1:
            raise WorkshopStudentMoveError(
                f'Legacy booking #{legacy_booking_id} is not on this workshop or could not be moved.'
            )


def move_workshop_students(
    *,
    source,
    destination,
    student_keys=None,
    booking_ids=None,
    user=None,
    send_confirmation_email=True,
):
    """
    Reassign confirmed new-site and legacy students from ``source`` to ``destination``.

    ``student_keys`` uses ``b:<id>``, ``la:<attendee_id>``, and ``lb:<gd_booking_id>``.
    ``booking_ids`` remains supported for new-site bookings only.

    Updates ``places_booked`` on both workshops and optionally sends the standard
    booking confirmation email for each moved student.

    Returns the list of Booking instances used for confirmation (new-site and/or
    legacy bridges).
    """
    if source is None or destination is None:
        raise WorkshopStudentMoveError('Source and destination workshops are required.')
    if source.pk == destination.pk:
        raise WorkshopStudentMoveError('Choose a different destination workshop.')
    if not destination.active:
        raise WorkshopStudentMoveError('The destination workshop is not active.')
    if not _destination_is_future(destination):
        raise WorkshopStudentMoveError('Students can only be moved to a future workshop.')
    if user is not None:
        if not user_can_access_workshop(user, source):
            raise WorkshopStudentMoveError('You cannot move students from this workshop.')
        if not user_can_access_workshop(user, destination):
            raise WorkshopStudentMoveError('You cannot move students to that workshop.')

    keys = list(student_keys or [])
    if booking_ids and not keys:
        keys = [f'b:{int(pk)}' for pk in booking_ids]

    new_ids, legacy_attendee_ids, legacy_booking_ids = _parse_student_keys(keys)
    if not new_ids and not legacy_attendee_ids and not legacy_booking_ids:
        raise WorkshopStudentMoveError('Select at least one student to move.')

    by_attendee, by_booking = _legacy_rows_by_selection(source)
    legacy_rows_to_move = []
    for attendee_id in legacy_attendee_ids:
        row = by_attendee.get(attendee_id)
        if row is None:
            raise WorkshopStudentMoveError(
                f'Legacy attendee #{attendee_id} is not on this workshop.'
            )
        legacy_rows_to_move.append(row)
    for legacy_booking_id in legacy_booking_ids:
        row = by_booking.get(legacy_booking_id)
        if row is None:
            raise WorkshopStudentMoveError(
                f'Legacy booking #{legacy_booking_id} is not on this workshop.'
            )
        legacy_rows_to_move.append(row)

    place_count = len(new_ids) + len(legacy_rows_to_move)
    confirmation_bookings = []

    with transaction.atomic():
        destination = Workshop.objects.select_for_update().get(pk=destination.pk)

        bookings = []
        if new_ids:
            bookings = list(
                Booking.objects.select_for_update()
                .filter(pk__in=new_ids)
                .filter(legacy_gd_booking_id__isnull=True, legacy_attendee_id__isnull=True)
                .order_by('id')
            )
            if len(bookings) != len(new_ids):
                raise WorkshopStudentMoveError(
                    'One or more selected bookings could not be found.'
                )
            for booking in bookings:
                if booking.workshop_id != source.pk:
                    raise WorkshopStudentMoveError(
                        f'Booking {booking.booking_reference} is not on this workshop.'
                    )
                if booking.status != 'confirmed':
                    raise WorkshopStudentMoveError(
                        f'Booking {booking.booking_reference} is not confirmed and cannot be moved.'
                    )

        if not destination_has_capacity(destination, place_count):
            spaces = max(0, int(destination.max_places or 0) - int(destination.places_booked or 0))
            raise WorkshopStudentMoveError(
                f'The destination workshop only has {spaces} place(s) available '
                f'for {place_count} student(s).'
            )

        for booking in bookings:
            booking.workshop = destination
            booking.save(update_fields=['workshop', 'updated_at'])
            confirmation_bookings.append(booking)

        for row in legacy_rows_to_move:
            if row.legacy_attendee_id:
                _move_legacy_attendee(row.legacy_attendee_id, source.pk, destination.pk)
            elif row.legacy_booking_id:
                _move_legacy_booking_workshop(row.legacy_booking_id, source.pk, destination.pk)

        if place_count:
            _adjust_workshop_places_booked(source.pk, -place_count)
            _adjust_workshop_places_booked(destination.pk, place_count)

        if legacy_rows_to_move:
            from bookings.legacy_workshop_emails import get_or_create_legacy_bridge

            for row in legacy_rows_to_move:
                bridge = get_or_create_legacy_bridge(destination, row)
                if bridge:
                    confirmation_bookings.append(bridge)

    if send_confirmation_email:
        from payments.tasks import send_booking_confirmation_email

        seen = set()
        for booking in confirmation_bookings:
            if booking.pk in seen:
                continue
            seen.add(booking.pk)
            try:
                send_booking_confirmation_email(booking.pk)
            except Exception:
                logger.exception(
                    'Failed to send confirmation email after moving booking %s to workshop %s',
                    booking.pk,
                    destination.pk,
                )

    return confirmation_bookings


class MoveWorkshopStudentsForm(forms.Form):
    destination = forms.ModelChoiceField(
        queryset=Workshop.objects.none(),
        label='Move to workshop',
        help_text='Future workshops only (any course). Students keep their existing payment details.',
    )
    students = forms.MultipleChoiceField(
        choices=(),
        widget=forms.CheckboxSelectMultiple,
        label='Students to move',
    )
    send_confirmation_email = forms.BooleanField(
        required=False,
        initial=True,
        label='Email each student a booking confirmation for the new workshop',
    )

    def __init__(self, *args, source=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source
        choices = build_movable_student_choices(source) if source else []
        self.fields['students'].choices = choices
        if source is None:
            self.fields['destination'].queryset = Workshop.objects.none()
        else:
            self.fields['destination'].queryset = destination_workshops_queryset(source, user)
        self.fields['destination'].label_from_instance = self._workshop_label

    @staticmethod
    def _workshop_label(workshop):
        spaces = workshop.spaces_available
        max_p = workshop.max_places or 0
        if max_p:
            capacity = f'{spaces} of {max_p} places free'
        else:
            capacity = 'no place limit'
        return f'{workshop} — {capacity}'
