"""Resolve course-list search keywords to a map point (town / city / postcode)."""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Q

from courses.models import Venue
from courses.postcode_lookup import (
    POSTCODE_RE,
    _http_get_json,
    lookup_uk_postcode,
)
from courses.venue_list import DEFAULT_NEAR_RADIUS_MILES

logger = logging.getLogger(__name__)

# Outward code only, e.g. BS8 / SW1A
OUTCODE_RE = re.compile(r'^[A-Z]{1,2}\d[A-Z\d]?$', re.IGNORECASE)

_MIN_PLACE_QUERY_LEN = 3
_CACHE_TTL_SECONDS = 60 * 60 * 24

# Course-topic words that should not trigger open geocoding (venue DB match still OK).
_TOPIC_BLOCKLIST = frozenset({
    'beginner', 'intermediate', 'advanced', 'portrait', 'portraits', 'landscape',
    'landscapes', 'wedding', 'weddings', 'street', 'wildlife', 'macro', 'product',
    'lightroom', 'photoshop', 'editing', 'camera', 'cameras', 'dslr', 'mirrorless',
    'flash', 'studio', 'night', 'astro', 'astrophotography', 'film', 'darkroom',
    'workshop', 'workshops', 'course', 'courses', 'photography', 'photo', 'photos',
})


@dataclass(frozen=True)
class ResolvedSearchPlace:
    latitude: float
    longitude: float
    label: str
    source: str  # postcode | outcode | venue | geocode


def _cache_get(key: str):
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key: str, value):
    try:
        cache.set(key, value, _CACHE_TTL_SECONDS)
    except Exception:
        pass


def _looks_like_full_postcode(query: str) -> bool:
    compact = re.sub(r'[^A-Za-z0-9]', '', query or '')
    if len(compact) < 5 or len(compact) > 7:
        return False
    formatted = f'{compact[:-3]} {compact[-3:]}'
    return bool(POSTCODE_RE.match(formatted))


def _looks_like_outcode(query: str) -> bool:
    compact = re.sub(r'[^A-Za-z0-9]', '', query or '').upper()
    return bool(OUTCODE_RE.match(compact)) and not _looks_like_full_postcode(query)


def _resolve_postcode(query: str) -> ResolvedSearchPlace | None:
    try:
        data = lookup_uk_postcode(query)
    except ValueError:
        return None
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat is None or lng is None:
        return None
    label = data.get('postcode') or query.strip().upper()
    town = (data.get('location') or '').strip()
    if town:
        label = f'{label} ({town})'
    return ResolvedSearchPlace(
        latitude=float(lat),
        longitude=float(lng),
        label=label,
        source='postcode',
    )


def _resolve_outcode(query: str) -> ResolvedSearchPlace | None:
    compact = re.sub(r'[^A-Za-z0-9]', '', query or '').upper()
    cache_key = f'search_place:outcode:{compact}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return ResolvedSearchPlace(**cached) if cached else None

    encoded = urllib.parse.quote(compact, safe='')
    url = f'https://api.postcodes.io/outcodes/{encoded}'
    try:
        data = _http_get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            _cache_set(cache_key, None)
            return None
        logger.info('Outcode lookup failed for %s: %s', compact, exc)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.info('Outcode lookup unavailable for %s: %s', compact, exc)
        return None

    result = data.get('result') or {}
    lat, lng = result.get('latitude'), result.get('longitude')
    if lat is None or lng is None:
        _cache_set(cache_key, None)
        return None

    place = ResolvedSearchPlace(
        latitude=float(lat),
        longitude=float(lng),
        label=result.get('outcode') or compact,
        source='outcode',
    )
    _cache_set(cache_key, {
        'latitude': place.latitude,
        'longitude': place.longitude,
        'label': place.label,
        'source': place.source,
    })
    return place


def _venue_centroid(queryset) -> tuple[float, float, str] | None:
    """Average lat/lng of venues with coordinates; label from most common location."""
    with_coords = queryset.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    agg = with_coords.aggregate(lat=Avg('latitude'), lng=Avg('longitude'))
    if agg['lat'] is None or agg['lng'] is None:
        return None

    locations = list(
        with_coords.exclude(location='')
        .exclude(location__isnull=True)
        .values_list('location', flat=True)[:20]
    )
    label = ''
    if locations:
        counts: dict[str, tuple[int, str]] = {}
        for loc in locations:
            key = loc.strip().lower()
            if not key:
                continue
            count, sample = counts.get(key, (0, loc.strip()))
            counts[key] = (count + 1, sample)
        if counts:
            label = max(counts.values(), key=lambda item: item[0])[1]
    if not label:
        first = with_coords.values_list('venue_name', flat=True).first()
        label = (first or 'Matched venues').strip()
    return float(agg['lat']), float(agg['lng']), label


def _resolve_from_venues(query: str) -> ResolvedSearchPlace | None:
    q = (query or '').strip()
    if len(q) < _MIN_PLACE_QUERY_LEN:
        return None

    base = Venue.objects.filter(active=1)

    exact = base.filter(location__iexact=q)
    result = _venue_centroid(exact)
    if result:
        lat, lng, label = result
        return ResolvedSearchPlace(lat, lng, label or q, 'venue')

    prefix = base.filter(location__istartswith=q)
    result = _venue_centroid(prefix)
    if result:
        lat, lng, label = result
        return ResolvedSearchPlace(lat, lng, label or q, 'venue')

    contains = base.filter(
        Q(location__icontains=q)
        | Q(venue_address__icontains=q)
        | Q(venue_name__icontains=q)
    )
    # Require at least one town (location) hit to avoid matching coursey venue names only.
    if not contains.filter(location__icontains=q).exists():
        return None
    result = _venue_centroid(contains)
    if not result:
        return None
    lat, lng, label = result
    return ResolvedSearchPlace(lat, lng, label or q, 'venue')


def _nominatim_user_agent() -> str:
    contact = getattr(settings, 'CONTACT_EMAIL', '') or 'info@goingdigital.co.uk'
    site = getattr(settings, 'SITE_URL', '') or 'https://www.goingdigital.co.uk'
    return f'GoingDigitalCourseSearch/1.0 ({site}; {contact})'


def _resolve_via_nominatim(query: str) -> ResolvedSearchPlace | None:
    q = (query or '').strip()
    if len(q) < _MIN_PLACE_QUERY_LEN:
        return None
    if q.lower() in _TOPIC_BLOCKLIST:
        return None
    tokens = [t for t in re.split(r'\s+', q.lower()) if t]
    if len(tokens) > 3:
        return None
    if any(t in _TOPIC_BLOCKLIST for t in tokens) and len(tokens) > 1:
        return None

    cache_key = f'search_place:nominatim:{q.lower()}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return ResolvedSearchPlace(**cached) if cached else None

    params = urllib.parse.urlencode({
        'q': q,
        'format': 'json',
        'limit': '1',
        'countrycodes': 'gb',
        'addressdetails': '0',
    })
    url = f'https://nominatim.openstreetmap.org/search?{params}'
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': _nominatim_user_agent(),
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        logger.info('Nominatim lookup failed for %r: %s', q, exc)
        return None

    if not data:
        _cache_set(cache_key, None)
        return None

    hit = data[0]
    try:
        lat = float(hit['lat'])
        lng = float(hit['lon'])
    except (KeyError, TypeError, ValueError):
        _cache_set(cache_key, None)
        return None

    display = (hit.get('display_name') or q).split(',')[0].strip() or q
    place = ResolvedSearchPlace(lat, lng, display, 'geocode')
    _cache_set(cache_key, {
        'latitude': place.latitude,
        'longitude': place.longitude,
        'label': place.label,
        'source': place.source,
    })
    return place


def resolve_search_place(query: str) -> ResolvedSearchPlace | None:
    """
    If `query` looks like a UK place (postcode, town, city), return coordinates.

    Order: full postcode → outcode → venues in our DB → Nominatim (GB).
    """
    q = (query or '').strip()
    if not q:
        return None

    if _looks_like_full_postcode(q):
        place = _resolve_postcode(q)
        if place:
            return place

    if _looks_like_outcode(q):
        place = _resolve_outcode(q)
        if place:
            return place

    place = _resolve_from_venues(q)
    if place:
        return place

    return _resolve_via_nominatim(q)


def place_search_radius(request_get) -> int:
    """Radius for place-from-keyword search (same clamp as near-me)."""
    from courses.venue_list import clamp_near_radius

    return clamp_near_radius(request_get.get('radius') or DEFAULT_NEAR_RADIUS_MILES)
