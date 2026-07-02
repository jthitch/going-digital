"""Save uploaded files as legacy gd_image records."""
import hashlib
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils import timezone

from courses.image_optimize import (
    optimize_image_file,
    upload_help_text,
    validate_image_upload,
)
from courses.models import Image

__all__ = [
    'validate_image_upload',
    'create_gd_image_from_upload',
    'upload_help_text',
]


def _gd_images_dir():
    from django.conf import settings

    directory = Path(settings.MEDIA_ROOT) / 'gd_images'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_gd_image_from_upload(uploaded_file, *, user_id=None, source_name='', description=''):
    """
    Write an optimized file under MEDIA_ROOT/gd_images/ and create a gd_image row.
    """
    if not uploaded_file:
        raise ValidationError('No file uploaded.')

    optimized = optimize_image_file(uploaded_file)
    unique = hashlib.sha256(f'{uuid.uuid4()}-{uploaded_file.name}'.encode()).hexdigest()[:32]
    file_name = f'im-ws-{unique}{optimized.extension}'
    dest_path = _gd_images_dir() / file_name
    dest_path.write_bytes(optimized.data)

    now = timezone.now()
    return Image.objects.create(
        file_name=file_name,
        source_name=(source_name or uploaded_file.name or file_name)[:1000],
        description=(description or '')[:1000],
        mime_type=optimized.mime_type[:20],
        file_size=len(optimized.data),
        width=optimized.width,
        height=optimized.height,
        active=1,
        user_id=user_id,
        createdby_id=user_id,
        updatedby_id=user_id,
        created_at=now,
        updated_at=now,
    )
