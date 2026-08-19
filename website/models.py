"""
Website models: HeroImage, GiftVoucherPageImage, GiftCardDesign, Testimonial, BeforeAfterImage, FAQ.
These models manage website content separate from course definitions.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
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


class GiftCardDesign(models.Model):
    """
    Printable gift card artwork. Text fields are overlaid at percentage positions
    when a voucher is downloaded or emailed after purchase.
    """
    name = models.CharField(max_length=100)
    image = models.ImageField(
        upload_to='gift-card-designs/',
        help_text='Background artwork (PNG or JPG). Text is drawn on top at the positions below.',
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text='Lower numbers appear first on the payment success page.',
    )

    value_x = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Value X (%)',
    )
    value_y = models.PositiveSmallIntegerField(
        default=42, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Value Y (%)',
    )
    value_font_size = models.PositiveSmallIntegerField(default=64)
    value_color = models.CharField(max_length=7, default='#1a1a1a')

    code_x = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Voucher code X (%)',
    )
    code_y = models.PositiveSmallIntegerField(
        default=55, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Voucher code Y (%)',
    )
    code_font_size = models.PositiveSmallIntegerField(default=32)
    code_color = models.CharField(max_length=7, default='#1a1a1a')

    recipient_x = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Recipient X (%)',
    )
    recipient_y = models.PositiveSmallIntegerField(
        default=68, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Recipient Y (%)',
    )
    recipient_font_size = models.PositiveSmallIntegerField(default=28)
    recipient_color = models.CharField(max_length=7, default='#333333')

    message_x = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Message X (%)',
    )
    message_y = models.PositiveSmallIntegerField(
        default=76, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Message Y (%)',
    )
    message_font_size = models.PositiveSmallIntegerField(default=22)
    message_color = models.CharField(max_length=7, default='#333333')
    message_max_width_pct = models.PositiveSmallIntegerField(
        default=80,
        validators=[MinValueValidator(20), MaxValueValidator(100)],
        help_text='Wrap long messages within this width (% of image).',
    )

    expiry_x = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Expiry X (%)',
    )
    expiry_y = models.PositiveSmallIntegerField(
        default=88, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Expiry Y (%)',
    )
    expiry_font_size = models.PositiveSmallIntegerField(default=18)
    expiry_color = models.CharField(max_length=7, default='#555555')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gift_card_design'
        ordering = ['display_order', 'name']
        verbose_name = 'Gift card design'
        verbose_name_plural = 'Gift card designs'

    def __str__(self):
        return self.name


class NewsletterModalSettings(models.Model):
    """
    Singleton settings for the site-wide newsletter signup modal.
    Platform super users can change the background image and focal point.
    """
    image = models.ImageField(
        upload_to='newsletter/modal/',
        blank=True,
        null=True,
        help_text=(
            'Background for the newsletter popup. Leave empty to use the default static image. '
            'Recommended: portrait or tall photo (e.g. 800×1200px).'
        ),
    )
    desktop_focus_x = models.PositiveSmallIntegerField(
        default=85,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Desktop: horizontal focus (0 = left edge, 100 = right edge).',
    )
    desktop_focus_y = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Desktop: vertical focus (0 = top, 100 = bottom).',
    )
    mobile_focus_x = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Mobile: horizontal focus (0 = left, 100 = right).',
    )
    mobile_focus_y = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Mobile: vertical focus (0 = top, 100 = bottom).',
    )
    desktop_zoom = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(100), MaxValueValidator(200)],
        help_text='Desktop: 100 = default crop; increase to zoom in on the focal point.',
    )
    mobile_zoom = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(100), MaxValueValidator(200)],
        help_text='Mobile: 100 = default crop; increase to zoom in on the focal point.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'newsletter_modal_settings'
        verbose_name = 'Newsletter modal'
        verbose_name_plural = 'Newsletter modal'

    def __str__(self):
        return 'Newsletter modal settings'

    @property
    def desktop_background_position(self):
        return f'{self.desktop_focus_x}% {self.desktop_focus_y}%'

    @property
    def mobile_background_position(self):
        return f'{self.mobile_focus_x}% {self.mobile_focus_y}%'

    @staticmethod
    def image_background_size(zoom):
        zoom_pct = 100 if zoom is None else int(zoom)
        zoom_pct = max(100, min(200, zoom_pct))
        image_size = 'cover' if zoom_pct <= 100 else f'{zoom_pct}%'
        return f'100% 100%, {image_size}'

    @property
    def desktop_background_size(self):
        return self.image_background_size(self.desktop_zoom)

    @property
    def mobile_background_size(self):
        return self.image_background_size(self.mobile_zoom)

    @classmethod
    def get_singleton(cls):
        return cls.objects.first()


class GoogleReviewsSettings(models.Model):
    """
    Homepage Google reviews trust badge — one row, edited in admin.
    """
    is_active = models.BooleanField(
        default=True,
        help_text='Show the Google reviews badge on the homepage.',
    )
    business_name = models.CharField(
        max_length=200,
        default='GD Photography Ltd',
    )
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=5.0,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Average star rating (1.0–5.0).',
    )
    review_count = models.PositiveIntegerField(
        default=0,
        help_text='Total number of Google reviews. Leave at 0 to hide the count.',
    )
    reviews_url = models.URLField(
        max_length=500,
        default=(
            'https://www.google.com/search?q=GD+Photography+Ltd&hl=en-GB'
            '#lrd=0xab70654900d0b227:0x926a542e36e35028,1'
        ),
        help_text='Link to your Google reviews (opens Google).',
    )
    google_place_id = models.CharField(
        max_length=128,
        blank=True,
        default='ChIJJ7LQAEllcKsRKFDjNi5UapI',
        help_text='Google Place ID (ChIJ…). Leave blank to look up automatically when the API key is set.',
    )
    google_cid = models.CharField(
        max_length=32,
        blank=True,
        default='10550337634534903848',
        help_text='Google Business Profile CID. Used to verify the correct listing is selected.',
    )
    use_live_reviews = models.BooleanField(
        default=True,
        help_text=(
            'Load the most relevant Google reviews live on the homepage when '
            'GOOGLE_PLACES_API_KEY is configured. Manual featured reviews are used as a fallback.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'google_reviews_settings'
        verbose_name = 'Google reviews'
        verbose_name_plural = 'Google reviews'

    def __str__(self):
        return 'Google reviews settings'

    @classmethod
    def get_singleton(cls):
        return cls.objects.first()


class GoogleReviewHighlight(models.Model):
    """Featured Google review shown on the homepage (admin-curated)."""
    settings = models.ForeignKey(
        GoogleReviewsSettings,
        on_delete=models.CASCADE,
        related_name='highlights',
    )
    author_name = models.CharField(max_length=120)
    review_text = models.TextField()
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    author_photo = models.ImageField(
        upload_to='google-reviews/',
        blank=True,
        null=True,
        help_text='Optional reviewer photo. Leave empty to use initials or a photo URL.',
    )
    author_photo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='Optional photo URL (e.g. from Google). Used when no uploaded image.',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'google_review_highlights'
        ordering = ['order', 'id']
        verbose_name = 'Featured Google review'
        verbose_name_plural = 'Featured Google reviews'

    def __str__(self):
        return f'{self.author_name} ({self.rating}★)'


class HeroImage(models.Model):
    """Hero images for homepage slider - managed by platform admins."""

    ORIENTATION_BOTH = 'both'
    ORIENTATION_LANDSCAPE = 'landscape'
    ORIENTATION_PORTRAIT = 'portrait'
    SCREEN_ORIENTATION_CHOICES = [
        (ORIENTATION_BOTH, 'Both portrait and landscape'),
        (ORIENTATION_LANDSCAPE, 'Landscape screens only'),
        (ORIENTATION_PORTRAIT, 'Portrait screens only'),
    ]

    image = models.ImageField(
        upload_to='hero-images/',
        help_text=(
            'Recommended size: 1000×667 px (3:2) for landscape-oriented screens, '
            'or a tall portrait crop for phones. Text overlay is fixed on the homepage.'
        ),
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show this image in the hero slider"
    )
    screen_orientation = models.CharField(
        max_length=16,
        choices=SCREEN_ORIENTATION_CHOICES,
        default=ORIENTATION_BOTH,
        db_column='screen_orientation',
        verbose_name='Show on',
        help_text=(
            'Landscape-only suits wide photos on tablets and desktops; '
            'portrait-only suits tall photos on phones held upright.'
        ),
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


    @classmethod
    def get_singleton(cls):
        return cls.objects.first()


DEFAULT_REMINDER_EMAIL_INTRO = (
    'This is a friendly reminder that your photography course is tomorrow.'
)
DEFAULT_REMINDER_EMAIL_CLOSING = (
    'We look forward to seeing you tomorrow. If you have any questions before '
    'the course, please contact your tutor.'
)


class WorkshopReminderEmailSettings(models.Model):
    """
    Singleton copy for the day-before workshop reminder email.
    Superusers edit the shared intro and closing; per-workshop notes live on each workshop.
    """

    intro = models.TextField(
        blank=True,
        default=DEFAULT_REMINDER_EMAIL_INTRO,
        help_text='Opening paragraph in every day-before reminder email.',
    )
    closing = models.TextField(
        blank=True,
        default=DEFAULT_REMINDER_EMAIL_CLOSING,
        help_text=(
            'Closing paragraph before the footer. Tutor contact details are inserted '
            'automatically when a tutor is assigned.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workshop_reminder_email_settings'
        verbose_name = 'Workshop reminder email'
        verbose_name_plural = 'Workshop reminder email'

    def __str__(self):
        return 'Workshop reminder email settings'

    @classmethod
    def get_singleton(cls):
        return cls.objects.first()

    def intro_text(self):
        return (self.intro or '').strip() or DEFAULT_REMINDER_EMAIL_INTRO

    def closing_text(self):
        return (self.closing or '').strip() or DEFAULT_REMINDER_EMAIL_CLOSING


class LegalPage(models.Model):
    """
    Editable legal pages (terms and privacy). Two fixed rows — edit in admin as superuser.
    """
    TERMS = 'terms'
    PRIVACY = 'privacy'
    PAGE_KEY_CHOICES = [
        (TERMS, 'Terms and conditions'),
        (PRIVACY, 'Privacy policy'),
    ]

    page_key = models.CharField(max_length=16, choices=PAGE_KEY_CHOICES, unique=True, editable=False)
    page_title = models.CharField(max_length=200, help_text='Heading shown at the top of the page.')
    browser_title = models.CharField(max_length=200, help_text='Browser tab title.')
    meta_description = models.CharField(max_length=500, blank=True)
    meta_keywords = models.CharField(max_length=500, blank=True)
    body = models.TextField(help_text='Main page content (HTML).')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_pages'
        verbose_name = 'Legal page'
        verbose_name_plural = 'Legal pages'

    def __str__(self):
        return self.get_page_key_display()