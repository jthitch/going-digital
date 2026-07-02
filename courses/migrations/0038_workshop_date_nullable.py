from django.db import migrations


def allow_null_workshop_date(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == 'mysql':
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT IS_NULLABLE, COLUMN_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'gd_workshop'
                  AND COLUMN_NAME = 'date'
                """
            )
            row = cursor.fetchone()
            if not row or row[0] == 'YES':
                return
            column_type = row[1]
            cursor.execute(
                f'ALTER TABLE gd_workshop MODIFY COLUMN `date` {column_type} NULL'
            )
    elif connection.vendor == 'sqlite':
        # Fresh SQLite installs from 0024 already allow NULL on date.
        pass


def disallow_null_workshop_date(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE gd_workshop SET `date` = UTC_TIMESTAMP() WHERE `date` IS NULL"
        )
        cursor.execute(
            """
            SELECT COLUMN_TYPE FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'gd_workshop'
              AND COLUMN_NAME = 'date'
            """
        )
        row = cursor.fetchone()
        if not row:
            return
        column_type = row[0]
        cursor.execute(
            f'ALTER TABLE gd_workshop MODIFY COLUMN `date` {column_type} NOT NULL'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0037_workshop_open_dated'),
    ]

    operations = [
        migrations.RunPython(allow_null_workshop_date, disallow_null_workshop_date),
    ]
