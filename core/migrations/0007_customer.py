from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_fix_django_admin_log_user_fk'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(db_column='id', primary_key=True, serialize=False)),
                ('active', models.SmallIntegerField(db_column='active', default=1)),
                ('archived', models.SmallIntegerField(db_column='archived', default=0)),
                ('guest_account', models.SmallIntegerField(db_column='guest_account', default=1)),
                ('facebook_id', models.IntegerField(blank=True, db_column='facebook_id', null=True)),
                ('registered_at', models.DateField(blank=True, db_column='registered_at', null=True)),
                ('confirmed_email', models.SmallIntegerField(blank=True, db_column='confirmed_email', null=True)),
                ('email', models.CharField(db_column='email', max_length=255)),
                ('password', models.CharField(db_column='password', default='', max_length=255)),
                ('firstname', models.CharField(db_column='firstname', default='', max_length=255)),
                ('lastname', models.CharField(db_column='lastname', default='', max_length=255)),
                ('address', models.CharField(blank=True, db_column='address', max_length=1000, null=True)),
                ('address1', models.CharField(blank=True, db_column='address1', max_length=255, null=True)),
                ('address2', models.CharField(blank=True, db_column='address2', max_length=255, null=True)),
                ('town_city', models.CharField(blank=True, db_column='town_city', max_length=255, null=True)),
                ('postcode', models.CharField(blank=True, db_column='postcode', max_length=255, null=True)),
                ('contact_number', models.CharField(blank=True, db_column='contact_number', max_length=255, null=True)),
                ('newsletter', models.SmallIntegerField(db_column='newsletter', default=0)),
                ('use_for_primary_booking', models.SmallIntegerField(db_column='use_for_primary_booking', default=1)),
                ('remember_token', models.CharField(blank=True, db_column='remember_token', max_length=100, null=True)),
                ('password_reset_token', models.CharField(blank=True, db_column='password_reset_token', max_length=99, null=True)),
                ('last_reset_password_date', models.DateTimeField(blank=True, db_column='last_reset_password_date', null=True)),
                ('last_login_date', models.DateField(blank=True, db_column='last_login_date', null=True)),
                ('createdby_id', models.IntegerField(blank=True, db_column='createdby_id', null=True)),
                ('updated_at', models.DateTimeField(blank=True, db_column='updated_at', null=True)),
                ('created_at', models.DateTimeField(blank=True, db_column='created_at', null=True)),
            ],
            options={
                'db_table': 'gd_customer',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
    ]
