# Create stub users table to satisfy FK constraints from instructors, franchises, bookings, payments.
# Those tables have REFERENCES users(id) - we keep a minimal users table synced with gd_user ids.

from django.db import migrations


def create_users_stub(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        return
    raw_conn = schema_editor.connection.connection
    raw_conn.execute("PRAGMA foreign_keys=OFF")
    raw_conn.execute("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER NOT NULL PRIMARY KEY)
    """)
    raw_conn.execute("""
        INSERT OR IGNORE INTO users (id) SELECT id FROM gd_user
    """)
    raw_conn.commit()


def drop_users_stub(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        return
    raw_conn = schema_editor.connection.connection
    raw_conn.execute("PRAGMA foreign_keys=OFF")
    raw_conn.execute("DROP TABLE IF EXISTS users")
    raw_conn.commit()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_migrate_to_gd_user'),
    ]

    operations = [
        migrations.RunPython(create_users_stub, drop_users_stub),
    ]
