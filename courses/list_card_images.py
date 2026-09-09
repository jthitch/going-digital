"""
Disk-cached list-card image variants.

Course/venue cards display at ~300–400 CSS pixels; source uploads are often
up to 1920px. Serving a ~720px WebP cuts LCP bytes without changing admin uploads.

Hot path rules:
- Cache hit + sidecar meta → URL/dims with no Pillow
- Cache miss + generate=False → original URL immediately (no encode)
- Cache miss + generate=True → encode once, write WebP + meta
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_media_root_resolved: Path | None = None


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


def _media_root_resolved_path() -> Path:
    global _media_root_resolved
    if _media_root_resolved is None:
        _media_root_resolved = _media_root().resolve()
    return _media_root_resolved


def _public_url(relative_posix: str) -> str:
    base = (getattr(settings, 'MEDIA_URL', '/media/') or '/media/').rstrip('/')
    return f'{base}/{relative_posix.lstrip("/")}'


def _relative_to_media(path: Path) -> str | None:
    try:
        resolved = path.resolve()
        return resolved.relative_to(_media_root_resolved_path()).as_posix()
    except (OSError, ValueError):
        return None


def _meta_path(dest: Path) -> Path:
    return dest.with_suffix('.meta.json')


def _read_meta(dest: Path) -> tuple[int, int] | None:
    meta_file = _meta_path(dest)
    try:
        data = json.loads(meta_file.read_text(encoding='utf-8'))
        width = int(data['width'])
        height = int(data['height'])
        if width > 0 and height > 0:
            return width, height
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def _write_meta(dest: Path, width: int, height: int) -> None:
    meta_file = _meta_path(dest)
    payload = json.dumps({'width': int(width), 'height': int(height)}, separators=(',', ':'))
    tmp = meta_file.with_suffix('.meta.json.tmp')
    try:
        tmp.write_text(payload, encoding='utf-8')
        os.replace(tmp, meta_file)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _image_size(path: Path) -> tuple[int, int] | None:
    """Pillow size probe — cold path / meta backfill only."""
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            return int(img.width), int(img.height)
    except Exception:
        return None


def _scaled_size(src_w: int, src_h: int, max_width: int) -> tuple[int, int]:
    if src_w <= max_width:
        return src_w, src_h
    return max_width, max(1, round(src_h * (max_width / src_w)))


def _cache_dest_for(rel: str, width: int, quality: int) -> tuple[str, Path]:
    digest = hashlib.sha1(
        f'{rel}|{width}|{quality}|webp'.encode('utf-8'),
    ).hexdigest()[:24]
    relative_out = f'cache/list_cards/{digest}.webp'
    return relative_out, _media_root() / relative_out


def cached_list_card_image(
    source_path: Path | str | None,
    *,
    generate: bool = True,
    fallback_size: tuple[int | None, int | None] | None = None,
) -> ListCardImage:
    """
    Return a MEDIA_URL and intrinsic size for a list-card image.

    generate=False never encodes; it returns a warm cache entry or the original.
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

    max_width = list_card_image_max_width()
    quality = list_card_image_quality()
    relative_out, dest = _cache_dest_for(rel, max_width, quality)
    original = ListCardImage(
        _public_url(rel),
        (fallback_size or (None, None))[0],
        (fallback_size or (None, None))[1],
    )

    try:
        if dest.is_file() and dest.stat().st_mtime >= source_mtime:
            size = _read_meta(dest)
            if not size:
                # One-time backfill for cache files written before sidecars existed.
                size = _image_size(dest)
                if size:
                    _write_meta(dest, size[0], size[1])
            if size:
                return ListCardImage(_public_url(relative_out), size[0], size[1])
            return ListCardImage(_public_url(relative_out))
    except OSError:
        pass

    if not generate:
        return original

    source_size = None
    if fallback_size and fallback_size[0] and fallback_size[1]:
        source_size = (int(fallback_size[0]), int(fallback_size[1]))
    if not source_size:
        source_size = _image_size(source)
    if not source_size:
        return original

    src_w, src_h = source_size
    if src_w <= max_width:
        return ListCardImage(_public_url(rel), src_w, src_h)

    out_w, out_h = _scaled_size(src_w, src_h, max_width)
    written = _write_list_card_webp(source, dest, width=max_width, quality=quality)
    if not written:
        return ListCardImage(_public_url(rel), src_w, src_h)
    _write_meta(dest, out_w, out_h)
    return ListCardImage(_public_url(relative_out), out_w, out_h)


def cached_list_card_image_url(source_path: Path | str | None, *, generate: bool = True) -> str:
    """Backward-compatible URL-only helper."""
    return cached_list_card_image(source_path, generate=generate).url


def _write_list_card_webp(source: Path, dest: Path, *, width: int, quality: int) -> bool:
    try:
        from PIL import Image, ImageOps
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
            img = ImageOps.exif_transpose(img)
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


def cached_image_for_field_file(field_file, *, generate: bool = True) -> ListCardImage:
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

    image = cached_list_card_image(path, generate=generate)
    if image:
        return image
    try:
        return ListCardImage(field_file.url or '')
    except (ValueError, AttributeError):
        return empty


def cached_url_for_field_file(field_file, *, generate: bool = True) -> str:
    return cached_image_for_field_file(field_file, generate=generate).url


def cached_image_for_gd_image(image, *, generate: bool = True) -> ListCardImage:
    """List-card image for a legacy gd_image row."""
    from courses.display_images import gd_image_file_path, gd_image_public_url

    path = gd_image_file_path(image)
    fallback = (getattr(image, 'width', None), getattr(image, 'height', None))
    resolved = cached_list_card_image(path, generate=generate, fallback_size=fallback)
    if resolved:
        return resolved
    return ListCardImage(
        gd_image_public_url(image),
        fallback[0] if fallback[0] else None,
        fallback[1] if fallback[1] else None,
    )


def cached_url_for_gd_image(image, *, generate: bool = True) -> str:
    return cached_image_for_gd_image(image, generate=generate).url


def first_venue_card_image_url(venues, *, generate: bool = True) -> str:
    """First available resized venue-card image URL from an iterable of venues."""
    for venue in venues or []:
        media_qs = getattr(venue, 'media', None)
        if media_qs is None:
            continue
        first = media_qs.first() if hasattr(media_qs, 'first') else None
        if first is None:
            continue
        image = cached_image_for_field_file(getattr(first, 'image', None), generate=generate)
        if image:
            return image.url
    return ''


def schedule_list_card_warm(paths: list[Path | str]) -> None:
    """Encode missing list-card variants off the request thread."""
    unique = []
    seen = set()
    for path in paths:
        if not path:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    if not unique:
        return

    def run():
        for path in unique:
            try:
                cached_list_card_image(path, generate=True)
            except Exception:
                logger.exception('Background list-card warm failed for %s', path)

    threading.Thread(target=run, name='list-card-warm', daemon=True).start()
