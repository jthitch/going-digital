# Generated manually for BookingTermsAcceptance

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_customer'),
        ('bookings', '0012_booking_loan_camera'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingTermsAcceptance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('basket_id', models.IntegerField(db_index=True, help_text='gd_basket.id for this checkout.')),
                ('booking_ids', models.JSONField(blank=True, default=list)),
                ('accepted_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('terms_updated_at', models.DateTimeField(blank=True, help_text='Terms and conditions page version at time of acceptance.', null=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='terms_acceptances', to='core.customer')),
            ],
            options={
                'verbose_name': 'Terms acceptance',
                'verbose_name_plural': 'Terms acceptances',
                'db_table': 'booking_terms_acceptance',
                'ordering': ['-accepted_at'],
            },
        ),
    ]
