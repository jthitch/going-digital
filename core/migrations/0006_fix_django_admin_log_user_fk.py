# Repoint django_admin_log.user_id from legacy `users` to gd_user (MySQL).
# After core.0005 drops `users`, admin actions still referenced users(id) and fail with 1452.

from django.db import migrations


def fix_django_admin_log_user_fk(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'django_admin_log'
              AND COLUMN_NAME = 'user_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        row = cursor.fetchone()
        if not row:
            return
        constraint_name, ref_table = row
        if ref_table == 'gd_user':
            return

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute(f"ALTER TABLE django_admin_log DROP FOREIGN KEY `{constraint_name}`")
        # Match gd_user.id (BIGINT) and payments.user_id; LogEntry.user is CASCADE.
        cursor.execute(
            "ALTER TABLE django_admin_log MODIFY COLUMN user_id BIGINT NOT NULL"
        )
        cursor.execute(
            "ALTER TABLE django_admin_log ADD CONSTRAINT django_admin_log_user_gd_user_fk "
            "FOREIGN KEY (user_id) REFERENCES gd_user(id) ON DELETE CASCADE"
        )
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # MySQL DDL

    dependencies = [
        ('core', '0005_remove_users_stub'),
        ('admin', '0003_logentry_add_action_flag_choices'),
    ]

    operations = [
        migrations.RunPython(fix_django_admin_log_user_fk, noop_reverse),
    ]
