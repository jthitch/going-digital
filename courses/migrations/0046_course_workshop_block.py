"""Add CourseWorkshopBlock deny-list for franchisee workshop course access."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0045_venue_workshop_access'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseWorkshopBlock',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='workshop_blocks',
                    to='courses.course',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='course_workshop_blocks',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('blocked_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'gd_course_workshop_block',
                'verbose_name': 'Course workshop block',
                'verbose_name_plural': 'Course workshop blocks',
                'ordering': ['course__course_name', 'user__lastname'],
                'unique_together': {('course', 'user')},
            },
        ),
    ]
