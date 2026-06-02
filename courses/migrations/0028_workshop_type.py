# Register legacy gd_workshop_type table (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0027_tutor'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkshopType',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('workshop_type', models.CharField(db_column='workshop_type', max_length=255)),
                ('display_on_site', models.SmallIntegerField(db_column='display_on_site', default=1)),
            ],
            options={
                'db_table': 'gd_workshop_type',
                'managed': False,
                'ordering': ['workshop_type'],
                'verbose_name': 'Workshop type',
                'verbose_name_plural': 'Workshop types',
            },
        ),
    ]
