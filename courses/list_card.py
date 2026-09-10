"""Shared helpers for photography-courses list cards (template + JSON API)."""

from django.urls import reverse

from .models import CourseMedia


def list_card_workshops(course):
    """Workshops prefetched for the course list (respects active filters)."""
    workshops = getattr(course, 'list_workshops', None)
    if workshops is not None:
        return workshops
    return list(course.workshops.all()[:50])


def list_card_location_names(course):
    """Unique venue names for list cards (one entry per venue, stable order)."""
    names = []
    seen_venue_ids = set()
    saw_tbc = False
    for workshop in list_card_workshops(course):
        venue = workshop.venue
        if not venue or not venue.pk:
            if not saw_tbc:
                saw_tbc = True
                names.append('TBC')
            continue
        if venue.pk in seen_venue_ids:
            continue
        seen_venue_ids.add(venue.pk)
        name = (venue.name or '').strip()
        if name:
            names.append(name)
        elif not saw_tbc:
            saw_tbc = True
            names.append('TBC')
    return names


def card_focal_point(course):
    """Return (x, y, zoom_percent) for list card image positioning."""
    x = 50 if course.card_image_focus_x is None else int(course.card_image_focus_x)
    y = 50 if course.card_image_focus_y is None else int(course.card_image_focus_y)
    zoom_pct = 100 if course.card_image_zoom is None else int(course.card_image_zoom)
    zoom_pct = max(100, min(200, zoom_pct))
    return x, y, zoom_pct


def card_thumbnail_style(course):
    x, y, zoom_pct = card_focal_point(course)
    scale = zoom_pct / 100
    return (
        f'object-position:{x}% {y}%;'
        f'transform:scale({scale});'
        f'transform-origin:{x}% {y}%;'
    )


def card_object_position_style(course):
    x, y, _zoom = card_focal_point(course)
    return f'object-position:{x}% {y}%;'


def list_card_thumbnail(course, *, generate: bool = False):
    """
    List-card image (URL + optional intrinsic width/height) for a course.

    Serves the original upload. ``generate`` is ignored (API compatibility).
    """
    cached = getattr(course, '_list_card_thumb', None)
    if cached is not None:
        return cached

    from courses.list_card_images import (
        ListCardImage,
        cached_image_for_field_file,
        cached_image_for_gd_image,
    )

    image = ListCardImage('')
    try:
        if course.image_id and course.image:
            image = cached_image_for_gd_image(course.image)
    except (ValueError, OSError):
        image = ListCardImage('')
    if not image:
        for media in course.media.all():
            if media.media_type == 'image' and media.image:
                image = cached_image_for_field_file(media.image)
                if image:
                    break

    course._list_card_thumb = image
    return image


def list_card_thumbnail_url(course, *, generate: bool = False):
    """Public URL for the list-card image (original upload)."""
    return list_card_thumbnail(course, generate=generate).url


def attach_list_card_thumbnails(courses, *, eager_count=3, warm_background=True):
    """Resolve list-card image URLs once per course for the request."""
    course_list = list(courses or [])
    for course in course_list:
        list_card_thumbnail(course)
    return course_list


def list_card_video_data(course):
    """First CourseMedia video payload for list card hover / in-view playback."""
    for media in course.media.all():
        if media.media_type != CourseMedia.MEDIA_TYPE_VIDEO:
            continue
        poster = list_card_thumbnail_url(course)
        position_style = card_object_position_style(course)
        if media.video_file:
            try:
                src = media.video_file.url
            except (ValueError, OSError):
                src = ''
            if src:
                return {
                    'kind': 'file',
                    'src': src,
                    'poster': poster,
                    'style': position_style,
                }
        embed = media.list_card_autoplay_embed_url()
        if embed:
            return {
                'kind': 'embed',
                'src': embed,
                'poster': poster,
                'style': position_style,
            }
    return None


def serialize_list_card(course, *, locations=None, detail_query=''):
    """JSON-serializable dict for infinite-scroll course cards."""
    if locations is None:
        locations = list_card_location_names(course)
    detail_url = reverse('courses:course_detail', kwargs={'slug': course.slug})
    if detail_query:
        detail_url = f'{detail_url}?{detail_query}'
    thumb = list_card_thumbnail(course)
    return {
        'id': course.id,
        'title': course.title,
        'slug': course.slug,
        'category': course.get_card_category_display(),
        'level': course.level,
        'level_display': course.get_level_display(),
        'min_price': str(course.min_price),
        'image_url': thumb.url,
        'image_width': thumb.width,
        'image_height': thumb.height,
        'card_image_style': card_thumbnail_style(course),
        'video': list_card_video_data(course),
        'locations': locations,
        'detail_url': detail_url,
    }
