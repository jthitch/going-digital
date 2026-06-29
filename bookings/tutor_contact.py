"""Mailto links for students to contact their workshop tutor."""
from urllib.parse import quote

from courses.models import Tutor


def _tutor_for_booking(booking):
    workshop = getattr(booking, 'workshop', None)
    if not workshop or not workshop.tutor_id:
        return None
    return Tutor.objects.filter(pk=workshop.tutor_id).first()


def tutor_contact_for_booking(booking):
    """Build mailto URL and metadata for contacting the booking tutor."""
    tutor = _tutor_for_booking(booking)
    tutor_email = (tutor.email or '').strip() if tutor else ''
    tutor_name = str(tutor) if tutor else ''

    empty = {
        'tutor_name': tutor_name,
        'tutor_email': tutor_email,
        'mailto_url': '',
        'has_tutor_contact': False,
    }
    if not tutor_email:
        return empty

    workshop = booking.workshop
    course = workshop.course if workshop else None
    venue = workshop.venue if workshop else None

    course_title = course.title if course else 'Workshop'
    start = workshop.start_date if workshop else None
    date_line = start.strftime('%A %d %B %Y at %I:%M %p').lstrip('0') if start else 'TBC'

    location_parts = []
    if venue:
        if venue.name:
            location_parts.append(venue.name)
        if venue.city:
            location_parts.append(venue.city)
    location_line = ', '.join(location_parts) or 'TBC'

    student_name = f'{booking.student_first_name} {booking.student_last_name}'.strip()

    subject = f'Booking enquiry — {course_title} ({booking.booking_reference})'
    body_lines = [
        'Hello,',
        '',
        'I have a question about my course booking:',
        '',
        f'Booking reference: {booking.booking_reference}',
        f'Course: {course_title}',
        f'Date: {date_line}',
        f'Location: {location_line}',
        f'Student: {student_name}',
        '',
        'My question:',
        '',
    ]
    body = '\r\n'.join(body_lines)

    mailto_url = (
        f'mailto:{tutor_email}'
        f'?subject={quote(subject)}'
        f'&body={quote(body)}'
    )

    return {
        'tutor_name': tutor_name,
        'tutor_email': tutor_email,
        'mailto_url': mailto_url,
        'has_tutor_contact': True,
    }


def attach_tutor_contact_to_booking(booking):
    booking.tutor_contact = tutor_contact_for_booking(booking)
    return booking
