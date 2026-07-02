from django.db import migrations, models


def add_open_dated_column(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == 'mysql':
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'gd_workshop'
                  AND COLUMN_NAME = 'open_dated'
                """
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'ALTER TABLE gd_workshop ADD COLUMN open_dated SMALLINT NOT NULL DEFAULT 0'
                )
        elif connection.vendor == 'sqlite':
            cursor.execute('PRAGMA table_info(gd_workshop)')
            columns = {row[1] for row in cursor.fetchall()}
            if 'open_dated' not in columns:
                cursor.execute(
                    'ALTER TABLE gd_workshop ADD COLUMN open_dated smallint NOT NULL DEFAULT 0'
                )


def remove_open_dated_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'gd_workshop'
              AND COLUMN_NAME = 'open_dated'
            """
        )
        if cursor.fetchone()[0]:
            cursor.execute('ALTER TABLE gd_workshop DROP COLUMN open_dated')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0036_course_card_image_focus'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='workshop',
                    name='open_dated',
                    field=models.SmallIntegerField(
                        db_column='open_dated',
                        default=0,
                        help_text='Date to be agreed with the student (e.g. one-to-one tuition).',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_open_dated_column, remove_open_dated_column),
            ],
        ),
    ]
