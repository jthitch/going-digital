# Migration: Remove CourseInstance and drop course_instances table
# Run after bookings has migrated to workshop

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0017_workshop_venue_remove_courseinstance'),
        ('bookings', '0003_migrate_to_workshop'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CourseInstance',
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS course_instances;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
