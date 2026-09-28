"""Refunded booking status and BookingRefund audit records."""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0020_booking_legacy_bridge_ids'),
        ('courses', '0050_fix_franchisee_access_user_fks'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending Payment'),
                    ('confirmed', 'Confirmed'),
                    ('cancelled', 'Cancelled'),
                    ('completed', 'Completed'),
                    ('refunded', 'Refunded'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='BookingRefund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('legacy_gd_booking_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('legacy_attendee_id', models.IntegerField(blank=True, db_index=True, null=True)),
                (
                    'legacy_bookings_workshops_id',
                    models.IntegerField(
                        blank=True,
                        db_index=True,
                        help_text='gd_bookings_workshops.id updated with refund_amount/date/reason.',
                        null=True,
                    ),
                ),
                ('booking_reference', models.CharField(blank=True, default='', max_length=50)),
                ('student_name', models.CharField(blank=True, default='', max_length=255)),
                ('student_email', models.CharField(blank=True, default='', max_length=255)),
                (
                    'amount',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                    ),
                ),
                ('refunded_on', models.DateField(help_text='Date the money was returned to the student.')),
                (
                    'method',
                    models.CharField(
                        choices=[
                            ('bank_transfer', 'Bank transfer'),
                            ('cash', 'Cash'),
                            ('cheque', 'Cheque'),
                            ('stripe', 'Stripe (refunded in Stripe dashboard)'),
                            ('other', 'Other'),
                        ],
                        default='bank_transfer',
                        max_length=20,
                    ),
                ),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'booking',
                    models.ForeignKey(
                        blank=True,
                        help_text='New-site booking (or legacy bridge) that was refunded.',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='refunds',
                        to='bookings.booking',
                    ),
                ),
                (
                    'recorded_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='recorded_refunds',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'workshop',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='refunds',
                        to='courses.workshop',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Refund',
                'verbose_name_plural': 'Refunds',
                'db_table': 'booking_refunds',
                'ordering': ['-refunded_on', '-id'],
            },
        ),
    ]
