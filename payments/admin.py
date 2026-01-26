from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'stripe_id',
        'user',
        'amount',
        'currency',
        'status',
        'intent_type',
        'created_at',
        'succeeded_at'
    ]
    list_filter = ['status', 'intent_type', 'currency', 'created_at']
    search_fields = ['stripe_id', 'user__username', 'user__email', 'description']
    readonly_fields = [
        'stripe_id',
        'created_at',
        'updated_at',
        'succeeded_at',
        'last_webhook_event',
        'webhook_processed'
    ]
    date_hierarchy = 'created_at'
