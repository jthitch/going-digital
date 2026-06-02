# Register legacy gd_region table for admin region picker (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0025_skill_level_display_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('region_name', models.CharField(db_column='region_name', default='', max_length=255)),
                ('slug', models.CharField(db_column='slug', default='', max_length=255)),
            ],
            options={
                'db_table': 'gd_region',
                'managed': False,
                'ordering': ['region_name'],
                'verbose_name': 'Region',
                'verbose_name_plural': 'Regions',
            },
        ),
    ]
