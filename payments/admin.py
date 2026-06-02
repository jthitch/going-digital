from django.contrib import admin
from django.utils.html import format_html

from .admin_mixins import RegionScopedPaymentAdminMixin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(RegionScopedPaymentAdminMixin, admin.ModelAdmin):
    list_display = [
        'stripe_id',
        'booking_reference',
        'course_name',
        'workshop_date',
        'amount',
        'currency',
        'status',
        'created_at',
        'succeeded_at',
    ]
    list_filter = ['status', 'intent_type', 'currency', 'created_at']
    search_fields = [
        'stripe_id',
        'user__email',
        'description',
        'booking__booking_reference',
        'booking__student_email',
        'booking__workshop__course__course_name',
    ]
    readonly_fields = [
        'stripe_id',
        'user',
        'intent_type',
        'amount',
        'currency',
        'status',
        'description',
        'metadata',
        'created_at',
        'updated_at',
        'succeeded_at',
        'last_webhook_event',
        'webhook_processed',
        'booking_link',
    ]
    fields = [
        'stripe_id',
        'status',
        'amount',
        'currency',
        'intent_type',
        'user',
        'description',
        'booking_link',
        'metadata',
        'created_at',
        'updated_at',
        'succeeded_at',
        'last_webhook_event',
        'webhook_processed',
    ]
    date_hierarchy = 'created_at'

    @admin.display(description='Booking')
    def booking_reference(self, obj):
        booking = getattr(obj, 'booking', None)
        if not booking:
            return '—'
        return booking.booking_reference

    @admin.display(description='Course')
    def course_name(self, obj):
        booking = getattr(obj, 'booking', None)
        if not booking or not booking.workshop or not booking.workshop.course:
            return '—'
        return booking.workshop.course.course_name

    @admin.display(description='Workshop date', ordering='booking__workshop__date')
    def workshop_date(self, obj):
        booking = getattr(obj, 'booking', None)
        if not booking or not booking.workshop or not booking.workshop.date:
            return '—'
        return booking.workshop.date.strftime('%d %b %Y')

    @admin.display(description='Booking details')
    def booking_link(self, obj):
        booking = getattr(obj, 'booking', None)
        if not booking:
            return '—'
        workshop = booking.workshop
        parts = [
            format_html('<strong>{}</strong>', booking.booking_reference),
            format_html('{} {}', booking.student_first_name, booking.student_last_name),
            format_html('{}', booking.student_email),
        ]
        if workshop:
            if workshop.course:
                parts.append(format_html('Course: {}', workshop.course.course_name))
            if workshop.venue:
                parts.append(format_html('Venue: {}', workshop.venue.venue_name))
            if workshop.date:
                parts.append(format_html('Date: {}', workshop.date.strftime('%d %B %Y')))
        return format_html('<br>'.join(parts))
