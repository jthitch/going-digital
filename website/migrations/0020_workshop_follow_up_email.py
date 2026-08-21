"""Editable copy for day-after workshop follow-up emails."""

from django.db import migrations, models

import website.models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0019_workshop_reminder_email_settings_default'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkshopFollowUpEmailSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'intro',
                    models.TextField(
                        blank=True,
                        default=website.models.DEFAULT_FOLLOW_UP_EMAIL_INTRO,
                        help_text='Opening paragraph in every day-after follow-up email.',
                    ),
                ),
                (
                    'closing',
                    models.TextField(
                        blank=True,
                        default=website.models.DEFAULT_FOLLOW_UP_EMAIL_CLOSING,
                        help_text='Closing paragraph after the star rating buttons.',
                    ),
                ),
                (
                    'feedback_prompt',
                    models.TextField(
                        blank=True,
                        default=website.models.DEFAULT_FOLLOW_UP_FEEDBACK_PROMPT,
                        help_text='Shown on the feedback form when the student rates 1-4 stars.',
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Workshop follow-up email',
                'verbose_name_plural': 'Workshop follow-up email',
                'db_table': 'workshop_follow_up_email_settings',
            },
        ),
    ]
