from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_payment_zero_amount_voucher_free'),
        ('bookings', '0009_booking_voucher_redeemed_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='booking',
            name='payment',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='payments.payment',
            ),
        ),
    ]
