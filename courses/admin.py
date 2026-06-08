from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .admin_mixins import (
    PlatformAdminOnlyMixin,
    RegionScopedCourseAdminMixin,
    RegionScopedVenueAdminMixin,
    RegionScopedWorkshopAdminMixin,
)
from .region_scope import user_has_full_region_access
from .forms import (
    CourseAdminForm,
    CourseCategoryAdminForm,
    CourseSkillLevelAdminForm,
    ImageAdminForm,
    VenueAdminForm,
    WorkshopAdminForm,
    BooleanToggleWidget,
)
from .models import (
    Content,
    Course,
    CourseCategory,
    CourseMedia,
    CourseSkillLevel,
    Image,
    Instructor,
    LEVEL_DISPLAY_NAMES,
    Venue,
    VenueMedia,
    Workshop,
)


@admin.register(Image)
class ImageAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    """Edit gd_image records (course images, etc.)."""
    form = ImageAdminForm
    list_display = [
        'id',
        'file_name',
        'source_name',
        'get_image_type_display',
        'get_image_category_display',
        'get_user_display',
        'active',
        'mime_type',
        'width',
        'height',
    ]
    list_filter = ['active', 'image_type_id', 'image_category_id']
    search_fields = ['file_name', 'source_name', 'description']
    readonly_fields = [
        'mime_type',
        'file_size',
        'height',
        'width',
        'createdby_id',
        'updatedby_id',
        'created_at',
        'updated_at',
    ]

    fieldsets = [
        ('File', {
            'fields': ('file_name', 'source_name', 'mime_type', 'file_size', 'height', 'width')
        }),
        ('Classification', {
            'fields': ('image_type', 'image_category', 'link_to', 'active', 'image_user')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Audit', {
            'fields': ('createdby_id', 'updatedby_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]

    class Media:
        css = {'all': ('admin/css/image-admin.css',)}

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
class ContentAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
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
class CourseSkillLevelAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    form = CourseSkillLevelAdminForm
    list_display = ['level_name', 'active', 'display_order']
    list_display_links = ['level_name']
    list_filter = ['active']
    search_fields = ['skill_level']
    ordering = ['display_order', 'id']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']

    @admin.display(description='Skill level', ordering='display_order')
    def level_name(self, obj):
        return LEVEL_DISPLAY_NAMES.get(obj.pk) or obj.skill_level or '—'

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
class CourseCategoryAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    form = CourseCategoryAdminForm
    list_display = ['course_category', 'parent', 'active', 'exclude_from_course_list', 'display_order']
    list_filter = ['active', 'exclude_from_course_list']
    list_editable = ['active', 'exclude_from_course_list']
    search_fields = ['course_category']
    ordering = ['display_order', 'course_category']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']

    class Media:
        css = {'all': ('admin/css/course-category-admin.css',)}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'active':
            return forms.BooleanField(
                required=False,
                label='Active',
                widget=BooleanToggleWidget(),
            )
        if db_field.name == 'exclude_from_course_list':
            return forms.BooleanField(
                required=False,
                label='Exclude from course list',
                widget=BooleanToggleWidget(),
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

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
class InstructorAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
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
    change_form_template = 'admin/courses/course/change_form.html'
    inlines = [CourseMediaInline]

    class Media:
        js = ('courses/js/admin-course-media.js',)
        css = {'all': ('admin/css/course-admin.css',)}
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

    def _course_field_names(self):
        names = []
        for _title, opts in self.fieldsets:
            names.extend(opts['fields'])
        return names

    def get_readonly_fields(self, request, obj=None):
        if obj and not user_has_full_region_access(request.user):
            return list(dict.fromkeys(self._course_field_names() + list(self.readonly_fields)))
        return self.readonly_fields

    fieldsets = [
        ('Course Details', {
            'fields': (
                'course_name', 'course_category', 'course_skill_level', 'region', 'course_abbr', 'slug',
                'course_url',
                'course_description', 'description_for_workshop',
                'link_name', 'link_title', 'filter_name',
            )
        }),
        ('Classification', {
            'fields': ('content', 'image')
        }),
        ('Page Content', {
            'fields': (
                'content_title', 'strapline',
                'main_content', 'sub_content',
                'meta_title', 'meta_description', 'meta_keywords',
            ),
            'description': 'Edit the linked Content. Select a Content above or fill these to create one.'
        }),
        ('Display & status', {
            'fields': ('active', 'status', 'clickable', 'show_workshops', 'display_order', 'use_on_filter', 'is_one_to_one')
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
class WorkshopAdmin(RegionScopedWorkshopAdminMixin, admin.ModelAdmin):
    form = WorkshopAdminForm
    autocomplete_fields = ['course', 'venue']
    list_display = [
        'id',
        'course',
        'venue',
        'region_name',
        'get_tutor_display',
        'get_assistant_display',
        'date',
        'cost',
        'max_places',
        'spaces_booked_percent',
        'active',
    ]
    list_filter = ['active', 'date', 'course']
    search_fields = ['course__course_name', 'venue__venue_name', 'venue__location']
    date_hierarchy = 'date'
    readonly_fields = [
        'user_display',
        'createdby_display',
        'updatedby_display',
        'image_preview',
        'created_at',
        'updated_at',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course', 'venue')

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change:
            obj.createdby_id = request.user.id
            if not obj.user_id:
                obj.user_id = request.user.id
            if obj.created_at is None:
                obj.created_at = now
        obj.updatedby_id = request.user.id
        obj.updated_at = now
        super().save_model(request, obj, form, change)

    @admin.display(description='Current image')
    def image_preview(self, obj):
        if not obj or not obj.image_id:
            return '—'
        image = Image.objects.filter(pk=obj.image_id).first()
        if not image or not image.url:
            return '—'
        return format_html(
            '<img src="{}" alt="" style="max-height:50px;max-width:100%;">',
            image.url,
        )

    @admin.display(description='User')
    def user_display(self, obj):
        return obj.get_user_display()

    @admin.display(description='Created by')
    def createdby_display(self, obj):
        return obj.get_createdby_display()

    @admin.display(description='Updated by')
    def updatedby_display(self, obj):
        return obj.get_updatedby_display()

    class Media:
        css = {'all': ('admin/css/workshop-admin.css',)}
        js = ('courses/js/admin-workshop.js',)

    @admin.display(description='Region', ordering='region_id')
    def region_name(self, obj):
        return obj.get_region_display() or '—'

    @admin.display(description='Booked', ordering='places_booked')
    def spaces_booked_percent(self, obj):
        max_places = obj.max_places or 0
        booked = obj.places_booked or 0
        if max_places <= 0:
            return format_html('<span class="gd-workshop-booked gd-workshop-booked-na" title="No capacity set">—</span>')
        percent = min(100, round(100 * booked / max_places))
        bar_class = 'gd-workshop-booked-full' if percent >= 100 else ''
        if percent >= 80:
            bar_class = 'gd-workshop-booked-high'
        return format_html(
            '<span class="gd-workshop-booked {}" title="{} of {} places">'
            '<span class="gd-workshop-booked-pct">{}%</span>'
            '<span class="gd-workshop-booked-count">({}/{})</span>'
            '</span>',
            bar_class,
            booked,
            max_places,
            percent,
            booked,
            max_places,
        )


class VenueMediaInline(admin.TabularInline):
    model = VenueMedia
    extra = 1
    fields = ['image', 'caption', 'display_order']
    verbose_name = 'Venue image'
    verbose_name_plural = 'Venue images'

    def _parent_venue_admin(self):
        return self.admin_site._registry[Venue]

    def has_view_permission(self, request, obj=None):
        parent = self._parent_venue_admin()
        if obj is None:
            return parent.has_add_permission(request)
        return parent.has_view_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        parent = self._parent_venue_admin()
        if obj is None:
            return parent.has_add_permission(request)
        return parent.has_change_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return self._parent_venue_admin().has_add_permission(request)
        return self._parent_venue_admin().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return self._parent_venue_admin().has_add_permission(request)
        return self._parent_venue_admin().has_change_permission(request, obj)


class VenueApprovalStateFilter(admin.SimpleListFilter):
    title = 'approval status'
    parameter_name = 'approval_state'

    def lookups(self, request, model_admin):
        return (
            ('pending', 'Pending approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('not_submitted', 'Not submitted'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'pending':
            return queryset.filter(approval_requested=1, approved=0, rejected=0)
        if value == 'approved':
            return queryset.filter(approved=1)
        if value == 'rejected':
            return queryset.filter(rejected=1)
        if value == 'not_submitted':
            return queryset.filter(approval_requested=0, approved=0, rejected=0)
        return queryset


@admin.register(Venue)
class VenueAdmin(RegionScopedVenueAdminMixin, admin.ModelAdmin):
    form = VenueAdminForm
    change_list_template = 'admin/courses/venue/change_list.html'
    prepopulated_fields = {'slug': ('venue_name',)}
    readonly_fields = ['created_at', 'updated_at']
    list_display = [
        'id',
        'venue_name',
        'slug',
        'location',
        'get_region_display',
        'approval_status',
        'get_county_display',
        'active',
    ]
    list_filter = [VenueApprovalStateFilter, 'active', 'region_id']
    search_fields = ['venue_name', 'venue_address', 'location', 'slug']
    inlines = [VenueMediaInline]

    franchisee_fieldsets = [
        (None, {
            'fields': (
                'venue_region',
                'county',
                'venue_name',
                'location',
                'slug',
                'venue_address',
                'venue_telephone',
                'venue_url',
                'latitude',
                'longitude',
                'show_workshops',
            ),
            'description': (
                'Complete the venue details, content, and images below before approval. '
                'You can assign pending venues to workshops, but workshops cannot be '
                'published until an administrator approves this venue.'
            ),
        }),
        ('Approval', {
            'fields': ('approval_status', 'reject_reason'),
            'description': (
                'Approval is handled by administrators. If your venue was rejected, '
                'update the listing and save to resubmit for review.'
            ),
        }),
        ('Venue content', {
            'fields': (
                'content_title',
                'strapline',
                'main_content',
                'sub_content',
                'meta_title',
                'meta_description',
                'meta_keywords',
            ),
            'description': (
                'Edits the linked gd_content record (stored as content_id on the venue). '
                'Fill in fields to create content when none is linked yet.'
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    franchisee_view_fieldsets = [
        (None, {
            'fields': (
                'display_venue_region',
                'display_county',
                'venue_name',
                'location',
                'slug',
                'venue_address',
                'venue_telephone',
                'venue_url',
                'latitude',
                'longitude',
                'show_workshops',
            ),
            'description': (
                'This venue is approved. You can view the listing below but cannot edit it. '
                'Contact an administrator if changes are required.'
            ),
        }),
        ('Approval', {
            'fields': ('approval_status', 'reject_reason'),
        }),
        ('Venue content', {
            'fields': (
                'display_content_title',
                'display_strapline',
                'display_main_content',
                'display_sub_content',
                'display_meta_title',
                'display_meta_description',
                'display_meta_keywords',
            ),
            'description': 'Page content linked to this venue (read-only).',
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    fieldsets = [
        (None, {
            'fields': (
                'active',
                'status',
                'venue_region',
                'venue_user',
                'county',
                'venue_name',
                'location',
                'slug',
                'venue_address',
                'venue_telephone',
                'venue_url',
                'latitude',
                'longitude',
                'show_workshops',
            ),
        }),
        ('Approval', {
            'fields': ('approved', 'approval_requested', 'rejected', 'reject_reason'),
            'description': 'Approve the venue so franchisees can publish workshops at this location.',
        }),
        ('Venue content', {
            'fields': (
                'content_title',
                'strapline',
                'main_content',
                'sub_content',
                'meta_title',
                'meta_description',
                'meta_keywords',
            ),
            'description': (
                'Edits the linked gd_content record (stored as content_id on the venue). '
                'Fill in fields to create content when none is linked yet.'
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    class Media:
        css = {
            'all': (
                'admin/css/venue-admin.css',
                'admin/css/course-admin.css',
            ),
        }
        js = (
            'admin/js/urlify.js',
            'admin/js/prepopulate.js',
            'courses/js/admin-venue.js',
        )

    def _venue_content_value(self, obj, attr, *, allow_html=False, empty='—'):
        if not obj:
            return empty
        content = obj.get_content()
        if not content:
            return empty
        value = getattr(content, attr, None) or ''
        if not value:
            return empty
        if allow_html:
            return mark_safe(value)
        return value

    @admin.display(description='Region', ordering='region_id')
    def display_venue_region(self, obj):
        return obj.get_region_display()

    @admin.display(description='County', ordering='county_id')
    def display_county(self, obj):
        return obj.get_county_display()

    @admin.display(description='Content title')
    def display_content_title(self, obj):
        return self._venue_content_value(obj, 'content_title')

    @admin.display(description='Strapline')
    def display_strapline(self, obj):
        return self._venue_content_value(obj, 'strapline')

    @admin.display(description='Main content')
    def display_main_content(self, obj):
        return self._venue_content_value(obj, 'main_content', allow_html=True)

    @admin.display(description='Sub content')
    def display_sub_content(self, obj):
        return self._venue_content_value(obj, 'sub_content', allow_html=True)

    @admin.display(description='Meta title')
    def display_meta_title(self, obj):
        return self._venue_content_value(obj, 'meta_title')

    @admin.display(description='Meta description')
    def display_meta_description(self, obj):
        return self._venue_content_value(obj, 'meta_description')

    @admin.display(description='Meta keywords')
    def display_meta_keywords(self, obj):
        return self._venue_content_value(obj, 'meta_keywords')

    @admin.display(description='Approval', ordering='approved')
    def approval_status(self, obj):
        label = obj.get_approval_display()
        if obj.is_pending_approval:
            return format_html(
                '<span class="gd-badge gd-badge-pending">{}</span>',
                label,
            )
        if obj.approved == 1:
            return format_html('<span class="gd-badge gd-badge-approved">{}</span>', label)
        if obj.rejected == 1:
            return format_html('<span class="gd-badge gd-badge-rejected">{}</span>', label)
        return label

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        now = timezone.now()
        if not change and obj.created_at is None:
            obj.created_at = now
        if not change:
            obj.createdby_id = obj.createdby_id or request.user.id
        obj.updated_at = now
        obj.updatedby_id = request.user.id
        super().save_model(request, obj, form, change)
        if hasattr(form, '_save_content') and form.cleaned_data:
            form._save_content(obj, request)


