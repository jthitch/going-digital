# Register legacy gd_image_type table (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0029_assistant'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageType',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('image_type', models.CharField(db_column='image_type', max_length=255)),
            ],
            options={
                'db_table': 'gd_image_type',
                'managed': False,
                'ordering': ['image_type'],
                'verbose_name': 'Image type',
                'verbose_name_plural': 'Image types',
            },
        ),
    ]
