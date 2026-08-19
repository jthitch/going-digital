# Expose existing gd_tutor.telephone on the unmanaged Tutor model.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0047_remove_instructor'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='tutor',
                    name='telephone',
                    field=models.CharField(
                        blank=True,
                        db_column='telephone',
                        max_length=255,
                        null=True,
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
