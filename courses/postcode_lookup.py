"""UK postcode lookup for venue addresses (admin)."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


POSTCODE_RE = re.compile(
    r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$',
    re.IGNORECASE,
)


def normalise_postcode(postcode):
    cleaned = re.sub(r'[^A-Za-z0-9]', '', (postcode or '').strip()).upper()
    if len(cleaned) < 5 or len(cleaned) > 7:
        raise ValueError('Enter a valid UK postcode.')
    formatted = f'{cleaned[:-3]} {cleaned[-3:]}'
    if not POSTCODE_RE.match(formatted):
        raise ValueError('Enter a valid UK postcode.')
    return formatted


def _http_get_json(url, *, headers=None, timeout=8):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _getaddress_lookup(postcode):
    api_key = (getattr(settings, 'GETADDRESS_API_KEY', None) or '').strip()
    if not api_key:
        return None

    encoded = urllib.parse.quote(postcode, safe='')
    url = f'https://api.getAddress.io/find/{encoded}?api-key={urllib.parse.quote(api_key, safe="")}&expand=true'
    try:
        data = _http_get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError('Postcode not found.') from exc
        if exc.code == 401:
            raise ValueError('Postcode lookup is not configured correctly.') from exc
        raise ValueError('Postcode lookup failed. Try again.') from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError('Postcode lookup is temporarily unavailable.') from exc

    addresses = []
    for entry in data.get('addresses') or []:
        if isinstance(entry, str):
            parts = [part.strip() for part in entry.split(',') if part.strip()]
            label = ', '.join(parts) if parts else entry.strip()
            addresses.append({
                'label': label,
                'address': '\n'.join(parts) if parts else entry.strip(),
                'location': parts[-2] if len(parts) >= 2 else (parts[0] if parts else ''),
                'county': parts[-1] if len(parts) >= 1 else '',
            })
        elif isinstance(entry, dict):
            lines = [
                entry.get('line_1') or '',
                entry.get('line_2') or '',
                entry.get('line_3') or '',
                entry.get('line_4') or '',
                entry.get('town_or_city') or '',
                entry.get('county') or '',
                entry.get('postcode') or postcode,
            ]
            parts = [line.strip() for line in lines if line and line.strip()]
            label = ', '.join(parts[:4]) if parts else postcode
            addresses.append({
                'label': label,
                'address': '\n'.join(parts),
                'location': entry.get('town_or_city') or entry.get('locality') or '',
                'county': entry.get('county') or entry.get('district') or '',
            })

    if not addresses:
        raise ValueError('No addresses found for this postcode.')

    return {
        'postcode': data.get('postcode') or postcode,
        'latitude': data.get('latitude'),
        'longitude': data.get('longitude'),
        'location': addresses[0].get('location') or '',
        'county': addresses[0].get('county') or '',
        'addresses': addresses,
        'source': 'getAddress.io',
    }


def _postcodes_io_lookup(postcode):
    encoded = urllib.parse.quote(postcode, safe='')
    url = f'https://api.postcodes.io/postcodes/{encoded}'
    try:
        data = _http_get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError('Postcode not found.') from exc
        raise ValueError('Postcode lookup failed. Try again.') from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError('Postcode lookup is temporarily unavailable.') from exc

    result = data.get('result') or {}
    if not result:
        raise ValueError('Postcode not found.')

    town = (
        result.get('admin_ward')
        or result.get('admin_district')
        or result.get('parish')
        or result.get('region')
        or ''
    )
    county = result.get('admin_county') or result.get('county') or ''
    parish = result.get('parish') or ''
    lines = [line for line in [parish, town, result.get('postcode') or postcode] if line]
    address = '\n'.join(dict.fromkeys(lines))

    return {
        'postcode': result.get('postcode') or postcode,
        'latitude': result.get('latitude'),
        'longitude': result.get('longitude'),
        'location': town,
        'county': county,
        'addresses': [{
            'label': address.replace('\n', ', '),
            'address': address,
            'location': town,
            'county': county,
        }],
        'source': 'postcodes.io',
        'message': (
            'Town and map coordinates were filled from the postcode. '
            'Add the street address if needed.'
        ),
    }


def lookup_uk_postcode(postcode):
    """Return address suggestions and map data for a UK postcode."""
    normalised = normalise_postcode(postcode)
    getaddress = _getaddress_lookup(normalised)
    if getaddress:
        return getaddress
    return _postcodes_io_lookup(normalised)
