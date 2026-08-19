from django.db import migrations, models

import website.models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0016_heroimage_screen_orientation'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkshopReminderEmailSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'intro',
                    models.TextField(
                        blank=True,
                        default=website.models.DEFAULT_REMINDER_EMAIL_INTRO,
                        help_text='Opening paragraph in every day-before reminder email.',
                    ),
                ),
                (
                    'closing',
                    models.TextField(
                        blank=True,
                        default=website.models.DEFAULT_REMINDER_EMAIL_CLOSING,
                        help_text=(
                            'Closing paragraph before the footer. Tutor contact details are inserted '
                            'automatically when a tutor is assigned.'
                        ),
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Workshop reminder email',
                'verbose_name_plural': 'Workshop reminder email',
                'db_table': 'workshop_reminder_email_settings',
            },
        ),
    ]
