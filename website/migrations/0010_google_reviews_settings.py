# Generated manually for GoogleReviewsSettings

from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def seed_google_reviews(apps, schema_editor):
    GoogleReviewsSettings = apps.get_model('website', 'GoogleReviewsSettings')
    if GoogleReviewsSettings.objects.exists():
        return
    GoogleReviewsSettings.objects.create(
        is_active=True,
        business_name='GD Photography Ltd',
        rating=Decimal('5.0'),
        review_count=0,
        reviews_url=(
            'https://www.google.com/search?q=GD+Photography+Ltd&hl=en-GB'
            '#lrd=0xab70654900d0b227:0x926a542e36e35028,1'
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0009_legal_page'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleReviewsSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, help_text='Show the Google reviews badge on the homepage.')),
                ('business_name', models.CharField(default='GD Photography Ltd', max_length=200)),
                ('rating', models.DecimalField(decimal_places=1, default=5.0, help_text='Average star rating (1.0–5.0).', max_digits=2, validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ('review_count', models.PositiveIntegerField(default=0, help_text='Total number of Google reviews. Leave at 0 to hide the count.')),
                ('reviews_url', models.URLField(default='https://www.google.com/search?q=GD+Photography+Ltd&hl=en-GB#lrd=0xab70654900d0b227:0x926a542e36e35028,1', help_text='Link to your Google reviews (opens Google).', max_length=500)),
                ('google_place_id', models.CharField(blank=True, help_text='Optional Google Place ID for live rating sync when GOOGLE_PLACES_API_KEY is set.', max_length=128)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Google reviews',
                'verbose_name_plural': 'Google reviews',
                'db_table': 'google_reviews_settings',
            },
        ),
        migrations.RunPython(seed_google_reviews, migrations.RunPython.noop),
    ]
