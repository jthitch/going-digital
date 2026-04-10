# Venue content and media for venue detail pages.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0019_alter_instructor_options_alter_course_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VenueContent',
            fields=[
                ('venue', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='content_block', serialize=False, to='courses.venue')),
                ('description', models.TextField(blank=True, help_text='Main description for the venue page')),
                ('meta_title', models.CharField(blank=True, help_text='SEO title (optional)', max_length=255)),
                ('meta_description', models.TextField(blank=True, help_text='SEO description (optional)', max_length=500)),
            ],
            options={
                'verbose_name': 'Venue content',
                'verbose_name_plural': 'Venue contents',
            },
        ),
        migrations.CreateModel(
            name='VenueMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(blank=True, null=True, upload_to='venues/images/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='media', to='courses.venue')),
            ],
            options={
                'verbose_name': 'Venue image',
                'verbose_name_plural': 'Venue images',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
