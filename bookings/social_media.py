"""Facebook group links shown after course bookings."""
import re
from html import unescape
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from core.models import User
from courses.models import Tutor

_OG_TAG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?P<prop>[^"\']+)["\'][^>]+content=["\'](?P<content>[^"\']+)["\']'
    r'|<meta[^>]+content=["\'](?P<content2>[^"\']+)["\'][^>]+(?:property|name)=["\'](?P<prop2>[^"\']+)["\']',
    re.IGNORECASE,
)
_LINK_PREVIEW_CACHE_SECONDS = 60 * 60 * 24


def normalize_facebook_url(url):
    """Return a usable https URL or empty string."""
    if not url:
        return ''
    url = str(url).strip()
    if not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    return url


def facebook_embed_preview_url(url):
    """Facebook plugin URL for an in-page preview (page or group)."""
    from urllib.parse import quote

    url = normalize_facebook_url(url)
    if not url:
        return ''

    encoded = quote(url, safe='')
    if '/groups/' in url.lower():
        return (
            f'https://www.facebook.com/plugins/group.php?href={encoded}'
            '&width=500&show_metadata=true&show_social_context=true&height=320'
            '&adapt_container_width=true'
        )
    return (
        f'https://www.facebook.com/plugins/page.php?href={encoded}'
        '&tabs=&width=500&height=320&small_header=true&adapt_container_width=true'
        '&hide_cover=false&show_facepile=true'
    )


def _urls_equivalent(a, b):
    if not a or not b:
        return False
    return normalize_facebook_url(a).rstrip('/').lower() == normalize_facebook_url(b).rstrip('/').lower()


def going_digital_facebook_group_url():
    return normalize_facebook_url(
        getattr(settings, 'GOING_DIGITAL_FACEBOOK_GROUP_URL', '')
    )


def resolve_workshop_facebook_user(workshop):
    """
    gd_user with a Facebook group URL for this workshop.
    Prefer workshop owner, then creator, then a user matching the tutor email.
    """
    if not workshop:
        return None

    candidate_ids = []
    for uid in (workshop.user_id, workshop.createdby_id):
        if uid and uid not in candidate_ids:
            candidate_ids.append(uid)

    for uid in candidate_ids:
        user = User.objects.filter(pk=uid, active=1).first()
        if user and (user.facebook_url or '').strip():
            return user

    if workshop.tutor_id:
        tutor = Tutor.objects.filter(pk=workshop.tutor_id).first()
        tutor_email = (tutor.email or '').strip() if tutor else ''
        if tutor_email:
            user = User.objects.filter(email__iexact=tutor_email, active=1).first()
            if user and (user.facebook_url or '').strip():
                return user

    return None


def local_facebook_group_for_workshop(workshop):
    """Return {'url', 'label'} for the franchisee/tutor group, or None."""
    user = resolve_workshop_facebook_user(workshop)
    if not user:
        return None

    url = normalize_facebook_url(user.facebook_url)
    if not url:
        return None

    main_url = going_digital_facebook_group_url()
    if main_url and _urls_equivalent(url, main_url):
        return None

    label = user.get_full_name() or user.email or 'your tutor'
    return {'url': url, 'label': label}


def facebook_groups_context_for_workshop(workshop):
    """Template/email context for a single workshop booking."""
    going_digital_url = going_digital_facebook_group_url()
    local_group = local_facebook_group_for_workshop(workshop)
    local_groups = [local_group] if local_group else []
    return {
        'going_digital_facebook_url': going_digital_url,
        'local_facebook_group': local_group,
        'local_facebook_groups': local_groups,
        'show_facebook_groups_cta': bool(going_digital_url or local_groups),
    }


def facebook_groups_context_for_booking(booking):
    """Template/email context for one booking."""
    workshop = getattr(booking, 'workshop', None)
    return facebook_groups_context_for_workshop(workshop)


def facebook_groups_context_for_bookings(bookings):
    """
    Context for payment success when multiple bookings may have different local groups.
    Deduplicates local groups by URL.
    """
    going_digital_url = going_digital_facebook_group_url()
    local_groups = []
    seen_urls = set()

    for booking in bookings:
        group = local_facebook_group_for_workshop(getattr(booking, 'workshop', None))
        if not group:
            continue
        key = group['url'].rstrip('/').lower()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        local_groups.append(group)

    return {
        'going_digital_facebook_url': going_digital_url,
        'local_facebook_group': local_groups[0] if len(local_groups) == 1 else None,
        'local_facebook_groups': local_groups,
        'show_facebook_groups_cta': bool(going_digital_url or local_groups),
    }


def facebook_groups_context_for_customer(customer):
    """Facebook groups for a student's recent confirmed bookings."""
    from core.student_auth import bookings_for_customer

    bookings = list(
        bookings_for_customer(customer)
        .select_related('workshop', 'workshop__course', 'workshop__venue')
        .filter(status='confirmed')
        .order_by('-created_at')[:5]
    )
    return facebook_groups_context_for_bookings(bookings)


def fetch_open_graph_preview(url, *, timeout=6):
    """Best-effort og:title, og:description, og:image for a Facebook URL."""
    url = normalize_facebook_url(url)
    if not url:
        return {'title': '', 'description': '', 'image': ''}

    cache_key = f'og_preview:{url.rstrip("/").lower()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    preview = {'title': '', 'description': '', 'image': ''}
    try:
        request = Request(
            url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-GB,en;q=0.9',
            },
        )
        with urlopen(request, timeout=timeout) as response:
            html = response.read(120_000).decode('utf-8', errors='replace')

        tags = {}
        for match in _OG_TAG_RE.finditer(html):
            prop = (match.group('prop') or match.group('prop2') or '').lower()
            content = unescape(match.group('content') or match.group('content2') or '').strip()
            if prop and content:
                tags[prop] = content

        preview['title'] = tags.get('og:title', '')
        preview['description'] = tags.get('og:description', '')
        preview['image'] = tags.get('og:image', '')
    except (URLError, OSError, ValueError, TimeoutError):
        pass

    cache.set(cache_key, preview, _LINK_PREVIEW_CACHE_SECONDS)
    return preview


def facebook_community_cards_for_bookings(bookings):
    """Rich card data for the post-booking community page."""
    return facebook_community_cards_from_groups_context(
        facebook_groups_context_for_bookings(bookings),
    )


def facebook_community_cards_from_groups_context(context):
    return _build_facebook_community_cards(
        context.get('going_digital_facebook_url', ''),
        context.get('local_facebook_groups') or [],
    )


def _build_facebook_community_cards(going_digital_url, local_groups):
    cards = []

    if going_digital_url:
        preview = fetch_open_graph_preview(going_digital_url)
        cards.append({
            'url': going_digital_url,
            'kind': 'main',
            'badge': 'Going Digital community',
            'headline': preview['title'] or 'Going Digital Photography Courses',
            'description': preview['description'] or (
                'Connect with students and tutors across the UK — share photos, '
                'ask questions, and get tips before your workshop.'
            ),
            'image': preview['image'],
            'embed_url': facebook_embed_preview_url(going_digital_url),
            'cta': 'Join on Facebook',
        })

    for group in local_groups or []:
        preview = fetch_open_graph_preview(group['url'])
        label = group.get('label') or 'your tutor'
        cards.append({
            'url': group['url'],
            'kind': 'local',
            'badge': f'Local group · {label}',
            'headline': preview['title'] or f'{label} on Facebook',
            'description': preview['description'] or (
                f'Join {label}\'s local Facebook community for workshop updates, '
                'venue details, and photos from your area.'
            ),
            'image': preview['image'],
            'embed_url': facebook_embed_preview_url(group['url']),
            'cta': 'Join local group',
        })

    return cards


def _absolute_url(path, request=None):
    if request:
        return request.build_absolute_uri(path)
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    if base and path.startswith('/'):
        return f'{base}{path}'
    return path


def facebook_share_url_for_page(share_url):
    """Open Facebook's share dialog for a public page URL."""
    share_url = (share_url or '').strip()
    if not share_url:
        return ''
    return f'https://www.facebook.com/sharer/sharer.php?u={quote(share_url, safe="")}'


def facebook_share_items_for_bookings(bookings, request=None):
    """
    Shareable course links for students to post on Facebook after booking.
    One item per unique workshop/course URL.
    """
    from courses.list_card import list_card_thumbnail_url

    items = []
    seen_urls = set()

    for booking in bookings or []:
        if booking.status == 'cancelled':
            continue
        workshop = getattr(booking, 'workshop', None)
        course = workshop.course if workshop else None
        if not workshop or not course:
            continue

        share_url = _absolute_url(workshop.get_absolute_url(), request)
        key = share_url.rstrip('/').lower()
        if key in seen_urls:
            continue
        seen_urls.add(key)

        venue = workshop.venue
        location_parts = []
        if venue:
            if venue.name:
                location_parts.append(venue.name)
            if venue.city:
                location_parts.append(venue.city)
        location_line = ', '.join(location_parts) or 'TBC'

        start = workshop.start_date
        date_line = start.strftime('%A %d %B %Y').lstrip('0') if start else 'TBC'

        image = list_card_thumbnail_url(course) or ''
        if image and not image.startswith(('http://', 'https://')):
            image = _absolute_url(image, request)

        course_title = course.title or 'Photography course'
        items.append({
            'booking_reference': booking.booking_reference,
            'course_title': course_title,
            'date_line': date_line,
            'location_line': location_line,
            'share_url': share_url,
            'facebook_share_url': facebook_share_url_for_page(share_url),
            'share_blurb': (
                f"I've just booked {course_title} with Going Digital on {date_line} "
                f"in {location_line}. Come and join me!"
            ),
            'image': image,
        })

    return items


def attach_facebook_share_to_booking(booking, request=None):
    """Attach a single share payload to a booking for templates."""
    items = facebook_share_items_for_bookings([booking], request)
    booking.facebook_share = items[0] if items else None
    return booking
