from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0015_gift_card_design'),
    ]

    operations = [
        migrations.AddField(
            model_name='heroimage',
            name='screen_orientation',
            field=models.CharField(
                choices=[
                    ('both', 'Both portrait and landscape'),
                    ('landscape', 'Landscape screens only'),
                    ('portrait', 'Portrait screens only'),
                ],
                db_column='screen_orientation',
                default='both',
                help_text=(
                    'Landscape-only suits wide photos on tablets and desktops; '
                    'portrait-only suits tall photos on phones held upright.'
                ),
                max_length=16,
                verbose_name='Show on',
            ),
        ),
    ]
