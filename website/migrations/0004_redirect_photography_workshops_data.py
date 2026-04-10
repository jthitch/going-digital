# Data migration: add 301 redirect from /photography-workshops/ to /photography-courses/

from django.db import migrations


def add_photography_workshops_redirect(apps, schema_editor):
    Redirect = apps.get_model('website', 'Redirect')
    Redirect.objects.get_or_create(
        old_path='/photography-workshops/',
        defaults={
            'new_path': '/photography-courses/',
            'permanent': True,
            'is_active': True,
        },
    )


def remove_photography_workshops_redirect(apps, schema_editor):
    Redirect = apps.get_model('website', 'Redirect')
    Redirect.objects.filter(old_path='/photography-workshops/').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0003_add_redirect_model'),
    ]

    operations = [
        migrations.RunPython(add_photography_workshops_redirect, remove_photography_workshops_redirect),
    ]
