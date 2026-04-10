# Add gd_course_category table and CourseCategory model; link Course via FK.

from django.db import migrations, models


# SQLite-compatible CREATE TABLE for gd_course_category
CREATE_GD_COURSE_CATEGORY_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_course_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    active INTEGER DEFAULT 1,
    parent_id INTEGER NULL REFERENCES gd_course_category(id),
    exclude_from_course_list INTEGER DEFAULT 0,
    course_category VARCHAR(255) NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 99,
    createdby_id INTEGER NULL,
    updatedby_id INTEGER NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL
);
"""

# MySQL-compatible (self-referential FK added after table exists)
CREATE_GD_COURSE_CATEGORY_SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_course_category (
    id INT AUTO_INCREMENT PRIMARY KEY,
    active INT DEFAULT 1,
    parent_id INT NULL,
    exclude_from_course_list INT DEFAULT 0,
    course_category VARCHAR(255) NOT NULL DEFAULT '',
    display_order INT NOT NULL DEFAULT 99,
    createdby_id INT NULL,
    updatedby_id INT NULL,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL
);
"""

DROP_GD_COURSE_CATEGORY_SQL = "DROP TABLE IF EXISTS gd_course_category;"


def create_gd_course_category_table(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(CREATE_GD_COURSE_CATEGORY_SQL_MYSQL)
    else:
        schema_editor.execute(CREATE_GD_COURSE_CATEGORY_SQL_SQLITE)


def drop_gd_course_category_table(apps, schema_editor):
    schema_editor.execute(DROP_GD_COURSE_CATEGORY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_gd_course_structure'),
    ]

    operations = [
        # Create gd_course_category table and CourseCategory model
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='CourseCategory',
                    fields=[
                        ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                        ('active', models.IntegerField(db_column='active', default=1)),
                        ('exclude_from_course_list', models.SmallIntegerField(db_column='exclude_from_course_list', default=0)),
                        ('course_category', models.CharField(db_column='course_category', default='', max_length=255)),
                        ('display_order', models.IntegerField(db_column='display_order', default=99)),
                        ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                        ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                        ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                        ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                        ('parent', models.ForeignKey(
                            blank=True,
                            db_column='parent_id',
                            null=True,
                            on_delete=models.deletion.SET_NULL,
                            related_name='children',
                            to='courses.coursecategory',
                        )),
                    ],
                    options={
                        'db_table': 'gd_course_category',
                        'ordering': ['display_order', 'course_category'],
                        'verbose_name': 'Course category',
                        'verbose_name_plural': 'Course categories',
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(create_gd_course_category_table, drop_gd_course_category_table),
            ],
        ),
        # Replace Course.course_category_id (IntegerField) with course_category (ForeignKey); column unchanged
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='course', name='course_category_id'),
                migrations.AddField(
                    model_name='course',
                    name='course_category',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='course_category_id',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='courses',
                        to='courses.coursecategory',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
