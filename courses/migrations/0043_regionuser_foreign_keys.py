# RegionUser ORM relations for admin (gd_region_user columns unchanged).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0042_workshop_end_date'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='regionuser',
                    name='region_id',
                ),
                migrations.RemoveField(
                    model_name='regionuser',
                    name='user_id',
                ),
                migrations.AddField(
                    model_name='regionuser',
                    name='region',
                    field=models.ForeignKey(
                        db_column='region_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='user_assignments',
                        to='courses.region',
                    ),
                ),
                migrations.AddField(
                    model_name='regionuser',
                    name='user',
                    field=models.ForeignKey(
                        db_column='user_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='region_assignments',
                        to='core.user',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
