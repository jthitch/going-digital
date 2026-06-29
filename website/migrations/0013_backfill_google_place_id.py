# Backfill Google Place ID for the Going Digital UK listing

from django.db import migrations

GOING_DIGITAL_PLACE_ID = 'ChIJy-33g8ebcUgRnxKoAfvoch4'


def set_google_place_id(apps, schema_editor):
    GoogleReviewsSettings = apps.get_model('website', 'GoogleReviewsSettings')
    GoogleReviewsSettings.objects.filter(google_place_id='').update(
        google_place_id=GOING_DIGITAL_PLACE_ID,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0012_googlereviewssettings_use_live_reviews'),
    ]

    operations = [
        migrations.RunPython(set_google_place_id, migrations.RunPython.noop),
    ]
