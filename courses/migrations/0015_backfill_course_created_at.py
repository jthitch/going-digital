# Backfill created_at for Course records where it is NULL.

from django.db import migrations
from django.utils import timezone


def backfill_created_at(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    now = timezone.now()
    Course.objects.filter(created_at__isnull=True).update(created_at=now)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0014_course_media'),
    ]

    operations = [
        migrations.RunPython(backfill_created_at, noop),
    ]
