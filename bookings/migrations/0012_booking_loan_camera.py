from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0011_booking_customer_nullable_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='loan_camera',
            field=models.BooleanField(
                default=False,
                help_text='Student has requested a loan camera for this place.',
            ),
        ),
    ]
