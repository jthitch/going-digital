# Remove GiftVoucherOrder - gift vouchers now use legacy gd_basket / gd_voucher

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0005_add_gift_voucher_order'),
    ]

    operations = [
        migrations.DeleteModel(
            name='GiftVoucherOrder',
        ),
    ]
