"""Calendar links and .ics content for workshop booking emails."""
from urllib.parse import quote

from django.urls import reverse
from django.utils import timezone

from courses.models import Tutor
from website.seo import absolute_url_from_base, site_base_url


def _ics_datetime(dt):
    if dt is None:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _escape_ics(text):
    return (text or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def build_workshop_calendar(*, start, end, title, description, location, uid):
    """
    Return Google/Outlook deeplink URLs and .ics file body for a workshop event.
    """
    if not start or not end:
        return {
            'google_calendar_url': '',
            'outlook_calendar_url': '',
            'calendar_ics': '',
        }

    start_utc = start
    end_utc = end
    if timezone.is_naive(start_utc):
        start_utc = timezone.make_aware(start_utc, timezone.get_current_timezone())
    if timezone.is_naive(end_utc):
        end_utc = timezone.make_aware(end_utc, timezone.get_current_timezone())
    start_utc = start_utc.astimezone(timezone.utc)
    end_utc = end_utc.astimezone(timezone.utc)

    start_ics = _ics_datetime(start_utc)
    end_ics = _ics_datetime(end_utc)
    dates_param = f'{start_ics}/{end_ics}'

    google_calendar_url = (
        'https://calendar.google.com/calendar/render?action=TEMPLATE'
        f'&text={quote(title)}'
        f'&dates={dates_param}'
        f'&details={quote(description)}'
        f'&location={quote(location)}'
    )

    outlook_calendar_url = (
        'https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent'
        f'&subject={quote(title)}'
        f'&body={quote(description)}'
        f'&location={quote(location)}'
        f'&startdt={quote(start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))}'
        f'&enddt={quote(end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))}'
    )

    calendar_ics = '\r\n'.join([
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Going Digital//Workshop Booking//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{_escape_ics(uid)}',
        f'DTSTAMP:{_ics_datetime(timezone.now())}',
        f'DTSTART:{start_ics}',
        f'DTEND:{end_ics}',
        f'SUMMARY:{_escape_ics(title)}',
        f'DESCRIPTION:{_escape_ics(description)}',
        f'LOCATION:{_escape_ics(location)}',
        'END:VEVENT',
        'END:VCALENDAR',
        '',
    ])

    return {
        'google_calendar_url': google_calendar_url,
        'outlook_calendar_url': outlook_calendar_url,
        'calendar_ics': calendar_ics,
    }


def _absolute_url(path, site_base=None):
    if site_base:
        return absolute_url_from_base(site_base, path)
    return absolute_url_from_base(site_base_url(), path)


def calendar_data_for_booking(booking, *, site_base=None):
    """Google/Outlook links and .ics body for a booking (my bookings, emails)."""
    workshop = getattr(booking, 'workshop', None)
    if not workshop or not workshop.start_date:
        return {
            'google_calendar_url': '',
            'outlook_calendar_url': '',
            'calendar_ics': '',
            'calendar_ics_filename': '',
            'has_calendar': False,
        }

    course = workshop.course if workshop else None
    venue = workshop.venue if workshop else None

    tutor_name = ''
    tutor_email = ''
    if workshop.tutor_id:
        tutor = Tutor.objects.filter(pk=workshop.tutor_id).first()
        if tutor:
            tutor_name = str(tutor)
            tutor_email = (tutor.email or '').strip()

    course_title = course.title if course else 'Workshop'
    location_name = venue.name if venue else 'TBC'
    location_city = venue.city if venue else ''
    location_address = ''
    if venue:
        location_address = (venue.venue_address or venue.location or '').strip()

    workshop_url = _absolute_url(workshop.get_absolute_url(), site_base) if workshop else ''

    calendar_location = ', '.join(
        part for part in [location_name, location_city, location_address] if part
    )
    calendar_description = (
        f'Booking reference: {booking.booking_reference}\n'
        f'Course: {course_title}\n'
    )
    if workshop_url:
        calendar_description += f'Details: {workshop_url}\n'
    if tutor_name:
        calendar_description += f'Tutor: {tutor_name}'
        if tutor_email:
            calendar_description += f' ({tutor_email})'

    calendar = build_workshop_calendar(
        start=workshop.start_date,
        end=workshop.end_date,
        title=f'{course_title} — Going Digital',
        description=calendar_description.strip(),
        location=calendar_location or 'TBC',
        uid=f'{booking.booking_reference}@goingdigital.co.uk',
    )

    return {
        **calendar,
        'calendar_ics_filename': f'going-digital-{booking.booking_reference}.ics',
        'has_calendar': bool(calendar['google_calendar_url']),
    }


def attach_calendar_to_booking(booking):
    """Set booking.calendar with download URL for templates."""
    cal = calendar_data_for_booking(booking)
    if cal.get('calendar_ics'):
        cal['ics_download_url'] = reverse(
            'account:booking_calendar',
            args=[booking.booking_reference],
        )
    booking.calendar = cal
    return booking
