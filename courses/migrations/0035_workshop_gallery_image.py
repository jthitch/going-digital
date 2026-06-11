from django.db import migrations, models
import django.db.models.deletion


CREATE_GALLERY_TABLE = """
CREATE TABLE IF NOT EXISTS `courses_workshopgalleryimage` (
    `id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `display_order` integer UNSIGNED NOT NULL,
    `image_id` integer NOT NULL,
    `workshop_id` integer NOT NULL,
    UNIQUE KEY `courses_workshopgalleryimage_workshop_id_image_id_uniq` (`workshop_id`, `image_id`),
    CONSTRAINT `courses_workshopgalleryimage_image_id_fk`
        FOREIGN KEY (`image_id`) REFERENCES `gd_image` (`id`),
    CONSTRAINT `courses_workshopgalleryimage_workshop_id_fk`
        FOREIGN KEY (`workshop_id`) REFERENCES `gd_workshop` (`id`)
)
"""


def backfill_workshop_gallery(apps, schema_editor):
    Workshop = apps.get_model('courses', 'Workshop')
    WorkshopGalleryImage = apps.get_model('courses', 'WorkshopGalleryImage')
    Image = apps.get_model('courses', 'Image')
    valid_image_ids = set(Image.objects.values_list('pk', flat=True))
    for workshop in Workshop.objects.exclude(image_id=0).exclude(image_id__isnull=True):
        if workshop.image_id not in valid_image_ids:
            continue
        WorkshopGalleryImage.objects.get_or_create(
            workshop_id=workshop.pk,
            image_id=workshop.image_id,
            defaults={'display_order': 0},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0034_alter_image_image_category_id_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='WorkshopGalleryImage',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('display_order', models.PositiveIntegerField(default=0)),
                        ('image', models.ForeignKey(
                            db_column='image_id',
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='workshop_gallery_links',
                            to='courses.image',
                        )),
                        ('workshop', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='gallery_images',
                            to='courses.workshop',
                        )),
                    ],
                    options={
                        'verbose_name': 'Workshop gallery image',
                        'verbose_name_plural': 'Workshop gallery images',
                        'ordering': ['display_order', 'id'],
                        'unique_together': {('workshop', 'image')},
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    CREATE_GALLERY_TABLE,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.RunPython(backfill_workshop_gallery, migrations.RunPython.noop),
    ]
