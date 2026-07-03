from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

from .admin_mixins import (
    LegacyAuditAdminMixin,
    PlatformAdminOnlyMixin,
    RegionScopedCourseAdminMixin,
    RegionScopedVenueAdminMixin,
    RegionScopedWorkshopAdminMixin,
)
from .region_scope import user_can_access_workshop, user_has_full_region_access
from .workshop_duplicate import (
    duplicate_workshop_querystring,
    get_duplicate_source_workshop,
    workshop_duplicate_initial,
)
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
    WorkshopDocument,
)


@admin.register(Image)
class ImageAdmin(LegacyAuditAdminMixin, PlatformAdminOnlyMixin, admin.ModelAdmin):
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
class CourseSkillLevelAdmin(LegacyAuditAdminMixin, PlatformAdminOnlyMixin, admin.ModelAdmin):
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


@admin.register(CourseCategory)
class CourseCategoryAdmin(LegacyAuditAdminMixin, PlatformAdminOnlyMixin, admin.ModelAdmin):
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
class CourseAdmin(LegacyAuditAdminMixin, RegionScopedCourseAdminMixin, admin.ModelAdmin):
    """Course admin - maps to legacy gd_course table. Content editable inline."""
    form = CourseAdminForm
    change_form_template = 'admin/courses/course/change_form.html'
    inlines = [CourseMediaInline]

    class Media:
        js = (
            'courses/js/admin-course-media.js',
            'courses/js/admin-course-card-image.js',
        )
        css = {'all': ('admin/css/course-admin.css',)}
    list_display = ['course_name', 'course_skill_level', 'course_category', 'active', 'created_at']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if hasattr(form, '_save_content') and form.cleaned_data:
            form._save_content(obj, request)

    list_filter = ['active', 'course_skill_level', 'course_category', 'created_at']
    search_fields = ['course_name', 'course_description', 'description_for_workshop', 'slug']
    prepopulated_fields = {'slug': ('course_name',)}
    readonly_fields = [
        'createdby_id', 'updatedby_id', 'created_at', 'updated_at',
        'card_list_image_preview',
    ]
    list_editable = ['active']

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
class WorkshopAdmin(LegacyAuditAdminMixin, RegionScopedWorkshopAdminMixin, admin.ModelAdmin):
    audit_set_user_id_on_create = True
    form = WorkshopAdminForm
    change_form_template = 'admin/courses/workshop/change_form.html'
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
    fieldsets = [
        (None, {
            'fields': (
                'active',
                'course',
                'venue',
                'region',
                'open_dated',
                'date',
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
                'reminder_message',
                'approve',
                'image_preview',
                'images',
                'image_upload',
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
        extra_context = extra_context or {}
        source = get_duplicate_source_workshop(request)
        if source:
            messages.info(
                request,
                f'Copied settings from {source}. Set a date or mark as open dated, then save.',
            )
            extra_context['is_workshop_duplicate'] = True
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and self.has_add_permission(request) and user_can_access_workshop(request.user, obj):
            add_url = reverse('admin:courses_workshop_add')
            extra_context['duplicate_workshop_url'] = (
                f'{add_url}?{duplicate_workshop_querystring(obj)}'
            )
        self._current_request = request
        return super().change_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'course', 'venue',
        ).prefetch_related('gallery_images__image', 'documents')

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

    @admin.display(description='Updated by')
    def updatedby_display(self, obj):
        return obj.get_updatedby_display()

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
    readonly_fields = ['created_at', 'updated_at', 'venue_document_display']
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

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
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
        ('Venue documents', {
            'fields': ('venue_document_display', 'add_document_to_booking_email'),
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
                'status',
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


