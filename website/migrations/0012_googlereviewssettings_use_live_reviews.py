# Generated manually for use_live_reviews on GoogleReviewsSettings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0011_google_review_highlight'),
    ]

    operations = [
        migrations.AddField(
            model_name='googlereviewssettings',
            name='use_live_reviews',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Load the most relevant Google reviews live on the homepage when '
                    'GOOGLE_PLACES_API_KEY is configured. Manual featured reviews are used as a fallback.'
                ),
            ),
        ),
        migrations.AlterField(
            model_name='googlereviewssettings',
            name='google_place_id',
            field=models.CharField(
                blank=True,
                help_text='Google Place ID (ChIJ…). Leave blank to look up from business name when the API key is set.',
                max_length=128,
            ),
        ),
    ]
