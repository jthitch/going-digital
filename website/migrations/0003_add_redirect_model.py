# Generated manually for Redirect model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0002_update_content_types'),
    ]

    operations = [
        migrations.CreateModel(
            name='Redirect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_path', models.CharField(help_text="Incoming path (e.g. /photography-workshops/). Must start with /.", max_length=500, unique=True)),
                ('new_path', models.CharField(help_text="Destination path or full URL (e.g. /photography-courses/).", max_length=500)),
                ('permanent', models.BooleanField(default=True, help_text='Use 301 (permanent) if True, 302 (temporary) if False.')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'redirects',
                'ordering': ['old_path'],
                'verbose_name': 'Redirect',
                'verbose_name_plural': 'Redirects',
            },
        ),
    ]
