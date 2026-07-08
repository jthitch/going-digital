"""Parse contract territory KML and match polygons to gd_region rows."""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from django.conf import settings

KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}

# KML placemark labels that differ from gd_region.region_name / slug wording.
_KML_NAME_ALIASES = {
    'south east': 'south east',
    'south': 'south south coast',
    'north west midlands': 'north west north west midlands',
    'mid and north wales': 'north and mid wales',
    'south wales': 'west of england south wales',
}


def _normalize_region_label(value: str) -> str:
    if not value:
        return ''
    text = unicodedata.normalize('NFKC', value)
    text = text.replace('&', ' and ')
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


def _kml_file_path() -> Path:
    candidates = [
        Path(settings.BASE_DIR) / 'courses' / 'data' / 'contract_territory_march_2019.kml',
        Path(settings.BASE_DIR) / 'Contract Territory March 2019-5.kml',
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _parse_coordinates(text: str) -> list[list[float]]:
    """Return Leaflet lat/lng pairs from KML coordinate text (lng,lat,alt)."""
    points: list[list[float]] = []
    for chunk in (text or '').split():
        parts = chunk.split(',')
        if len(parts) < 2:
            continue
        try:
            lng = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        points.append([lat, lng])
    return points


def _placemark_polygon(placemark: ET.Element) -> list[list[float]] | None:
    polygon = placemark.find('.//kml:Polygon', KML_NS)
    if polygon is None:
        return None
    coords_el = polygon.find('.//kml:coordinates', KML_NS)
    if coords_el is None or not (coords_el.text or '').strip():
        return None
    ring = _parse_coordinates(coords_el.text)
    return ring or None


@lru_cache(maxsize=1)
def load_territory_polygons() -> list[dict]:
    """Load territory polygons from the contract KML file."""
    path = _kml_file_path()
    if not path.is_file():
        return []

    root = ET.parse(path).getroot()
    polygons: list[dict] = []
    for placemark in root.findall('.//kml:Placemark', KML_NS):
        name_el = placemark.find('kml:name', KML_NS)
        raw_name = (name_el.text or '').strip() if name_el is not None else ''
        raw_name = re.sub(r'\s+', ' ', raw_name)
        if not raw_name:
            continue
        ring = _placemark_polygon(placemark)
        if not ring:
            continue
        polygons.append({
            'kml_name': raw_name,
            'normalized_name': _normalize_region_label(raw_name),
            'coordinates': ring,
        })
    return polygons


def _region_lookup_keys(region) -> set[str]:
    keys = {
        _normalize_region_label(region.region_name or ''),
        _normalize_region_label((region.slug or '').replace('-', ' ')),
    }
    keys.discard('')
    return keys


def _match_polygon_to_region(polygon: dict, regions_by_key: dict[str, object]):
    normalized = polygon['normalized_name']
    alias = _KML_NAME_ALIASES.get(normalized, normalized)
    if alias in regions_by_key:
        return regions_by_key[alias]

    if normalized in regions_by_key:
        return regions_by_key[normalized]

    partial = [
        region
        for key, region in regions_by_key.items()
        if key and (normalized in key or key in normalized)
    ]
    if len(partial) == 1:
        return partial[0]
    return None


def _assigned_users(region) -> list[dict]:
    users = []
    for assignment in region.user_assignments.all():
        user = assignment.user
        if not user:
            continue
        label = user.get_full_name() or user.email
        users.append({
            'id': user.pk,
            'label': label,
            'email': user.email,
            'user_type': user.get_user_type_display(),
        })
    return users


def build_region_map_payload():
    """Regions, KML polygons, and assignments for the admin map view."""
    from courses.models import Region

    regions = list(
        Region.objects.prefetch_related('user_assignments__user').order_by('region_name'),
    )

    regions_by_key: dict[str, object] = {}
    for region in regions:
        for key in _region_lookup_keys(region):
            regions_by_key.setdefault(key, region)

    matched_region_ids: set[int] = set()
    features = []
    for polygon in load_territory_polygons():
        region = _match_polygon_to_region(polygon, regions_by_key)
        users = _assigned_users(region) if region else []
        if region:
            matched_region_ids.add(region.pk)
        features.append({
            'kml_name': polygon['kml_name'],
            'region_id': region.pk if region else None,
            'region_name': region.region_name if region else polygon['kml_name'],
            'slug': region.slug if region else '',
            'matched': region is not None,
            'active': bool(region.active) if region else True,
            'coordinates': polygon['coordinates'],
            'users': users,
        })

    unmapped_regions = [
        {
            'region_id': region.pk,
            'region_name': region.region_name,
            'slug': region.slug,
            'users': _assigned_users(region),
        }
        for region in regions
        if region.pk not in matched_region_ids
    ]

    return {
        'features': features,
        'unmapped_regions': unmapped_regions,
        'kml_path': str(_kml_file_path()),
    }
