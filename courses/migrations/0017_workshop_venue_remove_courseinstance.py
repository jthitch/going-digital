# Migration: Add Workshop and Venue (gd_workshop, gd_venue), remove CourseInstance

from django.db import migrations, models
import django.db.models.deletion


def alter_course_instances_id_for_mysql(apps, schema_editor):
    """MySQL: course_instances.id must be BIGINT to match Django FK (bookings.course_instance_id)."""
    if schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(
            "ALTER TABLE course_instances MODIFY COLUMN id BIGINT AUTO_INCREMENT NOT NULL"
        )


class Migration(migrations.Migration):
    atomic = False  # MySQL DDL (ALTER TABLE) cannot run inside a transaction

    dependencies = [
        ('courses', '0016_fix_course_instance_fk'),
    ]

    operations = [
        migrations.RunPython(alter_course_instances_id_for_mysql, migrations.RunPython.noop),
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('status_id', models.SmallIntegerField(db_column='status_id', default=2)),
                ('region_id', models.IntegerField(blank=True, db_column='region_id', null=True)),
                ('user_id', models.IntegerField(blank=True, db_column='user_id', null=True)),
                ('content_id', models.IntegerField(blank=True, db_column='content_id', null=True)),
                ('county_id', models.IntegerField(blank=True, db_column='county_id', null=True)),
                ('venue_name', models.CharField(db_column='venue_name', default='', max_length=255)),
                ('location', models.CharField(blank=True, db_column='location', max_length=255, null=True)),
                ('slug', models.CharField(db_column='slug', default='', max_length=255)),
                ('venue_address', models.TextField(blank=True, db_column='venue_address', null=True)),
                ('venue_telephone', models.CharField(blank=True, db_column='venue_telephone', max_length=255, null=True)),
                ('venue_url', models.TextField(blank=True, db_column='venue_url', null=True)),
                ('latitude', models.FloatField(blank=True, db_column='latitude', null=True)),
                ('longitude', models.FloatField(blank=True, db_column='longitude', null=True)),
                ('show_workshops', models.SmallIntegerField(db_column='show_workshops', default=1)),
                ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
            ],
            options={
                'db_table': 'gd_venue',
                'managed': False,
                'ordering': ['venue_name'],
                'verbose_name': 'Venue',
                'verbose_name_plural': 'Venues',
            },
        ),
        migrations.CreateModel(
            name='Workshop',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('region_id', models.IntegerField(blank=True, db_column='region_id', null=True)),
                ('user_id', models.IntegerField(blank=True, db_column='user_id', null=True)),
                ('alt_course_id', models.IntegerField(db_column='alt_course_id', default=0)),
                ('tutor_id', models.IntegerField(blank=True, db_column='tutor_id', null=True)),
                ('assistant_id', models.IntegerField(blank=True, db_column='assistant_id', null=True)),
                ('workshop_type_id', models.IntegerField(blank=True, db_column='workshop_type_id', null=True)),
                ('cameras_available', models.SmallIntegerField(db_column='cameras_available', default=0)),
                ('number_of_loan_cameras_available', models.IntegerField(db_column='number_of_loan_cameras_available', default=0)),
                ('sticky', models.SmallIntegerField(db_column='sticky', default=0)),
                ('active', models.SmallIntegerField(db_column='active')),
                ('checksum', models.CharField(blank=True, db_column='checksum', max_length=32, null=True)),
                ('date', models.DateTimeField(db_column='date')),
                ('cost', models.IntegerField(db_column='cost', default=0)),
                ('deposit_required', models.IntegerField(db_column='deposit_required', default=0)),
                ('max_places', models.IntegerField(blank=True, db_column='max_places', null=True)),
                ('places_booked', models.IntegerField(blank=True, db_column='places_booked', null=True)),
                ('strapline', models.TextField(blank=True, db_column='strapline', null=True)),
                ('byline', models.TextField(blank=True, db_column='byline', null=True)),
                ('comments', models.TextField(blank=True, db_column='comments', null=True)),
                ('reminder_message', models.TextField(blank=True, db_column='reminder_message', null=True)),
                ('approve', models.SmallIntegerField(db_column='approve', default=1)),
                ('blurb', models.CharField(blank=True, db_column='blurb', max_length=500, null=True)),
                ('cloned_from_workshop_id', models.IntegerField(blank=True, db_column='cloned_from_workshop_id', null=True)),
                ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                ('image_id', models.IntegerField(db_column='image_id', default=0)),
                ('course', models.ForeignKey(blank=True, db_column='course_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workshops', to='courses.course')),
                ('venue', models.ForeignKey(blank=True, db_column='venue_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workshops', to='courses.venue')),
            ],
            options={
                'db_table': 'gd_workshop',
                'managed': False,
                'ordering': ['date'],
                'verbose_name': 'Workshop',
                'verbose_name_plural': 'Workshops',
            },
        ),
        # Don't delete CourseInstance yet - bookings still references it.
        # CourseInstance will be removed in 0018 after bookings migration.
    ]
