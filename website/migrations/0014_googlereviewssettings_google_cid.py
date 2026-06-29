# Point Google reviews at the main GD Photography Ltd listing (107 reviews)

from django.db import migrations, models

GD_PHOTOGRAPHY_PLACE_ID = 'ChIJJ7LQAEllcKsRKFDjNi5UapI'
GD_PHOTOGRAPHY_CID = '10550337634534903848'


def set_main_google_listing(apps, schema_editor):
    GoogleReviewsSettings = apps.get_model('website', 'GoogleReviewsSettings')
    GoogleReviewsSettings.objects.update(
        google_place_id=GD_PHOTOGRAPHY_PLACE_ID,
        google_cid=GD_PHOTOGRAPHY_CID,
        review_count=107,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0013_backfill_google_place_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='googlereviewssettings',
            name='google_cid',
            field=models.CharField(
                blank=True,
                default='10550337634534903848',
                help_text='Google Business Profile CID. Used to verify the correct listing is selected.',
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='googlereviewssettings',
            name='google_place_id',
            field=models.CharField(
                blank=True,
                default='ChIJJ7LQAEllcKsRKFDjNi5UapI',
                help_text='Google Place ID (ChIJ…). Leave blank to look up automatically when the API key is set.',
                max_length=128,
            ),
        ),
        migrations.RunPython(set_main_google_listing, migrations.RunPython.noop),
    ]
