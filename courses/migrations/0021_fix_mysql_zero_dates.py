# Fix MySQL zero dates (0000-00-00) in gd_workshop before schema migrations.
# MySQL strict mode rejects these; AlterField on Course can trigger validation of FKs.

from django.db import migrations


def fix_zero_dates_mysql(apps, schema_editor):
    """Replace 0000-00-00 in gd_workshop.date so MySQL strict mode doesn't fail."""
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT @@sql_mode")
        orig_mode = cursor.fetchone()[0]
        cursor.execute("SET SESSION sql_mode = ''")
        try:
            cursor.execute("""
                UPDATE gd_workshop
                SET date = '2000-01-01 00:00:00'
                WHERE date = '0000-00-00 00:00:00' OR CAST(date AS CHAR) LIKE '0000-%'
            """)
            if cursor.rowcount:
                print(f"Fixed {cursor.rowcount} rows in gd_workshop.date")
        finally:
            cursor.execute("SET SESSION sql_mode = %s", [orig_mode])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0020_venue_content_and_media'),
    ]

    operations = [
        migrations.RunPython(fix_zero_dates_mysql, noop),
    ]
