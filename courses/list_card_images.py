"""
Disk-cached list-card image variants.

Course/venue cards display at ~300–400 CSS pixels; source uploads are often
up to 1920px. Serving a ~720px WebP cuts LCP bytes without changing admin uploads.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ListCardImage:
    """Public URL plus intrinsic pixel size of the file we will serve."""

    url: str
    width: int | None = None
    height: int | None = None

    def __bool__(self):
        return bool(self.url)


def list_card_image_max_width():
    return int(getattr(settings, 'GD_LIST_CARD_IMAGE_WIDTH', 720))


def list_card_image_quality():
    return int(getattr(settings, 'GD_LIST_CARD_IMAGE_QUALITY', 72))


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT)


def _public_url(relative_posix: str) -> str:
    base = (getattr(settings, 'MEDIA_URL', '/media/') or '/media/').rstrip('/')
    return f'{base}/{relative_posix.lstrip("/")}'


def _relative_to_media(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(_media_root().resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as img:
            img = _exif_transpose(img)
            return int(img.width), int(img.height)
    except Exception:
        return None


def _exif_transpose(img):
    from PIL import ImageOps

    return ImageOps.exif_transpose(img)


def _scaled_size(src_w: int, src_h: int, max_width: int) -> tuple[int, int]:
    if src_w <= max_width:
        return src_w, src_h
    return max_width, max(1, round(src_h * (max_width / src_w)))


def cached_list_card_image(source_path: Path | str | None) -> ListCardImage:
    """
    Return a MEDIA_URL and intrinsic size for a list-card image.

    Only paths under MEDIA_ROOT are accepted. Existing cache files are reused
    when newer than the source. Sources already at or below the target width
    are returned as-is to avoid needless re-encoding.
    """
    empty = ListCardImage('')
    if not source_path:
        return empty

    source = Path(source_path)
    rel = _relative_to_media(source)
    if not rel:
        return empty
    try:
        if not source.is_file():
            return empty
        source_mtime = source.stat().st_mtime
    except OSError:
        return empty

    width = list_card_image_max_width()
    quality = list_card_image_quality()
    digest = hashlib.sha1(
        f'{rel}|{width}|{quality}|webp'.encode('utf-8'),
    ).hexdigest()[:24]
    relative_out = f'cache/list_cards/{digest}.webp'
    dest = _media_root() / relative_out

    try:
        if dest.is_file() and dest.stat().st_mtime >= source_mtime:
            size = _image_size(dest)
            if size:
                return ListCardImage(_public_url(relative_out), size[0], size[1])
            return ListCardImage(_public_url(relative_out))
    except OSError:
        pass

    source_size = _image_size(source)
    if not source_size:
        return ListCardImage(_public_url(rel))

    src_w, src_h = source_size
    if src_w <= width:
        return ListCardImage(_public_url(rel), src_w, src_h)

    out_w, out_h = _scaled_size(src_w, src_h, width)
    if not _write_list_card_webp(source, dest, width=width, quality=quality):
        return ListCardImage(_public_url(rel), src_w, src_h)
    return ListCardImage(_public_url(relative_out), out_w, out_h)


def cached_list_card_image_url(source_path: Path | str | None) -> str:
    """Backward-compatible URL-only helper."""
    return cached_list_card_image(source_path).url


def _write_list_card_webp(source: Path, dest: Path, *, width: int, quality: int) -> bool:
    try:
        from PIL import Image
    except ImportError:
        logger.warning('Pillow unavailable; list-card thumbnails disabled')
        return False

    import tempfile

    tmp_path = None
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            img.load()
            if getattr(img, 'is_animated', False):
                img.seek(0)
            img = _exif_transpose(img)
            if img.width > width:
                new_height = max(1, round(img.height * (width / img.width)))
                img = img.resize((width, new_height), Image.Resampling.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            fd, tmp_name = tempfile.mkstemp(
                prefix=f'.{dest.stem}.',
                suffix='.webp.tmp',
                dir=str(dest.parent),
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, 'wb') as handle:
                img.save(handle, format='WEBP', quality=quality, method=4)
            os.replace(tmp_path, dest)
            tmp_path = None
        return True
    except Exception:
        logger.exception('Failed to build list-card image for %s', source)
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False


def cached_image_for_field_file(field_file) -> ListCardImage:
    """Resize a Django FieldFile when it lives on local MEDIA_ROOT; else original URL."""
    empty = ListCardImage('')
    if not field_file:
        return empty
    try:
        name = field_file.name
    except (ValueError, AttributeError):
        return empty
    if not name:
        return empty

    try:
        path = Path(field_file.path)
    except (ValueError, NotImplementedError, AttributeError):
        try:
            return ListCardImage(field_file.url or '')
        except (ValueError, AttributeError):
            return empty

    image = cached_list_card_image(path)
    if image:
        return image
    try:
        return ListCardImage(field_file.url or '')
    except (ValueError, AttributeError):
        return empty


def cached_url_for_field_file(field_file) -> str:
    return cached_image_for_field_file(field_file).url


def cached_image_for_gd_image(image) -> ListCardImage:
    """List-card image for a legacy gd_image row."""
    from courses.display_images import gd_image_file_path, gd_image_public_url

    path = gd_image_file_path(image)
    resolved = cached_list_card_image(path)
    if resolved:
        return resolved
    return ListCardImage(gd_image_public_url(image))


def cached_url_for_gd_image(image) -> str:
    return cached_image_for_gd_image(image).url


def first_venue_card_image_url(venues) -> str:
    """First available resized venue-card image URL from an iterable of venues."""
    for venue in venues or []:
        media_qs = getattr(venue, 'media', None)
        if media_qs is None:
            continue
        first = media_qs.first() if hasattr(media_qs, 'first') else None
        if first is None:
            continue
        image = getattr(first, 'card_image', None)
        if image and image.url:
            return image.url
        url = getattr(first, 'card_image_url', '') or ''
        if url:
            return url
    return ''
