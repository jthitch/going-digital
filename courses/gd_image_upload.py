"""Save uploaded files as legacy gd_image records."""
import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from courses.models import Image

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UNSUPPORTED_IMAGE_TYPE_MSG = 'Unsupported image type. Use JPG, PNG, GIF, or WebP.'
IMAGE_TOO_LARGE_MSG = 'Image must be 10 MB or smaller.'


def validate_image_upload(uploaded_file):
    """Raise ValidationError when an admin upload is missing or invalid."""
    if not uploaded_file:
        return

    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(UNSUPPORTED_IMAGE_TYPE_MSG)

    size = getattr(uploaded_file, 'size', None) or 0
    if size > MAX_UPLOAD_BYTES:
        raise ValidationError(IMAGE_TOO_LARGE_MSG)


def _gd_images_dir():
    directory = Path(settings.MEDIA_ROOT) / 'gd_images'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _image_dimensions(uploaded_file):
    try:
        from PIL import Image as PILImage
    except ImportError:
        return None, None
    uploaded_file.seek(0)
    try:
        with PILImage.open(uploaded_file) as img:
            return img.size
    except Exception:
        return None, None
    finally:
        uploaded_file.seek(0)


def create_gd_image_from_upload(uploaded_file, *, user_id=None, source_name='', description=''):
    """
    Write file under MEDIA_ROOT/gd_images/ and create a gd_image row.
    """
    if not uploaded_file:
        raise ValidationError('No file uploaded.')

    validate_image_upload(uploaded_file)
    ext = Path(uploaded_file.name).suffix.lower()
    size = getattr(uploaded_file, 'size', None) or 0

    unique = hashlib.sha256(f'{uuid.uuid4()}-{uploaded_file.name}'.encode()).hexdigest()[:32]
    file_name = f'im-ws-{unique}{ext}'
    dest_path = _gd_images_dir() / file_name

    width, height = _image_dimensions(uploaded_file)
    with dest_path.open('wb') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    if not size:
        size = dest_path.stat().st_size

    mime_type = (getattr(uploaded_file, 'content_type', None) or 'image/jpeg')[:20]
    now = timezone.now()

    return Image.objects.create(
        file_name=file_name,
        source_name=(source_name or uploaded_file.name or file_name)[:1000],
        description=(description or '')[:1000],
        mime_type=mime_type,
        file_size=size,
        width=width,
        height=height,
        active=1,
        user_id=user_id,
        createdby_id=user_id,
        updatedby_id=user_id,
        created_at=now,
        updated_at=now,
    )
