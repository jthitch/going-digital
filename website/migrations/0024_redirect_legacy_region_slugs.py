# Ensure 301s for known live /photography-courses-in/<region> URLs.
# Complements 0023 (which seeds from gd_region); covers legacy slugs even if absent in DB.

from django.db import migrations

# Old live region hub slugs → /photography-courses/regions/<slug>/
LEGACY_REGION_SLUGS = (
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
)


def _path_variants(path: str) -> tuple[str, str]:
    stripped = path.rstrip('/') or '/'
    if stripped == '/':
        return ('/', '/')
    return (stripped, f'{stripped}/')


def add_legacy_region_redirects(apps, schema_editor):
    Redirect = apps.get_model('website', 'Redirect')
    for slug in LEGACY_REGION_SLUGS:
        new_path = f'/photography-courses/regions/{slug}/'
        for old_path in _path_variants(f'/photography-courses-in/{slug}'):
            Redirect.objects.get_or_create(
                old_path=old_path,
                defaults={
                    'new_path': new_path,
                    'permanent': True,
                    'is_active': True,
                },
            )


def remove_legacy_region_redirects(apps, schema_editor):
    Redirect = apps.get_model('website', 'Redirect')
    old_paths = []
    for slug in LEGACY_REGION_SLUGS:
        old_paths.extend(_path_variants(f'/photography-courses-in/{slug}'))
    Redirect.objects.filter(old_path__in=old_paths).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0023_redirect_location_hubs_data'),
    ]

    operations = [
        migrations.RunPython(add_legacy_region_redirects, remove_legacy_region_redirects),
    ]
