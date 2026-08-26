"""Shared SEO and AEO helpers."""
import json

from django.conf import settings
from django.urls import reverse


ORGANIZATION_NAME = 'Going Digital'
DEFAULT_OG_IMAGE_STATIC = 'img/logo/logo-dark.png'

# Shared homepage FAQ copy (visible HTML + JSON-LD must match for AEO).
HOMEPAGE_FAQ_ITEMS = (
    (
        'What photography courses are available near me?',
        'Going Digital offers photography courses and workshops across the UK for all skill levels. '
        'Browse courses by city or region on our locations pages, or use the course list and map to find training near you.',
    ),
    (
        'Are photography courses suitable for complete beginners?',
        'Yes. Level 1 courses such as Get Off Auto are designed for beginners and anyone who wants '
        'confidence with camera settings before moving on to more advanced workshops.',
    ),
    (
        'How do I book a photography course?',
        'Choose a course, pick a venue and date (or an open-dated one-to-one option), then complete '
        'checkout online. You can also buy gift vouchers if you are booking for someone else.',
    ),
    (
        'Do you offer one-to-one photography tuition?',
        'Yes. Some courses are open dated so you can book first and agree a date with your tutor afterwards — '
        'ideal for flexible one-to-one training.',
    ),
)


def homepage_faq_schema(base_url):
    return {
        '@type': 'FAQPage',
        '@id': f'{base_url}/#faqpage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': question,
                'acceptedAnswer': {'@type': 'Answer', 'text': answer},
            }
            for question, answer in HOMEPAGE_FAQ_ITEMS
        ],
    }


def site_base_url(request=None):
    """Canonical site origin (no trailing slash)."""
    if request is not None:
        return request.build_absolute_uri('/').rstrip('/')
    return getattr(settings, 'SITE_URL', 'https://goingdigital.co.uk').rstrip('/')


def absolute_url_from_base(site_base, path):
    """Join a site origin with a path, or pass through absolute URLs."""
    if path.startswith('http://') or path.startswith('https://'):
        return path
    base = (site_base or '').rstrip('/')
    if base and path.startswith('/'):
        return f'{base}{path}'
    return path


def site_url_for_booking(booking):
    """Site origin from checkout payment metadata, else settings fallback."""
    payment = getattr(booking, 'payment', None)
    if payment:
        stored = (payment.metadata or {}).get('site_url')
        if stored:
            return str(stored).rstrip('/')
    configured = site_base_url()
    from urllib.parse import urlparse
    host = (urlparse(configured).hostname or '').lower()
    if host in {'127.0.0.1', 'localhost'}:
        return 'https://goingdigital.co.uk'
    return configured


def absolute_url(request, path_or_route, *, kwargs=None):
    """Build an absolute URL from a path or named route."""
    if path_or_route.startswith('http://') or path_or_route.startswith('https://'):
        return path_or_route
    if path_or_route.startswith('/'):
        if request is None:
            return f'{site_base_url()}{path_or_route}'
        return request.build_absolute_uri(path_or_route)
    if request is None:
        path = reverse(path_or_route, kwargs=kwargs or {})
        return f'{site_base_url()}{path}'
    return request.build_absolute_uri(reverse(path_or_route, kwargs=kwargs or {}))


def breadcrumb_schema(items):
    """
    Build BreadcrumbList JSON-LD dict.
    items: iterable of (name, url) pairs; url may be None for current page.
    """
    elements = []
    for position, (name, url) in enumerate(items, start=1):
        entry = {
            '@type': 'ListItem',
            'position': position,
            'name': name,
        }
        if url:
            entry['item'] = url
        elements.append(entry)
    return {
        '@type': 'BreadcrumbList',
        'itemListElement': elements,
    }


def aggregate_rating_schema(google_reviews):
    """AggregateRating dict when live review data is available."""
    if not google_reviews:
        return None
    rating = google_reviews.get('rating')
    review_count = google_reviews.get('review_count')
    if rating is None or not review_count:
        return None
    return {
        '@type': 'AggregateRating',
        'ratingValue': str(rating),
        'reviewCount': int(review_count),
        'bestRating': '5',
        'worstRating': '1',
    }


def dumps_json_ld(data) -> str:
    """
    Serialize JSON-LD for embedding in <script type="application/ld+json">.
    Escapes '<' so venue/course names cannot break out of the script tag (XSS).
    """
    return json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')


def organization_schema(request=None, *, google_reviews=None):
    """Organization baseline for JSON-LD graphs."""
    base = site_base_url(request)
    schema = {
        '@type': 'Organization',
        '@id': f'{base}/#organization',
        'name': ORGANIZATION_NAME,
        'url': base,
        'logo': f'{base}/static/{DEFAULT_OG_IMAGE_STATIC}',
        'description': (
            'Going Digital runs hands-on photography courses and workshops across the UK '
            'for beginners through to advanced photographers.'
        ),
    }
    rating = aggregate_rating_schema(google_reviews)
    if rating:
        schema['aggregateRating'] = rating
    return schema


def local_business_schema(request=None, *, google_reviews=None):
    """LocalBusiness variant for homepage/local discovery."""
    base = site_base_url(request)
    schema = {
        '@type': 'LocalBusiness',
        '@id': f'{base}/#business',
        'name': ORGANIZATION_NAME,
        'image': f'{base}/static/{DEFAULT_OG_IMAGE_STATIC}',
        'url': base,
        'priceRange': '££',
        'address': {'@type': 'PostalAddress', 'addressCountry': 'GB'},
        'areaServed': {'@type': 'Country', 'name': 'United Kingdom'},
        'description': (
            'Hands-on photography courses and workshops across the UK for all skill levels.'
        ),
    }
    rating = aggregate_rating_schema(google_reviews)
    if rating:
        schema['aggregateRating'] = rating
    return schema
