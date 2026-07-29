"""Add VenueWorkshopAccess join table for shared venue workshop permissions."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0044_gddocument'),
    ]

    operations = [
        migrations.CreateModel(
            name='VenueWorkshopAccess',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('venue', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='workshop_access_grants',
                    to='courses.venue',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='venue_workshop_access',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('granted_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'gd_venue_workshop_access',
                'verbose_name': 'Venue workshop access',
                'verbose_name_plural': 'Venue workshop access',
                'unique_together': {('venue', 'user')},
                'ordering': ['venue__venue_name', 'user__lastname'],
            },
        ),
    ]
