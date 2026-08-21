"""Seed singleton WorkshopFollowUpEmailSettings row."""

from django.db import migrations


def create_workshop_follow_up_email_settings(apps, schema_editor):
    WorkshopFollowUpEmailSettings = apps.get_model('website', 'WorkshopFollowUpEmailSettings')
    if not WorkshopFollowUpEmailSettings.objects.exists():
        WorkshopFollowUpEmailSettings.objects.create()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0020_workshop_follow_up_email'),
    ]

    operations = [
        migrations.RunPython(
            create_workshop_follow_up_email_settings,
            migrations.RunPython.noop,
        ),
    ]
