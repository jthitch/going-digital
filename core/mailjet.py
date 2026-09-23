"""Minimal Mailjet HTTP client (contacts list sync + webhook token check)."""
from __future__ import annotations

import json
import logging
from base64 import b64encode
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

# Contact property names synced onto each list member (create via contactmetadata).
NEWSLETTER_CONTACT_PROPERTIES = (
    ('customer_id', 'str'),
    ('firstname', 'str'),
    ('lastname', 'str'),
    ('region_ids', 'str'),
    ('regions', 'str'),
    # datetime: send RFC3339 (YYYY-MM-DDTHH:MM:SSZ). Plain dates / Unix ints
    # are unreliable via managemanycontacts (epoch or dropped).
    ('created_at', 'datetime'),
    ('newsletter', 'bool'),
)


class MailjetError(Exception):
    """Mailjet API or configuration failure."""

    def __init__(self, message, *, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def mailjet_configured():
    return bool(
        (getattr(settings, 'MAILJET_API_KEY', '') or '').strip()
        and (getattr(settings, 'MAILJET_API_SECRET', '') or '').strip()
        and str(getattr(settings, 'MAILJET_NEWSLETTER_LIST_ID', '') or '').strip()
    )


def _api_base():
    base = (getattr(settings, 'MAILJET_API_BASE', '') or 'https://api.mailjet.com/v3').strip()
    return base.rstrip('/') + '/'


def _api_key():
    return (getattr(settings, 'MAILJET_API_KEY', '') or '').strip()


def _api_secret():
    return (getattr(settings, 'MAILJET_API_SECRET', '') or '').strip()


def newsletter_list_id():
    raw = str(getattr(settings, 'MAILJET_NEWSLETTER_LIST_ID', '') or '').strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise MailjetError('MAILJET_NEWSLETTER_LIST_ID must be an integer list ID.') from exc


def webhook_token():
    return (getattr(settings, 'MAILJET_WEBHOOK_TOKEN', '') or '').strip()


def verify_webhook_token(provided):
    """
    Optional shared-secret check for the unsub webhook.

    When MAILJET_WEBHOOK_TOKEN is blank, any caller is accepted (configure a
    token in production). When set, ``provided`` must match.
    """
    expected = webhook_token()
    if not expected:
        return True
    return bool(provided) and provided == expected


def _auth_header():
    token = b64encode(f'{_api_key()}:{_api_secret()}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def mailjet_request(method, path, *, params=None, json_body=None, timeout=60):
    """
    Perform a Mailjet API request.

    ``path`` is relative to the API base (e.g. ``REST/contact``).
    """
    if not _api_key() or not _api_secret():
        raise MailjetError('MAILJET_API_KEY / MAILJET_API_SECRET are not configured.')

    url = urljoin(_api_base(), path.lstrip('/'))
    if params:
        url = f'{url}?{urlencode(params, doseq=True)}'

    body = None
    headers = {
        'Authorization': _auth_header(),
        'Accept': 'application/json',
        'User-Agent': 'going-digital-mailjet/1.0',
    }
    if json_body is not None:
        body = json.dumps(json_body).encode('utf-8')
        headers['Content-Type'] = 'application/json'

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
            (payload or {}).get('ErrorMessage')
            or (payload or {}).get('ErrorInfo')
            or raw
            or f'Mailjet HTTP {exc.code}'
        )
        raise MailjetError(message, status_code=exc.code, payload=payload) from exc
    except URLError as exc:
        raise MailjetError(f'Mailjet connection failed: {exc.reason}') from exc


def ensure_contact_properties():
    """Create newsletter contact properties when missing; fix datatype when wrong."""
    existing = mailjet_request('GET', 'REST/contactmetadata')
    by_name = {}
    for item in (existing.get('Data') or []):
        name = (item.get('Name') or '').strip().lower()
        if name:
            by_name[name] = item

    for name, datatype in NEWSLETTER_CONTACT_PROPERTIES:
        current = by_name.get(name.lower())
        if current is None:
            mailjet_request(
                'POST',
                'REST/contactmetadata',
                json_body={
                    'Datatype': datatype,
                    'Name': name,
                    'NameSpace': 'static',
                },
            )
            logger.info('Created Mailjet contact property %s (%s)', name, datatype)
            continue

        current_type = (current.get('Datatype') or current.get('DataType') or '').strip().lower()
        prop_id = current.get('ID')
        if prop_id and current_type and current_type != datatype:
            mailjet_request(
                'PUT',
                f'REST/contactmetadata/{prop_id}',
                json_body={
                    'Datatype': datatype,
                    'Name': name,
                    'NameSpace': current.get('NameSpace') or 'static',
                },
            )
            logger.info(
                'Updated Mailjet contact property %s datatype %s → %s',
                name,
                current_type,
                datatype,
            )


def ensure_newsletter_list():
    """Verify the configured contact list exists."""
    list_id = newsletter_list_id()
    if list_id is None:
        raise MailjetError('MAILJET_NEWSLETTER_LIST_ID is not configured.')
    return mailjet_request('GET', f'REST/contactslist/{list_id}')


def manage_many_contacts(contacts: Iterable[dict[str, Any]], *, action='addnoforce'):
    """
    Upsert contacts onto the newsletter list.

    ``action``: addnoforce (default), addforce, remove, unsub.
    Each contact: Email, Name (optional), Properties (dict).
    """
    list_id = newsletter_list_id()
    if list_id is None:
        raise MailjetError('MAILJET_NEWSLETTER_LIST_ID is not configured.')

    payload_contacts = []
    for contact in contacts:
        email = (contact.get('Email') or contact.get('address') or '').strip()
        if not email:
            continue
        item = {
            'Email': email,
            'IsExcludedFromCampaigns': False,
        }
        name = contact.get('Name')
        if name is None:
            name = contact.get('name')
        if name is not None:
            item['Name'] = name
        props = contact.get('Properties')
        if props is None:
            props = contact.get('vars')
        if props is not None:
            item['Properties'] = props
        payload_contacts.append(item)

    if not payload_contacts:
        return {'Count': 0, 'Data': []}

    return mailjet_request(
        'POST',
        'REST/contact/managemanycontacts',
        json_body={
            'Contacts': payload_contacts,
            'ContactsLists': [
                {
                    'ListID': list_id,
                    'Action': action,
                },
            ],
        },
    )


def upsert_list_member(*, email, name='', properties=None):
    """Create/update one contact and add to the newsletter list."""
    return manage_many_contacts(
        [{
            'Email': email,
            'Name': name or '',
            'Properties': properties or {},
        }],
        action='addnoforce',
    )


def remove_list_member(email):
    """Remove a contact from the newsletter list (does not delete the contact)."""
    email = (email or '').strip()
    if not email:
        raise MailjetError('Member email is required.')
    return manage_many_contacts([{'Email': email}], action='remove')


def unsub_list_member(email):
    """Unsubscribe a contact from the newsletter list."""
    email = (email or '').strip()
    if not email:
        raise MailjetError('Member email is required.')
    return manage_many_contacts([{'Email': email}], action='unsub')


def iter_list_members(*, limit=1000):
    """Yield subscribed list-recipient rows for the newsletter list."""
    list_id = newsletter_list_id()
    if list_id is None:
        raise MailjetError('MAILJET_NEWSLETTER_LIST_ID is not configured.')

    offset = 0
    while True:
        result = mailjet_request(
            'GET',
            'REST/listrecipient',
            params={
                'ContactsList': list_id,
                'Limit': int(limit),
                'Offset': int(offset),
            },
        )
        items = result.get('Data') or []
        if not items:
            break
        for item in items:
            yield item
        if len(items) < limit:
            break
        offset += limit
