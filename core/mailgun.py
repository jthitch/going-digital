"""Minimal Mailgun HTTP client (mailing lists + webhook signatures)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from base64 import b64encode
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class MailgunError(Exception):
    """Mailgun API or configuration failure."""

    def __init__(self, message, *, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def mailgun_configured():
    return bool(
        (getattr(settings, 'MAILGUN_API_KEY', '') or '').strip()
        and (getattr(settings, 'MAILGUN_NEWSLETTER_LIST', '') or '').strip()
    )


def _api_base():
    base = (getattr(settings, 'MAILGUN_API_BASE', '') or 'https://api.mailgun.net/v3').strip()
    return base.rstrip('/') + '/'


def _api_key():
    return (getattr(settings, 'MAILGUN_API_KEY', '') or '').strip()


def _newsletter_list_address():
    return (getattr(settings, 'MAILGUN_NEWSLETTER_LIST', '') or '').strip()


def _webhook_signing_key():
    key = (getattr(settings, 'MAILGUN_WEBHOOK_SIGNING_KEY', '') or '').strip()
    return key or _api_key()


def _auth_header():
    token = b64encode(f'api:{_api_key()}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def mailgun_request(method, path, *, data=None, timeout=30):
    """
    Perform a Mailgun API request.

    ``path`` is relative to the API base (e.g. ``lists/newsletter@mg.example.com``).
    ``data`` is sent as form-urlencoded body when present.
    """
    if not _api_key():
        raise MailgunError('MAILGUN_API_KEY is not configured.')

    url = urljoin(_api_base(), path.lstrip('/'))
    body = None
    headers = {
        'Authorization': _auth_header(),
        'Accept': 'application/json',
        'User-Agent': 'going-digital-mailgun/1.0',
    }
    if data is not None:
        body = urlencode(data, doseq=True).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'

    request = Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode('utf-8') or '{}'
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {'raw': raw}
    except HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        payload = None
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = {'raw': raw}
        message = (
            (payload or {}).get('message')
            or raw
            or f'Mailgun HTTP {exc.code}'
        )
        raise MailgunError(message, status_code=exc.code, payload=payload) from exc
    except URLError as exc:
        raise MailgunError(f'Mailgun connection failed: {exc.reason}') from exc


def verify_webhook_signature(timestamp, token, signature):
    """
    Verify a Mailgun webhook signature.

    Uses MAILGUN_WEBHOOK_SIGNING_KEY when set, otherwise MAILGUN_API_KEY.
    """
    signing_key = _webhook_signing_key()
    if not signing_key or not timestamp or not token or not signature:
        return False
    digest = hmac.new(
        key=signing_key.encode('utf-8'),
        msg=f'{timestamp}{token}'.encode('utf-8'),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, str(signature))


def ensure_newsletter_list():
    """Create the newsletter mailing list when it does not already exist."""
    address = _newsletter_list_address()
    if not address:
        raise MailgunError('MAILGUN_NEWSLETTER_LIST is not configured.')
    encoded = quote(address, safe='')
    try:
        return mailgun_request('GET', f'lists/{encoded}')
    except MailgunError as exc:
        if exc.status_code != 404:
            raise
    description = (
        getattr(settings, 'MAILGUN_NEWSLETTER_LIST_DESCRIPTION', '')
        or 'Going Digital newsletter subscribers'
    ).strip()
    return mailgun_request(
        'POST',
        'lists',
        data={
            'address': address,
            'name': 'Going Digital Newsletter',
            'description': description,
            'access_level': 'readonly',
        },
    )


def upsert_list_member(*, email, name='', vars_dict=None, subscribed=True):
    """Create or update a single mailing-list member."""
    address = _newsletter_list_address()
    if not address:
        raise MailgunError('MAILGUN_NEWSLETTER_LIST is not configured.')
    email = (email or '').strip()
    if not email:
        raise MailgunError('Member email is required.')

    data = {
        'address': email,
        'name': name or '',
        'subscribed': 'yes' if subscribed else 'no',
        'upsert': 'yes',
    }
    if vars_dict is not None:
        data['vars'] = json.dumps(vars_dict, separators=(',', ':'))

    encoded_list = quote(address, safe='')
    return mailgun_request('POST', f'lists/{encoded_list}/members', data=data)


def upsert_list_members_bulk(members: Iterable[dict[str, Any]]):
    """
    Upsert up to 1000 members in one request.

    Each member dict: address, name (optional), vars (dict), subscribed (bool).
    """
    address = _newsletter_list_address()
    if not address:
        raise MailgunError('MAILGUN_NEWSLETTER_LIST is not configured.')

    payload = []
    for member in members:
        email = (member.get('address') or '').strip()
        if not email:
            continue
        item = {
            'address': email,
            'name': member.get('name') or '',
            'subscribed': bool(member.get('subscribed', True)),
        }
        vars_dict = member.get('vars')
        if vars_dict is not None:
            item['vars'] = vars_dict
        payload.append(item)

    if not payload:
        return {'list': {'_total_count': 0}}

    encoded_list = quote(address, safe='')
    return mailgun_request(
        'POST',
        f'lists/{encoded_list}/members.json',
        data={
            'members': json.dumps(payload, separators=(',', ':')),
            'upsert': 'yes',
        },
    )


def delete_list_member(email):
    """Remove a member from the newsletter list."""
    address = _newsletter_list_address()
    if not address:
        raise MailgunError('MAILGUN_NEWSLETTER_LIST is not configured.')
    email = (email or '').strip()
    if not email:
        raise MailgunError('Member email is required.')
    encoded_list = quote(address, safe='')
    encoded_member = quote(email, safe='')
    return mailgun_request('DELETE', f'lists/{encoded_list}/members/{encoded_member}')


def iter_list_members(*, limit=100):
    """Yield mailing-list member dicts (paginated)."""
    address = _newsletter_list_address()
    if not address:
        raise MailgunError('MAILGUN_NEWSLETTER_LIST is not configured.')
    encoded_list = quote(address, safe='')
    page_url = f'lists/{encoded_list}/members/pages?limit={int(limit)}'
    seen_pages = set()
    while page_url:
        if page_url in seen_pages:
            break
        seen_pages.add(page_url)
        # Absolute next URLs from Mailgun need a full request path relative to host.
        if page_url.startswith('http://') or page_url.startswith('https://'):
            # Convert absolute URL to path+query under /v3/
            from urllib.parse import urlparse

            parsed = urlparse(page_url)
            path = parsed.path or ''
            marker = '/v3/'
            if marker in path:
                path = path.split(marker, 1)[1]
            page_path = path.lstrip('/')
            if parsed.query:
                page_path = f'{page_path}?{parsed.query}'
            result = mailgun_request('GET', page_path)
        else:
            result = mailgun_request('GET', page_url)

        items = result.get('items') or []
        for item in items:
            yield item

        paging = result.get('paging') or {}
        next_url = paging.get('next') or ''
        # Stop when Mailgun loops or returns empty.
        if not items or not next_url or next_url == page_url:
            break
        page_url = next_url
