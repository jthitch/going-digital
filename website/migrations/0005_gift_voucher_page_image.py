# Generated manually for GiftVoucherPageImage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0004_redirect_photography_workshops_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='GiftVoucherPageImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'image',
                    models.ImageField(
                        help_text='Shown below the title on the gift vouchers page. Recommended: wide graphic (e.g. voucher artwork).',
                        upload_to='gift-vouchers/',
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'gift_voucher_page_image',
                'verbose_name': 'Gift vouchers page image',
                'verbose_name_plural': 'Gift vouchers page image',
            },
        ),
    ]
