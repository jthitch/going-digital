"""Legacy venue documents (gd_document) for admin preview."""
from pathlib import Path

from django.conf import settings
from django.utils.html import escape, format_html, format_html_join


def document_media_subdir():
    return getattr(settings, 'GD_DOCUMENT_MEDIA_SUBDIR', 'gd_documents')


def document_file_path(document):
    if not document or not document.document_filename:
        return None
    filename = document.document_filename.lstrip('/')
    return Path(settings.MEDIA_ROOT) / document_media_subdir() / filename


def document_exists_on_disk(document):
    path = document_file_path(document)
    return path is not None and path.is_file()


def venue_legacy_document(venue):
    if not venue:
        return None
    return venue.get_document()


def venue_document_email_enabled(venue_id):
    if not venue_id:
        return False
    from courses.models import VenueDocumentEmailSetting

    try:
        return VenueDocumentEmailSetting.objects.get(venue_id=venue_id).include_in_booking_email
    except VenueDocumentEmailSetting.DoesNotExist:
        return True


def set_venue_document_email_enabled(venue_id, enabled):
    if not venue_id:
        return
    from courses.models import VenueDocumentEmailSetting

    VenueDocumentEmailSetting.objects.update_or_create(
        venue_id=venue_id,
        defaults={'include_in_booking_email': bool(enabled)},
    )


def booking_email_venue_document_attachment(workshop):
    """Return (filename, bytes, mimetype) for booking email, or None."""
    if not workshop or not workshop.venue_id:
        return None
    venue = workshop.venue
    if not venue or not venue.document_id:
        return None
    if not venue_document_email_enabled(venue.id):
        return None

    document = venue_legacy_document(venue)
    if not document:
        return None

    path = document_file_path(document)
    if not path or not path.is_file():
        return None

    filename = (document.source_filename or document.document_filename or 'joining-instructions').strip()
    if not filename:
        filename = 'joining-instructions'
    mimetype = (document.mimetype or '').strip() or 'application/octet-stream'
    return filename, path.read_bytes(), mimetype


def render_venue_document_admin_preview(venue):
    """Read-only admin HTML for a venue's legacy document."""
    document = venue_legacy_document(venue)
    if not document:
        return format_html('<p class="gd-venue-document__empty">No venue document linked.</p>')

    url = document.url
    title = escape(document.title or 'Venue document')
    description = (document.description or '').strip()
    source = escape(document.source_filename or '')
    stored = escape(document.document_filename or '')
    mimetype = (document.mimetype or '').strip().lower()
    exists = document_exists_on_disk(document)

    status = ''
    if not exists:
        status = format_html(
            '<p class="gd-venue-document__warning">'
            'File not found on disk: <code>media/{}/{}</code>'
            '</p>',
            document_media_subdir(),
            stored,
        )

    meta_parts = []
    if source:
        meta_parts.append(format_html('Original file: <span>{}</span>', source))
    if stored:
        meta_parts.append(format_html('Stored as: <code>{}</code>', stored))
    if document.filesize:
        meta_parts.append(format_html('Size: {} KB', round(document.filesize / 1024)))

    meta = (
        format_html('<p class="gd-venue-document__meta">{}</p>', format_html_join(' · ', '{}', ((p,) for p in meta_parts)))
        if meta_parts else ''
    )

    actions = ''
    if url and exists:
        actions = format_html(
            '<p class="gd-venue-document__actions">'
            '<a href="{}" target="_blank" rel="noopener noreferrer">Open in new tab</a>'
            '</p>',
            url,
        )

    preview = ''
    if url and exists:
        if mimetype == 'application/pdf' or (document.document_filename or '').lower().endswith('.pdf'):
            preview = format_html(
                '<iframe class="gd-venue-document__preview" src="{}" title="{}"></iframe>',
                url,
                title,
            )
        elif mimetype.startswith('image/'):
            preview = format_html(
                '<img class="gd-venue-document__preview gd-venue-document__preview--image" src="{}" alt="{}">',
                url,
                title,
            )

    desc_block = (
        format_html('<p class="gd-venue-document__description">{}</p>', escape(description))
        if description else ''
    )

    return format_html(
        '<div class="gd-venue-document">'
        '<h3 class="gd-venue-document__title">{}</h3>'
        '{}'
        '{}'
        '{}'
        '{}'
        '{}'
        '</div>',
        title,
        status,
        desc_block,
        meta,
        actions,
        preview,
    )
