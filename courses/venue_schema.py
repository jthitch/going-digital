"""Build Place / PostalAddress structured data from Venue fields."""
from __future__ import annotations

import re
from functools import lru_cache

from courses.postcode_lookup import normalise_postcode

# UK postcode appearing anywhere in free-text address (e.g. end of venue_address).
_POSTCODE_IN_TEXT_RE = re.compile(
    r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b',
    re.IGNORECASE,
)


def extract_uk_postcode(text: str | None) -> str:
    """Return a normalised UK postcode found in text, or ''."""
    if not text:
        return ''
    match = _POSTCODE_IN_TEXT_RE.search(text)
    if not match:
        return ''
    try:
        return normalise_postcode(match.group(1))
    except ValueError:
        return ''


@lru_cache(maxsize=1)
def _county_name_by_id() -> dict[int, str]:
    """Load county labels once per process to avoid N+1 on schema graphs."""
    from courses.models import County
    return {
        pk: (name or '').strip()
        for pk, name in County.objects.values_list('id', 'county')
    }


def venue_county_label(venue) -> str:
    county_id = getattr(venue, 'county_id', None)
    if not county_id:
        return ''
    name = _county_name_by_id().get(county_id, '')
    if not name or name.startswith('County #'):
        return ''
    return name


def venue_postal_address(venue) -> dict:
    """
    schema.org PostalAddress for a Venue.

    gd_venue has no dedicated postcode / region / locality columns; we derive:
    - addressLocality from venue.location
    - addressRegion from linked county name
    - postalCode by parsing venue_address
    Empty properties are omitted (preferable for Google over empty strings).
    """
    address = {'@type': 'PostalAddress', 'addressCountry': 'GB'}

    street = (getattr(venue, 'venue_address', None) or '').strip()
    if street:
        address['streetAddress'] = street

    locality = (getattr(venue, 'location', None) or '').strip()
    if locality:
        address['addressLocality'] = locality

    county_label = venue_county_label(venue)
    if county_label:
        address['addressRegion'] = county_label

    postcode = extract_uk_postcode(street)
    if postcode:
        address['postalCode'] = postcode

    return address


def venue_place_schema(venue, *, name=None, description=None, url=None) -> dict:
    """schema.org Place for a Venue, including address and optional geo."""
    place = {
        '@type': 'Place',
        'name': name if name is not None else (venue.venue_name if venue else 'TBC'),
        'address': venue_postal_address(venue) if venue else {
            '@type': 'PostalAddress',
            'addressCountry': 'GB',
        },
    }
    if description:
        place['description'] = description
    if url:
        place['url'] = url
    if venue and venue.latitude and venue.longitude:
        place['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': float(venue.latitude),
            'longitude': float(venue.longitude),
        }
    return place
