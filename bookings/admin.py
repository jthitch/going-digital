from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'course_instance',
        'status',
        'price_paid',
        'created_at'
    ]
    list_filter = ['status', 'created_at', 'course_instance__course', 'course_instance__location']
    search_fields = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'student_email',
        'user__username',
        'user__email'
    ]
    readonly_fields = ['booking_reference', 'created_at', 'updated_at', 'cancelled_at']
    date_hierarchy = 'created_at'
