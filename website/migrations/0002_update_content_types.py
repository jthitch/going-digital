# Data migration to update django_content_type app_label from courses to website

from django.db import migrations


def update_content_types(apps, schema_editor):
    """Update django_content_type to reflect models moved from courses to website."""
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db_alias = schema_editor.connection.alias
    
    # Update app_label for moved models
    models_to_update = ['heroimage', 'testimonial', 'beforeafterimage', 'faq']
    
    for model_name in models_to_update:
        try:
            # Get the old content type
            old_ct = ContentType.objects.using(db_alias).get(
                app_label='courses',
                model=model_name
            )
            # Update to website app
            old_ct.app_label = 'website'
            old_ct.save(using=db_alias)
        except ContentType.DoesNotExist:
            # If it doesn't exist, create it
            ContentType.objects.using(db_alias).create(
                app_label='website',
                model=model_name
            )


def reverse_update_content_types(apps, schema_editor):
    """Reverse: change app_label back to courses."""
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db_alias = schema_editor.connection.alias
    
    models_to_revert = ['heroimage', 'testimonial', 'beforeafterimage', 'faq']
    
    for model_name in models_to_revert:
        try:
            ct = ContentType.objects.using(db_alias).get(
                app_label='website',
                model=model_name
            )
            ct.app_label = 'courses'
            ct.save(using=db_alias)
        except ContentType.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(update_content_types, reverse_update_content_types),
    ]