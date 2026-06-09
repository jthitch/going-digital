import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0007_fix_bookings_user_fk_mysql'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='list_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Workshop price before voucher discount',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='voucher_code',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='booking',
            name='voucher_discount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='booking',
            name='voucher_id',
            field=models.IntegerField(
                blank=True,
                help_text='gd_voucher.id applied at checkout (redeemed after payment)',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='booking',
            name='price_paid',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
            ),
        ),
    ]
