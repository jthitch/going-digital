# Add CourseMedia model for course image/video uploads.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_populate_skill_levels'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('media_type', models.CharField(choices=[('image', 'Image'), ('video', 'Video')], default='image', max_length=10)),
                ('image', models.ImageField(blank=True, null=True, upload_to='courses/images/')),
                ('video_file', models.FileField(blank=True, help_text='Upload a video file (mp4, webm, etc.)', null=True, upload_to='courses/videos/')),
                ('video_url', models.URLField(blank=True, help_text='Or paste a YouTube/Vimeo URL', null=True)),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('course', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='media', to='courses.course')),
            ],
            options={
                'verbose_name': 'Course media',
                'verbose_name_plural': 'Course media',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
