# Register legacy gd_image_category table (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0030_image_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageCategory',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('image_type_id', models.IntegerField(blank=True, db_column='image_type_id', null=True)),
                ('category', models.CharField(db_column='category', max_length=255)),
            ],
            options={
                'db_table': 'gd_image_category',
                'managed': False,
                'ordering': ['category'],
                'verbose_name': 'Image category',
                'verbose_name_plural': 'Image categories',
            },
        ),
    ]
