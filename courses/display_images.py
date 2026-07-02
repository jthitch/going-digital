"""Resolve course and workshop images for student-facing pages."""
from collections import defaultdict

from courses.models import Image, WorkshopGalleryImage


def gd_image_for_id(image_id):
    if not image_id:
        return None
    return Image.objects.filter(pk=image_id).first()


def workshop_gallery_image_ids(workshop):
    """Ordered gd_image ids for a workshop gallery, with legacy image_id fallback."""
    if not workshop:
        return []

    if workshop.pk:
        image_ids = list(
            workshop.gallery_images.order_by('display_order', 'id').values_list('image_id', flat=True)
        )
        if image_ids:
            return image_ids

    if workshop.image_id:
        return [workshop.image_id]

    return []


def workshop_gallery_images(workshop):
    """Ordered gd_image rows for a workshop gallery."""
    if not workshop:
        return []

    if hasattr(workshop, '_gd_images'):
        return list(workshop._gd_images or [])

    if workshop.pk:
        images = [
            link.image
            for link in workshop.gallery_images.select_related('image').order_by('display_order', 'id')
            if link.image and link.image.url
        ]
        if images:
            return images

    if workshop.image_id:
        image = gd_image_for_id(workshop.image_id)
        if image and image.url:
            return [image]

    return []


def attach_gd_images_to_workshops(workshops):
    """Batch-load workshop gallery images onto workshop._gd_images."""
    workshop_list = list(workshops or [])
    if not workshop_list:
        return workshop_list

    workshop_ids = [w.pk for w in workshop_list if w.pk]
    by_workshop = defaultdict(list)
    if workshop_ids:
        links = WorkshopGalleryImage.objects.filter(
            workshop_id__in=workshop_ids,
        ).select_related('image').order_by('workshop_id', 'display_order', 'id')
        for link in links:
            if link.image and link.image.url:
                by_workshop[link.workshop_id].append(link.image)

    legacy_ids = {
        w.image_id
        for w in workshop_list
        if w.image_id and (not w.pk or not by_workshop.get(w.pk))
    }
    legacy_by_pk = (
        {img.pk: img for img in Image.objects.filter(pk__in=legacy_ids)}
        if legacy_ids else {}
    )

    for workshop in workshop_list:
        images = by_workshop.get(workshop.pk, []) if workshop.pk else []
        if not images and workshop.image_id:
            legacy = legacy_by_pk.get(workshop.image_id)
            if legacy and legacy.url:
                images = [legacy]
        workshop._gd_images = images
        workshop._gd_image = images[0] if images else None
    return workshop_list


def workshop_gd_image(workshop):
    images = workshop_gallery_images(workshop)
    return images[0] if images else None


def primary_image_url(*, workshop=None, course=None):
    """First available image URL: workshop gallery, then course gd_image, then CourseMedia."""
    if workshop:
        images = workshop_gallery_images(workshop)
        if images:
            return images[0].url
        course = course or workshop.course

    if course:
        if course.image and course.image.url:
            return course.image.url
        first = course.first_uploaded_image
        if first and first.image:
            return first.image.url

    return ''


def collect_header_images(course, workshop=None):
    """
    Header / hero images for course detail.
    Workshop gallery images are included first when viewing a specific workshop.
    """
    images = []
    seen = set()
    title = course.title if course else 'Course'

    def add(url, alt):
        if url and url not in seen:
            seen.add(url)
            images.append({'url': url, 'alt': alt or title})

    if workshop:
        for image in workshop_gallery_images(workshop):
            add(image.url, image.source_name or title)

    if course:
        if course.image and course.image.url:
            add(course.image.url, title)
        for item in course.media.all():
            if item.media_type == 'image' and item.image and item.image.url:
                add(item.image.url, item.caption or title)

    return images
