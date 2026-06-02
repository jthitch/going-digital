# Register legacy gd_tutor table for workshop tutor picker (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0026_region'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tutor',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('firstname', models.CharField(db_column='firstname', default='', max_length=255)),
                ('lastname', models.CharField(db_column='lastname', default='', max_length=255)),
                ('email', models.CharField(blank=True, db_column='email', max_length=255, null=True)),
            ],
            options={
                'db_table': 'gd_tutor',
                'managed': False,
                'ordering': ['lastname', 'firstname'],
                'verbose_name': 'Tutor',
                'verbose_name_plural': 'Tutors',
            },
        ),
    ]
