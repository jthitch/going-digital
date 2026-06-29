# Generated manually for GoogleReviewHighlight

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0010_google_reviews_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleReviewHighlight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('author_name', models.CharField(max_length=120)),
                ('review_text', models.TextField()),
                ('rating', models.PositiveSmallIntegerField(default=5, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('author_photo', models.ImageField(blank=True, help_text='Optional reviewer photo. Leave empty to use initials or a photo URL.', null=True, upload_to='google-reviews/')),
                ('author_photo_url', models.URLField(blank=True, help_text='Optional photo URL (e.g. from Google). Used when no uploaded image.', max_length=500)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('settings', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='highlights', to='website.googlereviewssettings')),
            ],
            options={
                'verbose_name': 'Featured Google review',
                'verbose_name_plural': 'Featured Google reviews',
                'db_table': 'google_review_highlights',
                'ordering': ['order', 'id'],
            },
        ),
    ]
