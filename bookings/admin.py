from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from courses.admin_mixins import PlatformAdminOnlyMixin

from .admin_mixins import RegionScopedBookingAdminMixin
from .models import Booking, Voucher


@admin.register(Voucher)
class VoucherAdmin(PlatformAdminOnlyMixin, admin.ModelAdmin):
    list_display = [
        'id',
        'voucher_code',
        'value',
        'email',
        'active',
        'issue_date',
        'expiry_date',
        'claimed_date',
    ]
    list_filter = ['active', 'actioned', 'issue_date', 'expiry_date']
    search_fields = ['voucher_code', 'email', 'notes']
    readonly_fields = [
        'id', 'basket_id', 'active', 'voucher_type_id', 'use_once', 'voucher_group_id',
        'user_id', 'customer_id', 'claimed_by_customer_id', 'claimed_on_booking_id',
        'claimed_booking_link',
        'region_id', 'course_ids', 'workshop_id', 'actioned', 'email', 'issue_date',
        'expiry_date', 'value', 'voucher_code', 'claimed_date', 'amount_claimed',
        'payment_gateway_id', 'gateway_transaction_code', 'transaction_percentage_on_creation',
        'notes', 'minimum_workshops', 'allowed_course', 'createdby_id', 'updatedby_id',
        'created_at', 'updated_at',
    ]

    @admin.display(description='Claimed booking')
    def claimed_booking_link(self, obj):
        if not obj.claimed_on_booking_id:
            return '—'
        booking = Booking.objects.filter(pk=obj.claimed_on_booking_id).first()
        if not booking:
            return f'Booking #{obj.claimed_on_booking_id}'
        url = reverse('admin:bookings_booking_change', args=[booking.pk])
        return format_html('<a href="{}">{}</a>', url, booking.booking_reference)


@admin.register(Booking)
class BookingAdmin(RegionScopedBookingAdminMixin, admin.ModelAdmin):
    list_display = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'student_email',
        'course_name',
        'workshop_date',
        'status',
        'payment_status',
        'voucher_code',
        'voucher_discount',
        'price_paid',
        'created_at',
    ]
    list_filter = ['status', 'created_at', 'workshop__course', 'workshop__venue']
    search_fields = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'student_email',
        'voucher_code',
        'user__email',
        'workshop__course__course_name',
    ]
    readonly_fields = [
        'booking_reference',
        'workshop',
        'user',
        'payment',
        'student_first_name',
        'student_last_name',
        'student_email',
        'student_phone',
        'special_requirements',
        'status',
        'list_price',
        'voucher_id',
        'voucher_code',
        'voucher_discount',
        'voucher_redeemed_at',
        'voucher_admin_link',
        'price_paid',
        'created_at',
        'updated_at',
        'cancelled_at',
        'workshop_summary',
    ]
    fieldsets = (
        (None, {
            'fields': (
                'booking_reference',
                'status',
                'workshop_summary',
            ),
        }),
        ('Pricing', {
            'fields': (
                'list_price',
                'voucher_code',
                'voucher_discount',
                'voucher_id',
                'voucher_admin_link',
                'voucher_redeemed_at',
                'price_paid',
            ),
        }),
        ('Student', {
            'fields': (
                'student_first_name',
                'student_last_name',
                'student_email',
                'student_phone',
                'special_requirements',
            ),
        }),
        ('Payment & account', {
            'fields': (
                'payment',
                'user',
            ),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'cancelled_at',
            ),
        }),
    )
    date_hierarchy = 'created_at'

    @admin.display(description='Course', ordering='workshop__course__course_name')
    def course_name(self, obj):
        if not obj.workshop or not obj.workshop.course:
            return '—'
        return obj.workshop.course.course_name

    @admin.display(description='Workshop date', ordering='workshop__date')
    def workshop_date(self, obj):
        if not obj.workshop or not obj.workshop.date:
            return '—'
        return obj.workshop.date.strftime('%d %b %Y')

    @admin.display(description='Payment', ordering='payment__status')
    def payment_status(self, obj):
        if not obj.payment:
            return '—'
        return obj.payment.get_status_display() if hasattr(obj.payment, 'get_status_display') else obj.payment.status

    @admin.display(description='Voucher record')
    def voucher_admin_link(self, obj):
        if not obj.voucher_id:
            return '—'
        url = reverse('admin:bookings_voucher_change', args=[obj.voucher_id])
        label = obj.voucher_code or f'Voucher #{obj.voucher_id}'
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(description='Workshop')
    def workshop_summary(self, obj):
        workshop = obj.workshop
        if not workshop:
            return '—'
        parts = []
        if workshop.course:
            parts.append(format_html('Course: <strong>{}</strong>', workshop.course.course_name))
        if workshop.venue:
            parts.append(format_html('Venue: {}', workshop.venue.venue_name))
        if workshop.date:
            parts.append(format_html('Date: {}', workshop.date.strftime('%d %B %Y')))
        return format_html('<br>'.join(parts)) if parts else '—'
