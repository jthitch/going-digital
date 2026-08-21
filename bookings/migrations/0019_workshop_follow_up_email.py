"""Booking follow-up fields and WorkshopFeedback model."""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0018_booking_reminder_email_sent_at'),
        ('courses', '0048_tutor_telephone'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='follow_up_email_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the day-after workshop follow-up / rating email was sent.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='follow_up_token',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Secret token used in follow-up email star-rating links.',
                max_length=64,
            ),
        ),
        migrations.CreateModel(
            name='WorkshopFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'rating',
                    models.PositiveSmallIntegerField(
                        help_text='1-5 star rating from the follow-up email.',
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                ('comment', models.TextField(blank=True, default='')),
                ('rated_at', models.DateTimeField(auto_now_add=True)),
                ('comment_submitted_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'booking',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='workshop_feedback',
                        to='bookings.booking',
                    ),
                ),
                (
                    'workshop',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='student_feedback',
                        to='courses.workshop',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Workshop feedback',
                'verbose_name_plural': 'Workshop feedback',
                'db_table': 'workshop_feedback',
                'ordering': ['-rated_at'],
            },
        ),
    ]
