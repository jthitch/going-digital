import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_make_user_nullable_for_guest'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='amount',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
            ),
        ),
        migrations.AlterField(
            model_name='payment',
            name='intent_type',
            field=models.CharField(
                choices=[
                    ('checkout_session', 'Checkout Session'),
                    ('payment_intent', 'Payment Intent'),
                    ('voucher_free', 'Voucher (no card charge)'),
                ],
                max_length=20,
            ),
        ),
    ]
