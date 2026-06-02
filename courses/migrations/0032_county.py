# Register legacy gd_county table (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0031_image_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='County',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('county', models.CharField(db_column='county', max_length=255)),
            ],
            options={
                'db_table': 'gd_county',
                'managed': False,
                'ordering': ['county'],
                'verbose_name': 'County',
                'verbose_name_plural': 'Counties',
            },
        ),
    ]
