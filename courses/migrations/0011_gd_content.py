# Add gd_content table and Content model; link Course via content_id FK.

from django.db import migrations, models


CREATE_GD_CONTENT_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS gd_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type_id INTEGER NULL,
    content_master_ref_id INTEGER NULL,
    parent_id INTEGER NULL REFERENCES gd_content(id),
    active INTEGER NOT NULL DEFAULT 1,
    exclude_from_search INTEGER DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0,
    header_image_type INTEGER DEFAULT 1,
    PageTitleX VARCHAR(1000) NULL,
    content_title VARCHAR(1000) NULL,
    header_image_id INTEGER NULL,
    header_content TEXT NULL,
    strapline TEXT NULL,
    main_content TEXT NULL,
    sub_content TEXT NULL,
    side_content TEXT NULL,
    footer_content TEXT NULL,
    youtube_code VARCHAR(255) NULL,
    meta_image_id INTEGER NULL,
    meta_title TEXT NULL,
    meta_description TEXT NULL,
    meta_keywords TEXT NULL,
    social_title TEXT NULL,
    search_keywords TEXT NULL,
    change_frequency_id INTEGER DEFAULT 3,
    createdby_id INTEGER NULL,
    updatedby_id INTEGER NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    date_last_viewed DATETIME NULL,
    video_url VARCHAR(200) NULL,
    video_inline INTEGER NULL,
    video_image_id INTEGER NULL
);
"""

CREATE_GD_CONTENT_SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS gd_content (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content_type_id INT NULL,
    content_master_ref_id INT NULL,
    parent_id INT NULL,
    active INT NOT NULL DEFAULT 1,
    exclude_from_search INT DEFAULT 0,
    requests INT NOT NULL DEFAULT 0,
    header_image_type INT DEFAULT 1,
    PageTitleX VARCHAR(1000) NULL,
    content_title VARCHAR(1000) NULL,
    header_image_id INT NULL,
    header_content TEXT NULL,
    strapline TEXT NULL,
    main_content TEXT NULL,
    sub_content TEXT NULL,
    side_content TEXT NULL,
    footer_content TEXT NULL,
    youtube_code VARCHAR(255) NULL,
    meta_image_id INT NULL,
    meta_title TEXT NULL,
    meta_description TEXT NULL,
    meta_keywords TEXT NULL,
    social_title TEXT NULL,
    search_keywords TEXT NULL,
    change_frequency_id INT DEFAULT 3,
    createdby_id INT NULL,
    updatedby_id INT NULL,
    created_at DATETIME(6) NULL,
    updated_at DATETIME(6) NULL,
    date_last_viewed DATETIME(6) NULL,
    video_url VARCHAR(200) NULL,
    video_inline INT NULL,
    video_image_id INT NULL
);
"""

DROP_GD_CONTENT_SQL = "DROP TABLE IF EXISTS gd_content;"


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        schema_editor.execute(CREATE_GD_CONTENT_SQL_MYSQL)
    else:
        schema_editor.execute(CREATE_GD_CONTENT_SQL_SQLITE)


def drop_table(apps, schema_editor):
    schema_editor.execute(DROP_GD_CONTENT_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0010_gd_course_skill_level'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Content',
                    fields=[
                        ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                        ('content_type_id', models.IntegerField(blank=True, db_column='content_type_id', null=True)),
                        ('content_master_ref_id', models.IntegerField(blank=True, db_column='content_master_ref_id', null=True)),
                        ('active', models.SmallIntegerField(db_column='active', default=1)),
                        ('exclude_from_search', models.SmallIntegerField(db_column='exclude_from_search', default=0)),
                        ('requests', models.IntegerField(db_column='requests', default=0)),
                        ('header_image_type', models.SmallIntegerField(db_column='header_image_type', default=1)),
                        ('PageTitleX', models.CharField(blank=True, db_column='PageTitleX', max_length=1000, null=True)),
                        ('content_title', models.CharField(blank=True, db_column='content_title', max_length=1000, null=True)),
                        ('header_image_id', models.IntegerField(blank=True, db_column='header_image_id', null=True)),
                        ('header_content', models.TextField(blank=True, db_column='header_content', null=True)),
                        ('strapline', models.TextField(blank=True, db_column='strapline', null=True)),
                        ('main_content', models.TextField(blank=True, db_column='main_content', null=True)),
                        ('sub_content', models.TextField(blank=True, db_column='sub_content', null=True)),
                        ('side_content', models.TextField(blank=True, db_column='side_content', null=True)),
                        ('footer_content', models.TextField(blank=True, db_column='footer_content', null=True)),
                        ('youtube_code', models.CharField(blank=True, db_column='youtube_code', max_length=255, null=True)),
                        ('meta_image_id', models.IntegerField(blank=True, db_column='meta_image_id', null=True)),
                        ('meta_title', models.TextField(blank=True, db_column='meta_title', null=True)),
                        ('meta_description', models.TextField(blank=True, db_column='meta_description', null=True)),
                        ('meta_keywords', models.TextField(blank=True, db_column='meta_keywords', null=True)),
                        ('social_title', models.TextField(blank=True, db_column='social_title', null=True)),
                        ('search_keywords', models.TextField(blank=True, db_column='search_keywords', null=True)),
                        ('change_frequency_id', models.IntegerField(db_column='change_frequency_id', default=3)),
                        ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                        ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                        ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                        ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                        ('date_last_viewed', models.DateTimeField(blank=True, db_column='date_last_viewed', null=True)),
                        ('video_url', models.CharField(blank=True, db_column='video_url', max_length=200, null=True)),
                        ('video_inline', models.IntegerField(blank=True, db_column='video_inline', null=True)),
                        ('video_image_id', models.IntegerField(blank=True, db_column='video_image_id', null=True)),
                        ('parent', models.ForeignKey(
                            blank=True,
                            db_column='parent_id',
                            null=True,
                            on_delete=models.deletion.SET_NULL,
                            related_name='children',
                            to='courses.content',
                        )),
                    ],
                    options={
                        'db_table': 'gd_content',
                        'ordering': ['id'],
                        'verbose_name': 'Content',
                        'verbose_name_plural': 'Content',
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(create_table, drop_table),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='course', name='content_id'),
                migrations.AddField(
                    model_name='course',
                    name='content',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='content_id',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='courses',
                        to='courses.content',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
