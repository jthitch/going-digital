from django.db import migrations


def create_workshop_reminder_email_settings(apps, schema_editor):
    WorkshopReminderEmailSettings = apps.get_model('website', 'WorkshopReminderEmailSettings')
    if not WorkshopReminderEmailSettings.objects.exists():
        WorkshopReminderEmailSettings.objects.create()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0017_workshop_reminder_email_settings'),
        ('website', '0018_alter_heroimage_image'),
    ]

    operations = [
        migrations.RunPython(create_workshop_reminder_email_settings, migrations.RunPython.noop),
    ]
