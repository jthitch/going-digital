# Fix MySQL zero dates in gd_workshop.created_at and updated_at.
# Run after 0021 (which fixes date); needed when 0022 hits created_at/updated_at.

from django.db import migrations


def fix_created_updated_zero_dates(apps, schema_editor):
    """Replace 0000-00-00 in gd_workshop.created_at and updated_at."""
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT @@sql_mode")
        orig_mode = cursor.fetchone()[0]
        cursor.execute("SET SESSION sql_mode = ''")
        try:
            cursor.execute("""
                UPDATE gd_workshop
                SET created_at = NULL
                WHERE created_at = '0000-00-00 00:00:00' OR CAST(created_at AS CHAR) LIKE '0000-%'
            """)
            if cursor.rowcount:
                print(f"Fixed {cursor.rowcount} rows in gd_workshop.created_at")
            cursor.execute("""
                UPDATE gd_workshop
                SET updated_at = NULL
                WHERE updated_at = '0000-00-00 00:00:00' OR CAST(updated_at AS CHAR) LIKE '0000-%'
            """)
            if cursor.rowcount:
                print(f"Fixed {cursor.rowcount} rows in gd_workshop.updated_at")
        finally:
            cursor.execute("SET SESSION sql_mode = %s", [orig_mode])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0021_fix_mysql_zero_dates'),
    ]

    operations = [
        migrations.RunPython(fix_created_updated_zero_dates, noop),
    ]
