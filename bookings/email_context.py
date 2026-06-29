"""Template context for booking-related emails."""
from django.conf import settings
from django.urls import reverse

from core.student_auth import account_setup_from_bookings

from courses.models import Tutor

from .calendar import calendar_data_for_booking
from .social_media import facebook_groups_context_for_booking, facebook_share_items_for_bookings


def _absolute_url(path):
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    if base and path.startswith('/'):
        return f'{base}{path}'
    return path


def booking_confirmation_context(booking):
    """Build context dict for booking confirmation templates."""
    workshop = booking.workshop
    course = workshop.course if workshop else None
    venue = workshop.venue if workshop else None

    tutor_name = ''
    tutor_email = ''
    if workshop and workshop.tutor_id:
        tutor = Tutor.objects.filter(pk=workshop.tutor_id).first()
        if tutor:
            tutor_name = str(tutor)
            tutor_email = (tutor.email or '').strip()

    course_title = course.title if course else 'Workshop'
    start = workshop.start_date if workshop else None
    location_name = venue.name if venue else 'TBC'
    location_city = venue.city if venue else ''
    location_address = ''
    if venue:
        location_address = (venue.venue_address or venue.location or '').strip()

    workshop_url = ''
    if workshop:
        workshop_url = _absolute_url(workshop.get_absolute_url())

    static_url = settings.STATIC_URL.rstrip('/')
    logo_url = _absolute_url(f'{static_url}/img/logo/logo-dark.png')

    calendar = calendar_data_for_booking(booking)

    account_setup_url = ''
    setup = account_setup_from_bookings([booking])
    if setup and setup.get('booking_reference'):
        account_setup_url = _absolute_url(
            reverse('account:complete_setup')
            + f'?ref={setup["booking_reference"]}'
        )

    context = {
        'booking': booking,
        'account_setup_url': account_setup_url,
        'booking_reference': booking.booking_reference,
        'student_name': f'{booking.student_first_name} {booking.student_last_name}'.strip(),
        'student_email': booking.student_email,
        'student_phone': booking.student_phone or '',
        'special_requirements': booking.special_requirements or '',
        'course_title': course_title,
        'workshop_date': start.strftime('%d %B %Y') if start else 'TBC',
        'workshop_time': start.strftime('%I:%M %p').lstrip('0') if start else '',
        'location_name': location_name,
        'location_city': location_city,
        'location_address': location_address,
        'price_paid': booking.price_paid,
        'list_price': booking.list_price or booking.price_paid,
        'voucher_code': booking.voucher_code or '',
        'voucher_discount': booking.voucher_discount or 0,
        'tutor_name': tutor_name,
        'tutor_email': tutor_email,
        'workshop_url': workshop_url,
        'contact_email': getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'site_url': getattr(settings, 'SITE_URL', '').rstrip('/'),
        'logo_url': logo_url,
        'google_calendar_url': calendar['google_calendar_url'],
        'outlook_calendar_url': calendar['outlook_calendar_url'],
        'calendar_ics': calendar['calendar_ics'],
        'calendar_ics_filename': calendar['calendar_ics_filename'],
    }
    context.update(facebook_groups_context_for_booking(booking))
    context['facebook_share_items'] = facebook_share_items_for_bookings([booking])
    return context
