"""Compress and resize admin image uploads for web delivery (Pillow)."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
UNSUPPORTED_IMAGE_TYPE_MSG = 'Unsupported image type. Use JPG, PNG, GIF, or WebP.'


def _setting(name, default):
    return getattr(settings, name, default)


def max_upload_bytes():
    return int(_setting('GD_IMAGE_MAX_UPLOAD_BYTES', 10 * 1024 * 1024))


def max_stored_bytes():
    return int(_setting('GD_IMAGE_MAX_STORED_BYTES', 750 * 1024))


def max_image_dimension():
    return int(_setting('GD_IMAGE_MAX_DIMENSION', 1920))


def jpeg_quality():
    return int(_setting('GD_IMAGE_JPEG_QUALITY', 85))


def upload_too_large_message():
    mb = max_upload_bytes() // (1024 * 1024)
    return f'Image must be {mb} MB or smaller before compression.'


def upload_help_text():
    mb = max_upload_bytes() // (1024 * 1024)
    return (
        f'Optional. JPG, PNG, GIF, or WebP up to {mb} MB — '
        'automatically resized and compressed for the website.'
    )


@dataclass(frozen=True)
class OptimizedImage:
    data: bytes
    extension: str
    mime_type: str
    width: int
    height: int


def validate_image_upload(uploaded_file):
    """Raise ValidationError when an admin upload is missing or invalid."""
    if not uploaded_file:
        return

    ext = Path(getattr(uploaded_file, 'name', '') or '').suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(UNSUPPORTED_IMAGE_TYPE_MSG)

    size = getattr(uploaded_file, 'size', None) or 0
    if size > max_upload_bytes():
        raise ValidationError(upload_too_large_message())


def _jpeg_bytes(img, *, quality):
    from PIL import Image

    if img.mode != 'RGB':
        img = img.convert('RGB')
    buffer = io.BytesIO()
    img.save(
        buffer,
        format='JPEG',
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return buffer.getvalue()


def _png_bytes(img):
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def _webp_bytes(img, *, quality):
    buffer = io.BytesIO()
    img.save(buffer, format='WEBP', quality=quality, method=6)
    return buffer.getvalue()


def _has_alpha(img):
    if img.mode in ('RGBA', 'LA'):
        return True
    if img.mode == 'P':
        return 'transparency' in img.info
    return False


def optimize_image_file(uploaded_file) -> OptimizedImage:
    """
    Resize and compress an uploaded image for web use.
    Photos become JPEG; images with transparency stay PNG (or WebP when uploaded as WebP).
    """
    validate_image_upload(uploaded_file)

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValidationError('Image processing is unavailable (Pillow not installed).') from exc

    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as img:
            img.load()
            if getattr(img, 'is_animated', False):
                raise ValidationError(
                    'Animated GIFs are not supported. Upload a JPG or PNG instead.'
                )

            img = ImageOps.exif_transpose(img)
            max_dim = max_image_dimension()
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            width, height = img.size

            original_ext = Path(getattr(uploaded_file, 'name', '') or '').suffix.lower()
            target_max = max_stored_bytes()
            has_alpha = _has_alpha(img)

            if original_ext == '.webp' and not has_alpha:
                quality = jpeg_quality()
                data = _webp_bytes(img, quality=quality)
                while len(data) > target_max and quality > 55:
                    quality -= 5
                    data = _webp_bytes(img, quality=quality)
                return OptimizedImage(data, '.webp', 'image/webp', width, height)

            if has_alpha:
                if img.mode not in ('RGBA', 'LA'):
                    img = img.convert('RGBA')
                data = _png_bytes(img)
                if len(data) > target_max * 2:
                    raise ValidationError(
                        'This PNG is too large even after resizing. '
                        'Try a smaller source image or export as JPG if transparency is not needed.'
                    )
                return OptimizedImage(data, '.png', 'image/png', width, height)

            quality = jpeg_quality()
            data = _jpeg_bytes(img, quality=quality)
            while len(data) > target_max and quality > 55:
                quality -= 5
                data = _jpeg_bytes(img, quality=quality)

            return OptimizedImage(data, '.jpg', 'image/jpeg', width, height)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError('Could not process this image. Try a different JPG or PNG file.') from exc
    finally:
        uploaded_file.seek(0)


def optimize_django_field_file(field_file):
    """Replace a Django FieldFile with an optimized version (new uploads only)."""
    if not field_file or getattr(field_file, '_committed', True):
        return

    optimized = optimize_image_file(field_file.file)
    stem = Path(field_file.name or 'upload').stem
    new_name = f'{stem}{optimized.extension}'
    field_file.save(new_name, ContentFile(optimized.data), save=False)
