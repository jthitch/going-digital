"""
Payment models integrated with Stripe.
"""
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator
from core.models import User


class Payment(models.Model):
    """
    Payment record linked to Stripe.
    Supports both Checkout Sessions and Payment Intents.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    INTENT_CHOICES = [
        ('checkout_session', 'Checkout Session'),
        ('payment_intent', 'Payment Intent'),
    ]
    
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='payments',
        null=True, blank=True  # Null for guest gift voucher purchases (gd_customer only)
    )
    intent_type = models.CharField(max_length=20, choices=INTENT_CHOICES)
    stripe_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='gbp')
    
    # Metadata
    description = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)
    
    # Webhook tracking
    last_webhook_event = models.CharField(max_length=255, blank=True)
    webhook_processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.stripe_id} - ${self.amount} ({self.status})"
