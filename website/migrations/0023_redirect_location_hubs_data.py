# Data migration: 301 redirects for legacy location hub URLs.
#
# Regions:  /photography-courses-in/<slug>[/] → /photography-courses/regions/<slug>/
# Cities:   /photography-courses/<city>[/]    → /photography-courses/in/<city>/
# Indexes:  /photography-courses/in[/] and /photography-courses-in[/]
#           → /photography-courses/locations/

from django.db import migrations

LOCATIONS_INDEX = '/photography-courses/locations/'

# Path segments under /photography-courses/ that must never become city redirects.
_RESERVED_COURSE_SEGMENTS = frozenset({
    'locations',
    'regions',
    'venues',
    'in',
})

_INDEX_REDIRECTS = (
    ('/photography-courses/in', LOCATIONS_INDEX),
    ('/photography-courses/in/', LOCATIONS_INDEX),
    ('/photography-courses-in', LOCATIONS_INDEX),
    ('/photography-courses-in/', LOCATIONS_INDEX),
)

# Known live region hubs (also re-seeded in 0024 if DB rows are missing).
_LEGACY_REGION_SLUGS = frozenset({
    'south-east-scotland',
    'scottish-highlands-islands',
    'south-west-scotland',
    'lancashire',
    'east-midlands',
    'north-wales',
    'south-wales-bristol',
    'devon-cornwall',
    'south-south-coast',
    'south-east',
    'east-anglia',
    'london',
    'south-midlands',
    'east-england',
})


def _path_variants(path: str) -> tuple[str, str]:
    """Return (without trailing slash, with trailing slash), excluding bare '/'."""
    stripped = path.rstrip('/') or '/'
    if stripped == '/':
        return ('/', '/')
    return (stripped, f'{stripped}/')


def _upsert_redirect(Redirect, old_path: str, new_path: str, created_paths: list[str]) -> None:
    obj, created = Redirect.objects.get_or_create(
        old_path=old_path,
        defaults={
            'new_path': new_path,
            'permanent': True,
            'is_active': True,
        },
    )
    if created:
        created_paths.append(old_path)
        return
    # Refresh inactive / non-permanent rows we own; leave custom targets alone.
    if obj.new_path == new_path and (not obj.is_active or not obj.permanent):
        obj.is_active = True
        obj.permanent = True
        obj.save(update_fields=['is_active', 'permanent', 'updated_at'])


def add_location_hub_redirects(apps, schema_editor):
    Redirect = apps.get_model('website', 'Redirect')
    Region = apps.get_model('courses', 'Region')
    Course = apps.get_model('courses', 'Course')

    created_paths: list[str] = []

    for old_path, new_path in _INDEX_REDIRECTS:
        _upsert_redirect(Redirect, old_path, new_path, created_paths)

    region_slugs = {
        (slug or '').strip()
        for slug in Region.objects.exclude(slug='')
        .exclude(slug__isnull=True)
        .values_list('slug', flat=True)
        if (slug or '').strip()
    }
    region_slugs |= _LEGACY_REGION_SLUGS
    for slug in sorted(region_slugs):
        new_path = f'/photography-courses/regions/{slug}/'
        for old_path in _path_variants(f'/photography-courses-in/{slug}'):
            _upsert_redirect(Redirect, old_path, new_path, created_paths)

    course_slugs = {
        (slug or '').strip().lower()
        for slug in Course.objects.exclude(slug='')
        .exclude(slug__isnull=True)
        .values_list('slug', flat=True)
        if (slug or '').strip()
    }

    # Prefer live city-landing derivation so redirects match public /in/<slug>/ pages.
    from courses.location_landings import indexable_cities

    for city in indexable_cities():
        slug = (city.slug or '').strip().lower()
        if not slug or slug in _RESERVED_COURSE_SEGMENTS or slug in course_slugs:
            continue
        new_path = f'/photography-courses/in/{slug}/'
        for old_path in _path_variants(f'/photography-courses/{slug}'):
            _upsert_redirect(Redirect, old_path, new_path, created_paths)


def remove_location_hub_redirects(apps, schema_editor):
    """
    Reverse only the known patterns from this migration.
    Does not delete unrelated Redirect rows.
    """
    Redirect = apps.get_model('website', 'Redirect')
    Region = apps.get_model('courses', 'Region')
    Course = apps.get_model('courses', 'Course')

    old_paths = {old for old, _new in _INDEX_REDIRECTS}

    for slug in Region.objects.exclude(slug='').exclude(slug__isnull=True).values_list('slug', flat=True):
        slug = (slug or '').strip()
        if not slug:
            continue
        old_paths.update(_path_variants(f'/photography-courses-in/{slug}'))
    for slug in _LEGACY_REGION_SLUGS:
        old_paths.update(_path_variants(f'/photography-courses-in/{slug}'))

    course_slugs = {
        (slug or '').strip().lower()
        for slug in Course.objects.exclude(slug='')
        .exclude(slug__isnull=True)
        .values_list('slug', flat=True)
        if (slug or '').strip()
    }

    from courses.location_landings import indexable_cities

    for city in indexable_cities():
        slug = (city.slug or '').strip().lower()
        if not slug or slug in _RESERVED_COURSE_SEGMENTS or slug in course_slugs:
            continue
        old_paths.update(_path_variants(f'/photography-courses/{slug}'))

    Redirect.objects.filter(old_path__in=old_paths).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0022_update_privacy_cookie_policy'),
        ('courses', '0049_venuecontentchangerequest'),
    ]

    operations = [
        migrations.RunPython(add_location_hub_redirects, remove_location_hub_redirects),
    ]
