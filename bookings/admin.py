from django.contrib import admin
from .models import Booking, Voucher


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
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
        'region_id', 'course_ids', 'workshop_id', 'actioned', 'email', 'issue_date',
        'expiry_date', 'value', 'voucher_code', 'claimed_date', 'amount_claimed',
        'payment_gateway_id', 'gateway_transaction_code', 'transaction_percentage_on_creation',
        'notes', 'minimum_workshops', 'allowed_course', 'createdby_id', 'updatedby_id',
        'created_at', 'updated_at',
    ]
    # No date_hierarchy - issue_date has legacy 0000-00-00 values that break aggregate queries


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'workshop',
        'status',
        'price_paid',
        'created_at'
    ]
    list_filter = ['status', 'created_at', 'workshop__course', 'workshop__venue']
    search_fields = [
        'booking_reference',
        'student_first_name',
        'student_last_name',
        'student_email',
        'user__email',
        'user__email'
    ]
    readonly_fields = ['booking_reference', 'created_at', 'updated_at', 'cancelled_at']
    date_hierarchy = 'created_at'


