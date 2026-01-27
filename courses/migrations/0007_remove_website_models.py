# Migration to remove models that have been moved to website app
# This is a state-only migration - we don't drop the tables since website app manages them

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_beforeafterimage'),
        ('website', '0002_update_content_types'),  # Ensure website migrations run first
    ]

    operations = [
        # Remove models from courses app state
        # Note: We don't actually delete the tables since they're managed by website app now
        # This migration only updates Django's state, not the database
        migrations.SeparateDatabaseAndState(
            database_operations=[],  # Don't modify database - tables are managed by website app
            state_operations=[
                migrations.DeleteModel(
                    name='HeroImage',
                ),
                migrations.DeleteModel(
                    name='Testimonial',
                ),
                migrations.DeleteModel(
                    name='BeforeAfterImage',
                ),
                migrations.DeleteModel(
                    name='FAQ',
                ),
            ],
        ),
    ]