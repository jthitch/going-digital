"""Move confirmed students from one workshop to another (admin cancel/transfer)."""
from __future__ import annotations

import logging

from django import forms
from django.db import transaction

from bookings.models import Booking
from courses.models import Workshop
from courses.region_scope import filter_workshops_for_user, user_can_access_workshop
from payments.checkout_completion import _adjust_workshop_places_booked

logger = logging.getLogger(__name__)


class WorkshopStudentMoveError(Exception):
    """Validation or permission failure when moving workshop students."""


def movable_bookings_queryset(workshop):
    """Confirmed bookings on ``workshop`` that can be transferred."""
    return (
        Booking.objects.filter(workshop_id=workshop.pk, status='confirmed')
        .select_related('workshop', 'workshop__course', 'workshop__venue')
        .order_by('student_last_name', 'student_first_name', 'id')
    )


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


def move_workshop_students(
    *,
    source,
    destination,
    booking_ids,
    user=None,
    send_confirmation_email=True,
):
    """
    Reassign confirmed bookings from ``source`` to ``destination``.

    Updates ``places_booked`` on both workshops and optionally sends the standard
    booking confirmation email for each moved student.

    Returns the list of moved Booking instances (refreshed).
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

    ids = []
    for raw in booking_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    # Preserve order while de-duplicating.
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise WorkshopStudentMoveError('Select at least one student to move.')

    moved = []
    with transaction.atomic():
        destination = Workshop.objects.select_for_update().get(pk=destination.pk)
        bookings = list(
            Booking.objects.select_for_update()
            .filter(pk__in=ids)
            .order_by('id')
        )
        if len(bookings) != len(ids):
            raise WorkshopStudentMoveError('One or more selected bookings could not be found.')

        for booking in bookings:
            if booking.workshop_id != source.pk:
                raise WorkshopStudentMoveError(
                    f'Booking {booking.booking_reference} is not on this workshop.'
                )
            if booking.status != 'confirmed':
                raise WorkshopStudentMoveError(
                    f'Booking {booking.booking_reference} is not confirmed and cannot be moved.'
                )

        if not destination_has_capacity(destination, len(bookings)):
            spaces = max(0, int(destination.max_places or 0) - int(destination.places_booked or 0))
            raise WorkshopStudentMoveError(
                f'The destination workshop only has {spaces} place(s) available '
                f'for {len(bookings)} student(s).'
            )

        for booking in bookings:
            booking.workshop = destination
            booking.save(update_fields=['workshop', 'updated_at'])
            moved.append(booking)

        count = len(moved)
        _adjust_workshop_places_booked(source.pk, -count)
        _adjust_workshop_places_booked(destination.pk, count)

    if send_confirmation_email:
        from payments.tasks import send_booking_confirmation_email

        for booking in moved:
            try:
                send_booking_confirmation_email(booking.pk)
            except Exception:
                logger.exception(
                    'Failed to send confirmation email after moving booking %s to workshop %s',
                    booking.pk,
                    destination.pk,
                )

    return moved


class MoveWorkshopStudentsForm(forms.Form):
    destination = forms.ModelChoiceField(
        queryset=Workshop.objects.none(),
        label='Move to workshop',
        help_text='Future workshops only (any course). Students keep their existing payment details.',
    )
    bookings = forms.ModelMultipleChoiceField(
        queryset=Booking.objects.none(),
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
        if source is None:
            self.fields['destination'].queryset = Workshop.objects.none()
            self.fields['bookings'].queryset = Booking.objects.none()
        else:
            self.fields['destination'].queryset = destination_workshops_queryset(source, user)
            self.fields['bookings'].queryset = movable_bookings_queryset(source)
        self.fields['bookings'].label_from_instance = self._booking_label
        self.fields['destination'].label_from_instance = self._workshop_label

    @staticmethod
    def _booking_label(booking):
        name = f'{booking.student_first_name} {booking.student_last_name}'.strip()
        ref = booking.booking_reference or f'#{booking.pk}'
        email = booking.student_email or ''
        if email:
            return f'{name} — {email} ({ref})'
        return f'{name} ({ref})'

    @staticmethod
    def _workshop_label(workshop):
        spaces = workshop.spaces_available
        max_p = workshop.max_places or 0
        if max_p:
            capacity = f'{spaces} of {max_p} places free'
        else:
            capacity = 'no place limit'
        return f'{workshop} — {capacity}'
