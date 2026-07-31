# Remove unused Instructor model (replaced by gd_tutor for workshops).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0046_course_workshop_block'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Instructor',
        ),
    ]
