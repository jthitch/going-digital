# Migration: adopt gd_course table structure for Course model (legacy DB integration)
# Creates gd_course table and updates Django model state to match.

from django.db import migrations, models


# MySQL-compatible DDL for gd_course
CREATE_GD_COURSE_SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_course (
    id INT AUTO_INCREMENT PRIMARY KEY,
    CID INT NULL,
    active SMALLINT DEFAULT 1,
    status_id SMALLINT DEFAULT 2,
    clickable SMALLINT DEFAULT 0,
    course_category_id INT NULL,
    course_skill_level_id INT NULL,
    content_id INT NULL,
    image_id INT NULL,
    region_id INT NULL,
    is_one_to_one SMALLINT DEFAULT 0,
    show_workshops SMALLINT DEFAULT 1,
    display_order INT DEFAULT 99,
    use_on_filter SMALLINT DEFAULT 1,
    course_name VARCHAR(255) NOT NULL,
    course_abbr VARCHAR(16) NULL,
    course_description TEXT NULL,
    description_for_workshop TEXT NULL,
    slug VARCHAR(255) NULL UNIQUE,
    link_name VARCHAR(255) NULL,
    link_title VARCHAR(255) NULL,
    filter_name VARCHAR(255) NULL,
    page_title VARCHAR(1000) NULL,
    createdby_id INT NULL,
    updatedby_id INT NULL,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL,
    workshop_image_id INT DEFAULT 0
);
"""

# SQLite uses INTEGER not SMALLINT - use a simpler version for maximum compatibility
CREATE_GD_COURSE_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_course (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    CID INTEGER NULL,
    active INTEGER DEFAULT 1,
    status_id INTEGER DEFAULT 2,
    clickable INTEGER DEFAULT 0,
    course_category_id INTEGER NULL,
    course_skill_level_id INTEGER NULL,
    content_id INTEGER NULL,
    image_id INTEGER NULL,
    region_id INTEGER NULL,
    is_one_to_one INTEGER DEFAULT 0,
    show_workshops INTEGER DEFAULT 1,
    display_order INTEGER DEFAULT 99,
    use_on_filter INTEGER DEFAULT 1,
    course_name VARCHAR(255) NOT NULL,
    course_abbr VARCHAR(16) NULL,
    course_description TEXT NULL,
    description_for_workshop TEXT NULL,
    slug VARCHAR(255) NULL UNIQUE,
    link_name VARCHAR(255) NULL,
    link_title VARCHAR(255) NULL,
    filter_name VARCHAR(255) NULL,
    page_title VARCHAR(1000) NULL,
    createdby_id INTEGER NULL,
    updatedby_id INTEGER NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    workshop_image_id INTEGER DEFAULT 0
);
"""

DROP_GD_COURSE_SQL = "DROP TABLE IF EXISTS gd_course;"


def create_gd_course(apps, schema_editor):
    """Create gd_course table; SQLite or MySQL DDL."""
    if schema_editor.connection.vendor == 'sqlite':
        schema_editor.execute(CREATE_GD_COURSE_SQL_SQLITE)
    elif schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(CREATE_GD_COURSE_SQL_MYSQL)
    else:
        schema_editor.execute(CREATE_GD_COURSE_SQL_SQLITE)


def drop_gd_course(apps, schema_editor):
    schema_editor.execute(DROP_GD_COURSE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0007_remove_website_models'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Course'),
                migrations.CreateModel(
                    name='Course',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('CID', models.IntegerField(blank=True, db_column='CID', null=True)),
                        ('active', models.BooleanField(db_column='active', default=True)),
                        ('status_id', models.SmallIntegerField(db_column='status_id', default=2)),
                        ('clickable', models.BooleanField(db_column='clickable', default=False)),
                        ('course_category_id', models.IntegerField(blank=True, db_column='course_category_id', null=True)),
                        ('course_skill_level_id', models.IntegerField(blank=True, db_column='course_skill_level_id', null=True)),
                        ('content_id', models.IntegerField(blank=True, db_column='content_id', null=True)),
                        ('image_id', models.IntegerField(blank=True, db_column='image_id', null=True)),
                        ('region_id', models.IntegerField(blank=True, db_column='region_id', null=True)),
                        ('is_one_to_one', models.SmallIntegerField(db_column='is_one_to_one', default=0)),
                        ('show_workshops', models.BooleanField(db_column='show_workshops', default=True)),
                        ('display_order', models.IntegerField(db_column='display_order', default=99)),
                        ('use_on_filter', models.BooleanField(db_column='use_on_filter', default=True)),
                        ('course_name', models.CharField(db_column='course_name', max_length=255)),
                        ('course_abbr', models.CharField(blank=True, db_column='course_abbr', max_length=16, null=True)),
                        ('course_description', models.TextField(blank=True, db_column='course_description', null=True)),
                        ('description_for_workshop', models.TextField(blank=True, db_column='description_for_workshop', null=True)),
                        ('slug', models.SlugField(blank=True, db_column='slug', max_length=255, null=True, unique=True)),
                        ('link_name', models.CharField(blank=True, db_column='link_name', max_length=255, null=True)),
                        ('link_title', models.CharField(blank=True, db_column='link_title', max_length=255, null=True)),
                        ('filter_name', models.CharField(blank=True, db_column='filter_name', max_length=255, null=True)),
                        ('page_title', models.CharField(blank=True, db_column='page_title', max_length=1000, null=True)),
                        ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                        ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                        ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                        ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                        ('workshop_image_id', models.IntegerField(db_column='workshop_image_id', default=0)),
                    ],
                    options={
                        'db_table': 'gd_course',
                        'ordering': ['display_order', 'course_name'],
                        'verbose_name': 'Course',
                        'verbose_name_plural': 'Courses',
                    },
                ),
                # Re-add FK from CourseInstance to Course (Django may have removed it when Course was deleted)
                migrations.AlterField(
                    model_name='courseinstance',
                    name='course',
                    field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='instances', to='courses.course'),
                ),
            ],
            database_operations=[
                migrations.RunPython(create_gd_course, drop_gd_course),
            ],
        ),
    ]
