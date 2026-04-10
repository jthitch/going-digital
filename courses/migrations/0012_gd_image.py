# Add gd_image table and Image model; link Course via image_id FK.

from django.db import migrations, models


CREATE_GD_IMAGE_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_image (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_type_id INTEGER NULL,
    link_to VARCHAR(200) NULL,
    image_category_id INTEGER NULL,
    active INTEGER DEFAULT 1,
    user_id INTEGER NULL,
    source_name VARCHAR(1000) NULL,
    file_name VARCHAR(1000) NOT NULL,
    description VARCHAR(1000) NULL,
    mime_type VARCHAR(20) NOT NULL,
    file_size INTEGER NOT NULL,
    height INTEGER NULL,
    width INTEGER NULL,
    checksum VARCHAR(255) NULL,
    createdby_id INTEGER NULL,
    updatedby_id INTEGER NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    converted INTEGER DEFAULT 0
);
"""

CREATE_GD_IMAGE_SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_image (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_type_id INT NULL,
    link_to VARCHAR(200) NULL,
    image_category_id INT NULL,
    active INT DEFAULT 1,
    user_id INT NULL,
    source_name VARCHAR(1000) NULL,
    file_name VARCHAR(1000) NOT NULL,
    description VARCHAR(1000) NULL,
    mime_type VARCHAR(20) NOT NULL,
    file_size INT NOT NULL,
    height INT NULL,
    width INT NULL,
    checksum VARCHAR(255) NULL,
    createdby_id INT NULL,
    updatedby_id INT NULL,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL,
    converted INT DEFAULT 0
);
"""

DROP_GD_IMAGE_SQL = "DROP TABLE IF EXISTS gd_image;"


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(CREATE_GD_IMAGE_SQL_MYSQL)
    else:
        schema_editor.execute(CREATE_GD_IMAGE_SQL_SQLITE)


def drop_table(apps, schema_editor):
    schema_editor.execute(DROP_GD_IMAGE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0011_gd_content'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Image',
                    fields=[
                        ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                        ('image_type_id', models.IntegerField(blank=True, db_column='image_type_id', null=True)),
                        ('link_to', models.CharField(blank=True, db_column='link_to', max_length=200, null=True)),
                        ('image_category_id', models.IntegerField(blank=True, db_column='image_category_id', null=True)),
                        ('active', models.SmallIntegerField(db_column='active', default=1)),
                        ('user_id', models.IntegerField(blank=True, db_column='user_id', null=True)),
                        ('source_name', models.CharField(blank=True, db_column='source_name', max_length=1000, null=True)),
                        ('file_name', models.CharField(db_column='file_name', default='', max_length=1000)),
                        ('description', models.CharField(blank=True, db_column='description', max_length=1000, null=True)),
                        ('mime_type', models.CharField(db_column='mime_type', default='image/jpeg', max_length=20)),
                        ('file_size', models.IntegerField(db_column='file_size', default=0)),
                        ('height', models.IntegerField(blank=True, db_column='height', null=True)),
                        ('width', models.IntegerField(blank=True, db_column='width', null=True)),
                        ('checksum', models.CharField(blank=True, db_column='checksum', max_length=255, null=True)),
                        ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                        ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                        ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                        ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                        ('converted', models.IntegerField(db_column='converted', default=0)),
                    ],
                    options={
                        'db_table': 'gd_image',
                        'ordering': ['id'],
                        'verbose_name': 'Image',
                        'verbose_name_plural': 'Images',
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(create_table, drop_table),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='course', name='image_id'),
                migrations.AddField(
                    model_name='course',
                    name='image',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='image_id',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='courses',
                        to='courses.image',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
