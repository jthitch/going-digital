from django.contrib import admin
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .forms_newsletter import NewsletterModalSettingsForm
from .forms_legal import LegalPageAdminForm
from .models import (
    GiftCardDesign,
    GiftVoucherPageImage,
    GoogleReviewHighlight,
    GoogleReviewsSettings,
    HeroImage,
    LegalPage,
    NewsletterModalSettings,
    Testimonial,
    BeforeAfterImage,
    FAQ,
    Redirect,
    WorkshopReminderEmailSettings,
)
from core.permissions import PlatformAdminMixin, SuperuserOnlyAdminMixin


@admin.register(GiftVoucherPageImage)
class GiftVoucherPageImageAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Gift vouchers page image — same audience as Hero Images; only one row allowed."""
    list_display = ['id', 'image_preview', 'updated_at']
    fieldsets = [
        (
            'Gift vouchers page',
            {
                'fields': ('image',),
                'description': (
                    'Image shown on /gift-vouchers/ below the heading. '
                    'Use the same kind of asset as homepage hero images (platform-managed).'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('updated_at',), 'classes': ('collapse',)},
        ),
    ]
    readonly_fields = ['updated_at']

    def image_preview(self, obj):
        if obj.image:
            from django.utils.html import format_html

            return format_html(
                '<img src="{}" style="max-height: 80px; width: auto;" />', obj.image.url
            )
        return 'No image'

    image_preview.short_description = 'Preview'

    def has_add_permission(self, request):
        if GiftVoucherPageImage.objects.exists():
            return False
        return request.user.is_platform_admin

    def has_change_permission(self, request, obj=None):
        return request.user.is_platform_admin

    def has_delete_permission(self, request, obj=None):
        return request.user.is_platform_admin


@admin.register(GiftCardDesign)
class GiftCardDesignAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Uploadable gift card artwork with overlay positions for voucher details."""
    list_display = ['name', 'image_preview', 'is_active', 'display_order', 'updated_at']
    list_editable = ['is_active', 'display_order']
    list_filter = ['is_active']
    search_fields = ['name']
    readonly_fields = ['image_preview', 'created_at', 'updated_at']
    fieldsets = [
        (
            'Design',
            {
                'fields': ('name', 'image', 'image_preview', 'is_active', 'display_order'),
                'description': (
                    'Upload the background artwork. Voucher details (logo, amount, message, '
                    'code, recipient and expiry) are laid out automatically on a white panel '
                    'over the image. Colours below control the overlay text.'
                ),
            },
        ),
        (
            'Text colours',
            {
                'fields': (
                    'value_color', 'code_color', 'recipient_color',
                    'message_color', 'expiry_color',
                ),
                'description': 'Optional colours for amount, code, labels, message and footer text.',
            },
        ),
        (
            'Advanced position overrides (optional)',
            {
                'classes': ('collapse',),
                'fields': (
                    'value_x', 'value_y', 'value_font_size',
                    'code_x', 'code_y', 'code_font_size',
                    'recipient_x', 'recipient_y', 'recipient_font_size',
                    'message_x', 'message_y', 'message_font_size', 'message_max_width_pct',
                    'expiry_x', 'expiry_y', 'expiry_font_size',
                ),
                'description': 'Legacy fields — the renderer uses automatic layout and ignores positions.',
            },
        ),
        (
            'Timestamps',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    ]

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="max-height: 120px; width: auto;" />',
                obj.image.url,
            )
        return 'No image'

    image_preview.short_description = 'Preview'

    def has_add_permission(self, request):
        return request.user.is_platform_admin

    def has_change_permission(self, request, obj=None):
        return request.user.is_platform_admin

    def has_delete_permission(self, request, obj=None):
        return request.user.is_platform_admin


@admin.register(NewsletterModalSettings)
class NewsletterModalSettingsAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Newsletter signup modal — image and focal point (one row)."""
    form = NewsletterModalSettingsForm
    list_display = ['id', 'image_preview', 'desktop_focus', 'mobile_focus', 'updated_at']
    fieldsets = [
        (
            'Background image',
            {
                'fields': ('image', 'image_preview'),
                'description': (
                    'Image behind the newsletter popup on every page. '
                    'Leave empty to keep the default static artwork.'
                ),
            },
        ),
        (
            'Image position — desktop',
            {
                'fields': (
                    'desktop_position_preview',
                    'desktop_focus_x',
                    'desktop_focus_y',
                    'desktop_zoom',
                ),
                'description': (
                    'Drag the image in the preview frame to choose what visitors see on wider screens. '
                    'Text sits on the left; aim the subject toward the right (e.g. 85% horizontal).'
                ),
            },
        ),
        (
            'Image position — mobile',
            {
                'fields': (
                    'mobile_position_preview',
                    'mobile_focus_x',
                    'mobile_focus_y',
                    'mobile_zoom',
                ),
                'description': (
                    'Drag the image in the mobile preview. The form sits at the bottom; '
                    'a lower vertical value (e.g. 20–35%) often keeps faces visible above the gradient.'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('updated_at',), 'classes': ('collapse',)},
        ),
    ]
    readonly_fields = [
        'updated_at',
        'image_preview',
        'desktop_position_preview',
        'mobile_position_preview',
    ]

    class Media:
        css = {'all': ('admin/css/newsletter-modal-admin.css',)}
        js = ('admin/js/admin-newsletter-modal.js',)

    def image_preview(self, obj):
        url = self._image_url(obj)
        if not url:
            return 'No image (using default static file)'
        return format_html(
            '<img src="{}" style="max-height: 160px; width: auto; border-radius: 8px;" />',
            url,
        )

    image_preview.short_description = 'Preview'

    def desktop_focus(self, obj):
        if not obj:
            return '—'
        return obj.desktop_background_position

    desktop_focus.short_description = 'Desktop position'

    def mobile_focus(self, obj):
        if not obj:
            return '—'
        return obj.mobile_background_position

    mobile_focus.short_description = 'Mobile position'

    def _default_image_url(self):
        return static('img/newsletter/man-in-shaddow-newsletter-signup.jpg')

    def _image_url(self, obj):
        if obj and obj.image:
            return obj.image.url
        return self._default_image_url()

    def _interactive_position_preview(self, obj, variant):
        url = self._image_url(obj)
        if variant == 'mobile':
            x = 50 if not obj else int(obj.mobile_focus_x)
            y = 25 if not obj else int(obj.mobile_focus_y)
            zoom = 100 if not obj else int(obj.mobile_zoom)
            preview_id = 'newsletter-admin-preview-mobile'
            modifier = 'mobile'
            label = 'Mobile modal'
        else:
            x = 85 if not obj else int(obj.desktop_focus_x)
            y = 50 if not obj else int(obj.desktop_focus_y)
            zoom = 100 if not obj else int(obj.desktop_zoom)
            preview_id = 'newsletter-admin-preview-desktop'
            modifier = 'desktop'
            label = 'Desktop modal'

        bg_size = NewsletterModalSettings.image_background_size(zoom)

        return format_html(
            '<div class="newsletter-admin-preview newsletter-admin-preview--{}" id="{}" '
            'data-variant="{}" data-image-url="{}" data-default-image-url="{}" '
            'data-focus-x="{}" data-focus-y="{}" data-zoom="{}">'
            '<div class="newsletter-admin-preview__frame" data-preview-frame>'
            '<div class="newsletter-admin-preview__panel" data-preview-viewport '
            'style="--newsletter-preview-bg: url(\'{}\');background-position:{}% {}%;'
            'background-size:{};">'
            '<div class="newsletter-admin-preview__mock" aria-hidden="true">'
            '<p class="newsletter-admin-preview__mock-title">Become a better photographer</p>'
            '<p class="newsletter-admin-preview__mock-lead">Course news, tips, and offers.</p>'
            '<span class="newsletter-admin-preview__mock-input"></span>'
            '<span class="newsletter-admin-preview__mock-btn"></span>'
            '</div>'
            '<span class="newsletter-admin-preview__focus" data-preview-focus '
            'title="Drag to position the image" style="left:{}%;top:{}%;"></span>'
            '</div>'
            '</div>'
            '<p class="newsletter-admin-preview__hint">'
            '{} — drag anywhere on the frame or the blue handle to reposition the photo. '
            'Use the sliders below to fine-tune position and zoom, then save.</p>'
            '</div>',
            modifier,
            preview_id,
            variant,
            url,
            self._default_image_url(),
            x,
            y,
            zoom,
            url,
            x,
            y,
            bg_size,
            x,
            y,
            label,
        )

    @admin.display(description='Drag to position')
    def desktop_position_preview(self, obj):
        return self._interactive_position_preview(obj, 'desktop')

    @admin.display(description='Drag to position')
    def mobile_position_preview(self, obj):
        return self._interactive_position_preview(obj, 'mobile')

    def has_add_permission(self, request):
        if NewsletterModalSettings.objects.exists():
            return False
        return request.user.is_platform_admin

    def has_change_permission(self, request, obj=None):
        return request.user.is_platform_admin

    def has_delete_permission(self, request, obj=None):
        return request.user.is_platform_admin


@admin.register(WorkshopReminderEmailSettings)
class WorkshopReminderEmailSettingsAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    """Shared intro and closing copy for day-before workshop reminder emails."""

    list_display = ['id', 'intro_preview', 'updated_at']
    readonly_fields = ['updated_at', 'sample_preview']
    fieldsets = [
        (
            'Reminder email copy',
            {
                'fields': ('intro', 'closing', 'sample_preview'),
                'description': (
                    'Sent automatically one day before each fixed-date workshop to confirmed students. '
                    'Course details, tutor contact, and per-workshop notes are added from each workshop '
                    '(Workshops → Reminder email).'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('updated_at',), 'classes': ('collapse',)},
        ),
    ]

    @admin.display(description='Intro')
    def intro_preview(self, obj):
        if not obj:
            return '—'
        text = (obj.intro or '').strip()
        if len(text) > 80:
            return f'{text[:77]}…'
        return text or '—'

    @admin.display(description='Sample email')
    def sample_preview(self, obj):
        from django.template.loader import render_to_string

        from bookings.email_context import workshop_reminder_preview_context
        from courses.models import Workshop

        workshop = (
            Workshop.objects.filter(open_dated=0, active=1)
            .select_related('course', 'venue')
            .order_by('-date')
            .first()
        )
        if not workshop:
            return 'No workshops available to preview.'
        context = workshop_reminder_preview_context(workshop)
        html = render_to_string('emails/workshop_reminder.html', context)
        return format_html(
            '<div style="border:1px solid #ddd;border-radius:6px;max-width:720px;'
            'overflow:auto;background:#fff;">{}</div>',
            mark_safe(html),
        )

    def has_add_permission(self, request):
        if WorkshopReminderEmailSettings.objects.exists():
            return False
        return request.user.is_active and request.user.is_superuser


@admin.register(LegalPage)
class LegalPageAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    """Terms and privacy policy — editable by superusers only."""
    form = LegalPageAdminForm
    list_display = ['page_key', 'page_title', 'updated_at']
    readonly_fields = ['page_key', 'updated_at']
    fieldsets = [
        (
            'Page',
            {
                'fields': ('page_key', 'page_title', 'browser_title'),
            },
        ),
        (
            'SEO',
            {
                'fields': ('meta_description', 'meta_keywords'),
            },
        ),
        (
            'Content',
            {
                'fields': ('body',),
                'description': (
                    'Main page body (HTML). Keep section IDs on headings if you use the table of contents links.'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('updated_at',), 'classes': ('collapse',)},
        ),
    ]


class GoogleReviewHighlightInline(admin.TabularInline):
    model = GoogleReviewHighlight
    extra = 1
    fields = (
        'is_active',
        'order',
        'author_name',
        'rating',
        'review_text',
        'author_photo',
        'author_photo_url',
    )
    ordering = ('order', 'id')


@admin.register(GoogleReviewsSettings)
class GoogleReviewsSettingsAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Homepage Google reviews section — one row."""
    inlines = [GoogleReviewHighlightInline]
    list_display = [
        'id',
        'business_name',
        'rating',
        'review_count',
        'use_live_reviews',
        'is_active',
        'updated_at',
    ]
    fieldsets = [
        (
            'Homepage summary',
            {
                'fields': ('is_active', 'business_name', 'rating', 'review_count', 'reviews_url'),
                'description': (
                    'Summary shown above “Your Photography Journey”. '
                    'When live reviews are enabled, rating and review count are refreshed from Google.'
                ),
            },
        ),
        (
            'Live Google reviews',
            {
                'fields': ('use_live_reviews', 'google_place_id', 'google_cid'),
                'description': (
                    'Set GOOGLE_PLACES_API_KEY in your environment. Google returns up to five '
                    'reviews sorted by relevance, with reviewer photos. The main GD Photography '
                    'Ltd listing is a service-area business, so the Place ID must match your '
                    '107-review Google profile.'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('updated_at',), 'classes': ('collapse',)},
        ),
    ]
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        if GoogleReviewsSettings.objects.exists():
            return False
        return request.user.is_platform_admin

    def has_change_permission(self, request, obj=None):
        return request.user.is_platform_admin

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HeroImage)
class HeroImageAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Hero image admin - only accessible to platform admins."""
    list_display = ['id', 'image_preview', 'order', 'screen_orientation', 'is_active', 'created_at']
    list_filter = ['is_active', 'screen_orientation', 'created_at']
    list_editable = ['order', 'is_active']
    fieldsets = [
        ('Image', {
            'fields': ('image',),
            'description': (
                'Upload hero image. The text overlay is fixed on the homepage and cannot be '
                'changed per image. Use a wide crop for landscape screens and a tall crop for '
                'portrait screens.'
            ),
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active', 'screen_orientation'),
            'description': (
                'Control display order, visibility, and which screen orientations show this image.'
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def image_preview(self, obj):
        """Display image preview in admin list."""
        if obj.image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-height: 50px; width: auto;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Preview'
    
    def has_add_permission(self, request):
        """Only platform admins can add hero images."""
        return request.user.is_platform_admin
    
    def has_change_permission(self, request, obj=None):
        """Only platform admins can change hero images."""
        return request.user.is_platform_admin
    
    def has_delete_permission(self, request, obj=None):
        """Only platform admins can delete hero images."""
        return request.user.is_platform_admin


@admin.register(BeforeAfterImage)
class BeforeAfterImageAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Before/After image admin - only accessible to platform admins."""
    list_display = ['id', 'title', 'before_preview', 'after_preview', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    list_editable = ['order', 'is_active']
    fieldsets = [
        ('Images', {
            'fields': ('title', 'before_image', 'after_image'),
            'description': 'Upload before and after images. Recommended size: same dimensions for both images (e.g., 1200x800 pixels).'
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active'),
            'description': 'Control the display order and visibility of this before/after comparison.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def before_preview(self, obj):
        """Display before image preview in admin list."""
        if obj.before_image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-height: 50px; width: auto;" />', obj.before_image.url)
        return "No image"
    before_preview.short_description = 'Before'
    
    def after_preview(self, obj):
        """Display after image preview in admin list."""
        if obj.after_image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-height: 50px; width: auto;" />', obj.after_image.url)
        return "No image"
    after_preview.short_description = 'After'
    
    def has_add_permission(self, request):
        """Only platform admins can add before/after images."""
        return request.user.is_platform_admin
    
    def has_change_permission(self, request, obj=None):
        """Only platform admins can change before/after images."""
        return request.user.is_platform_admin
    
    def has_delete_permission(self, request, obj=None):
        """Only platform admins can delete before/after images."""
        return request.user.is_platform_admin


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['course', 'question', 'order']
    list_filter = ['course']
    search_fields = ['question', 'answer', 'course__title']
    ordering = ['course', 'order']


@admin.register(Testimonial)
class TestimonialAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Testimonial admin - only accessible to platform admins."""
    list_display = ['name', 'role', 'venue', 'rating_display', 'image_preview', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'rating', 'created_at']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'role', 'testimonial_text', 'venue']
    fieldsets = [
        ('Testimonial Content', {
            'fields': ('name', 'role', 'testimonial_text'),
            'description': 'Customer name, their role/occupation, and their testimonial text.'
        }),
        ('Course Details', {
            'fields': ('venue', 'course_date', 'rating'),
            'description': 'Information about the course and rating.'
        }),
        ('Media', {
            'fields': ('image',),
            'description': 'Optional customer photo (recommended: 200x200 pixels, square).'
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active'),
            'description': 'Control the display order and visibility of this testimonial.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def rating_display(self, obj):
        """Display rating as stars."""
        return '★' * obj.rating + '☆' * (5 - obj.rating)
    rating_display.short_description = 'Rating'
    
    def image_preview(self, obj):
        """Display image preview in admin list."""
        if obj.image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-height: 50px; width: auto; border-radius: 50%;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Photo'
    
    def has_add_permission(self, request):
        """Only platform admins can add testimonials."""
        return request.user.is_platform_admin
    
    def has_change_permission(self, request, obj=None):
        """Only platform admins can change testimonials."""
        return request.user.is_platform_admin
    
    def has_delete_permission(self, request, obj=None):
        """Only platform admins can delete testimonials."""
        return request.user.is_platform_admin


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    """Manage URL redirects (301/302) for path changes."""
    list_display = ['old_path', 'new_path', 'permanent', 'is_active', 'updated_at']
    list_filter = ['permanent', 'is_active']
    list_editable = ['is_active']
    search_fields = ['old_path', 'new_path']
    ordering = ['old_path']