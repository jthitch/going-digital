# Add gd_course_skill_level table and CourseSkillLevel model; link Course via FK.

from django.db import migrations, models


CREATE_GD_COURSE_SKILL_LEVEL_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_course_skill_level (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    active INTEGER DEFAULT 1,
    skill_level VARCHAR(255) NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0,
    createdby_id INTEGER NULL,
    updatedby_id INTEGER NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL
);
"""

CREATE_GD_COURSE_SKILL_LEVEL_SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_course_skill_level (
    id INT AUTO_INCREMENT PRIMARY KEY,
    active INT DEFAULT 1,
    skill_level VARCHAR(255) NOT NULL DEFAULT '',
    display_order INT NOT NULL DEFAULT 0,
    createdby_id INT NULL,
    updatedby_id INT NULL,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL
);
"""

DROP_GD_COURSE_SKILL_LEVEL_SQL = "DROP TABLE IF EXISTS gd_course_skill_level;"


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(CREATE_GD_COURSE_SKILL_LEVEL_SQL_MYSQL)
    else:
        schema_editor.execute(CREATE_GD_COURSE_SKILL_LEVEL_SQL_SQLITE)


def drop_table(apps, schema_editor):
    schema_editor.execute(DROP_GD_COURSE_SKILL_LEVEL_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0009_gd_course_category'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='CourseSkillLevel',
                    fields=[
                        ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                        ('active', models.IntegerField(db_column='active', default=1)),
                        ('skill_level', models.CharField(db_column='skill_level', default='', max_length=255)),
                        ('display_order', models.IntegerField(db_column='display_order', default=0)),
                        ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                        ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                        ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                        ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                    ],
                    options={
                        'db_table': 'gd_course_skill_level',
                        'ordering': ['display_order', 'skill_level'],
                        'verbose_name': 'Course skill level',
                        'verbose_name_plural': 'Course skill levels',
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(create_table, drop_table),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='course', name='course_skill_level_id'),
                migrations.AddField(
                    model_name='course',
                    name='course_skill_level',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='course_skill_level_id',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='courses',
                        to='courses.courseskilllevel',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
