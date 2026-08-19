"""Where gd_image and other media appear on the public site."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from courses.models import (
    Course,
    CourseMedia,
    Venue,
    Workshop,
    WorkshopGalleryImage,
)
from courses.workshop_querysets import bookable_workshop_visibility_q


@dataclass(frozen=True)
class ImageUsage:
    """One place an image is shown on the live site."""

    area: str
    label: str
    admin_url: str = ''
    preview_url: str = ''
    image_id: int | None = None  # set for gd_image rows only


def _admin_change_url(app_label, model_name, pk):
    try:
        return reverse(f'admin:{app_label}_{model_name}_change', args=[pk])
    except Exception:
        return ''


def _workshop_label(workshop):
    course_name = ''
    if workshop.course_id and getattr(workshop, 'course', None):
        course_name = workshop.course.course_name or ''
    venue_name = ''
    if workshop.venue_id and getattr(workshop, 'venue', None):
        venue_name = workshop.venue.venue_name or ''
    parts = [p for p in (course_name, venue_name) if p]
    detail = ' — '.join(parts) if parts else f'#{workshop.pk}'
    return f'Workshop: {detail}'


def bookable_workshop_q(*, now=None):
    """Active course + bookable workshop visibility (public site)."""
    return Q(course__active=True) & bookable_workshop_visibility_q(now=now)


def live_gd_image_filter_q(*, now=None):
    """
    Expression for Image rows currently shown via course card or workshop gallery.
    """
    now = now or timezone.now()
    course_live = Course.objects.filter(image_id=OuterRef('pk'), active=True)
    gallery_live = WorkshopGalleryImage.objects.filter(
        image_id=OuterRef('pk'),
        workshop__active=1,
        workshop__course__active=True,
    ).filter(
        Q(workshop__open_dated=1) | Q(workshop__date__gte=now),
    )
    legacy_live = Workshop.objects.filter(
        image_id=OuterRef('pk'),
        active=1,
        course__active=True,
    ).exclude(image_id=0).filter(
        Q(open_dated=1) | Q(date__gte=now),
    )
    return (
        Exists(course_live)
        | Exists(gallery_live)
        | Exists(legacy_live)
    )


def annotate_images_live_on_site(queryset, *, now=None):
    return queryset.annotate(live_on_site=live_gd_image_filter_q(now=now))


def build_gd_image_usage_map(image_ids=None, *, now=None):
    """
    Map gd_image pk → list[ImageUsage] for live (public) usages only.

    If image_ids is None, include every live usage site-wide.
    """
    now = now or timezone.now()
    usages = defaultdict(list)
    id_filter = None
    if image_ids is not None:
        id_filter = {int(i) for i in image_ids if i}
        if not id_filter:
            return {}

    course_qs = Course.objects.filter(active=True, image_id__isnull=False).exclude(image_id=0)
    if id_filter is not None:
        course_qs = course_qs.filter(image_id__in=id_filter)
    for course in course_qs.only('id', 'course_name', 'image_id'):
        usages[course.image_id].append(
            ImageUsage(
                area='Course',
                label=f'Course: {course.course_name}',
                admin_url=_admin_change_url('courses', 'course', course.pk),
                image_id=course.image_id,
            )
        )

    workshop_qs = (
        Workshop.objects.filter(bookable_workshop_q(now=now))
        .select_related('course', 'venue')
    )
    gallery_qs = WorkshopGalleryImage.objects.filter(
        workshop_id__in=workshop_qs.values('pk'),
    ).select_related('workshop', 'workshop__course', 'workshop__venue')
    if id_filter is not None:
        gallery_qs = gallery_qs.filter(image_id__in=id_filter)

    workshops_with_gallery = set()
    for link in gallery_qs:
        workshops_with_gallery.add(link.workshop_id)
        usages[link.image_id].append(
            ImageUsage(
                area='Workshop',
                label=_workshop_label(link.workshop),
                admin_url=_admin_change_url('courses', 'workshop', link.workshop_id),
                image_id=link.image_id,
            )
        )

    legacy_qs = workshop_qs.exclude(image_id=0).exclude(pk__in=workshops_with_gallery)
    if id_filter is not None:
        legacy_qs = legacy_qs.filter(image_id__in=id_filter)
    for workshop in legacy_qs:
        usages[workshop.image_id].append(
            ImageUsage(
                area='Workshop',
                label=_workshop_label(workshop),
                admin_url=_admin_change_url('courses', 'workshop', workshop.pk),
                image_id=workshop.image_id,
            )
        )

    return dict(usages)


def format_usage_lines(usages, *, max_items=5):
    """HTML lines for admin list/detail."""
    if not usages:
        return '—'
    lines = []
    for usage in usages[:max_items]:
        if usage.admin_url:
            lines.append(
                format_html('<a href="{}">{}</a>', usage.admin_url, usage.label)
            )
        else:
            lines.append(format_html('{}', usage.label))
    extra = len(usages) - max_items
    if extra > 0:
        lines.append(format_html('+{} more', extra))
    return format_html_join(mark_safe('<br>'), '{}', ((line,) for line in lines))


def _safe_media_url(file_field):
    if not file_field:
        return ''
    try:
        name = file_field.name
        if not name:
            return ''
        if file_field.storage.exists(name):
            return file_field.url
    except (OSError, ValueError):
        return ''
    return ''


def collect_live_site_images(*, now=None):
    """
    All images currently shown on the public UI across every media area.

    Includes gd_image (courses/workshops) and separate ImageField uploads
    (heroes, gift vouchers, before/after, venues, course media, gift cards).
    """
    now = now or timezone.now()
    rows = []

    try:
        from website.models import HeroImage
    except ImportError:
        HeroImage = None
    if HeroImage is not None:
        for hero in HeroImage.objects.filter(is_active=True).order_by('order', 'id'):
            url = _safe_media_url(hero.image)
            if not url:
                continue
            rows.append(
                ImageUsage(
                    area='Hero',
                    label=f'Homepage hero (order {hero.order})',
                    admin_url=_admin_change_url('website', 'heroimage', hero.pk),
                    preview_url=url,
                )
            )

    try:
        from website.models import GiftVoucherPageImage
    except ImportError:
        GiftVoucherPageImage = None
    if GiftVoucherPageImage is not None:
        for row in GiftVoucherPageImage.objects.all()[:1]:
            url = _safe_media_url(row.image)
            if not url:
                continue
            rows.append(
                ImageUsage(
                    area='Gift voucher',
                    label='Gift vouchers page',
                    admin_url=_admin_change_url('website', 'giftvoucherpageimage', row.pk),
                    preview_url=url,
                )
            )

    try:
        from website.models import GiftCardDesign
    except ImportError:
        GiftCardDesign = None
    if GiftCardDesign is not None:
        for design in GiftCardDesign.objects.filter(is_active=True).order_by(
            'display_order', 'name'
        ):
            url = _safe_media_url(design.image)
            if not url:
                continue
            rows.append(
                ImageUsage(
                    area='Gift card',
                    label=f'Gift card design: {design.name}',
                    admin_url=_admin_change_url('website', 'giftcarddesign', design.pk),
                    preview_url=url,
                )
            )

    try:
        from website.models import BeforeAfterImage
    except ImportError:
        BeforeAfterImage = None
    if BeforeAfterImage is not None:
        for pair in BeforeAfterImage.objects.filter(is_active=True).order_by('order', 'id'):
            for kind, field in (
                ('Before', pair.before_image),
                ('After', pair.after_image),
            ):
                url = _safe_media_url(field)
                if not url:
                    continue
                title = pair.title or f'#{pair.pk}'
                rows.append(
                    ImageUsage(
                        area='Before & after',
                        label=f'{kind}: {title}',
                        admin_url=_admin_change_url(
                            'website', 'beforeafterimage', pair.pk
                        ),
                        preview_url=url,
                    )
                )

    from courses.display_images import (
        attach_gd_images_to_workshops,
        course_media_image_url,
        gd_image_public_url,
    )

    for course in Course.objects.filter(active=True).select_related('image').prefetch_related(
        'media'
    ):
        if course.image_id and course.image:
            preview = gd_image_public_url(course.image)
            if preview:
                rows.append(
                    ImageUsage(
                        area='Course',
                        label=f'Course: {course.course_name}',
                        admin_url=_admin_change_url('courses', 'course', course.pk),
                        preview_url=preview,
                        image_id=course.image_id,
                    )
                )
        for media in course.media.all():
            if media.media_type != CourseMedia.MEDIA_TYPE_IMAGE:
                continue
            preview = course_media_image_url(media)
            if not preview:
                continue
            caption = media.caption or f'media #{media.pk}'
            rows.append(
                ImageUsage(
                    area='Course media',
                    label=f'{course.course_name}: {caption}',
                    admin_url=_admin_change_url('courses', 'course', course.pk),
                    preview_url=preview,
                )
            )

    workshops = list(
        Workshop.objects.filter(bookable_workshop_q(now=now)).select_related(
            'course', 'venue'
        )
    )
    attach_gd_images_to_workshops(workshops)
    for workshop in workshops:
        for image in getattr(workshop, '_gd_images', None) or []:
            preview = gd_image_public_url(image)
            if not preview:
                continue
            rows.append(
                ImageUsage(
                    area='Workshop',
                    label=_workshop_label(workshop),
                    admin_url=_admin_change_url('courses', 'workshop', workshop.pk),
                    preview_url=preview,
                    image_id=image.pk,
                )
            )

    for venue in Venue.objects.filter(active=1).prefetch_related('media'):
        for media in venue.media.all():
            preview = _safe_media_url(media.image)
            if not preview:
                continue
            caption = media.caption or f'image #{media.pk}'
            rows.append(
                ImageUsage(
                    area='Venue',
                    label=f'{venue.venue_name}: {caption}',
                    admin_url=_admin_change_url('courses', 'venue', venue.pk),
                    preview_url=preview,
                )
            )

    area_order = {
        'Hero': 0,
        'Gift voucher': 1,
        'Gift card': 2,
        'Before & after': 3,
        'Course': 4,
        'Course media': 5,
        'Workshop': 6,
        'Venue': 7,
    }
    rows.sort(key=lambda r: (area_order.get(r.area, 99), r.label.lower()))
    return rows
