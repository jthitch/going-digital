# Repoint franchisee access tables' user FKs from legacy `users` to `gd_user` (MySQL).
# Without this, saving a user with venue workshop-access grants fails with IntegrityError 1452:
#   gd_venue_workshop_access.user_id → REFERENCES users(id)

from django.db import migrations


def _gd_user_id_type(cursor):
    cursor.execute("SHOW COLUMNS FROM gd_user WHERE Field = 'id'")
    row = cursor.fetchone()
    return row[1] if row else None


def _fk_rows(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
          AND REFERENCED_TABLE_NAME IS NOT NULL
        """,
        [table_name, column_name],
    )
    return cursor.fetchall()


def _constraint_exists(cursor, table_name, constraint_name):
    cursor.execute(
        """
        SELECT CONSTRAINT_NAME
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND CONSTRAINT_NAME = %s
        """,
        [table_name, constraint_name],
    )
    return cursor.fetchone() is not None


def _table_exists(cursor, table_name):
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
        """,
        [table_name],
    )
    return cursor.fetchone() is not None


def _repoint_user_fk(
    cursor,
    *,
    table_name,
    column_name,
    new_constraint_name,
    on_delete,
    null_ok,
    gd_user_id_type,
):
    """Drop any FK on column and add one to gd_user(id) if needed."""
    if not _table_exists(cursor, table_name):
        return

    rows = _fk_rows(cursor, table_name, column_name)
    already_ok = any(ref == 'gd_user' for _name, ref in rows)
    if already_ok and not any(ref != 'gd_user' for _name, ref in rows):
        return

    for constraint_name, _ref in rows:
        cursor.execute(f'ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`')

    null_sql = 'NULL' if null_ok else 'NOT NULL'
    cursor.execute(
        f'ALTER TABLE `{table_name}` MODIFY COLUMN `{column_name}` '
        f'{gd_user_id_type} {null_sql}'
    )

    if _constraint_exists(cursor, table_name, new_constraint_name):
        cursor.execute(
            f'ALTER TABLE `{table_name}` DROP FOREIGN KEY `{new_constraint_name}`'
        )

    cursor.execute(
        f'ALTER TABLE `{table_name}` ADD CONSTRAINT `{new_constraint_name}` '
        f'FOREIGN KEY (`{column_name}`) REFERENCES gd_user(id) ON DELETE {on_delete}'
    )


def fix_franchisee_access_user_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        gd_user_id_type = _gd_user_id_type(cursor)
        if not gd_user_id_type:
            return

        cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
        try:
            _repoint_user_fk(
                cursor,
                table_name='gd_venue_workshop_access',
                column_name='user_id',
                new_constraint_name='gd_venue_workshop_access_user_gd_user_fk',
                on_delete='CASCADE',
                null_ok=False,
                gd_user_id_type=gd_user_id_type,
            )
            _repoint_user_fk(
                cursor,
                table_name='gd_venue_workshop_access',
                column_name='granted_by_id',
                new_constraint_name='gd_venue_workshop_access_granted_by_gd_user_fk',
                on_delete='SET NULL',
                null_ok=True,
                gd_user_id_type=gd_user_id_type,
            )
            _repoint_user_fk(
                cursor,
                table_name='gd_course_workshop_block',
                column_name='user_id',
                new_constraint_name='gd_course_workshop_block_user_gd_user_fk',
                on_delete='CASCADE',
                null_ok=False,
                gd_user_id_type=gd_user_id_type,
            )
            _repoint_user_fk(
                cursor,
                table_name='gd_course_workshop_block',
                column_name='blocked_by_id',
                new_constraint_name='gd_course_workshop_block_blocked_by_gd_user_fk',
                on_delete='SET NULL',
                null_ok=True,
                gd_user_id_type=gd_user_id_type,
            )
        finally:
            cursor.execute('SET FOREIGN_KEY_CHECKS = 1')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # MySQL DDL

    dependencies = [
        ('courses', '0049_venuecontentchangerequest'),
        ('core', '0006_fix_django_admin_log_user_fk'),
    ]

    operations = [
        migrations.RunPython(fix_franchisee_access_user_fks, noop_reverse),
    ]
