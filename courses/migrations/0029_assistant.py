# Register legacy gd_assistant table (table already exists in MySQL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0028_workshop_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assistant',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('firstname', models.CharField(db_column='firstname', default='', max_length=255)),
                ('lastname', models.CharField(db_column='lastname', default='', max_length=255)),
                ('email', models.CharField(blank=True, db_column='email', max_length=255, null=True)),
            ],
            options={
                'db_table': 'gd_assistant',
                'managed': False,
                'ordering': ['lastname', 'firstname'],
                'verbose_name': 'Assistant',
                'verbose_name_plural': 'Assistants',
            },
        ),
    ]
