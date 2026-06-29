# Generated manually for NewsletterModalSettings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0005_gift_voucher_page_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsletterModalSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(
                    blank=True,
                    help_text='Background for the newsletter popup. Leave empty to use the default static image. Recommended: portrait or tall photo (e.g. 800×1200px).',
                    null=True,
                    upload_to='newsletter/modal/',
                )),
                ('desktop_focus_x', models.PositiveSmallIntegerField(
                    default=85,
                    help_text='Desktop: horizontal focus (0 = left edge, 100 = right edge).',
                )),
                ('desktop_focus_y', models.PositiveSmallIntegerField(
                    default=50,
                    help_text='Desktop: vertical focus (0 = top, 100 = bottom).',
                )),
                ('mobile_focus_x', models.PositiveSmallIntegerField(
                    default=50,
                    help_text='Mobile: horizontal focus (0 = left, 100 = right).',
                )),
                ('mobile_focus_y', models.PositiveSmallIntegerField(
                    default=25,
                    help_text='Mobile: vertical focus (0 = top, 100 = bottom).',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Newsletter modal',
                'verbose_name_plural': 'Newsletter modal',
                'db_table': 'newsletter_modal_settings',
            },
        ),
    ]
