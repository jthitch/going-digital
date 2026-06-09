from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0008_booking_voucher_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='voucher_redeemed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the voucher was marked redeemed against this booking',
                null=True,
            ),
        ),
    ]
