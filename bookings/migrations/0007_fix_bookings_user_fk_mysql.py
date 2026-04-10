# Fix bookings.user_id FK - point to gd_user instead of removed users table.
# Run after core.0005 which drops users. MySQL only.

from django.db import migrations


def fix_bookings_user_fk(apps, schema_editor):
    """Drop FK to users, align user_id type with gd_user.id, add FK to gd_user."""
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        # Get gd_user.id column type (must match for FK)
        cursor.execute("""
            SELECT COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'gd_user'
              AND COLUMN_NAME = 'id'
        """)
        id_row = cursor.fetchone()
        ref_type = id_row[0] if id_row else 'int'

        # Check if new FK already exists (idempotent if migration failed partway)
        cursor.execute("""
            SELECT 1 FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'bookings'
              AND CONSTRAINT_NAME = 'bookings_user_gd_user_fk'
        """)
        if cursor.fetchone():
            return  # Already fixed

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        # Drop old FK to users if it exists
        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'bookings'
              AND REFERENCED_TABLE_NAME = 'users'
              AND COLUMN_NAME = 'user_id'
        """)
        row = cursor.fetchone()
        if row:
            cursor.execute(f"ALTER TABLE bookings DROP FOREIGN KEY `{row[0]}`")

        # Align bookings.user_id type with gd_user.id (required for FK compatibility)
        cursor.execute(
            f"ALTER TABLE bookings MODIFY COLUMN user_id {ref_type} NOT NULL"
        )
        cursor.execute(
            "ALTER TABLE bookings ADD CONSTRAINT bookings_user_gd_user_fk "
            "FOREIGN KEY (user_id) REFERENCES gd_user(id) ON DELETE RESTRICT"
        )
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0006_remove_gift_voucher_order'),
        ('core', '0005_remove_users_stub'),
    ]

    operations = [
        migrations.RunPython(fix_bookings_user_fk, noop),
    ]
