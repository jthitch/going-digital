# Generated manually for camera make/model catalog

from django.db import migrations, models
import django.db.models.deletion


SEED_CAMERAS = {
    'Canon': [
        'EOS R5', 'EOS R6', 'EOS R6 Mark II', 'EOS R7', 'EOS R8', 'EOS R10',
        'EOS 5D Mark IV', 'EOS 90D', 'EOS 250D', 'EOS M50 Mark II', 'PowerShot G7 X',
    ],
    'Nikon': [
        'Z6', 'Z6 II', 'Z7', 'Z7 II', 'Z8', 'Z9', 'Z30', 'Z50', 'Zfc',
        'D850', 'D780', 'D7500', 'D5600', 'D3500',
    ],
    'Sony': [
        'A7 III', 'A7 IV', 'A7R IV', 'A7R V', 'A7C', 'A7C II', 'A9 III',
        'A6400', 'A6600', 'A6700', 'ZV-E10', 'RX100 VII',
    ],
    'Fujifilm': [
        'X-T4', 'X-T5', 'X-S20', 'X-H2', 'X-H2S', 'X100V', 'X100VI', 'GFX 50S II',
    ],
    'Olympus / OM System': [
        'OM-1', 'OM-5', 'E-M1 Mark III', 'E-M5 Mark III', 'E-M10 Mark IV',
    ],
    'Panasonic': [
        'Lumix GH6', 'Lumix GH5 II', 'Lumix G9 II', 'Lumix S5 II', 'Lumix GX9',
    ],
    'Pentax': ['K-3 III', 'K-70', 'KP'],
    'Leica': ['Q3', 'Q2', 'SL2', 'CL', 'M11'],
    'GoPro': ['Hero 12', 'Hero 11', 'Hero 10'],
    'DJI': ['Osmo Action 4', 'Osmo Pocket 3'],
}


def seed_camera_catalog(apps, schema_editor):
    CameraMake = apps.get_model('bookings', 'CameraMake')
    CameraModel = apps.get_model('bookings', 'CameraModel')
    for index, (make_name, models_list) in enumerate(SEED_CAMERAS.items()):
        make, _ = CameraMake.objects.get_or_create(
            name=make_name,
            defaults={'sort_order': index * 10, 'is_active': True},
        )
        for model_index, model_name in enumerate(models_list):
            CameraModel.objects.get_or_create(
                make=make,
                name=model_name,
                defaults={'sort_order': model_index * 10, 'is_active': True},
            )


def unseed_camera_catalog(apps, schema_editor):
    CameraMake = apps.get_model('bookings', 'CameraMake')
    CameraMake.objects.filter(name__in=SEED_CAMERAS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0015_gdbooking_reportbookingbycourse_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CameraMake',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Camera make',
                'verbose_name_plural': 'Camera makes',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CameraModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('make', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='models',
                    to='bookings.cameramake',
                )),
            ],
            options={
                'verbose_name': 'Camera model',
                'verbose_name_plural': 'Camera models',
                'ordering': ['sort_order', 'name'],
                'unique_together': {('make', 'name')},
            },
        ),
        migrations.RunPython(seed_camera_catalog, unseed_camera_catalog),
    ]
