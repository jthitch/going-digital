# Fix course_instances FK: it references "courses" but Course model uses "gd_course".
# Recreate the table with FK to gd_course.

from django.db import migrations


def fix_fk_forward_sqlite(apps, schema_editor):
    """SQLite: Recreate course_instances with FK to gd_course."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE course_instances_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                start_date DATETIME NOT NULL,
                end_date DATETIME NOT NULL,
                enrollment_open BOOL NOT NULL,
                current_students INTEGER UNSIGNED NOT NULL CHECK (current_students >= 0),
                price_override DECIMAL NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                course_id INTEGER NOT NULL REFERENCES gd_course(id) DEFERRABLE INITIALLY DEFERRED,
                location_id BIGINT NOT NULL REFERENCES locations(id) DEFERRABLE INITIALLY DEFERRED,
                instructor_id BIGINT NULL REFERENCES instructors(id) DEFERRABLE INITIALLY DEFERRED
            )
        """)
        cursor.execute("""
            INSERT INTO course_instances_new
            SELECT ci.id, ci.start_date, ci.end_date, ci.enrollment_open, ci.current_students,
                   ci.price_override, ci.created_at, ci.updated_at, ci.course_id, ci.location_id, ci.instructor_id
            FROM course_instances ci
            WHERE ci.course_id IN (SELECT id FROM gd_course)
        """)
        cursor.execute("DROP TABLE course_instances")
        cursor.execute("ALTER TABLE course_instances_new RENAME TO course_instances")
        cursor.execute(
            "CREATE INDEX course_inst_start_d_17dd5a_idx ON course_instances (start_date, location_id)"
        )
        cursor.execute(
            "CREATE INDEX course_inst_course__123e20_idx ON course_instances (course_id, location_id)"
        )


def fix_fk_forward_mysql(apps, schema_editor):
    """MySQL: Recreate course_instances with FK to gd_course."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE course_instances_new (
                id INT AUTO_INCREMENT PRIMARY KEY,
                start_date DATETIME(6) NOT NULL,
                end_date DATETIME(6) NOT NULL,
                enrollment_open TINYINT(1) NOT NULL,
                current_students INT UNSIGNED NOT NULL,
                price_override DECIMAL(10,2) NULL,
                created_at DATETIME(6) NOT NULL,
                updated_at DATETIME(6) NOT NULL,
                course_id INT NOT NULL,
                location_id BIGINT NOT NULL,
                instructor_id BIGINT NULL,
                CONSTRAINT fk_ci_course FOREIGN KEY (course_id) REFERENCES gd_course(id),
                CONSTRAINT fk_ci_location FOREIGN KEY (location_id) REFERENCES locations(id),
                CONSTRAINT fk_ci_instructor FOREIGN KEY (instructor_id) REFERENCES instructors(id)
            )
        """)
        cursor.execute("""
            INSERT INTO course_instances_new
            (id, start_date, end_date, enrollment_open, current_students, price_override,
             created_at, updated_at, course_id, location_id, instructor_id)
            SELECT ci.id, ci.start_date, ci.end_date, ci.enrollment_open, ci.current_students,
                   ci.price_override, ci.created_at, ci.updated_at, ci.course_id, ci.location_id, ci.instructor_id
            FROM course_instances ci
            WHERE ci.course_id IN (SELECT id FROM gd_course)
        """)
        cursor.execute("DROP TABLE course_instances")
        cursor.execute("RENAME TABLE course_instances_new TO course_instances")
        cursor.execute(
            "CREATE INDEX course_inst_start_d_17dd5a_idx ON course_instances (start_date, location_id)"
        )
        cursor.execute(
            "CREATE INDEX course_inst_course__123e20_idx ON course_instances (course_id, location_id)"
        )


def fix_fk_forward(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == 'sqlite':
        fix_fk_forward_sqlite(apps, schema_editor)
    elif vendor == 'mysql':
        fix_fk_forward_mysql(apps, schema_editor)
    else:
        raise NotImplementedError(f'Migration does not support {vendor}.')


def fix_fk_reverse(apps, schema_editor):
    """Reverse: recreate with FK to courses (for rollback - SQLite only)."""
    if schema_editor.connection.vendor != 'sqlite':
        raise NotImplementedError('Reverse only supported for SQLite.')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE course_instances_old (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                start_date DATETIME NOT NULL,
                end_date DATETIME NOT NULL,
                enrollment_open BOOL NOT NULL,
                current_students INTEGER UNSIGNED NOT NULL CHECK (current_students >= 0),
                price_override DECIMAL NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                course_id BIGINT NOT NULL REFERENCES courses(id) DEFERRABLE INITIALLY DEFERRED,
                location_id BIGINT NOT NULL REFERENCES locations(id) DEFERRABLE INITIALLY DEFERRED,
                instructor_id BIGINT NULL REFERENCES instructors(id) DEFERRABLE INITIALLY DEFERRED
            )
        """)
        cursor.execute("""
            INSERT INTO course_instances_old
            SELECT * FROM course_instances
        """)
        cursor.execute("DROP TABLE course_instances")
        cursor.execute("ALTER TABLE course_instances_old RENAME TO course_instances")
        cursor.execute(
            "CREATE INDEX course_inst_start_d_17dd5a_idx ON course_instances (start_date, location_id)"
        )
        cursor.execute(
            "CREATE INDEX course_inst_course__123e20_idx ON course_instances (course_id, location_id)"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0015_backfill_course_created_at'),
    ]

    operations = [
        migrations.RunPython(fix_fk_forward, fix_fk_reverse),
    ]
