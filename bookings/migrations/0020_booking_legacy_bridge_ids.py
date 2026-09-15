"""Add legacy bridge ids on Booking for reminder/follow-up emails."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0019_workshop_follow_up_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='legacy_gd_booking_id',
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text=(
                    'gd_booking.id when this row bridges a legacy paid place '
                    'for reminder/follow-up emails.'
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='legacy_attendee_id',
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text='gd_bookings_workshops_attendees.id when bridging a legacy attendee.',
                null=True,
            ),
        ),
    ]
