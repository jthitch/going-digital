from django.contrib import admin
from .models import Course, CourseInstance, Instructor
from .forms import CourseAdminForm


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


