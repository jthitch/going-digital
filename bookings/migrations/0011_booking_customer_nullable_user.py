import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _mysql_booking_customer_nullable_user(schema_editor):
    """Add customer_id and nullable user_id with compatible FK types on MySQL."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'gd_user'
              AND COLUMN_NAME = 'id'
            """
        )
        user_id_row = cursor.fetchone()
        user_id_type = user_id_row[0] if user_id_row else 'bigint'

        cursor.execute(
            """
            SELECT COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'gd_customer'
              AND COLUMN_NAME = 'id'
            """
        )
        customer_id_row = cursor.fetchone()
        customer_id_type = customer_id_row[0] if customer_id_row else 'int'

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'bookings'
              AND COLUMN_NAME = 'user_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """
        )
        for (constraint_name,) in cursor.fetchall():
            cursor.execute(f"ALTER TABLE bookings DROP FOREIGN KEY `{constraint_name}`")

        cursor.execute(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'bookings'
              AND COLUMN_NAME = 'customer_id'
            """
        )
        if not cursor.fetchone():
            cursor.execute(
                f"ALTER TABLE bookings ADD COLUMN customer_id {customer_id_type} NULL"
            )

        cursor.execute(
            """
            SELECT 1
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'bookings'
              AND CONSTRAINT_NAME = 'bookings_customer_gd_customer_fk'
            """
        )
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE bookings ADD CONSTRAINT bookings_customer_gd_customer_fk "
                "FOREIGN KEY (customer_id) REFERENCES gd_customer(id) ON DELETE RESTRICT"
            )

        cursor.execute(
            f"ALTER TABLE bookings MODIFY COLUMN user_id {user_id_type} NULL"
        )

        cursor.execute(
            """
            SELECT 1
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'bookings'
              AND CONSTRAINT_NAME = 'bookings_user_gd_user_fk'
            """
        )
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE bookings ADD CONSTRAINT bookings_user_gd_user_fk "
                "FOREIGN KEY (user_id) REFERENCES gd_user(id) ON DELETE RESTRICT"
            )

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def _generic_booking_customer_nullable_user(apps, schema_editor):
    """SQLite / PostgreSQL: use schema editor for the column changes."""
    Booking = apps.get_model('bookings', 'Booking')
    Customer = apps.get_model('core', 'Customer')

    customer_field = models.ForeignKey(
        Customer,
        on_delete=django.db.models.deletion.PROTECT,
        related_name='bookings',
        null=True,
        blank=True,
    )
    customer_field.set_attributes_from_name('customer')

    table = Booking._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor == 'sqlite':
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
        else:
            cursor.execute(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                """,
                [table],
            )
            columns = {row[0] for row in cursor.fetchall()}

    if 'customer_id' not in columns:
        schema_editor.add_field(Booking, customer_field)

    user_field = Booking._meta.get_field('user')
    user_field.null = True
    user_field.blank = True
    schema_editor.alter_field(Booking, user_field, user_field)


def apply_booking_customer_nullable_user(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        _mysql_booking_customer_nullable_user(schema_editor)
    else:
        _generic_booking_customer_nullable_user(apps, schema_editor)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0010_booking_payment_fk'),
        ('core', '0007_customer'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='booking',
                    name='customer',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='bookings',
                        to='core.customer',
                    ),
                ),
                migrations.AlterField(
                    model_name='booking',
                    name='user',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='bookings',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(apply_booking_customer_nullable_user, noop),
            ],
        ),
    ]
