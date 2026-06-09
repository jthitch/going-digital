"""Calendar links and .ics content for workshop booking emails."""
from urllib.parse import quote

from django.utils import timezone


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
