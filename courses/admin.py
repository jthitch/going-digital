from django.contrib import admin
from .forms import CourseAdminForm
from .models import Content, Course, CourseCategory, CourseMedia, CourseSkillLevel, Image, Instructor, Venue, VenueContent, VenueMedia, Workshop


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    """Edit gd_image records (course images, etc.)."""
    list_display = ['id', 'file_name', 'source_name', 'image_type_id', 'active', 'mime_type', 'width', 'height']
    list_filter = ['active', 'image_type_id', 'image_category_id']
    search_fields = ['file_name', 'source_name', 'description']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']

    fieldsets = [
        ('File', {
            'fields': ('file_name', 'source_name', 'mime_type', 'file_size', 'height', 'width', 'checksum', 'converted')
        }),
        ('Classification', {
            'fields': ('image_type_id', 'image_category_id', 'link_to', 'active', 'user_id')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Audit', {
            'fields': ('createdby_id', 'updatedby_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change:
            obj.createdby_id = request.user.id
            obj.created_at = now
        obj.updatedby_id = request.user.id
        obj.updated_at = now
        super().save_model(request, obj, form, change)


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    """Edit gd_content records (course page content, meta, etc.)."""
    list_display = ['id', 'content_title', 'active', 'content_type_id', 'parent', 'created_at']
    list_filter = ['active', 'exclude_from_search']
    search_fields = ['content_title', 'main_content', 'meta_title', 'meta_description', 'search_keywords']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at', 'date_last_viewed', 'requests']

    fieldsets = [
        ('Identity', {
            'fields': ('content_title', 'PageTitleX', 'content_type_id', 'content_master_ref_id', 'parent', 'active', 'exclude_from_search', 'requests')
        }),
        ('Header', {
            'fields': ('header_image_type', 'header_image_id', 'header_content', 'strapline')
        }),
        ('Main content', {
            'fields': ('main_content', 'sub_content', 'side_content', 'footer_content')
        }),
        ('Video', {
            'fields': ('youtube_code', 'video_url', 'video_inline', 'video_image_id'),
            'classes': ('collapse',)
        }),
        ('SEO & meta', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords', 'meta_image_id', 'social_title', 'search_keywords', 'change_frequency_id')
        }),
        ('Audit', {
            'fields': ('createdby_id', 'updatedby_id', 'created_at', 'updated_at', 'date_last_viewed'),
            'classes': ('collapse',)
        }),
    ]

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change:
            obj.createdby_id = request.user.id
            obj.created_at = now
        obj.updatedby_id = request.user.id
        obj.updated_at = now
        super().save_model(request, obj, form, change)


@admin.register(CourseSkillLevel)
class CourseSkillLevelAdmin(admin.ModelAdmin):
    list_display = ['skill_level', 'active', 'display_order']
    list_filter = ['active']
    search_fields = ['skill_level']
    ordering = ['display_order', 'skill_level']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change:
            obj.createdby_id = request.user.id
            obj.created_at = now
        obj.updatedby_id = request.user.id
        obj.updated_at = now
        super().save_model(request, obj, form, change)


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ['course_category', 'parent', 'active', 'exclude_from_course_list', 'display_order']
    list_filter = ['active', 'exclude_from_course_list']
    search_fields = ['course_category']
    ordering = ['display_order', 'course_category']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change:
            obj.createdby_id = request.user.id
            obj.created_at = now
        obj.updatedby_id = request.user.id
        obj.updated_at = now
        super().save_model(request, obj, form, change)


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialties', 'years_experience', 'is_active']
    list_filter = ['is_active', 'years_experience']
    search_fields = ['user__email', 'user__firstname', 'user__lastname', 'specialties']
    readonly_fields = ['created_at', 'updated_at']


class CourseMediaInline(admin.TabularInline):
    model = CourseMedia
    extra = 0
    fields = ['media_type', 'image', 'video_file', 'video_url', 'caption', 'display_order']
    verbose_name = 'Image/Video'
    verbose_name_plural = 'Images & Videos'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Course admin - maps to legacy gd_course table. Content editable inline."""
    form = CourseAdminForm
    inlines = [CourseMediaInline]

    class Media:
        js = ('courses/js/admin-course-media.js',)
        css = {'all': ('admin/css/course-admin.css',)}
    autocomplete_fields = ['course_skill_level']
    list_display = ['course_name', 'course_skill_level', 'course_category', 'active', 'created_at']

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change:
            obj.createdby_id = request.user.id
            obj.created_at = now
        obj.updatedby_id = request.user.id
        obj.updated_at = now
        super().save_model(request, obj, form, change)
        if hasattr(form, '_save_content') and form.cleaned_data:
            form._save_content(obj, request)
    list_filter = ['active', 'course_skill_level', 'course_category', 'created_at']
    search_fields = ['course_name', 'course_description', 'description_for_workshop', 'slug']
    prepopulated_fields = {'slug': ('course_name',)}
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']
    list_editable = ['active']

    fieldsets = [
        ('Course Details', {
            'fields': (
                'course_name', 'course_abbr', 'slug', 'course_description', 'description_for_workshop',
                'link_name', 'link_title', 'filter_name', 'page_title',
            )
        }),
        ('Classification', {
            'fields': ('course_category', 'course_skill_level', 'content', 'image', 'region_id')
        }),
        ('Page Content', {
            'fields': (
                'content_title', 'header_content', 'strapline',
                'main_content', 'sub_content', 'footer_content',
                'meta_title', 'meta_description', 'meta_keywords',
            ),
            'description': 'Edit the linked Content. Select a Content above or fill these to create one.'
        }),
        ('Display & status', {
            'fields': ('active', 'status_id', 'clickable', 'show_workshops', 'display_order', 'use_on_filter', 'is_one_to_one')
        }),
        ('Legacy IDs', {
            'fields': ('workshop_image_id', 'CID', 'createdby_id', 'updatedby_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'course',
        'venue',
        'date',
        'cost',
        'max_places',
        'places_booked',
        'active'
    ]
    list_filter = ['active', 'date', 'course']
    search_fields = ['course__course_name', 'venue__venue_name', 'venue__location']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']


class VenueContentInline(admin.StackedInline):
    model = VenueContent
    extra = 0
    max_num = 1


class VenueMediaInline(admin.TabularInline):
    model = VenueMedia
    extra = 1
    fields = ['image', 'caption', 'display_order']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['id', 'venue_name', 'slug', 'location', 'active']
    list_filter = ['active']
    search_fields = ['venue_name', 'venue_address', 'location', 'slug']
    inlines = [VenueContentInline, VenueMediaInline]


