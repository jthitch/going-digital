# Create users stub table for MySQL - payments and other tables have FK to users(id).
# gd_user is the real User table; we keep a minimal users stub synced for legacy FK constraints.

from django.db import migrations


def create_users_stub_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT NOT NULL PRIMARY KEY
            )
        """)
        cursor.execute("""
            INSERT IGNORE INTO users (id) SELECT id FROM gd_user
        """)


def drop_users_stub_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_users_stub_for_fk'),
    ]

    operations = [
        migrations.RunPython(create_users_stub_mysql, drop_users_stub_mysql),
    ]
