"""Admin training guides loaded from docs/admin-training/*.md."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.template import Context, Engine
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

GUIDES_DIR = Path(settings.BASE_DIR) / 'docs' / 'admin-training'


@dataclass(frozen=True)
class TrainingGuide:
    slug: str
    title: str
    summary: str
    filename: str
    # Used for contextual help banners on related admin screens.
    contexts: tuple[str, ...] = ()


GUIDE_CATALOG: tuple[TrainingGuide, ...] = (
    TrainingGuide(
        slug='create-venue',
        title='Create a venue',
        summary='Add a photography venue, fill address and content, then submit for approval.',
        filename='create-venue.md',
        contexts=('venue',),
    ),
    TrainingGuide(
        slug='create-course',
        title='Create a course',
        summary='Set up a course with content, skill level, category, and public SEO fields.',
        filename='create-course.md',
        contexts=('course',),
    ),
    TrainingGuide(
        slug='create-workshop',
        title='Create a workshop',
        summary='Schedule a bookable workshop at a venue with dates, price, and tutor.',
        filename='create-workshop.md',
        contexts=('workshop',),
    ),
    TrainingGuide(
        slug='venue-approval',
        title='Venue approval & content changes',
        summary='How superusers approve new venues and franchisee content updates.',
        filename='venue-approval.md',
        contexts=('venue',),
    ),
    TrainingGuide(
        slug='discount-codes',
        title='Discount codes',
        summary='Create promotional £ or % off codes and attach them to workshops.',
        filename='discount-codes.md',
        contexts=('discount_code', 'workshop'),
    ),
    TrainingGuide(
        slug='workshop-feedback',
        title='Workshop feedback',
        summary='How day-after rating emails work and where to read student feedback.',
        filename='workshop-feedback.md',
        contexts=('workshop_feedback',),
    ),
)


def get_guide(slug: str) -> TrainingGuide | None:
    slug = (slug or '').strip()
    for guide in GUIDE_CATALOG:
        if guide.slug == slug:
            return guide
    return None


def guides_for_context(context_key: str) -> list[TrainingGuide]:
    key = (context_key or '').strip().lower()
    return [g for g in GUIDE_CATALOG if key in g.contexts]


def training_url_context(request=None) -> dict:
    """URLs available inside guide Markdown templates."""
    def _rev(name, *args, **kwargs):
        try:
            return reverse(name, args=args, kwargs=kwargs)
        except NoReverseMatch:
            return '#'

    site_base = ''
    if request is not None:
        site_base = request.build_absolute_uri('/').rstrip('/')

    guide_urls = {
        f'guide_{guide.slug.replace("-", "_")}': _rev(
            'admin:admin_training_guide',
            slug=guide.slug,
        )
        for guide in GUIDE_CATALOG
    }

    return {
        'admin_index': _rev('admin:index'),
        'training_index': _rev('admin:admin_training_index'),
        'venue_changelist': _rev('admin:courses_venue_changelist'),
        'venue_add': _rev('admin:courses_venue_add'),
        'course_changelist': _rev('admin:courses_course_changelist'),
        'course_add': _rev('admin:courses_course_add'),
        'workshop_changelist': _rev('admin:courses_workshop_changelist'),
        'workshop_add': _rev('admin:courses_workshop_add'),
        'workshop_calendar': _rev('admin:courses_workshop_calendar'),
        'region_map': _rev('admin:courses_region_map'),
        'tutor_changelist': _rev('admin:courses_tutor_changelist'),
        'image_changelist': _rev('admin:courses_image_changelist'),
        'discount_code_changelist': _rev('admin:bookings_discountcode_changelist'),
        'discount_code_add': _rev('admin:bookings_discountcode_add'),
        'workshop_feedback_changelist': _rev('admin:bookings_workshopfeedback_changelist'),
        'public_courses': _rev('courses:course_list'),
        'public_venues': _rev('courses:venue_list'),
        'public_locations': _rev('courses:location_landing_index'),
        'public_home': _rev('courses:homepage'),
        'site_base': site_base or getattr(settings, 'SITE_URL', '').rstrip('/'),
        **guide_urls,
    }


def _read_guide_markdown(guide: TrainingGuide) -> str:
    path = GUIDES_DIR / guide.filename
    if not path.is_file():
        return f'# {guide.title}\n\nGuide file missing: `{guide.filename}`.\n'
    return path.read_text(encoding='utf-8')


def render_guide_html(guide: TrainingGuide, request=None) -> str:
    """Render guide Markdown (with Django template vars) to safe HTML."""
    import markdown

    raw = _read_guide_markdown(guide)
    engine = Engine(autoescape=False)
    template = engine.from_string(raw)
    rendered_md = template.render(Context({'urls': training_url_context(request)}))
    html = markdown.markdown(
        rendered_md,
        extensions=['extra', 'sane_lists', 'nl2br', 'toc'],
        output_format='html5',
    )
    return mark_safe(html)


@lru_cache(maxsize=1)
def guide_catalog_slugs() -> frozenset[str]:
    return frozenset(g.slug for g in GUIDE_CATALOG)
