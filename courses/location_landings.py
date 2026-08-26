"""Indexable city/region landing pages built from existing Venue + Region data."""
from __future__ import annotations

import re
from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import Exists, OuterRef, QuerySet
from django.urls import reverse
from django.utils.text import slugify

from courses.models import Region, Venue
from courses.venue_list import public_venues_queryset
from courses.venue_schema import extract_uk_postcode
from courses.workshop_querysets import bookable_workshop_ordering, bookable_workshops_queryset

# Short TTL: landings follow workshop/venue changes without requiring explicit invalidation.
_CACHE_TTL_SECONDS = 60 * 15
_CACHE_CITIES = 'location_landings:cities:v1'
_CACHE_REGION_SLUGS = 'location_landings:region_slugs:v1'

# Address parts that usually are streets, not towns.
_STREET_SUFFIX_RE = re.compile(
    r'\b(road|street|st|lane|avenue|ave|drive|dr|way|close|court|crescent|place|row|grove|hill|gardens?)\.?$',
    re.IGNORECASE,
)

# Common UK county / ceremonial labels to skip when picking a town from an address.
_COUNTY_HINTS = frozenset({
    'bedfordshire', 'berkshire', 'buckinghamshire', 'bucks', 'cambridgeshire',
    'cheshire', 'cornwall', 'cumbria', 'derbyshire', 'devon', 'dorset', 'durham',
    'east sussex', 'east yorkshire', 'essex', 'gloucestershire',
    'greater london', 'greater manchester', 'hampshire', 'herefordshire', 'hertfordshire',
    'isle of wight', 'kent', 'lancashire', 'leicestershire', 'lincolnshire', 'merseyside',
    'middlesex', 'norfolk', 'north yorkshire', 'northamptonshire', 'northumberland',
    'nottinghamshire', 'oxfordshire', 'rutland', 'shropshire', 'somerset', 'south yorkshire',
    'staffordshire', 'suffolk', 'surrey', 'tyne and wear', 'warwickshire', 'west midlands',
    'west sussex', 'west yorkshire', 'wiltshire', 'worcestershire',
    'clwyd', 'dyfed', 'gwynedd', 'powys', 'gwent', 'mid glamorgan', 'south glamorgan',
    'west glamorgan', 'anglesey', 'ceredigion', 'conwy', 'denbighshire', 'flintshire',
    'monmouthshire', 'pembrokeshire', 'vale of glamorgan',
    'aberdeenshire', 'angus', 'argyll', 'ayrshire', 'banffshire', 'berwickshire',
    'caithness', 'dumfries', 'dunbartonshire', 'east lothian', 'fife', 'inverness-shire',
    'kincardineshire', 'lanarkshire', 'midlothian', 'moray', 'perthshire', 'renfrewshire',
    'roxburghshire', 'scottish borders', 'stirlingshire', 'west lothian',
    'antrim', 'armagh', 'down', 'fermanagh', 'londonderry', 'tyrone',
    'county durham', 'england', 'scotland', 'wales', 'northern ireland', 'united kingdom', 'uk',
})


@dataclass(frozen=True)
class CityLanding:
    """A city/town landing derived from venue location or address locality."""
    slug: str
    name: str
    venue_ids: tuple[int, ...]


def bookable_venue_exists_q():
    """Exists() filter: venue has at least one bookable workshop."""
    return Exists(bookable_workshops_queryset().filter(venue_id=OuterRef('pk')))


def venues_with_bookable_workshops() -> QuerySet[Venue]:
    return public_venues_queryset().filter(bookable_venue_exists_q())


def indexable_regions() -> QuerySet[Region]:
    """
    Active regions with a public slug that have ≥1 public venue with a bookable workshop.
    Uses a distinct region_id list rather than nested Exists for clearer/faster SQL.
    """
    region_ids = (
        venues_with_bookable_workshops()
        .exclude(region_id__isnull=True)
        .values_list('region_id', flat=True)
        .distinct()
    )
    return (
        Region.objects.filter(active=1, pk__in=region_ids)
        .exclude(slug='')
        .exclude(slug__isnull=True)
        .order_by('region_name')
    )


def indexable_region_slugs() -> frozenset[str]:
    """Cached set of region slugs that have public landings (for venue-list links)."""
    cached = cache.get(_CACHE_REGION_SLUGS)
    if cached is not None:
        return cached
    slugs = frozenset(indexable_regions().values_list('slug', flat=True))
    cache.set(_CACHE_REGION_SLUGS, slugs, _CACHE_TTL_SECONDS)
    return slugs


def get_indexable_region(slug: str) -> Region | None:
    """Resolve one region landing without scanning every indexable region."""
    slug = (slug or '').strip()
    if not slug:
        return None
    region = (
        Region.objects.filter(active=1, slug=slug)
        .exclude(slug='')
        .first()
    )
    if region is None:
        return None
    if not venues_with_bookable_workshops().filter(region_id=region.pk).exists():
        return None
    return region


def region_landing_venues(region: Region) -> QuerySet[Venue]:
    return (
        venues_with_bookable_workshops()
        .filter(region_id=region.pk)
        .prefetch_related('media')
        .order_by('venue_name')
    )


def city_slug_for_location(location: str | None) -> str:
    return slugify((location or '').strip())


def _looks_like_street(part: str) -> bool:
    return bool(_STREET_SUFFIX_RE.search(part.strip()))


def _looks_like_county(part: str) -> bool:
    lower = part.strip().lower().rstrip('.')
    return lower in _COUNTY_HINTS


def _is_usable_locality(name: str) -> bool:
    """Drop instructional / brand / overly long address fragments."""
    cleaned = (name or '').strip()
    if len(cleaned) < 2 or len(cleaned) > 40:
        return False
    lower = cleaned.lower()
    if lower.startswith('going digital'):
        return False
    if 'joining instruction' in lower or 'please see' in lower:
        return False
    if '(' in cleaned or ')' in cleaned:
        return False
    return True


def infer_venue_locality(venue) -> str:
    """
    Best town/city label for a venue.
    Prefer Venue.location; otherwise parse a locality from venue_address.
    """
    explicit = (getattr(venue, 'location', None) or '').strip()
    if explicit and _is_usable_locality(explicit):
        return explicit

    address = (getattr(venue, 'venue_address', None) or '').strip()
    if not address:
        return ''

    text = address
    postcode = extract_uk_postcode(address)
    if postcode:
        text = re.sub(re.escape(postcode), '', text, flags=re.IGNORECASE)

    parts = [p.strip(' .,') for p in re.split(r'[,\n;/]+', text) if p.strip(' .,')]
    if not parts:
        return ''

    for part in reversed(parts):
        if not _is_usable_locality(part):
            continue
        if _looks_like_street(part) or _looks_like_county(part):
            continue
        if not re.search(r'[A-Za-z]{2,}', part):
            continue
        return part

    for part in reversed(parts):
        if (
            _is_usable_locality(part)
            and not _looks_like_street(part)
            and re.search(r'[A-Za-z]{2,}', part)
        ):
            return part
    return ''


def _canonical_city_name(location_values: list[str]) -> str:
    """Prefer the most common original spelling; ties broken alphabetically."""
    counts: dict[str, int] = {}
    for value in location_values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.keys(), key=lambda v: (-counts[v], v.lower()))[0]


def build_city_landings(venues=None) -> list[CityLanding]:
    """
    Group venues by inferred locality slug into CityLanding records.
    If venues is None, load venues that have bookable workshops.
    """
    if venues is None:
        venues = list(
            venues_with_bookable_workshops().only(
                'id', 'location', 'venue_address', 'venue_name',
            )
        )

    by_slug: dict[str, dict] = {}
    for venue in venues:
        name = infer_venue_locality(venue)
        if not name:
            continue
        slug = city_slug_for_location(name)
        if not slug:
            continue
        bucket = by_slug.setdefault(slug, {'names': [], 'ids': []})
        bucket['names'].append(name)
        bucket['ids'].append(venue.pk)

    cities = [
        CityLanding(
            slug=slug,
            name=_canonical_city_name(data['names']),
            venue_ids=tuple(sorted(set(data['ids']))),
        )
        for slug, data in by_slug.items()
        if data['ids']
    ]
    cities.sort(key=lambda c: c.name.lower())
    return cities


def indexable_cities() -> list[CityLanding]:
    cached = cache.get(_CACHE_CITIES)
    if cached is not None:
        return cached
    cities = build_city_landings()
    cache.set(_CACHE_CITIES, cities, _CACHE_TTL_SECONDS)
    return cities


def get_indexable_city(slug: str) -> CityLanding | None:
    slug = (slug or '').strip().lower()
    if not slug:
        return None
    for city in indexable_cities():
        if city.slug == slug:
            return city
    return None


def city_landing_venues(city: CityLanding) -> QuerySet[Venue]:
    """Venues for a city landing; re-check bookable so stale cache cannot over-include."""
    return (
        venues_with_bookable_workshops()
        .filter(pk__in=city.venue_ids)
        .prefetch_related('media')
        .order_by('venue_name')
    )


def landing_workshops_for_venues(venue_ids) -> list:
    if not venue_ids:
        return []
    return list(
        bookable_workshops_queryset()
        .filter(venue_id__in=venue_ids)
        .select_related('course', 'venue')
        .order_by(*bookable_workshop_ordering())[:60]
    )


def region_landing_url(region: Region) -> str:
    return reverse('courses:region_landing', kwargs={'slug': region.slug})


def city_landing_url(city: CityLanding | str) -> str:
    slug = city.slug if isinstance(city, CityLanding) else city
    return reverse('courses:city_landing', kwargs={'slug': slug})


def clear_location_landing_cache() -> None:
    """Test helper / manual refresh."""
    cache.delete(_CACHE_CITIES)
    cache.delete(_CACHE_REGION_SLUGS)
