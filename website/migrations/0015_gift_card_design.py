from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0014_googlereviewssettings_google_cid'),
    ]

    operations = [
        migrations.CreateModel(
            name='GiftCardDesign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('image', models.ImageField(help_text='Background artwork (PNG or JPG). Text is drawn on top at the positions below.', upload_to='gift-card-designs/')),
                ('is_active', models.BooleanField(default=True)),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='Lower numbers appear first on the payment success page.')),
                ('value_x', models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Value X (%)')),
                ('value_y', models.PositiveSmallIntegerField(default=42, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Value Y (%)')),
                ('value_font_size', models.PositiveSmallIntegerField(default=64)),
                ('value_color', models.CharField(default='#1a1a1a', max_length=7)),
                ('code_x', models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Voucher code X (%)')),
                ('code_y', models.PositiveSmallIntegerField(default=55, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Voucher code Y (%)')),
                ('code_font_size', models.PositiveSmallIntegerField(default=32)),
                ('code_color', models.CharField(default='#1a1a1a', max_length=7)),
                ('recipient_x', models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Recipient X (%)')),
                ('recipient_y', models.PositiveSmallIntegerField(default=68, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Recipient Y (%)')),
                ('recipient_font_size', models.PositiveSmallIntegerField(default=28)),
                ('recipient_color', models.CharField(default='#333333', max_length=7)),
                ('message_x', models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Message X (%)')),
                ('message_y', models.PositiveSmallIntegerField(default=76, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Message Y (%)')),
                ('message_font_size', models.PositiveSmallIntegerField(default=22)),
                ('message_color', models.CharField(default='#333333', max_length=7)),
                ('message_max_width_pct', models.PositiveSmallIntegerField(default=80, help_text='Wrap long messages within this width (% of image).', validators=[MinValueValidator(20), MaxValueValidator(100)])),
                ('expiry_x', models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Expiry X (%)')),
                ('expiry_y', models.PositiveSmallIntegerField(default=88, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Expiry Y (%)')),
                ('expiry_font_size', models.PositiveSmallIntegerField(default=18)),
                ('expiry_color', models.CharField(default='#555555', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Gift card design',
                'verbose_name_plural': 'Gift card designs',
                'db_table': 'gift_card_design',
                'ordering': ['display_order', 'name'],
            },
        ),
    ]
