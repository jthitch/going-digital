import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'photocourses.settings')
django.setup()

from django.db import connection

with connection.cursor() as c:
    c.execute("""
        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'django_admin_log'
          AND COLUMN_NAME = 'user_id'
          AND REFERENCED_TABLE_NAME IS NOT NULL
    """)
    print('django_admin_log FK:', c.fetchall())
    c.execute("SHOW TABLES LIKE 'users'")
    print('users table:', c.fetchall())
    c.execute("SHOW TABLES LIKE 'gd_user'")
    print('gd_user table:', c.fetchall())
    c.execute("SELECT id, email FROM gd_user ORDER BY id LIMIT 5")
    print('gd_user sample:', c.fetchall())
