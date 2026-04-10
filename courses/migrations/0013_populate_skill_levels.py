# Populate default course skill levels so users can assign them to courses.

from django.db import migrations


def populate_skill_levels(apps, schema_editor):
    CourseSkillLevel = apps.get_model('courses', 'CourseSkillLevel')
    if CourseSkillLevel.objects.exists():
        return  # Already populated
    levels = [
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, 'Various'),
    ]
    for display_order, skill_level in levels:
        CourseSkillLevel.objects.create(
            active=1,
            skill_level=skill_level,
            display_order=display_order,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0012_gd_image'),
    ]

    operations = [
        migrations.RunPython(populate_skill_levels, noop),
    ]
