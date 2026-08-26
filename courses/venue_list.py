"""Public /venues/ list: search, near-me distance, and region grouping."""
from __future__ import annotations

import math
from typing import Iterable

from django.db.models import Q, QuerySet

from courses.models import Region, Venue

OTHER_REGION_LABEL = 'Other regions'
DEFAULT_NEAR_RADIUS_MILES = 25
MIN_NEAR_RADIUS_MILES = 5
MAX_NEAR_RADIUS_MILES = 100
NEAR_RADIUS_STEP_MILES = 5
EARTH_RADIUS_MILES = 3958.7613


def public_venues_queryset() -> QuerySet[Venue]:
    """Active venues with a public slug."""
    return Venue.objects.filter(active=1).exclude(
        Q(slug='') | Q(slug__isnull=True),
    )


def filter_venues_by_search(queryset: QuerySet[Venue], search: str) -> QuerySet[Venue]:
    """
    Match venue name, town (location), address/postcode, or region name.
    """
    q = (search or '').strip()
    if not q:
        return queryset

    search_q = (
        Q(venue_name__icontains=q)
        | Q(location__icontains=q)
        | Q(venue_address__icontains=q)
    )
    # Postcodes are often typed with or without spaces.
    compact = ''.join(q.split())
    if compact and compact != q:
        search_q |= Q(venue_address__icontains=compact)

    region_ids = list(
        Region.objects.filter(region_name__icontains=q).values_list('id', flat=True)
    )
    if region_ids:
        search_q |= Q(region_id__in=region_ids)

    return queryset.filter(search_q)


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS84 points, in miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def parse_near_me(request_get) -> tuple[float, float, int] | tuple[None, None, int]:
    """
    Return (lat, lng, radius_miles) when near-me coords are present.
    Radius always defaults/clamps even when coords are missing.
    """
    radius = clamp_near_radius(request_get.get('radius'))
    try:
        lat = float(request_get.get('lat'))
        lng = float(request_get.get('lng'))
    except (TypeError, ValueError):
        return None, None, radius
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None, None, radius
    return lat, lng, radius


def clamp_near_radius(raw) -> int:
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return DEFAULT_NEAR_RADIUS_MILES
    # Snap to step, then clamp.
    stepped = int(round(value / NEAR_RADIUS_STEP_MILES) * NEAR_RADIUS_STEP_MILES)
    return max(MIN_NEAR_RADIUS_MILES, min(MAX_NEAR_RADIUS_MILES, stepped))


def filter_venues_near(
    venues: Iterable[Venue],
    *,
    lat: float,
    lng: float,
    radius_miles: int,
) -> list[Venue]:
    """
    Keep venues with coordinates within radius_miles of (lat, lng).
    Attaches distance_miles (float) and sorts nearest-first.
    """
    nearby: list[Venue] = []
    for venue in venues:
        if venue.latitude is None or venue.longitude is None:
            continue
        try:
            v_lat = float(venue.latitude)
            v_lng = float(venue.longitude)
        except (TypeError, ValueError):
            continue
        distance = haversine_miles(lat, lng, v_lat, v_lng)
        if distance <= radius_miles:
            venue.distance_miles = round(distance, 1)
            nearby.append(venue)
    nearby.sort(key=lambda v: (v.distance_miles, (v.venue_name or '').lower()))
    return nearby


def nearby_venue_ids(
    *,
    lat: float,
    lng: float,
    radius_miles: int,
    venue_ids: Iterable[int] | None = None,
) -> list[int]:
    """Venue primary keys within radius of (lat, lng)."""
    qs = Venue.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    if venue_ids is not None:
        ids = [pk for pk in venue_ids if pk]
        if not ids:
            return []
        qs = qs.filter(pk__in=ids)
    nearby = filter_venues_near(
        qs.only('id', 'latitude', 'longitude', 'venue_name'),
        lat=lat,
        lng=lng,
        radius_miles=radius_miles,
    )
    return [venue.pk for venue in nearby]


def apply_near_me_to_workshop_queryset(queryset, *, lat: float, lng: float, radius_miles: int):
    """Restrict workshops to venues within radius_miles of the user."""
    candidate_ids = list(
        queryset.exclude(venue_id__isnull=True).values_list('venue_id', flat=True).distinct()
    )
    near_ids = nearby_venue_ids(
        lat=lat,
        lng=lng,
        radius_miles=radius_miles,
        venue_ids=candidate_ids,
    )
    if not near_ids:
        return queryset.none()
    return queryset.filter(venue_id__in=near_ids)


def group_venues_by_region(venues):
    """
    Return [{'name', 'slug', 'venues'}, ...] sorted by region name.
    Venues without a region (or unknown region id) go under OTHER_REGION_LABEL last.
    slug is set when the region has a public landing slug (for SEO links).
    """
    venues = list(venues)
    region_ids = {v.region_id for v in venues if v.region_id}
    meta = {
        r.id: {
            'name': (r.region_name or '').strip() or f'Region #{r.id}',
            'slug': (r.slug or '').strip() or None,
        }
        for r in Region.objects.filter(pk__in=region_ids)
    }

    grouped: dict[str, dict] = {}
    for venue in venues:
        if venue.region_id and venue.region_id in meta:
            info = meta[venue.region_id]
            label = info['name']
            slug = info['slug']
        else:
            label = OTHER_REGION_LABEL
            slug = None
        bucket = grouped.setdefault(label, {'name': label, 'slug': slug, 'venues': []})
        bucket['venues'].append(venue)

    for bucket in grouped.values():
        bucket['venues'].sort(key=lambda v: (v.venue_name or '').lower())

    return [
        grouped[name]
        for name in sorted(
            grouped.keys(),
            key=lambda n: (n == OTHER_REGION_LABEL, n.lower()),
        )
    ]


def format_distance_miles(miles: float) -> str:
    if miles < 10:
        return f'{miles:.1f} miles'
    return f'{int(round(miles))} miles'
