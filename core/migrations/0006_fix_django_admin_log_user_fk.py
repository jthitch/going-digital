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

        cursor.execute("SHOW COLUMNS FROM gd_user WHERE Field = 'id'")
        gd_user_id_col = cursor.fetchone()
        if not gd_user_id_col:
            return
        gd_user_id_type = gd_user_id_col[1]

        if row:
            constraint_name, ref_table = row
            if ref_table == 'gd_user':
                return
        else:
            constraint_name = None

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        if constraint_name:
            cursor.execute(f"ALTER TABLE django_admin_log DROP FOREIGN KEY `{constraint_name}`")
        cursor.execute(
            f"ALTER TABLE django_admin_log MODIFY COLUMN user_id {gd_user_id_type} NOT NULL"
        )
        cursor.execute(
            "SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'django_admin_log' "
            "AND CONSTRAINT_NAME = 'django_admin_log_user_gd_user_fk'"
        )
        if cursor.fetchone():
            cursor.execute(
                "ALTER TABLE django_admin_log DROP FOREIGN KEY django_admin_log_user_gd_user_fk"
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
