"""
Repoint django_admin_log.user_id FK from legacy `users` to `gd_user`.
Run: python scripts/fix_admin_log_user_fk.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'photocourses.settings')
django.setup()

from django.db import connection


def fix():
    if connection.vendor != 'mysql':
        print('This fix is for MySQL only.')
        return
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'django_admin_log'
              AND COLUMN_NAME = 'user_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        row = cursor.fetchone()

        cursor.execute('SHOW COLUMNS FROM gd_user WHERE Field = %s', ['id'])
        gd_user_id_col = cursor.fetchone()
        if not gd_user_id_col:
            raise SystemExit('gd_user.id column not found')
        gd_user_id_type = gd_user_id_col[1]
        print(f'gd_user.id type: {gd_user_id_type}')

        if row:
            constraint_name, ref_table = row[0], row[1]
            print(f'Current FK: {constraint_name} -> {ref_table}')
            if ref_table == 'gd_user':
                print('Already points to gd_user.')
                return
        else:
            print('No user_id FK on django_admin_log; will add FK to gd_user.')
            constraint_name = None

        cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
        if constraint_name:
            cursor.execute(f'ALTER TABLE django_admin_log DROP FOREIGN KEY `{constraint_name}`')
        cursor.execute(
            f'ALTER TABLE django_admin_log MODIFY COLUMN user_id {gd_user_id_type} NOT NULL'
        )
        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'django_admin_log'
              AND CONSTRAINT_NAME = 'django_admin_log_user_gd_user_fk'
        """)
        if cursor.fetchone():
            cursor.execute(
                'ALTER TABLE django_admin_log DROP FOREIGN KEY django_admin_log_user_gd_user_fk'
            )
        cursor.execute(
            'ALTER TABLE django_admin_log ADD CONSTRAINT django_admin_log_user_gd_user_fk '
            'FOREIGN KEY (user_id) REFERENCES gd_user(id) ON DELETE CASCADE'
        )
        cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
        print('Fixed: django_admin_log.user_id now references gd_user(id).')


if __name__ == '__main__':
    fix()
