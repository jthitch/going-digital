from datetime import timedelta

from django.db import migrations, models


def add_end_date_column(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == 'mysql':
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'gd_workshop'
                  AND COLUMN_NAME = 'end_date'
                """
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'ALTER TABLE gd_workshop ADD COLUMN end_date DATETIME(6) NULL'
                )
        elif connection.vendor == 'sqlite':
            cursor.execute('PRAGMA table_info(gd_workshop)')
            columns = {row[1] for row in cursor.fetchall()}
            if 'end_date' not in columns:
                cursor.execute(
                    'ALTER TABLE gd_workshop ADD COLUMN end_date datetime NULL'
                )


def backfill_end_date(apps, schema_editor):
    Workshop = apps.get_model('courses', 'Workshop')
    for workshop in Workshop.objects.filter(date__isnull=False, end_at__isnull=True).iterator():
        workshop.end_at = workshop.date + timedelta(hours=6)
        workshop.save(update_fields=['end_at'])


def remove_end_date_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'gd_workshop'
              AND COLUMN_NAME = 'end_date'
            """
        )
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE gd_workshop DROP COLUMN end_date')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0041_workshop_document'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='workshop',
                    name='end_at',
                    field=models.DateTimeField(
                        blank=True,
                        db_column='end_date',
                        null=True,
                        verbose_name='End date and time',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_end_date_column, remove_end_date_column),
            ],
        ),
        migrations.RunPython(backfill_end_date, migrations.RunPython.noop),
    ]
