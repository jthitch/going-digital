"""
Website models: HeroImage, GiftVoucherPageImage, Testimonial, BeforeAfterImage, FAQ.
These models manage website content separate from course definitions.
"""
from django.db import models
from courses.models import Course


class GiftVoucherPageImage(models.Model):
    """
    Single promotional image for /gift-vouchers/ (one row — add via admin once).
    Managed alongside hero images for platform admins.
    """
    image = models.ImageField(
        upload_to='gift-vouchers/',
        help_text='Shown below the title on the gift vouchers page. Recommended: wide graphic (e.g. voucher artwork).',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gift_voucher_page_image'
        verbose_name = 'Gift vouchers page image'
        verbose_name_plural = 'Gift vouchers page image'

    def __str__(self):
        return 'Gift vouchers page image'


class HeroImage(models.Model):
    """Hero images for homepage slider - managed by platform admins."""
    image = models.ImageField(
        upload_to='hero-images/',
        help_text="Recommended size: 1000x667 pixels (3:2 aspect ratio). Text overlay is fixed on the homepage."
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this image in the hero slider"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'hero_images'
        ordering = ['order', 'created_at']
        verbose_name = 'Hero Image'
        verbose_name_plural = 'Hero Images'
    
    def __str__(self):
        return f"Hero Image {self.id} (Order: {self.order})"


class Testimonial(models.Model):
    """Customer testimonials for homepage - managed by platform admins."""
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    name = models.CharField(
        max_length=200,
        help_text="Customer's full name"
    )
    role = models.CharField(
        max_length=200,
        blank=True,
        help_text="Customer's role/occupation (e.g., 'Amateur Photographer', 'Wedding Photographer')"
    )
    testimonial_text = models.TextField(
        help_text="The testimonial content (recommended: 2-3 sentences)"
    )
    venue = models.CharField(
        max_length=200,
        blank=True,
        help_text="Location where the course was taken (e.g., 'London Studio', 'Manchester')"
    )
    course_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date when the course was taken (optional)"
    )
    rating = models.PositiveIntegerField(
        choices=RATING_CHOICES,
        default=5,
        help_text="Rating out of 5 stars"
    )
    image = models.ImageField(
        upload_to='testimonials/',
        blank=True,
        null=True,
        help_text="Optional: Customer photo (recommended: 200x200 pixels, square)"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this testimonial on the homepage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'testimonials'
        ordering = ['order', 'created_at']
        verbose_name = 'Testimonial'
        verbose_name_plural = 'Testimonials'
    
    def __str__(self):
        return f"{self.name} - {self.role or 'Testimonial'}"


class BeforeAfterImage(models.Model):
    """Before and after images for editing courses page - managed by platform admins."""
    title = models.CharField(
        max_length=200,
        help_text="Title or description of this before/after comparison"
    )
    before_image = models.ImageField(
        upload_to='editing-before-after/before/',
        help_text="Original/unedited image"
    )
    after_image = models.ImageField(
        upload_to='editing-before-after/after/',
        help_text="Edited/final image"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this before/after comparison on the editing courses page"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'before_after_images'
        ordering = ['order', 'created_at']
        verbose_name = 'Before/After Image'
        verbose_name_plural = 'Before/After Images'
    
    def __str__(self):
        return f"{self.title} (Order: {self.order})"


class FAQ(models.Model):
    """FAQ entries for courses - used for FAQPage schema."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=500)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'course_faqs'
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"{self.course.title}: {self.question[:50]}"


class Redirect(models.Model):
    """
    Permanent (301) or temporary (302) redirects for managing URL changes.
    Add rows for old paths that should redirect to new paths (e.g. after a restructure).
    """
    old_path = models.CharField(
        max_length=500,
        unique=True,
        help_text="Incoming path (e.g. /photography-workshops/). Must start with /."
    )
    new_path = models.CharField(
        max_length=500,
        help_text="Destination path or full URL (e.g. /photography-courses/)."
    )
    permanent = models.BooleanField(
        default=True,
        help_text="Use 301 (permanent) if True, 302 (temporary) if False."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'redirects'
        ordering = ['old_path']
        verbose_name = 'Redirect'
        verbose_name_plural = 'Redirects'

    def __str__(self):
        return f"{self.old_path} → {self.new_path}"