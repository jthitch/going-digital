# Migration: Replace course_instance with workshop (gd_workshop)

import django.db.models.deletion
from django.db import migrations, models


def clear_old_bookings(apps, schema_editor):
    """Clear bookings that reference course_instances (no mapping to gd_workshop)."""
    Booking = apps.get_model('bookings', 'Booking')
    Booking.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_initial'),
        ('courses', '0017_workshop_venue_remove_courseinstance'),
    ]

    operations = [
        migrations.RunPython(clear_old_bookings, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='booking',
            name='bookings_course__1a71ce_idx',
        ),
        migrations.RemoveField(
            model_name='booking',
            name='course_instance',
        ),
        migrations.AddField(
            model_name='booking',
            name='workshop',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bookings',
                to='courses.workshop',
                null=True
            ),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['workshop', 'status'], name='bookings_workshop_status_idx'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='workshop',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bookings',
                to='courses.workshop'
            ),
        ),
    ]
