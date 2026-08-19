"""Template context for booking-related emails."""
from decimal import Decimal

from django.conf import settings
from django.urls import reverse

from core.student_auth import account_setup_from_bookings
from website.seo import absolute_url_from_base, site_base_url, site_url_for_booking

from courses.models import Tutor

from .calendar import calendar_data_for_booking
from .franchisee_contract import (
    franchisee_contract_details,
    franchisee_contract_notice_from_details,
)
from .reminder_email_copy import reminder_email_copy
from .social_media import facebook_groups_context_for_bookings, facebook_share_items_for_bookings


def _logo_url(site_url):
    static_url = settings.STATIC_URL.rstrip('/')
    if static_url.startswith('http://') or static_url.startswith('https://'):
        return f'{static_url}/img/logo/logo-dark.png'
    return absolute_url_from_base(site_url, f'{static_url}/img/logo/logo-dark.png')


def _booking_item_context(booking, *, site_url):
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
        workshop_url = absolute_url_from_base(site_url, workshop.get_absolute_url())

    calendar = calendar_data_for_booking(booking, site_base=site_url)
    contract = franchisee_contract_details(workshop)
    franchisee_name = contract['name'] if contract else ''
    franchisee_address = contract['address'] if contract else ''
    notice = franchisee_contract_notice_from_details(contract)

    return {
        'booking': booking,
        'booking_reference': booking.booking_reference,
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
        'special_requirements': booking.special_requirements or '',
        'google_calendar_url': calendar['google_calendar_url'],
        'outlook_calendar_url': calendar['outlook_calendar_url'],
        'calendar_ics': calendar['calendar_ics'],
        'calendar_ics_filename': calendar['calendar_ics_filename'],
        'workshop': workshop,
        'franchisee_name': franchisee_name,
        'franchisee_address': franchisee_address,
        'franchisee_contract_notice': notice,
    }


def bookings_confirmation_context(bookings, *, request=None):
    """Build context for one or more bookings confirmed in the same payment."""
    bookings = list(bookings)
    if not bookings:
        raise ValueError('At least one booking is required for confirmation context.')

    primary = bookings[0]
    site_url = site_base_url(request) if request is not None else site_url_for_booking(primary)
    booking_items = [_booking_item_context(booking, site_url=site_url) for booking in bookings]
    first = booking_items[0]

    account_setup_url = ''
    setup = account_setup_from_bookings(bookings)
    if setup and setup.get('booking_reference'):
        account_setup_url = absolute_url_from_base(
            site_url,
            reverse('account:complete_setup')
            + f'?ref={setup["booking_reference"]}',
        )

    total_price_paid = sum(
        (Decimal(str(item['price_paid'] or 0)) for item in booking_items),
        Decimal('0.00'),
    )
    total_voucher_discount = sum(
        (Decimal(str(item['voucher_discount'] or 0)) for item in booking_items),
        Decimal('0.00'),
    )
    voucher_codes = {
        (item['voucher_code'] or '').strip()
        for item in booking_items
        if (item['voucher_code'] or '').strip()
    }
    shared_voucher_code = next(iter(voucher_codes)) if len(voucher_codes) == 1 else ''

    context = {
        'booking': primary,
        'booking_items': booking_items,
        'is_multi_booking': len(booking_items) > 1,
        'booking_count': len(booking_items),
        'account_setup_url': account_setup_url,
        'booking_reference': first['booking_reference'],
        'student_name': f'{primary.student_first_name} {primary.student_last_name}'.strip(),
        'student_email': primary.student_email,
        'student_phone': primary.student_phone or '',
        'special_requirements': first['special_requirements'],
        'course_title': first['course_title'],
        'workshop_date': first['workshop_date'],
        'workshop_time': first['workshop_time'],
        'location_name': first['location_name'],
        'location_city': first['location_city'],
        'location_address': first['location_address'],
        'price_paid': first['price_paid'],
        'list_price': first['list_price'],
        'total_price_paid': total_price_paid,
        'voucher_code': shared_voucher_code or first['voucher_code'],
        'voucher_discount': total_voucher_discount if shared_voucher_code else first['voucher_discount'],
        'tutor_name': first['tutor_name'],
        'tutor_email': first['tutor_email'],
        'workshop_url': first['workshop_url'],
        'contact_email': getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'site_url': site_url,
        'logo_url': _logo_url(site_url),
        'google_calendar_url': first['google_calendar_url'],
        'outlook_calendar_url': first['outlook_calendar_url'],
        'calendar_ics': first['calendar_ics'],
        'calendar_ics_filename': first['calendar_ics_filename'],
        'franchisee_name': first['franchisee_name'],
        'franchisee_address': first['franchisee_address'],
        'franchisee_contract_notice': first['franchisee_contract_notice'],
    }
    context.update(facebook_groups_context_for_bookings(bookings))
    context['facebook_share_items'] = facebook_share_items_for_bookings(
        bookings,
        site_base=site_url,
    )
    return context


def booking_confirmation_context(booking, *, request=None):
    """Build context dict for a single booking confirmation email."""
    return bookings_confirmation_context([booking], request=request)


def booking_confirmation_subject(bookings):
    bookings = list(bookings)
    if not bookings:
        return 'Booking confirmed'
    if len(bookings) == 1:
        workshop = bookings[0].workshop
        course_title = workshop.course.title if workshop and workshop.course else 'Workshop'
        return f'Booking confirmed: {course_title}'

    titles = []
    seen = set()
    for booking in bookings:
        workshop = booking.workshop
        title = workshop.course.title if workshop and workshop.course else 'Workshop'
        if title not in seen:
            seen.add(title)
            titles.append(title)

    if len(titles) == 1:
        return f'Booking confirmed: {titles[0]} ({len(bookings)} places)'
    if len(titles) == 2:
        return f'Booking confirmed: {titles[0]} and {titles[1]}'
    return f'Booking confirmed: {len(bookings)} courses'


def _workshop_notes_for_email(workshop):
    """Plain-text notes to include in the day-before reminder."""
    if not workshop:
        return []

    notes = []
    reminder = (workshop.reminder_message or '').strip()
    if reminder:
        notes.append(('Course notes', reminder))

    byline = (workshop.byline_plain or '').strip()
    if byline:
        notes.append(('Workshop details', byline))

    return notes


def booking_reminder_context(booking, *, request=None):
    """Build context for the day-before workshop reminder email."""
    site_url = site_base_url(request) if request is not None else site_url_for_booking(booking)
    item = _booking_item_context(booking, site_url=site_url)
    workshop = booking.workshop

    tutor_telephone = ''
    if workshop and workshop.tutor_id:
        tutor = Tutor.objects.filter(pk=workshop.tutor_id).first()
        if tutor:
            tutor_telephone = (tutor.telephone or '').strip()

    from bookings.tutor_contact import tutor_contact_for_booking

    tutor_contact = tutor_contact_for_booking(booking)

    copy = reminder_email_copy()
    return {
        'booking': booking,
        'student_name': f'{booking.student_first_name} {booking.student_last_name}'.strip(),
        'student_email': booking.student_email,
        'contact_email': getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'site_url': site_url,
        'logo_url': _logo_url(site_url),
        'tutor_telephone': tutor_telephone,
        'tutor_mailto_url': tutor_contact.get('mailto_url', ''),
        'workshop_notes': _workshop_notes_for_email(workshop),
        'reminder_intro': copy['intro'],
        'reminder_closing': copy['closing'],
        **item,
    }


def workshop_reminder_preview_context(workshop, *, site_url=None):
    """Build reminder email context for admin preview (sample student if no booking)."""
    from bookings.models import Booking

    booking = (
        Booking.objects.filter(workshop=workshop, status='confirmed')
        .select_related('workshop', 'workshop__course', 'workshop__venue', 'payment')
        .order_by('id')
        .first()
    )
    if booking and booking.is_confirmed:
        return booking_reminder_context(booking)

    from types import SimpleNamespace
    from decimal import Decimal

    if site_url is None:
        site_url = getattr(settings, 'SITE_URL', 'https://example.com').rstrip('/')

    sample = SimpleNamespace(
        id=0,
        workshop=workshop,
        booking_reference='SAMPLE-REF',
        student_first_name='Sample',
        student_last_name='Student',
        student_email='student@example.com',
        student_phone='',
        special_requirements='',
        price_paid=Decimal('0.00'),
        list_price=Decimal('0.00'),
        voucher_code='',
        voucher_discount=Decimal('0.00'),
        is_confirmed=True,
        status='confirmed',
    )
    return booking_reminder_context(sample, request=None)


def booking_reminder_subject(booking):
    workshop = booking.workshop
    course_title = workshop.course.title if workshop and workshop.course else 'Workshop'
    start = workshop.start_date if workshop else None
    if start:
        date_label = start.strftime('%A %d %B')
        return f'Reminder: {course_title} — {date_label}'
    return f'Reminder: {course_title} is tomorrow'

