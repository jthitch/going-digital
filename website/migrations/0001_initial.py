# Generated manually for moving models from courses to website

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0006_beforeafterimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='HeroImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(help_text='Recommended size: 1000x667 pixels (3:2 aspect ratio). Text overlay is fixed on the homepage.', upload_to='hero-images/')),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order (lower numbers appear first)')),
                ('is_active', models.BooleanField(default=True, help_text='Show this image in the hero slider')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Hero Image',
                'verbose_name_plural': 'Hero Images',
                'db_table': 'hero_images',
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='Testimonial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Customer's full name", max_length=200)),
                ('role', models.CharField(blank=True, help_text="Customer's role/occupation (e.g., 'Amateur Photographer', 'Wedding Photographer')", max_length=200)),
                ('testimonial_text', models.TextField(help_text='The testimonial content (recommended: 2-3 sentences)')),
                ('venue', models.CharField(blank=True, help_text="Location where the course was taken (e.g., 'London Studio', 'Manchester')", max_length=200)),
                ('course_date', models.DateField(blank=True, help_text='Date when the course was taken (optional)', null=True)),
                ('rating', models.PositiveIntegerField(choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')], default=5, help_text='Rating out of 5 stars')),
                ('image', models.ImageField(blank=True, help_text='Optional: Customer photo (recommended: 200x200 pixels, square)', null=True, upload_to='testimonials/')),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order (lower numbers appear first)')),
                ('is_active', models.BooleanField(default=True, help_text='Show this testimonial on the homepage')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Testimonial',
                'verbose_name_plural': 'Testimonials',
                'db_table': 'testimonials',
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='BeforeAfterImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Title or description of this before/after comparison', max_length=200)),
                ('before_image', models.ImageField(help_text='Original/unedited image', upload_to='editing-before-after/before/')),
                ('after_image', models.ImageField(help_text='Edited/final image', upload_to='editing-before-after/after/')),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order (lower numbers appear first)')),
                ('is_active', models.BooleanField(default=True, help_text='Show this before/after comparison on the editing courses page')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Before/After Image',
                'verbose_name_plural': 'Before/After Images',
                'db_table': 'before_after_images',
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='FAQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=500)),
                ('answer', models.TextField()),
                ('order', models.PositiveIntegerField(default=0)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='faqs', to='courses.course')),
            ],
            options={
                'db_table': 'course_faqs',
                'ordering': ['order', 'id'],
            },
        ),
    ]