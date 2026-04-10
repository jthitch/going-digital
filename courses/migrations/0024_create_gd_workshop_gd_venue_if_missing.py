# Physical tables for Workshop and Venue (managed=False in 0017 — no DDL was emitted).
# Fresh MySQL/SQLite installs need gd_venue + gd_workshop before bookings.0003 adds FK to gd_workshop.

from django.db import migrations


CREATE_GD_VENUE_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_venue (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    active SMALLINT NOT NULL DEFAULT 1,
    status_id SMALLINT NOT NULL DEFAULT 2,
    region_id INT NULL,
    user_id INT NULL,
    content_id INT NULL,
    county_id INT NULL,
    venue_name VARCHAR(255) NOT NULL DEFAULT '',
    location VARCHAR(255) NULL,
    slug VARCHAR(255) NOT NULL DEFAULT '',
    venue_address TEXT NULL,
    venue_telephone VARCHAR(255) NULL,
    venue_url TEXT NULL,
    latitude DOUBLE NULL,
    longitude DOUBLE NULL,
    show_workshops SMALLINT NOT NULL DEFAULT 1,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

CREATE_GD_WORKSHOP_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_workshop (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    region_id INT NULL,
    user_id INT NULL,
    course_id INT NULL,
    alt_course_id INT NOT NULL DEFAULT 0,
    tutor_id INT NULL,
    assistant_id INT NULL,
    venue_id INT NULL,
    workshop_type_id INT NULL,
    cameras_available SMALLINT NOT NULL DEFAULT 0,
    number_of_loan_cameras_available INT NOT NULL DEFAULT 0,
    sticky SMALLINT NOT NULL DEFAULT 0,
    active SMALLINT NOT NULL DEFAULT 1,
    checksum VARCHAR(32) NULL,
    `date` DATETIME(6) NULL,
    cost INT NOT NULL DEFAULT 0,
    deposit_required INT NOT NULL DEFAULT 0,
    max_places INT NULL,
    places_booked INT NULL,
    strapline TEXT NULL,
    byline TEXT NULL,
    comments TEXT NULL,
    reminder_message TEXT NULL,
    approve SMALLINT NOT NULL DEFAULT 1,
    blurb VARCHAR(500) NULL,
    cloned_from_workshop_id INT NULL,
    createdby_id INT NULL,
    updatedby_id INT NULL,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL,
    image_id INT NOT NULL DEFAULT 0,
    KEY idx_gd_workshop_course_id (course_id),
    KEY idx_gd_workshop_venue_id (venue_id),
    CONSTRAINT fk_gd_workshop_course FOREIGN KEY (course_id) REFERENCES gd_course (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_gd_workshop_venue FOREIGN KEY (venue_id) REFERENCES gd_venue (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

CREATE_GD_VENUE_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_venue (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    active INTEGER NOT NULL DEFAULT 1,
    status_id INTEGER NOT NULL DEFAULT 2,
    region_id INTEGER NULL,
    user_id INTEGER NULL,
    content_id INTEGER NULL,
    county_id INTEGER NULL,
    venue_name VARCHAR(255) NOT NULL DEFAULT '',
    location VARCHAR(255) NULL,
    slug VARCHAR(255) NOT NULL DEFAULT '',
    venue_address TEXT NULL,
    venue_telephone VARCHAR(255) NULL,
    venue_url TEXT NULL,
    latitude REAL NULL,
    longitude REAL NULL,
    show_workshops INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NULL,
    updated_at DATETIME NULL
);
"""

CREATE_GD_WORKSHOP_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_workshop (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    region_id INTEGER NULL,
    user_id INTEGER NULL,
    course_id INTEGER NULL REFERENCES gd_course (id) ON DELETE CASCADE,
    alt_course_id INTEGER NOT NULL DEFAULT 0,
    tutor_id INTEGER NULL,
    assistant_id INTEGER NULL,
    venue_id INTEGER NULL REFERENCES gd_venue (id) ON DELETE SET NULL,
    workshop_type_id INTEGER NULL,
    cameras_available INTEGER NOT NULL DEFAULT 0,
    number_of_loan_cameras_available INTEGER NOT NULL DEFAULT 0,
    sticky INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    checksum VARCHAR(32) NULL,
    date DATETIME NULL,
    cost INTEGER NOT NULL DEFAULT 0,
    deposit_required INTEGER NOT NULL DEFAULT 0,
    max_places INTEGER NULL,
    places_booked INTEGER NULL,
    strapline TEXT NULL,
    byline TEXT NULL,
    comments TEXT NULL,
    reminder_message TEXT NULL,
    approve INTEGER NOT NULL DEFAULT 1,
    blurb VARCHAR(500) NULL,
    cloned_from_workshop_id INTEGER NULL,
    createdby_id INTEGER NULL,
    updatedby_id INTEGER NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    image_id INTEGER NOT NULL DEFAULT 0
);
"""


def create_tables(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == 'mysql':
            cursor.execute(CREATE_GD_VENUE_MYSQL)
            cursor.execute(CREATE_GD_WORKSHOP_MYSQL)
        elif vendor == 'sqlite':
            cursor.execute(CREATE_GD_VENUE_SQLITE)
            cursor.execute(CREATE_GD_WORKSHOP_SQLITE)
        else:
            raise NotImplementedError(
                f'0024_create_gd_workshop_gd_venue_if_missing: add DDL for {vendor!r} or use legacy import.'
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # MySQL DDL

    dependencies = [
        ('courses', '0017_workshop_venue_remove_courseinstance'),
    ]

    operations = [
        migrations.RunPython(create_tables, noop_reverse),
    ]
