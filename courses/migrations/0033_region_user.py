# Register legacy gd_region_user for franchisee region assignments.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0032_county'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegionUser',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('region_id', models.IntegerField(db_column='region_id')),
                ('user_id', models.IntegerField(db_column='user_id')),
                ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                ('updatedby_id', models.IntegerField(blank=True, db_column='updatedby_id', null=True)),
                ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
                ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
            ],
            options={
                'db_table': 'gd_region_user',
                'managed': False,
                'verbose_name': 'Region user',
                'verbose_name_plural': 'Region users',
            },
        ),
    ]
