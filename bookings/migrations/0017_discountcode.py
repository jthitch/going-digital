# Generated manually for franchisee discount codes

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bookings', '0016_cameramake_cameramodel'),
        ('courses', '0044_gddocument'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiscountCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=40, unique=True)),
                ('discount_type', models.CharField(
                    choices=[('fixed', 'Fixed amount (£)'), ('percent', 'Percentage (%)')],
                    default='fixed',
                    max_length=10,
                )),
                ('amount', models.DecimalField(
                    decimal_places=2,
                    help_text='Pounds off for fixed codes, or percentage (e.g. 10 for 10%).',
                    max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                )),
                ('is_active', models.BooleanField(default=True)),
                ('expiry_date', models.DateField(
                    blank=True,
                    help_text='Optional. Code stops working after this date.',
                    null=True,
                )),
                ('times_redeemed', models.PositiveIntegerField(default=0)),
                ('notes', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='discount_codes',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('workshops', models.ManyToManyField(
                    blank=True,
                    help_text='Workshops this code can be used on.',
                    related_name='discount_codes',
                    to='courses.workshop',
                )),
            ],
            options={
                'verbose_name': 'Discount code',
                'verbose_name_plural': 'Discount codes',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='booking',
            name='discount_code',
            field=models.ForeignKey(
                blank=True,
                help_text='Franchisee/admin promotional code applied at checkout.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='bookings.discountcode',
            ),
        ),
        migrations.AlterField(
            model_name='booking',
            name='voucher_redeemed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the voucher/discount code was marked redeemed against this booking',
                null=True,
            ),
        ),
    ]
