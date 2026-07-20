from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0013_booking_terms_acceptance'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='camera_make',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Camera manufacturer (e.g. Canon, Nikon).',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='camera_model',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Camera model (e.g. EOS R6, D850).',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='attendee_details_collected_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When post-checkout attendee/camera details were collected.',
                null=True,
            ),
        ),
    ]
