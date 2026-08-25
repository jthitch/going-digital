from django import forms
from django.contrib import admin, messages
from django.db.models import Q
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from .admin_changelist import GdActiveFilter, SearchFirstChangeListMixin
from .admin_mixins import (
    LegacyAuditAdminMixin,
    PlatformAdminOnlyMixin,
    RegionScopedCourseAdminMixin,
    RegionScopedVenueAdminMixin,
    RegionScopedWorkshopAdminMixin,
)
from .region_scope import (
    filter_regions_for_user,
    filter_workshops_for_user,
    user_can_access_workshop,
    user_can_edit_venue_details,
    user_has_full_region_access,
)
from .workshop_admin_list import (
    is_workshop_changelist_request,
    narrow_workshop_changelist,
    order_workshop_changelist,
    workshop_changelist_show_full_history,
)
from .workshop_duplicate import (
    duplicate_workshop_querystring,
    get_duplicate_source_workshop,
    workshop_duplicate_initial,
)
from .forms import (
    AssistantAdminForm,
    CourseAdminForm,
    CourseCategoryAdminForm,
    CourseSkillLevelAdminForm,
    ImageAdminForm,
    TutorAdminForm,
    VenueAdminForm,
    WorkshopAdminForm,
    BooleanToggleWidget,
)
from .models import (
    Assistant,
    Content,
    Course,
    CourseCategory,
    CourseMedia,
    CourseSkillLevel,
    Image,
    LEVEL_DISPLAY_NAMES,
    Region,
    RegionUser,
    Tutor,
    Venue,
    VenueMedia,
    VenueWorkshopAccess,
    Workshop,
    WorkshopDocument,
)


class WorkshopRegionFilter(admin.SimpleListFilter):
    """Filter workshops by legacy region_id (integer, not an ORM FK)."""

    title = 'Region'
    parameter_name = 'region_id'

    def lookups(self, request, model_admin):
        qs = filter_regions_for_user(Region.objects.filter(active=1), request.user)
        return [(str(r.pk), r.region_name) for r in qs.order_by('region_name')]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(region_id=value)
        return queryset


class WorkshopTutorFilter(admin.SimpleListFilter):
    """Filter workshops by legacy tutor_id (integer, not an ORM FK)."""

    title = 'Tutor'
    parameter_name = 'tutor_id'

    def lookups(self, request, model_admin):
        return [
            (str(tutor.pk), str(tutor))
            for tutor in Tutor.objects.filter(active=1).order_by('lastname', 'firstname')
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(tutor_id=value)
        return queryset


class ImageLiveOnSiteFilter(admin.SimpleListFilter):
    """Filter gd_image rows by whether they appear on the public site."""

    title = 'Live on site'
    parameter_name = 'live_on_site'

    def lookups(self, request, model_admin):
        return [
            ('1', 'Yes — shown on site'),
            ('0', 'No — not shown'),
        ]

    def queryset(self, request, queryset):
        from courses.image_usage import annotate_images_live_on_site

        value = self.value()
        if value is None:
            return queryset
        annotated = annotate_images_live_on_site(queryset)
        if value == '1':
            return annotated.filter(live_on_site=True)
        if value == '0':
            return annotated.filter(live_on_site=False)
        return queryset


@admin.register(Image)
class ImageAdmin(LegacyAuditAdminMixin, PlatformAdminOnlyMixin, admin.ModelAdmin):
    """Edit gd_image records (course images, etc.)."""
    form = ImageAdminForm
    change_list_template = 'admin/courses/image/change_list.html'
    list_per_page = 50
    list_max_show_all = 100
    show_full_result_count = False
    list_display = [
        'thumbnail_preview',
        'id',
        'file_name',
        'source_name',
        'live_on_site_display',
        'live_usage_display',
        'get_image_type_display',
        'get_image_category_display',
        'get_user_display',
        'active',
        'mime_type',
        'width',
        'height',
    ]
    list_filter = [ImageLiveOnSiteFilter, 'active', 'image_type_id', 'image_category_id']
    search_fields = ['file_name', 'source_name', 'description']
    readonly_fields = [
        'mime_type',
        'file_size',
        'height',
        'width',
        'live_usage_detail',
        'createdby_id',
        'updatedby_id',
        'created_at',
        'updated_at',
    ]

    @admin.display(description='Preview')
    def thumbnail_preview(self, obj):
        if not obj:
            return '—'
        from courses.display_images import gd_image_public_url

        url = gd_image_public_url(obj)
        if not url:
            return '—'
        return format_html(
            '<img src="{}" alt="" class="gd-image-admin-thumb" loading="lazy" decoding="async">',
            url,
        )

    def _usage_map(self):
        cache = getattr(self, '_live_usage_map_cache', None)
        if cache is None:
            from courses.image_usage import build_gd_image_usage_map

            cache = build_gd_image_usage_map()
            self._live_usage_map_cache = cache
        return cache

    @admin.display(description='Live on site', boolean=True)
    def live_on_site_display(self, obj):
        if not obj or not obj.pk:
            return False
        annotated = getattr(obj, 'live_on_site', None)
        if annotated is not None:
            return bool(annotated)
        return obj.pk in self._usage_map()

    @admin.display(description='Used where')
    def live_usage_display(self, obj):
        if not obj or not obj.pk:
            return '—'
        from courses.image_usage import format_usage_lines

        return format_usage_lines(self._usage_map().get(obj.pk, []), max_items=3)

    @admin.display(description='Live on site')
    def live_usage_detail(self, obj):
        if not obj or not obj.pk:
            return 'Save the image first.'
        from courses.image_usage import build_gd_image_usage_map, format_usage_lines

        usages = build_gd_image_usage_map([obj.pk]).get(obj.pk, [])
        if not usages:
            return 'Not currently shown on the public site (active courses or bookable workshops).'
        return format_usage_lines(usages, max_items=20)

    def get_queryset(self, request):
        from courses.image_usage import annotate_images_live_on_site

        return annotate_images_live_on_site(super().get_queryset(request))

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'live-on-site/',
                self.admin_site.admin_view(self.live_on_site_view),
                name='courses_image_live_on_site',
            ),
        ]
        return custom + urls

    def live_on_site_view(self, request):
        from collections import Counter

        from courses.image_usage import collect_live_site_images

        rows = collect_live_site_images()
        area_counts = sorted(Counter(r.area for r in rows).items())
        context = {
            **self.admin_site.each_context(request),
            'title': 'Images live on the public site',
            'rows': rows,
            'area_counts': area_counts,
            'opts': self.model._meta,
        }
        return TemplateResponse(
            request,
            'admin/courses/image/live_on_site.html',
            context,
        )

    fieldsets = [
        ('File', {
            'fields': ('file_name', 'source_name', 'mime_type', 'file_size', 'height', 'width')
        }),
        ('Classification', {
            'fields': ('image_type', 'image_category', 'link_to', 'active', 'image_user')
        }),
        ('Live on site', {
            'fields': ('live_usage_detail',),
            'description': (
                'Where this library image appears on the public site '
                '(active courses and bookable workshops). '
                'Heroes, gift vouchers, before/after and venue uploads are separate assets — '
                'see “Live on site” on the Images list.'
            ),
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


@admin.register(Content)
class ContentAdmin(LegacyAuditAdminMixin, PlatformAdminOnlyMixin, admin.ModelAdmin):
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


@admin.register(CourseSkillLevel)
class CourseSkillLevelAdmin(
    LegacyAuditAdminMixin,
    PlatformAdminOnlyMixin,
    SearchFirstChangeListMixin,
    admin.ModelAdmin,
):
    form = CourseSkillLevelAdminForm
    list_display = ['level_name', 'active', 'display_order']
    list_display_links = ['level_name']
    list_filter = [GdActiveFilter]
    search_fields = ['skill_level']
    search_help_text = 'Search by skill level name.'
    ordering = ['display_order', 'id']
    readonly_fields = ['createdby_id', 'updatedby_id', 'created_at', 'updated_at']

    @admin.display(description='Skill level', ordering='display_order')
    def level_name(self, obj):
        return LEVEL_DISPLAY_NAMES.get(obj.pk) or obj.skill_level or '—'


@admin.register(CourseCategory)
class CourseCategoryAdmin(
    LegacyAuditAdminMixin,
    PlatformAdminOnlyMixin,
    SearchFirstChangeListMixin,
    admin.ModelAdmin,
):
    form = CourseCategoryAdminForm
    list_display = ['course_category', 'parent', 'active', 'exclude_from_course_list', 'display_order']
    list_filter = [GdActiveFilter, 'exclude_from_course_list']
    list_editable = ['active', 'exclude_from_course_list']
    search_fields = ['course_category']
    search_help_text = 'Search by category name.'
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


class RegionAdminForm(forms.ModelForm):
    active = forms.BooleanField(
        required=False,
        label='Active',
        widget=BooleanToggleWidget(),
    )

    class Meta:
        model = Region
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['active'].initial = bool(self.instance.active)

    def save(self, commit=True):
        region = super().save(commit=False)
        region.active = 1 if self.cleaned_data.get('active') else 0
        if commit:
            region.save()
        return region


class RegionUserInline(admin.TabularInline):
    model = RegionUser
    extra = 0
    autocomplete_fields = ['user']
    fields = ['user']
    verbose_name = 'Assigned user'
    verbose_name_plural = 'Assigned users'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user':
            from core.models import User

            kwargs['queryset'] = (
                User.objects.filter(active=1)
                .order_by('lastname', 'firstname', 'email')
            )
            kwargs.setdefault(
                'help_text',
                'Franchisee or administrator who can manage workshops in this region.',
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Region)
class RegionAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    """Franchise regions (gd_region) and assigned users (gd_region_user)."""
    form = RegionAdminForm
    change_list_template = 'admin/courses/region/change_list.html'
    list_display = ['region_name', 'slug', 'is_active_display', 'assigned_users_display']
    list_filter = ['active']
    search_fields = ['region_name', 'slug']
    ordering = ['region_name']
    inlines = [RegionUserInline]
    readonly_fields = ['id']

    @admin.display(description='Active', boolean=True)
    def is_active_display(self, obj):
        return bool(obj.active)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            'user_assignments__user',
        )

    @admin.display(description='Assigned users')
    def assigned_users_display(self, obj):
        assignments = list(obj.user_assignments.all())
        if not assignments:
            return '—'
        links = []
        for assignment in assignments:
            user = assignment.user
            if not user:
                links.append(f'User #{assignment.user_id}')
                continue
            label = user.get_full_name() or user.email
            user_type = user.get_user_type_display()
            if user_type and user_type != '—':
                label = f'{label} ({user_type})'
            links.append(format_html(
                '<a href="{}">{}</a>',
                reverse('admin:core_user_change', args=[user.pk]),
                label,
            ))
        return format_html_join(', ', '{}', ((link,) for link in links))

    def save_formset(self, request, form, formset, change):
        if formset.model is not RegionUser:
            return super().save_formset(request, form, formset, change)

        from django.utils import timezone

        now = timezone.now()
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.createdby_id = request.user.pk
                instance.created_at = now
            instance.updatedby_id = request.user.pk
            instance.updated_at = now
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'map/',
                self.admin_site.admin_view(self.region_map_view),
                name='courses_region_map',
            ),
        ]
        return custom_urls + urls

    def region_map_view(self, request):
        from courses.region_territory import build_region_map_payload

        payload = build_region_map_payload()
        context = {
            **self.admin_site.each_context(request),
            'title': 'Region map',
            'opts': self.model._meta,
            'region_map_data': payload,
            'has_permission': self.has_view_permission(request),
        }
        return TemplateResponse(request, 'admin/courses/region/map.html', context)


@admin.register(Tutor)
class TutorAdmin(PlatformAdminOnlyMixin, SearchFirstChangeListMixin, admin.ModelAdmin):
    """Manage gd_tutor rows used by the workshop Tutor dropdown."""

    change_list_template = 'admin/courses/tutor/change_list.html'
    form = TutorAdminForm
    list_display = ['lastname', 'firstname', 'email', 'telephone', 'active']
    list_display_links = ['lastname', 'firstname']
    list_editable = ['active']
    list_filter = [GdActiveFilter]
    search_fields = ['firstname', 'lastname', 'email', 'telephone']
    search_help_text = 'Search by name, email, or telephone.'
    ordering = ['lastname', 'firstname']
    fields = ['firstname', 'lastname', 'email', 'telephone', 'active']

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'active':
            return forms.BooleanField(
                required=False,
                label='Active',
                widget=BooleanToggleWidget(),
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Assistant)
class AssistantAdmin(PlatformAdminOnlyMixin, SearchFirstChangeListMixin, admin.ModelAdmin):
    """Manage gd_assistant rows used by the workshop Assistant dropdown."""

    change_list_template = 'admin/courses/assistant/change_list.html'
    form = AssistantAdminForm
    list_display = ['lastname', 'firstname', 'email', 'active']
    list_display_links = ['lastname', 'firstname']
    list_editable = ['active']
    list_filter = [GdActiveFilter]
    search_fields = ['firstname', 'lastname', 'email']
    search_help_text = 'Search by name or email.'
    ordering = ['lastname', 'firstname']
    fields = ['firstname', 'lastname', 'email', 'active']

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'active':
            return forms.BooleanField(
                required=False,
                label='Active',
                widget=BooleanToggleWidget(),
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class CourseMediaInline(admin.TabularInline):
    model = CourseMedia
    extra = 0
    fields = ['media_type', 'image', 'video_file', 'video_url', 'caption', 'display_order']
    verbose_name = 'Image/Video'
    verbose_name_plural = 'Images & Videos'


@admin.register(Course)
class CourseAdmin(
    LegacyAuditAdminMixin,
    RegionScopedCourseAdminMixin,
    SearchFirstChangeListMixin,
    admin.ModelAdmin,
):
    """Course admin - maps to legacy gd_course table. Content editable inline."""
    form = CourseAdminForm
    change_form_template = 'admin/courses/course/change_form.html'
    inlines = [CourseMediaInline]
    list_display = ['course_name', 'course_skill_level', 'course_category', 'active', 'created_at']
    list_filter = [GdActiveFilter, 'course_skill_level', 'course_category', 'created_at']
    search_fields = ['course_name', 'course_description', 'description_for_workshop', 'slug']
    search_help_text = 'Search by course name, description, or URL slug.'
    prepopulated_fields = {'slug': ('course_name',)}
    readonly_fields = [
        'createdby_id', 'updatedby_id', 'created_at', 'updated_at',
        'card_list_image_preview',
    ]
    list_editable = ['active']

    class Media:
        js = (
            'courses/js/admin-course-media.js',
            'courses/js/admin-course-card-image.js',
        )
        css = {'all': ('admin/css/course-admin.css',)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if hasattr(form, '_save_content') and form.cleaned_data:
            form._save_content(obj, request)

    READONLY_FORM_FIELD_DISPLAY = {
        'course_url': 'display_course_url',
        'region': 'display_region',
        'status': 'display_status',
        'content_title': 'display_content_title',
        'strapline': 'display_strapline',
        'main_content': 'display_main_content',
        'sub_content': 'display_sub_content',
        'meta_title': 'display_meta_title',
        'meta_description': 'display_meta_description',
        'meta_keywords': 'display_meta_keywords',
    }

    def _course_field_names(self):
        names = []
        for _title, opts in self.fieldsets:
            names.extend(opts['fields'])
        return names

    @classmethod
    def _swap_readonly_field_names(cls, field_names):
        return [
            cls.READONLY_FORM_FIELD_DISPLAY.get(name, name)
            for name in field_names
        ]

    def _readonly_fieldsets_for_viewer(self, fieldsets):
        updated = []
        for title, opts in fieldsets:
            fields = self._swap_readonly_field_names(opts.get('fields', ()))
            updated.append((title, {**opts, 'fields': tuple(fields)}))
        return updated

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj and not user_has_full_region_access(request.user):
            return self._readonly_fieldsets_for_viewer(fieldsets)
        return fieldsets

    def _course_content_value(self, obj, attr, *, allow_html=False, empty='—'):
        if not obj:
            return empty
        content = obj.content
        if not content:
            return empty
        value = getattr(content, attr, None) or ''
        if not value:
            return empty
        if allow_html:
            return mark_safe(value)
        return value

    @admin.display(description='Course URL')
    def display_course_url(self, obj):
        if not obj or not (obj.slug or '').strip():
            return '—'
        path = CourseAdminForm.course_url_path(obj.slug)
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            path,
            path,
        )

    @admin.display(description='Region', ordering='region_id')
    def display_region(self, obj):
        return obj.get_region_display() or '—'

    @admin.display(description='Status', ordering='status_id')
    def display_status(self, obj):
        return obj.get_status_display()

    @admin.display(description='Content title')
    def display_content_title(self, obj):
        return self._course_content_value(obj, 'content_title')

    @admin.display(description='Strapline')
    def display_strapline(self, obj):
        return self._course_content_value(obj, 'strapline')

    @admin.display(description='Main content')
    def display_main_content(self, obj):
        return self._course_content_value(obj, 'main_content', allow_html=True)

    @admin.display(description='Sub content')
    def display_sub_content(self, obj):
        return self._course_content_value(obj, 'sub_content', allow_html=True)

    @admin.display(description='Meta title')
    def display_meta_title(self, obj):
        return self._course_content_value(obj, 'meta_title')

    @admin.display(description='Meta description')
    def display_meta_description(self, obj):
        return self._course_content_value(obj, 'meta_description')

    @admin.display(description='Meta keywords')
    def display_meta_keywords(self, obj):
        return self._course_content_value(obj, 'meta_keywords')

    @admin.display(description='List card preview')
    def card_list_image_preview(self, obj):
        if not obj or not obj.pk:
            return 'Save the course and choose an image to adjust the list card preview.'
        image_url = obj.list_card_thumbnail_url()
        if not image_url:
            return (
                'No list image yet — set Classification → Image or add a course media image.'
            )
        x = 50 if obj.card_image_focus_x is None else int(obj.card_image_focus_x)
        y = 50 if obj.card_image_focus_y is None else int(obj.card_image_focus_y)
        zoom = 100 if obj.card_image_zoom is None else int(obj.card_image_zoom)
        image_style = obj.list_card_thumbnail_style()
        return format_html(
            '<div class="course-card-admin-preview" id="course-card-admin-preview" '
            'data-image-url="{}" data-focus-x="{}" data-focus-y="{}" data-zoom="{}">'
            '<div class="course-card-admin-preview-frame" data-preview-frame>'
            '<div class="course-card-admin-preview-stage" data-preview-stage>'
            '<div class="course-card-admin-preview-viewport" data-preview-viewport>'
            '<img src="{}" alt="" class="course-card-admin-preview-img" '
            'data-preview-img style="{}">'
            '<div class="course-card-admin-preview-viewport-ui" aria-hidden="true">'
            '<div class="course-card-admin-preview-scrim"></div>'
            '<span class="course-card-admin-preview-viewport-label">'
            'Visible on listing</span>'
            '<span class="course-card-admin-preview-sample">Course title</span>'
            '</div>'
            '<span class="course-card-admin-preview-focus" data-preview-focus '
            'title="Drag to set focal point" style="left:{}%;top:{}%;"></span>'
            '</div>'
            '</div>'
            '</div>'
            '<p class="course-card-admin-preview-hint">'
            'The framed area matches the list card. Zoomed-in areas outside the '
            'frame are cropped on the site. Drag the blue circle or use the sliders.</p>'
            '</div>',
            image_url,
            x,
            y,
            zoom,
            image_url,
            image_style,
            x,
            y,
        )

    def get_readonly_fields(self, request, obj=None):
        if obj and not user_has_full_region_access(request.user):
            names = self._swap_readonly_field_names(self._course_field_names())
            return list(dict.fromkeys(names + list(self.readonly_fields)))
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
        ('Course list card image', {
            'fields': (
                'card_list_image_preview',
                'card_image_focus_x',
                'card_image_focus_y',
                'card_image_zoom',
            ),
            'description': (
                'Controls how this course image appears on the photography courses listing. '
                'Drag the focal point in the preview or use the sliders, then save.'
            ),
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


@admin.action(description='Duplicate workshop')
def duplicate_workshop_action(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(
            request,
            'Select exactly one workshop to duplicate.',
            level=messages.ERROR,
        )
        return
    workshop = queryset.first()
    if not user_can_access_workshop(request.user, workshop):
        modeladmin.message_user(
            request,
            'You cannot duplicate this workshop.',
            level=messages.ERROR,
        )
        return
    add_url = reverse('admin:courses_workshop_add')
    return HttpResponseRedirect(f'{add_url}?{duplicate_workshop_querystring(workshop)}')


class WorkshopDocumentInlineForm(forms.ModelForm):
    include_in_booking_email = forms.BooleanField(
        required=False,
        label='Add to booking email',
        widget=BooleanToggleWidget(),
    )

    class Meta:
        model = WorkshopDocument
        fields = ['title', 'file', 'description', 'include_in_booking_email', 'display_order']

    def clean_file(self):
        from courses.workshop_documents import validate_workshop_document_upload

        upload = self.cleaned_data.get('file')
        if upload:
            validate_workshop_document_upload(upload)
        elif not self.instance.pk:
            raise forms.ValidationError('Choose a file to upload.')
        return upload


class WorkshopDocumentInline(admin.TabularInline):
    model = WorkshopDocument
    form = WorkshopDocumentInlineForm
    extra = 1
    fields = ['title', 'file', 'include_in_booking_email', 'display_order']
    verbose_name = 'Workshop document'
    verbose_name_plural = 'Workshop documents'
    classes = ['gd-workshop-documents-inline']

    def _parent_workshop_admin(self):
        return self.admin_site._registry[Workshop]

    def has_view_permission(self, request, obj=None):
        parent = self._parent_workshop_admin()
        if obj is None:
            return parent.has_add_permission(request)
        return parent.has_view_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        parent = self._parent_workshop_admin()
        if obj is None:
            return parent.has_add_permission(request)
        return parent.has_change_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        parent = self._parent_workshop_admin()
        if obj is None:
            return parent.has_add_permission(request)
        return parent.has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Workshop)
class WorkshopAdmin(
    LegacyAuditAdminMixin,
    RegionScopedWorkshopAdminMixin,
    SearchFirstChangeListMixin,
    admin.ModelAdmin,
):
    audit_set_user_id_on_create = True
    form = WorkshopAdminForm
    change_form_template = 'admin/courses/workshop/change_form.html'
    change_list_template = 'admin/courses/workshop/change_list.html'
    gd_changelist_extra_params = ('show_all',)
    gd_changelist_show_date_range = True
    gd_changelist_date_field = 'date__date'
    gd_changelist_date_range_id_prefix = 'workshop'
    gd_changelist_date_range_hint = _(
        'Start date in range; open-dated workshops always included.'
    )
    filter_input_length = {
        'course__id__exact': 2,
    }
    actions = [duplicate_workshop_action]
    inlines = [WorkshopDocumentInline]
    autocomplete_fields = ['course', 'venue']
    list_display = [
        'id',
        'course',
        'venue',
        'region_name',
        'get_tutor_display',
        'get_assistant_display',
        'workshop_schedule',
        'cost',
        'max_places',
        'spaces_booked_percent',
        'active',
    ]
    list_filter = [
        GdActiveFilter,
        WorkshopRegionFilter,
        WorkshopTutorFilter,
        ('course', admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = [
        'id',
        'course__course_name',
        'venue__venue_name',
        'venue__location',
        'strapline',
        'blurb',
    ]
    search_help_text = 'Search by course, venue, location, tutor, region, strapline, or workshop ID.'
    readonly_fields = [
        'user_display',
        'createdby_display',
        'updatedby_display',
        'image_preview',
        'applicable_discount_codes_display',
        'created_at',
        'updated_at',
    ]
    fieldsets = [
        (None, {
            'fields': (
                'active',
                'course',
                'venue',
                'region',
                'open_dated',
        'date',
                'end_at',
                'tutor',
                'assistant',
                'alt_course',
                'workshop_type',
        'cost',
                'deposit_required',
        'max_places',
        'places_booked',
                'cameras_available',
                'number_of_loan_cameras_available',
                'strapline',
                'byline',
                'blurb',
                'comments',
                'approve',
                'image_preview',
                'images',
                'image_upload',
                'applicable_discount_codes_display',
                'user_display',
                'createdby_display',
                'updatedby_display',
                'created_at',
                'updated_at',
            ),
        }),
    ]

    def _fieldsets_without_bookings(self, fieldsets):
        cleaned = []
        for title, opts in fieldsets:
            fields = tuple(f for f in opts.get('fields', ()) if f != 'bookings_display')
            cleaned.append((title, {**opts, 'fields': fields}))
        return cleaned

    def get_fieldsets(self, request, obj=None):
        fieldsets = self._fieldsets_without_bookings(list(super().get_fieldsets(request, obj)))
        if request.user.is_superuser:
            reminder_fields = ['reminder_message']
            if obj and obj.pk:
                reminder_fields.append('reminder_email_preview')
            fieldsets.append((
                'Reminder email',
                {
                    'fields': tuple(reminder_fields),
                    'description': (
                        'Sent to confirmed students one day before a fixed-date workshop. '
                        'Edit the shared intro and closing under Website → Workshop reminder email.'
                    ),
                },
            ))
        if obj and obj.pk:
            fieldsets.append((
                'Customers',
                {
                    'fields': ('bookings_display',),
                    'classes': ('wide', 'gd-workshop-customers-tab'),
                },
            ))
            if obj.venue_id:
                venue = obj.venue
                if venue and venue.document_id:
                    fieldsets.insert(1, (
                        'Venue documents',
                        {
                            'fields': (
                                'venue_document_display',
                                'add_document_to_booking_email',
                            ),
                        },
                    ))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if request.user.is_superuser and obj and obj.pk:
            if 'reminder_email_preview' not in readonly:
                readonly.append('reminder_email_preview')
        if obj and obj.pk:
            if 'bookings_display' not in readonly:
                readonly.append('bookings_display')
            venue = obj.venue if obj.venue_id else None
            if venue and venue.document_id and 'venue_document_display' not in readonly:
                readonly.append('venue_document_display')
        else:
            readonly = [f for f in readonly if f not in ('bookings_display', 'venue_document_display')]
        return readonly

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        source = get_duplicate_source_workshop(request, prefetch_gallery=True)
        if source:
            initial.update(workshop_duplicate_initial(source))
        return initial

    def add_view(self, request, form_url='', extra_context=None):
        self._current_request = request
        extra_context = extra_context or {}
        source = get_duplicate_source_workshop(request)
        if source:
            messages.info(
                request,
                f'Copied settings from {source}. Set start and end date/time, or mark as open dated, then save.',
            )
            extra_context['is_workshop_duplicate'] = True
        return super().add_view(request, form_url, extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'calendar/',
                self.admin_site.admin_view(self.calendar_view),
                name='courses_workshop_calendar',
            ),
            path(
                '<path:object_id>/students.csv/',
                self.admin_site.admin_view(self.students_csv_view),
                name='courses_workshop_students_csv',
            ),
        ]
        return custom_urls + urls

    def calendar_view(self, request):
        if not self.has_view_permission(request):
            return HttpResponseForbidden('You do not have permission to view the workshop calendar.')

        from courses.workshop_admin_calendar import build_workshop_calendar_context

        qs = filter_workshops_for_user(
            Workshop.objects.select_related('course', 'venue'),
            request.user,
        )
        context = {
            **self.admin_site.each_context(request),
            **build_workshop_calendar_context(request, qs),
            'title': 'Workshop calendar',
            'opts': self.model._meta,
            'changelist_url': reverse('admin:courses_workshop_changelist'),
            'has_view_permission': self.has_view_permission(request),
            'has_add_permission': self.has_add_permission(request),
        }
        return TemplateResponse(request, 'admin/courses/workshop/calendar.html', context)

    def students_csv_view(self, request, object_id):
        workshop = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_view_permission(request, workshop):
            return HttpResponseForbidden('You do not have permission to download this report.')
        if not (
            user_has_full_region_access(request.user)
            or user_can_access_workshop(request.user, workshop)
        ):
            return HttpResponseForbidden('You do not have permission to download this report.')

        from courses.workshop_student_report import build_workshop_student_csv_response

        return build_workshop_student_csv_response(workshop, user=request.user)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and self.has_add_permission(request) and user_can_access_workshop(request.user, obj):
            add_url = reverse('admin:courses_workshop_add')
            extra_context['duplicate_workshop_url'] = (
                f'{add_url}?{duplicate_workshop_querystring(obj)}'
            )
        if obj and (
            user_has_full_region_access(request.user)
            or user_can_access_workshop(request.user, obj)
        ):
            extra_context['students_csv_url'] = reverse(
                'admin:courses_workshop_students_csv',
                args=[obj.pk],
            )
        self._current_request = request
        return super().change_view(request, object_id, form_url, extra_context)

    def get_changelist_date_range_or_q(self, request):
        return Q(open_dated=1)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            'course', 'venue',
        ).prefetch_related('gallery_images__image', 'documents')
        if is_workshop_changelist_request(request):
            qs = order_workshop_changelist(qs)
            if not workshop_changelist_show_full_history(request):
                qs = narrow_workshop_changelist(qs)
        return qs

    def get_search_results(self, request, queryset, search_term):
        search_qs, use_distinct = super().get_search_results(request, queryset, search_term)
        term = (search_term or '').strip()
        if term:
            from django.db.models import Q

            tutor_ids = list(
                Tutor.objects.filter(
                    Q(firstname__icontains=term)
                    | Q(lastname__icontains=term)
                    | Q(email__icontains=term)
                ).values_list('pk', flat=True)
            )
            region_ids = list(
                Region.objects.filter(region_name__icontains=term).values_list('pk', flat=True)
            )
            extra = Q()
            if tutor_ids:
                extra |= Q(tutor_id__in=tutor_ids)
            if region_ids:
                extra |= Q(region_id__in=region_ids)
            if tutor_ids or region_ids:
                # Integer FKs cannot use related lookups; OR tutor/region name matches in.
                search_qs = (search_qs | queryset.filter(extra)).distinct()
                use_distinct = True
        # Manual booking picker: today first, then older workshops.
        if (
            request.path.endswith('/autocomplete/')
            and request.GET.get('app_label') == 'bookings'
            and request.GET.get('model_name') == 'booking'
            and request.GET.get('field_name') == 'workshop'
        ):
            from bookings.manual_booking import filter_workshops_for_manual_booking_picker

            include_future = request.GET.get('include_future') in ('1', 'true', 'yes', 'on')
            search_qs = filter_workshops_for_manual_booking_picker(
                search_qs,
                include_future=include_future,
            )
        return search_qs, use_distinct

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if hasattr(form, 'sync_gallery'):
            form.sync_gallery(obj)
        if not change and obj.cloned_from_workshop_id:
            from courses.workshop_documents import copy_workshop_documents

            copy_workshop_documents(
                obj.cloned_from_workshop_id,
                obj.pk,
                user_id=request.user.pk,
            )

    def save_formset(self, request, form, formset, change):
        if formset.model is not WorkshopDocument:
            return super().save_formset(request, form, formset, change)

        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk and not instance.createdby_id:
                instance.createdby_id = request.user.pk
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    def response_change(self, request, obj):
        """Stay on the workshop edit page after save (avoids slow changelist redirect)."""
        if '_addanother' in request.POST:
            return super().response_change(request, obj)
        return HttpResponseRedirect(
            reverse('admin:courses_workshop_change', args=[obj.pk]),
        )

    @admin.display(description='Selected images')
    def image_preview(self, obj):
        if not obj or not obj.pk:
            return '—'
        from courses.display_images import workshop_gallery_images

        images = workshop_gallery_images(obj)
        if not images:
            return '—'
        thumbs = format_html_join(
            '',
            '<img src="{}" alt="" style="max-height:50px;max-width:80px;margin-right:0.5rem;border-radius:4px;">',
            ((image.url,) for image in images if image.url),
        )
        return thumbs or '—'

    @admin.display(description='User')
    def user_display(self, obj):
        return obj.get_user_display()

    @admin.display(description='Created by')
    def createdby_display(self, obj):
        return obj.get_createdby_display()

    @admin.display(description='Discount codes')
    def applicable_discount_codes_display(self, obj):
        from bookings.discount_codes import (
            codes_for_workshop,
            codes_owned_by_user,
            format_discount_codes_html,
        )

        if obj and obj.pk:
            html = format_discount_codes_html(codes_for_workshop(obj))
        else:
            request = getattr(self, '_current_request', None)
            user = getattr(request, 'user', None) if request else None
            if user and not user_has_full_region_access(user) and getattr(user, 'is_region_scoped', False):
                codes = list(codes_owned_by_user(user))
                if codes:
                    html = format_html(
                        '<p style="margin:0 0 0.5rem;">Your active discount codes '
                        '(attach workshops on each code after saving this course):</p>{}',
                        format_discount_codes_html(codes),
                    )
                else:
                    html = (
                        'No discount codes yet. Create one under Bookings → Discount codes, '
                        'then attach this workshop.'
                    )
            else:
                html = (
                    'Save this workshop, then create or edit a discount code and select this '
                    'workshop. Applicable codes will appear here.'
                )

        try:
            add_url = reverse('admin:bookings_discountcode_add')
            html = format_html(
                '{}<p style="margin:0.75rem 0 0;"><a href="{}">Create a discount code</a></p>',
                html,
                add_url,
            )
        except Exception:
            pass
        return html

    @admin.display(description='Updated by')
    def updatedby_display(self, obj):
        return obj.get_updatedby_display()

    @admin.display(description='Preview')
    def reminder_email_preview(self, obj):
        if not obj or not obj.pk:
            return 'Save the workshop first.'
        from django.template.loader import render_to_string

        from bookings.email_context import workshop_reminder_preview_context

        context = workshop_reminder_preview_context(obj)
        html = render_to_string('emails/workshop_reminder.html', context)
        return format_html(
            '<div class="gd-reminder-email-preview" style="border:1px solid #ddd;'
            'border-radius:6px;max-width:720px;overflow:auto;background:#fff;">{}</div>',
            mark_safe(html),
        )

    @admin.display(description='')
    def bookings_display(self, obj):
        if not obj or not obj.pk:
            return '—'

        from .workshop_bookings_display import render_workshop_bookings_table

        request = getattr(self, '_current_request', None)
        return mark_safe(render_workshop_bookings_table(obj, request))

    @admin.display(description='')
    def venue_document_display(self, obj):
        if not obj or not obj.venue_id:
            return '—'
        from courses.venue_documents import render_venue_document_admin_preview

        venue = obj.venue
        if not venue:
            return '—'
        return mark_safe(render_venue_document_admin_preview(venue))

    class Media:
        css = {'all': ('admin/css/workshop-admin.css', 'admin/css/venue-document.css')}
        js = ('courses/js/admin-workshop.js',)

    @admin.display(description='Date', ordering='date')
    def workshop_schedule(self, obj):
        if obj.open_dated:
            return 'Open dated'
        if obj.date:
            end = obj.get_end_date()
            if end and end.date() != obj.date.date():
                return (
                    f'{obj.date.strftime("%d %b %Y %H:%M")} – '
                    f'{end.strftime("%d %b %Y %H:%M")}'
                )
            return obj.date.strftime('%d %b %Y %H:%M')
        return '—'

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

    def _can_edit_media(self, request, obj=None):
        parent = self._parent_venue_admin()
        if obj is None:
            return parent.has_add_permission(request)
        if not parent.has_change_permission(request, obj):
            return False
        return user_can_edit_venue_details(request.user, obj)

    def has_view_permission(self, request, obj=None):
        parent = self._parent_venue_admin()
        if obj is None:
            return parent.has_add_permission(request)
        return parent.has_view_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        return self._can_edit_media(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._can_edit_media(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._can_edit_media(request, obj)


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


class VenueContentChangeFilter(admin.SimpleListFilter):
    title = 'content changes'
    parameter_name = 'content_change'

    def lookups(self, request, model_admin):
        return (
            ('pending', 'Content awaiting approval'),
            ('rejected', 'Content rejected'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'pending':
            return queryset.filter(content_change_request__status='pending')
        if value == 'rejected':
            return queryset.filter(content_change_request__status='rejected')
        return queryset


class VenueWorkshopAccessInline(admin.TabularInline):
    """Superuser-only inline: grant franchisees permission to add workshops to this venue."""

    model = VenueWorkshopAccess
    extra = 1
    autocomplete_fields = ['user']
    readonly_fields = ['granted_by', 'created_at']
    verbose_name = 'Workshop access grant'
    verbose_name_plural = 'Franchisees allowed to add workshops'

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Venue)
class VenueAdmin(RegionScopedVenueAdminMixin, SearchFirstChangeListMixin, admin.ModelAdmin):
    form = VenueAdminForm
    change_list_template = 'admin/courses/venue/change_list.html'
    prepopulated_fields = {'slug': ('venue_name',)}
    readonly_fields = [
        'created_at',
        'updated_at',
        'venue_document_display',
        'pending_content_preview',
        'approval_status',
        'content_change_status',
        'display_active',
        'display_venue_region',
        'display_county',
        'display_venue_name',
        'display_slug',
        'display_venue_address',
        'display_location',
        'display_venue_telephone',
        'display_venue_url',
        'display_latitude',
        'display_longitude',
        'display_show_workshops',
        'display_content_title',
        'display_strapline',
        'display_main_content',
        'display_sub_content',
        'display_meta_title',
        'display_meta_description',
        'display_meta_keywords',
    ]

    def get_prepopulated_fields(self, request, obj=None):
        # Content-only franchisee forms drop venue_name/slug; prepopulate would KeyError.
        if (
            obj
            and not user_has_full_region_access(request.user)
            and not user_can_edit_venue_details(request.user, obj)
        ):
            return {}
        return super().get_prepopulated_fields(request, obj)
    list_display = [
        'id',
        'venue_name',
        'slug',
        'location',
        'get_region_display',
        'approval_status',
        'get_county_display',
        'display_active',
    ]
    list_filter = [
        VenueApprovalStateFilter,
        VenueContentChangeFilter,
        GdActiveFilter,
        WorkshopRegionFilter,
    ]
    search_fields = ['venue_name', 'venue_address', 'location', 'slug']
    search_help_text = 'Search by name, address, location, or URL slug.'
    inlines = [VenueMediaInline, VenueWorkshopAccessInline]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if user_has_full_region_access(request.user):
            from courses.venue_approval import get_venue_content_change_request

            change = get_venue_content_change_request(obj) if obj else None
            if not (change and change.is_pending):
                fieldsets = [
                    (title, {
                        **opts,
                        'fields': tuple(
                            field_name
                            for field_name in opts.get('fields', ())
                            if field_name not in (
                                'content_change_decision',
                                'content_change_reject_reason',
                                'pending_content_preview',
                            )
                        ),
                    })
                    for title, opts in fieldsets
                ]
        if not obj or not obj.document_id:
            return [
                (title, {
                    **opts,
                    'fields': tuple(
                        field_name
                        for field_name in opts.get('fields', ())
                        if field_name not in (
                            'venue_document_display',
                            'add_document_to_booking_email',
                        )
                    ),
                })
                for title, opts in fieldsets
                if title != 'Venue documents'
            ]
        return fieldsets

    franchisee_fieldsets = [
        (None, {
            'fields': (
                'display_active',
                'venue_region',
                'county',
                'venue_name',
                'slug',
                'postcode_lookup',
                'venue_address',
                'location',
                'venue_telephone',
                'venue_url',
                'latitude',
                'longitude',
                'show_workshops',
            ),
            'description': (
                'Complete the venue details, content, and images below before approval. '
                'You can assign pending venues to workshops, but workshops cannot be '
                'published until an administrator approves this venue. '
                'Active is set by an administrator when the venue is approved for the public site.'
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
        ('Venue documents', {
            'fields': ('venue_document_display', 'add_document_to_booking_email'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    franchisee_approved_content_fieldsets = [
        (None, {
            'fields': (
                'display_active',
                'display_venue_region',
                'display_county',
                'display_venue_name',
                'display_slug',
                'display_venue_address',
                'display_location',
                'display_venue_telephone',
                'display_venue_url',
                'display_latitude',
                'display_longitude',
                'display_show_workshops',
            ),
            'description': (
                'This venue is approved. Address and contact details are locked. '
                'You can update the page content below; changes stay off the public '
                'site until an administrator approves them. '
                'Active controls whether the venue appears on the public site (set by an administrator).'
            ),
        }),
        ('Approval', {
            'fields': ('approval_status', 'content_change_status'),
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
                'Edit content and save to submit changes for administrator approval. '
                'The live venue page is unchanged until those changes are approved.'
            ),
        }),
        ('Venue documents', {
            'fields': ('venue_document_display',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    franchisee_view_fieldsets = [
        (None, {
            'fields': (
                'display_active',
                'display_venue_region',
                'display_county',
                'venue_name',
                'slug',
                'venue_address',
                'location',
                'venue_telephone',
                'venue_url',
                'latitude',
                'longitude',
                'show_workshops',
            ),
            'description': (
                'You can view this venue but cannot edit it.'
            ),
        }),
        ('Approval', {
            'fields': ('approval_status', 'content_change_status'),
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
        ('Venue documents', {
            'fields': ('venue_document_display',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    fieldsets = [
        (None, {
            'fields': (
                'active',
                'venue_region',
                'venue_user',
                'county',
                'venue_name',
                'slug',
                'postcode_lookup',
                'venue_address',
                'location',
                'venue_telephone',
                'venue_url',
                'latitude',
                'longitude',
                'show_workshops',
            ),
        }),
        ('Approval', {
            'fields': (
                'approval_decision',
                'reject_reason',
                'pending_content_preview',
                'content_change_decision',
                'content_change_reject_reason',
            ),
            'description': (
                'Set approval to Approved, Rejected, or Pending. '
                'Reject reason is required when Rejected. '
                'Active (above) controls whether the venue appears on the public site. '
                'Pending content changes from franchisees are reviewed separately below.'
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
        ('Venue documents', {
            'fields': ('venue_document_display', 'add_document_to_booking_email'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    ]

    class Media:
        css = {
            'all': (
                'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
                'admin/css/venue-admin.css',
                'admin/css/course-admin.css',
                'admin/css/venue-document.css',
            ),
        }
        js = (
            'admin/js/urlify.js',
            'admin/js/prepopulate.js',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'courses/js/admin-venue.js',
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'postcode-lookup/',
                self.admin_site.admin_view(self.postcode_lookup_view),
                name='courses_venue_postcode_lookup',
            ),
        ]
        return custom_urls + urls

    @staticmethod
    @require_GET
    def postcode_lookup_view(request):
        from courses.postcode_lookup import lookup_uk_postcode

        postcode = (request.GET.get('postcode') or '').strip()
        if not postcode:
            return JsonResponse({'error': 'Enter a postcode.'}, status=400)
        try:
            result = lookup_uk_postcode(postcode)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        except Exception:
            return JsonResponse(
                {'error': 'Postcode lookup failed. Try again.'},
                status=502,
            )
        return JsonResponse(result)

    @admin.display(description='')
    def venue_document_display(self, obj):
        if not obj:
            return '—'
        from courses.venue_documents import render_venue_document_admin_preview

        return mark_safe(render_venue_document_admin_preview(obj))

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

    @admin.display(description='Active', boolean=True, ordering='active')
    def display_active(self, obj):
        return bool(obj and obj.active == 1)

    @admin.display(description='Content changes')
    def content_change_status(self, obj):
        from courses.venue_approval import content_change_status_label, get_venue_content_change_request

        label = content_change_status_label(obj)
        change = get_venue_content_change_request(obj)
        if change and change.is_pending:
            return format_html(
                '<span class="gd-badge gd-badge-pending">{}</span>',
                label,
            )
        if change and change.status == change.STATUS_REJECTED:
            return format_html(
                '<span class="gd-badge gd-badge-rejected">{}</span>',
                label,
            )
        return label

    @admin.display(description='Pending content')
    def pending_content_preview(self, obj):
        from courses.venue_approval import get_venue_content_change_request

        change = get_venue_content_change_request(obj)
        if not change or not change.is_pending:
            return '—'
        return format_html(
            '<div class="gd-pending-content-preview">{}</div>',
            format_html_join(
                '',
                '<div class="mb-2"><strong>{}</strong><div>{}</div></div>',
                (
                    (
                        label,
                        mark_safe(value) if name in ('main_content', 'sub_content') and value else (value or '—'),
                    )
                    for name, label, value in (
                        ('content_title', 'Content title', change.content_title),
                        ('strapline', 'Strapline', change.strapline),
                        ('main_content', 'Main content', change.main_content),
                        ('sub_content', 'Sub content', change.sub_content),
                        ('meta_title', 'Meta title', change.meta_title),
                        ('meta_description', 'Meta description', change.meta_description),
                        ('meta_keywords', 'Meta keywords', change.meta_keywords),
                    )
                ),
            ),
        )

    @admin.display(description='Venue name')
    def display_venue_name(self, obj):
        return obj.venue_name or '—'

    @admin.display(description='Slug')
    def display_slug(self, obj):
        return obj.slug or '—'

    @admin.display(description='Address')
    def display_venue_address(self, obj):
        return obj.venue_address or '—'

    @admin.display(description='Location')
    def display_location(self, obj):
        return obj.location or '—'

    @admin.display(description='Telephone')
    def display_venue_telephone(self, obj):
        return obj.venue_telephone or '—'

    @admin.display(description='URL')
    def display_venue_url(self, obj):
        return obj.venue_url or '—'

    @admin.display(description='Latitude')
    def display_latitude(self, obj):
        return obj.latitude if obj.latitude is not None else '—'

    @admin.display(description='Longitude')
    def display_longitude(self, obj):
        return obj.longitude if obj.longitude is not None else '—'

    @admin.display(description='Show workshops')
    def display_show_workshops(self, obj):
        return 'Yes' if obj.show_workshops == 1 else 'No'

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
        if getattr(form, 'content_only_mode', False):
            from courses.venue_approval import (
                get_venue_content_change_request,
                upsert_venue_content_change_request,
            )

            upsert_venue_content_change_request(
                obj,
                form.cleaned_data,
                user_id=request.user.pk,
            )
            pending = get_venue_content_change_request(obj)
            if pending and pending.is_pending:
                messages.info(
                    request,
                    'Content changes submitted for administrator approval. '
                    'The live venue page is unchanged until approved.',
                )
            else:
                messages.info(request, 'No content changes to submit (matches live content).')
            return
        if hasattr(form, '_save_content') and form.cleaned_data:
            form._save_content(obj, request)
        if form.cleaned_data and not getattr(form, 'franchisee_mode', False):
            from courses.venue_approval import (
                CONTENT_CHANGE_APPLY,
                CONTENT_CHANGE_REJECT,
                apply_venue_content_change_request,
                reject_venue_content_change_request,
            )

            content_decision = form.cleaned_data.get('content_change_decision')
            if content_decision == CONTENT_CHANGE_APPLY:
                apply_venue_content_change_request(
                    obj,
                    editor_user=request.user,
                    now=now,
                )
                messages.success(request, 'Pending content changes published.')
            elif content_decision == CONTENT_CHANGE_REJECT:
                reject_venue_content_change_request(
                    obj,
                    reject_reason=form.cleaned_data.get('content_change_reject_reason'),
                    editor_user=request.user,
                    now=now,
                )
                messages.warning(request, 'Pending content changes rejected.')

    def save_formset(self, request, form, formset, change):
        """Stamp granted_by on new VenueWorkshopAccess rows."""
        instances = formset.save(commit=False)
        for obj in instances:
            if hasattr(obj, 'granted_by_id') and not obj.granted_by_id:
                obj.granted_by = request.user
            obj.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()


