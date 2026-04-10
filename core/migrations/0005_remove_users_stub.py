# Remove users stub table - payments and other FKs should reference gd_user.
# 1. Alter payments FK from users to gd_user (MySQL only - constraint may reference users)
# 2. Drop users table

from django.db import migrations


def remove_users_stub(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == 'mysql':
            # Must match BIGINT FKs (e.g. payments.user_id from BigAutoField User in 0001).
            # Older 0002 used INT for gd_user.id; widen before adding FK to gd_user.
            cursor.execute(
                "ALTER TABLE gd_user MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT"
            )
            # Get FK constraint name (Django uses table_column_hash_fk_reftable_id format)
            cursor.execute("""
                SELECT CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'payments'
                  AND REFERENCED_TABLE_NAME = 'users'
                  AND REFERENCED_COLUMN_NAME = 'id'
            """)
            row = cursor.fetchone()
            if row:
                constraint_name = row[0]
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                cursor.execute(
                    f"ALTER TABLE payments DROP FOREIGN KEY `{constraint_name}`"
                )
                cursor.execute(
                    "ALTER TABLE payments ADD CONSTRAINT payments_user_gd_user_fk "
                    "FOREIGN KEY (user_id) REFERENCES gd_user(id) ON DELETE RESTRICT"
                )
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        # Drop users table (both MySQL and SQLite)
        if vendor == 'sqlite':
            cursor.execute("PRAGMA foreign_keys=OFF")
        elif vendor == 'mysql':
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        cursor.execute("DROP TABLE IF EXISTS users")

        if vendor == 'sqlite':
            cursor.execute("PRAGMA foreign_keys=ON")
        elif vendor == 'mysql':
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def reverse_remove_users_stub(apps, schema_editor):
    """Reverse: recreate users stub (requires 0003/0004 logic). Not fully implemented."""
    raise NotImplementedError(
        "Cannot reverse: users table removal. Run 0003/0004 to recreate if needed."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_users_stub_mysql'),
    ]

    operations = [
        migrations.RunPython(remove_users_stub, reverse_remove_users_stub),
    ]
