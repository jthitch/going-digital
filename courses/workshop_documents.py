"""Workshop-specific documents: upload, duplicate, and booking email attachments."""
import mimetypes
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from courses.models import WorkshopDocument

MAX_WORKSHOP_DOCUMENT_BYTES = 15 * 1024 * 1024
ALLOWED_WORKSHOP_DOCUMENT_EXTENSIONS = {
    '.pdf',
    '.doc',
    '.docx',
    '.txt',
    '.png',
    '.jpg',
    '.jpeg',
    '.webp',
}


def validate_workshop_document_upload(uploaded_file):
    if not uploaded_file:
        raise ValidationError('Choose a file to upload.')
    size = getattr(uploaded_file, 'size', None) or 0
    if size > MAX_WORKSHOP_DOCUMENT_BYTES:
        raise ValidationError('File is too large (maximum 15 MB).')
    extension = Path(getattr(uploaded_file, 'name', '') or '').suffix.lower()
    if extension and extension not in ALLOWED_WORKSHOP_DOCUMENT_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_WORKSHOP_DOCUMENT_EXTENSIONS))
        raise ValidationError(f'Unsupported file type. Allowed: {allowed}')


def copy_workshop_documents(source_workshop_id, target_workshop_id, *, user_id=None):
    """Copy workshop documents when duplicating a workshop."""
    if not source_workshop_id or not target_workshop_id:
        return 0
    if int(source_workshop_id) == int(target_workshop_id):
        return 0

    source_docs = list(
        WorkshopDocument.objects.filter(workshop_id=source_workshop_id).order_by(
            'display_order',
            'id',
        ),
    )
    if not source_docs:
        return 0

    created = 0
    for source in source_docs:
        if not source.file:
            continue
        try:
            content = source.file.read()
        except OSError:
            continue
        filename = source.original_filename or Path(source.file.name).name
        new_doc = WorkshopDocument(
            workshop_id=target_workshop_id,
            title=source.title,
            description=source.description,
            original_filename=filename,
            mimetype=source.mimetype,
            file_size=len(content),
            include_in_booking_email=source.include_in_booking_email,
            display_order=source.display_order,
            createdby_id=user_id,
        )
        new_doc.file.save(filename, ContentFile(content), save=True)
        created += 1
    return created


def workshop_document_attachment(document):
    """Return (filename, bytes, mimetype) for a workshop document, or None."""
    if not document or not document.file:
        return None
    try:
        if not document.file.storage.exists(document.file.name):
            return None
        content = document.file.read()
    except OSError:
        return None

    filename = (document.original_filename or Path(document.file.name).name or 'document').strip()
    mimetype = (document.mimetype or '').strip()
    if not mimetype:
        guessed, _encoding = mimetypes.guess_type(filename)
        mimetype = guessed or 'application/octet-stream'
    return filename, content, mimetype


def booking_email_workshop_document_attachments(workshop):
    """Workshop documents flagged for booking confirmation emails."""
    if not workshop or not workshop.pk:
        return []

    attachments = []
    for document in WorkshopDocument.objects.filter(
        workshop_id=workshop.pk,
        include_in_booking_email=True,
    ).order_by('display_order', 'id'):
        attachment = workshop_document_attachment(document)
        if attachment:
            attachments.append(attachment)
    return attachments
