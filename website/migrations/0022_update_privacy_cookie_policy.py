from django.db import migrations

OLD_COOKIE_MARKER = 'We use only Google Analytics to analyse the use of this website'


def update_privacy_cookie_section(apps, schema_editor):
    LegalPage = apps.get_model('website', 'LegalPage')
    from website.legal_page_defaults import DEFAULT_LEGAL_PAGES

    page = LegalPage.objects.filter(page_key='privacy').first()
    if not page or OLD_COOKIE_MARKER not in (page.body or ''):
        return
    page.body = DEFAULT_LEGAL_PAGES['privacy']['body']
    page.save(update_fields=['body'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0021_workshop_follow_up_email_settings_default'),
    ]

    operations = [
        migrations.RunPython(update_privacy_cookie_section, noop_reverse),
    ]
