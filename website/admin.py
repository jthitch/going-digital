from django.contrib import admin
from .models import GiftVoucherPageImage, HeroImage, Testimonial, BeforeAfterImage, FAQ, Redirect
from core.permissions import PlatformAdminMixin


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


@admin.register(HeroImage)
class HeroImageAdmin(PlatformAdminMixin, admin.ModelAdmin):
    """Hero image admin - only accessible to platform admins."""
    list_display = ['id', 'image_preview', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    list_editable = ['order', 'is_active']
    fieldsets = [
        ('Image', {
            'fields': ('image',),
            'description': 'Upload hero image. The text overlay is fixed on the homepage and cannot be changed per image.'
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active'),
            'description': 'Control the display order and visibility of this hero image.'
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