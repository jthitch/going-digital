# Generated manually for LegalPage

from django.db import migrations, models


def seed_legal_pages(apps, schema_editor):
    LegalPage = apps.get_model('website', 'LegalPage')
    from website.legal_page_defaults import DEFAULT_LEGAL_PAGES

    for page_key, defaults in DEFAULT_LEGAL_PAGES.items():
        LegalPage.objects.get_or_create(
            page_key=page_key,
            defaults={
                'page_title': defaults['page_title'],
                'browser_title': defaults['browser_title'],
                'meta_description': defaults['meta_description'],
                'meta_keywords': defaults['meta_keywords'],
                'body': defaults['body'],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0008_newsletter_modal_zoom'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegalPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_key', models.CharField(choices=[('terms', 'Terms and conditions'), ('privacy', 'Privacy policy')], editable=False, max_length=16, unique=True)),
                ('page_title', models.CharField(help_text='Heading shown at the top of the page.', max_length=200)),
                ('browser_title', models.CharField(help_text='Browser tab title.', max_length=200)),
                ('meta_description', models.CharField(blank=True, max_length=500)),
                ('meta_keywords', models.CharField(blank=True, max_length=500)),
                ('body', models.TextField(help_text='Main page content (HTML).')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Legal page',
                'verbose_name_plural': 'Legal pages',
                'db_table': 'legal_pages',
            },
        ),
        migrations.RunPython(seed_legal_pages, migrations.RunPython.noop),
    ]
