# Rename legacy numeric skill_level values to human-readable labels.

from django.db import migrations

LEVEL_NAMES = {
    1: 'Beginner',
    2: 'Intermediate',
    3: 'Advanced',
    4: 'Masterclass',
    5: 'Various',
}
OLD_SKILL_LEVEL_VALUES = {str(pk): name for pk, name in LEVEL_NAMES.items()}


def rename_skill_levels(apps, schema_editor):
    CourseSkillLevel = apps.get_model('courses', 'CourseSkillLevel')
    for pk, name in LEVEL_NAMES.items():
        CourseSkillLevel.objects.filter(pk=pk).update(skill_level=name)
    for old, name in OLD_SKILL_LEVEL_VALUES.items():
        CourseSkillLevel.objects.filter(skill_level=old).exclude(pk__in=LEVEL_NAMES).update(skill_level=name)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0022_alter_course_id_alter_image_file_name_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_skill_levels, noop),
    ]
