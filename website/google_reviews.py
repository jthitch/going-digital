"""Google reviews badge and featured reviews for the homepage."""

import json
import logging
import re
import urllib.error
import urllib.request
from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings as django_settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

LIVE_REVIEWS_CACHE_SECONDS = 60 * 60 * 12
PLACE_ID_LOOKUP_CACHE_SECONDS = 60 * 60 * 24 * 7
DISPLAY_CACHE_KEY = 'google_reviews_display:v1'
_CACHE_ABSENT = object()
GD_PHOTOGRAPHY_PLACE_ID = 'ChIJJ7LQAEllcKsRKFDjNi5UapI'


def _cache_slug(value):
    return re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-')


def _rating_stars(rating):
    """Return full star count (0–5) and whether to show a partial star."""
    value = max(1.0, min(5.0, float(rating)))
    full = int(value)
    remainder = value - full
    if remainder >= 0.75:
        full += 1
        partial = False
    else:
        partial = remainder >= 0.25 and full < 5
    return min(full, 5), partial


def _format_rating(rating):
    value = Decimal(str(rating)).quantize(Decimal('0.1'))
    text = f'{value:.1f}'
    if text.endswith('0'):
        text = text[:-2]
    return text


def _author_initials(name):
    parts = [part for part in (name or '').split() if part]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f'{parts[0][0]}{parts[-1][0]}'.upper()


def _review_star_context(rating):
    full_stars, has_partial_star = _rating_stars(rating)
    empty_stars = max(0, 5 - full_stars - (1 if has_partial_star else 0))
    return {
        'full_star_range': range(full_stars),
        'has_partial_star': has_partial_star,
        'empty_star_range': range(empty_stars),
    }


def _normalize_place_id(place_id):
    value = (place_id or '').strip()
    if value.startswith('places/'):
        return value[len('places/'):]
    return value


def _google_cid_for_config(config):
    cid = (getattr(config, 'google_cid', '') or '').strip()
    if cid:
        return cid

    reviews_url = (config.reviews_url or '').strip()
    match = re.search(r'0x[a-f0-9]+:(0x[a-f0-9]+)', reviews_url, re.I)
    if match:
        return str(int(match.group(1), 16))

    match = re.search(r'[?&]cid=(\d+)', reviews_url)
    if match:
        return match.group(1)
    return ''


def _places_api_request(url, api_key, *, field_mask, method='GET', body=None):
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': field_mask,
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:500]
        logger.warning('Google Places API HTTP %s for %s: %s', exc.code, field_mask, detail)
        raise


def _place_maps_cid(place_id, api_key):
    place_id = _normalize_place_id(place_id)
    if not place_id:
        return ''

    cache_key = f'google_place_maps_cid:{place_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        payload = _places_api_request(
            f'https://places.googleapis.com/v1/places/{place_id}',
            api_key,
            field_mask='googleMapsUri',
        )
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
        return ''

    uri = payload.get('googleMapsUri') or ''
    match = re.search(r'[?&]cid=(\d+)', uri)
    cid = match.group(1) if match else ''
    cache.set(cache_key, cid, PLACE_ID_LOOKUP_CACHE_SECONDS)
    return cid


def _lookup_place_id_from_cid(cid, api_key):
    """Resolve Place ID from a Google Business Profile CID (legacy Places API)."""
    cache_key = f'google_place_id_from_cid:{cid}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = (
        'https://maps.googleapis.com/maps/api/place/details/json'
        f'?cid={cid}&fields=place_id&key={api_key}'
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
        return ''

    if payload.get('status') != 'OK':
        return ''

    place_id = _normalize_place_id((payload.get('result') or {}).get('place_id', ''))
    if place_id:
        cache.set(cache_key, place_id, PLACE_ID_LOOKUP_CACHE_SECONDS)
    return place_id


def _place_lookup_queries(config):
    """Build search queries — legal name often differs from the Google listing title."""
    queries = []
    name = (config.business_name or '').strip()
    if name:
        queries.append(name)

    for fallback in (
        'GD Photography Ltd',
        'Going Digital photography courses',
        'Going Digital photographic training',
        'goingdigital.co.uk photography courses',
    ):
        queries.append(fallback)

    site_url = getattr(django_settings, 'SITE_URL', '')
    host = urlparse(site_url).netloc.replace('www.', '') if site_url else ''
    if host and host not in {'127.0.0.1', 'localhost'}:
        queries.append(f'{host} photography courses')

    seen = set()
    unique = []
    for query in queries:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            unique.append(query)
    return unique


def _pick_place_from_results(places, config, api_key=''):
    """Prefer the main Going Digital listing over regional pages."""
    if not places:
        return ''

    business_name = (config.business_name or '').strip().lower()
    target_cid = _google_cid_for_config(config)
    best_place_id = ''
    best_score = -1

    for place in places:
        place_id = _normalize_place_id(place.get('id', ''))
        if not place_id:
            continue

        display_name = ((place.get('displayName') or {}).get('text') or '').lower()
        website = (place.get('websiteUri') or '').lower()
        review_count = int(place.get('userRatingCount') or 0)
        score = review_count

        if business_name and business_name in display_name:
            score += 10_000
        if display_name == business_name:
            score += 5_000
        if 'goingdigital.co.uk' in website:
            score += 500

        if score > best_score:
            best_score = score
            best_place_id = place_id

    if best_place_id and target_cid and api_key:
        maps_cid = _place_maps_cid(best_place_id, api_key)
        if maps_cid and maps_cid != target_cid:
            for place in places:
                place_id = _normalize_place_id(place.get('id', ''))
                if not place_id:
                    continue
                maps_cid = _place_maps_cid(place_id, api_key)
                if maps_cid == target_cid:
                    return place_id

    return best_place_id


def _lookup_place_id(config, api_key):
    """Resolve a Place ID via Text Search when not configured explicitly."""
    queries = _place_lookup_queries(config)
    if not queries:
        return ''

    cache_key = f'google_place_id_lookup:{_cache_slug("|".join(queries[:3]))}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    place_id = ''
    for query in queries:
        try:
            payload = _places_api_request(
                'https://places.googleapis.com/v1/places:searchText',
                api_key,
                field_mask='places.id,places.displayName,places.websiteUri,places.userRatingCount',
                method='POST',
                body={
                    'textQuery': query,
                    'regionCode': 'GB',
                    'includePureServiceAreaBusinesses': True,
                },
            )
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
            continue

        place_id = _pick_place_from_results(payload.get('places') or [], config, api_key)
        if place_id:
            break

    if place_id:
        cache.set(cache_key, place_id, PLACE_ID_LOOKUP_CACHE_SECONDS)
    return place_id


def _resolve_place_id_cache_key(config):
    explicit = (config.google_place_id or '').strip()
    env_place = (getattr(django_settings, 'GOOGLE_PLACE_ID', '') or '').strip()
    cid = _google_cid_for_config(config)
    return (
        'google_resolved_place_id:'
        f'{_cache_slug(explicit)}:{_cache_slug(env_place)}:{cid}'
    )


def _resolve_place_id(config, api_key):
    if not api_key:
        place_id = _normalize_place_id(config.google_place_id)
        if not place_id:
            place_id = _normalize_place_id(getattr(django_settings, 'GOOGLE_PLACE_ID', ''))
        return place_id or GD_PHOTOGRAPHY_PLACE_ID

    cache_key = _resolve_place_id_cache_key(config)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    explicit = bool((config.google_place_id or '').strip())
    place_id = _normalize_place_id(config.google_place_id)
    if not place_id:
        place_id = _normalize_place_id(getattr(django_settings, 'GOOGLE_PLACE_ID', ''))
    if not place_id:
        place_id = GD_PHOTOGRAPHY_PLACE_ID

    if not explicit:
        target_cid = _google_cid_for_config(config)
        if target_cid and place_id:
            maps_cid = _place_maps_cid(place_id, api_key)
            if maps_cid and maps_cid != target_cid:
                place_id = ''

        if not place_id and target_cid:
            place_id = _lookup_place_id_from_cid(target_cid, api_key)

        if not place_id:
            place_id = _lookup_place_id(config, api_key) or GD_PHOTOGRAPHY_PLACE_ID

    cache.set(cache_key, place_id, PLACE_ID_LOOKUP_CACHE_SECONDS)
    return place_id


def _normalize_review(
    author_name,
    review_text,
    rating,
    *,
    photo_url='',
    photo_upload='',
    relative_time='',
):
    text = (review_text or '').strip()
    if not text:
        return None
    name = (author_name or 'Google reviewer').strip()
    stars = _review_star_context(rating)
    return {
        'author_name': name,
        'review_text': text,
        'rating': int(rating),
        'photo_url': photo_upload or photo_url or '',
        'initials': _author_initials(name),
        'relative_time': (relative_time or '').strip(),
        **stars,
    }


def _fetch_live_place_data(place_id, api_key):
    place_id = _normalize_place_id(place_id)
    if not place_id:
        return None

    cache_key = f'google_place_data:{place_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        payload = _places_api_request(
            f'https://places.googleapis.com/v1/places/{place_id}',
            api_key,
            field_mask='rating,userRatingCount,reviews',
        )
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
        return None

    rating = payload.get('rating')
    if rating is None:
        return None

    reviews = []
    # Google returns up to five reviews, sorted by relevance.
    for item in payload.get('reviews') or []:
        attribution = item.get('authorAttribution') or {}
        text_block = item.get('text') or {}
        normalized = _normalize_review(
            attribution.get('displayName', ''),
            text_block.get('text', ''),
            item.get('rating') or rating,
            photo_url=attribution.get('photoUri', ''),
            relative_time=item.get('relativePublishTimeDescription', ''),
        )
        if normalized:
            reviews.append(normalized)

    result = {
        'rating': Decimal(str(rating)).quantize(Decimal('0.1')),
        'review_count': int(payload.get('userRatingCount') or 0),
        'reviews': reviews,
        'is_live': True,
    }
    cache.set(cache_key, result, LIVE_REVIEWS_CACHE_SECONDS)
    return result


def _highlights_from_admin(config):
    highlights = []
    for item in config.highlights.filter(is_active=True).order_by('order', 'id')[:6]:
        photo_upload = item.author_photo.url if item.author_photo else ''
        normalized = _normalize_review(
            item.author_name,
            item.review_text,
            item.rating,
            photo_url=item.author_photo_url,
            photo_upload=photo_upload,
        )
        if normalized:
            highlights.append(normalized)
    return highlights


def _place_id_for_config(config, api_key=''):
    """Resolve a Google place ID from settings, then live lookup if needed."""
    place_id = _normalize_place_id(config.google_place_id)
    if not place_id:
        place_id = _normalize_place_id(getattr(django_settings, 'GOOGLE_PLACE_ID', ''))
    if not place_id and api_key:
        place_id = _resolve_place_id(config, api_key)
    return place_id


def _build_reviews_url(config, api_key=''):
    """
    Return a reliable outbound URL for reading Google reviews.

    Prefer the dedicated Google reviews page (place ID), then Maps (CID),
    then the admin-configured fallback URL.
    """
    place_id = _place_id_for_config(config, api_key=api_key)
    if place_id:
        return f'https://search.google.com/local/reviews?placeid={place_id}'

    cid = _google_cid_for_config(config)
    if cid:
        return f'https://www.google.com/maps?cid={cid}'

    fallback = (config.reviews_url or '').strip()
    return fallback or 'https://www.google.com/maps'


def _build_write_review_url(config, api_key=''):
    """
    Return a URL that opens Google's leave-a-review flow when possible.
    Falls back to the read reviews URL if place ID is unavailable.
    """
    place_id = _place_id_for_config(config, api_key=api_key)
    if place_id:
        return f'https://search.google.com/local/writereview?placeid={place_id}'
    return _build_reviews_url(config, api_key=api_key)


def google_write_review_url():
    """Public helper: Google write-review URL from active site settings."""
    from website.models import GoogleReviewsSettings

    config = GoogleReviewsSettings.objects.first()
    if config is None:
        place_id = _normalize_place_id(getattr(django_settings, 'GOOGLE_PLACE_ID', ''))
        if place_id:
            return f'https://search.google.com/local/writereview?placeid={place_id}'
        return 'https://www.google.com/maps'
    api_key = (getattr(django_settings, 'GOOGLE_PLACES_API_KEY', '') or '').strip()
    return _build_write_review_url(config, api_key=api_key)


def invalidate_google_reviews_cache(*, place_id=''):
    """Clear cached review display (and optional live place payload) after admin edits."""
    cache.delete(DISPLAY_CACHE_KEY)
    normalized = _normalize_place_id(place_id)
    if normalized:
        cache.delete(f'google_place_data:{normalized}')
        cache.delete(f'google_place_maps_cid:{normalized}')


def _build_google_reviews_display():
    """Build review badge context; callers should use get_google_reviews_display()."""
    from website.models import GoogleReviewsSettings

    config = GoogleReviewsSettings.objects.prefetch_related('highlights').first()
    if config is None or not config.is_active:
        return None

    rating = config.rating
    review_count = config.review_count
    featured_reviews = []
    reviews_are_live = False

    api_key = (getattr(django_settings, 'GOOGLE_PLACES_API_KEY', '') or '').strip()
    if config.use_live_reviews and api_key:
        place_id = _resolve_place_id(config, api_key)
        if place_id:
            live = _fetch_live_place_data(place_id, api_key)
            if live:
                rating = live['rating']
                review_count = live['review_count']
                featured_reviews = live.get('reviews') or []
                reviews_are_live = bool(featured_reviews)

    if not featured_reviews:
        featured_reviews = _highlights_from_admin(config)

    reviews_url = _build_reviews_url(config, api_key=api_key)
    full_stars, has_partial_star = _rating_stars(rating)
    empty_stars = max(0, 5 - full_stars - (1 if has_partial_star else 0))
    return {
        'business_name': config.business_name,
        'rating': rating,
        'rating_display': _format_rating(rating),
        'review_count': review_count,
        'reviews_url': reviews_url,
        'full_stars': full_stars,
        'has_partial_star': has_partial_star,
        'empty_stars': empty_stars,
        'full_star_range': range(full_stars),
        'empty_star_range': range(empty_stars),
        'featured_reviews': featured_reviews,
        'reviews_are_live': reviews_are_live,
    }


def get_google_reviews_display():
    """Context for the homepage Google reviews section, or None when hidden."""
    cached = cache.get(DISPLAY_CACHE_KEY)
    if cached is _CACHE_ABSENT:
        return None
    if cached is not None:
        return cached

    result = _build_google_reviews_display()
    cache.set(
        DISPLAY_CACHE_KEY,
        _CACHE_ABSENT if result is None else result,
        LIVE_REVIEWS_CACHE_SECONDS,
    )
    return result
