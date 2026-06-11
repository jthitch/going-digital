from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0035_workshop_gallery_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='card_image_focus_x',
            field=models.PositiveSmallIntegerField(
                db_column='card_image_focus_x',
                default=50,
                help_text='0 = left edge, 50 = centre, 100 = right edge.',
                validators=[MinValueValidator(0), MaxValueValidator(100)],
                verbose_name='List card image focus (horizontal %)',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='card_image_focus_y',
            field=models.PositiveSmallIntegerField(
                db_column='card_image_focus_y',
                default=50,
                help_text='0 = top, 50 = centre, 100 = bottom.',
                validators=[MinValueValidator(0), MaxValueValidator(100)],
                verbose_name='List card image focus (vertical %)',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='card_image_zoom',
            field=models.PositiveSmallIntegerField(
                db_column='card_image_zoom',
                default=100,
                help_text='100 = default crop; increase to zoom in on the focal point.',
                validators=[MinValueValidator(100), MaxValueValidator(200)],
                verbose_name='List card image zoom (%)',
            ),
        ),
    ]
