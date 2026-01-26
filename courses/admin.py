from django.contrib import admin
from .models import Course, CourseInstance, Instructor, FAQ, HeroImage, Testimonial, BeforeAfterImage
from .forms import CourseAdminForm
from core.permissions import PlatformAdminMixin


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


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialties', 'years_experience', 'is_active']
    list_filter = ['is_active', 'years_experience']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'specialties']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    form = CourseAdminForm
    list_display = ['title', 'level', 'category', 'price', 'duration_hours', 'is_active']
    list_filter = ['level', 'category', 'is_active', 'created_at']
    search_fields = ['title', 'description', 'short_description']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = []
    
    def get_fieldsets(self, request, obj=None):
        """Organize fields into sections and exclude what_youll_learn JSON field."""
        fieldsets = [
            ('Basic Information', {
                'fields': ('title', 'slug', 'short_description', 'description')
            }),
            ('Course Details', {
                'fields': ('level', 'category', 'duration_hours', 'max_students', 'price')
            }),
            ('Content', {
                'fields': ('what_youll_learn_text', 'audience', 'prerequisites')
            }),
            ('SEO & Media', {
                'fields': ('image', 'meta_description', 'meta_keywords')
            }),
            ('Status', {
                'fields': ('is_active',)
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]
        return fieldsets


@admin.register(CourseInstance)
class CourseInstanceAdmin(admin.ModelAdmin):
    list_display = [
        'course',
        'location',
        'instructor',
        'start_date',
        'end_date',
        'current_students',
        'enrollment_open'
    ]
    list_filter = ['enrollment_open', 'start_date', 'location__franchise', 'course']
    search_fields = ['course__title', 'location__name', 'location__city']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at']


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
