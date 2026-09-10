"""
List-card image helpers.

Card templates expect a small ListCardImage (URL + optional intrinsic size).
We serve the original upload — no on-disk WebP resize. Uploads are already
sized for the site, and re-encoding was hurting quality (and causing nginx
permission issues on newly written cache files).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class ListCardImage:
    """Public URL plus intrinsic pixel size of the file we will serve."""

    url: str
    width: int | None = None
    height: int | None = None

    def __bool__(self):
        return bool(self.url)


def _media_root_resolved() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _public_url(relative_posix: str) -> str:
    base = (getattr(settings, 'MEDIA_URL', '/media/') or '/media/').rstrip('/')
    return f'{base}/{relative_posix.lstrip("/")}'


def _relative_to_media(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(_media_root_resolved()).as_posix()
    except (OSError, ValueError):
        return None


def cached_list_card_image(
    source_path: Path | str | None,
    *,
    generate: bool = False,
    fallback_size: tuple[int | None, int | None] | None = None,
) -> ListCardImage:
    """
    Return a MEDIA_URL and optional size for a list-card image.

    ``generate`` is ignored (kept for call-site compatibility). Always returns
    the original file under MEDIA_ROOT when present.
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
    except OSError:
        return empty

    width = height = None
    if fallback_size:
        if fallback_size[0]:
            width = int(fallback_size[0])
        if fallback_size[1]:
            height = int(fallback_size[1])
    return ListCardImage(_public_url(rel), width, height)


def cached_list_card_image_url(source_path: Path | str | None, *, generate: bool = False) -> str:
    """Backward-compatible URL-only helper."""
    return cached_list_card_image(source_path, generate=generate).url


def cached_image_for_field_file(field_file, *, generate: bool = False) -> ListCardImage:
    """List-card image for a Django FieldFile on local MEDIA_ROOT; else original URL."""
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


def cached_url_for_field_file(field_file, *, generate: bool = False) -> str:
    return cached_image_for_field_file(field_file, generate=generate).url


def cached_image_for_gd_image(image, *, generate: bool = False) -> ListCardImage:
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


def cached_url_for_gd_image(image, *, generate: bool = False) -> str:
    return cached_image_for_gd_image(image, generate=generate).url


def first_venue_card_image_url(venues, *, generate: bool = False) -> str:
    """First available venue-card image URL from an iterable of venues."""
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
    """No-op: list cards no longer encode on-disk thumbnails."""
    return
