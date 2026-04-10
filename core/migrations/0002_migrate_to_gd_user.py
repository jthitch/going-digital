# Migration: Replace users table with gd_user
# 1. Copy Django users into gd_user (overwrite rows with same id)
# 2. Drop users table
# 3. Update model state to use gd_user

from django.db import migrations, models


def migrate_users_to_gd_user_sqlite(apps, schema_editor):
    """SQLite: Copy users into gd_user, then drop users."""
    raw_conn = schema_editor.connection.connection
    raw_conn.execute("PRAGMA foreign_keys=OFF")
    cursor = raw_conn.cursor()
    cursor.execute("""
        SELECT id, password, last_login, username, first_name, last_name, email,
               is_staff, is_active, is_superuser, date_joined, role, created_at, updated_at
        FROM users
    """)
    rows = cursor.fetchall()
    for row in rows:
        (uid, password, last_login, username, first_name, last_name, email,
         is_staff, is_active, is_superuser, date_joined, role, created_at, updated_at) = row
        if is_superuser:
            user_type_id = 1
        elif is_staff:
            user_type_id = 2
        elif role == 'franchise_owner':
            user_type_id = 3
        else:
            user_type_id = 3
        active = 1 if is_active else 0
        firstname = first_name or ''
        lastname = last_name or ''
        email = email or username or ''
        cursor.execute("""
            INSERT OR REPLACE INTO gd_user
            (id, firstname, lastname, email, password, active, user_type_id,
             last_login_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, firstname, lastname, email, password, active, user_type_id,
              last_login, created_at, updated_at))
    raw_conn.commit()


def migrate_users_to_gd_user_mysql(apps, schema_editor):
    """MySQL: Create gd_user if needed, copy users into gd_user, then drop users."""
    cursor = schema_editor.connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gd_user (
            id INT AUTO_INCREMENT PRIMARY KEY,
            firstname VARCHAR(255) DEFAULT '',
            lastname VARCHAR(255) DEFAULT '',
            email VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL DEFAULT '',
            FID INT NULL, RID INT NULL, user_type_id INT NULL, region_id INT NULL,
            active SMALLINT DEFAULT 1, is_franchisee SMALLINT NULL, guid VARCHAR(32) NULL,
            secure_code VARCHAR(255) NULL, company VARCHAR(255) NULL, address TEXT NULL,
            address1 VARCHAR(255) NULL, address2 VARCHAR(255) NULL, town_city VARCHAR(255) NULL,
            postcode VARCHAR(255) NULL, telephone VARCHAR(255) NULL, mobile VARCHAR(255) NULL,
            last_login_date DATETIME NULL, created_at DATETIME NULL, updated_at DATETIME NULL,
            UNIQUE KEY (email)
        )
    """)
    cursor.execute("""
        INSERT INTO gd_user
        (id, firstname, lastname, email, password, active, user_type_id,
         last_login_date, created_at, updated_at)
        SELECT id, COALESCE(first_name,''), COALESCE(last_name,''),
               COALESCE(email, username, ''),
               COALESCE(password, ''),
               IF(is_active, 1, 0),
               CASE WHEN is_superuser THEN 1 WHEN is_staff THEN 2 ELSE 3 END,
               last_login, created_at, updated_at
        FROM users
        ON DUPLICATE KEY UPDATE
            firstname=VALUES(firstname), lastname=VALUES(lastname), email=VALUES(email),
            password=VALUES(password), active=VALUES(active), user_type_id=VALUES(user_type_id),
            last_login_date=VALUES(last_login_date), created_at=VALUES(created_at), updated_at=VALUES(updated_at)
    """)
    # MySQL: disable FK checks to drop users (auth tables reference it)
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def migrate_users_to_gd_user(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == 'sqlite':
        migrate_users_to_gd_user_sqlite(apps, schema_editor)
    elif vendor == 'mysql':
        migrate_users_to_gd_user_mysql(apps, schema_editor)
    else:
        raise NotImplementedError(f'Migration does not support {vendor}.')


def reverse_migrate(apps, schema_editor):
    """Reverse: cannot restore users from gd_user (schema differs)."""
    raise NotImplementedError("Cannot reverse migration from gd_user to users.")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_users_to_gd_user, reverse_migrate),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS users;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='User'),
                migrations.CreateModel(
                    name='User',
                    fields=[
                        ('id', models.AutoField(primary_key=True, serialize=False, db_column='id')),
                        ('password', models.CharField(max_length=255, db_column='password')),
                        ('last_login', models.DateTimeField(null=True, blank=True, db_column='last_login_date')),
                        ('FID', models.IntegerField(null=True, blank=True, db_column='FID')),
                        ('RID', models.IntegerField(null=True, blank=True, db_column='RID')),
                        ('user_type_id', models.IntegerField(null=True, blank=True, db_column='user_type_id')),
                        ('region_id', models.IntegerField(null=True, blank=True, db_column='region_id')),
                        ('active', models.SmallIntegerField(default=1, db_column='active')),
                        ('firstname', models.CharField(max_length=255, default='', db_column='firstname')),
                        ('lastname', models.CharField(max_length=255, default='', db_column='lastname')),
                        ('email', models.CharField(max_length=255, unique=True, db_column='email')),
                        ('telephone', models.CharField(max_length=255, null=True, blank=True, db_column='telephone')),
                        ('mobile', models.CharField(max_length=255, null=True, blank=True, db_column='mobile')),
                        ('created_at', models.DateTimeField(null=True, blank=True, db_column='created_at')),
                        ('updated_at', models.DateTimeField(null=True, blank=True, db_column='updated_at')),
                    ],
                    options={'db_table': 'gd_user', 'managed': False, 'ordering': ['-created_at']},
                    managers=[],
                ),
            ],
        ),
    ]
