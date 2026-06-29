"""
Booking models for course reservations.
"""
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from decimal import Decimal
from core.models import User, Customer
from courses.models import Workshop
from payments.models import Payment
from courses.models import SafeDateTimeField, SafeDateField


class Booking(models.Model):
    """
    Booking for a course instance.
    Each booking is for one student.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='bookings',
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='bookings',
        null=True,
        blank=True,
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
    )
    
    # Student information (may differ from user account)
    student_first_name = models.CharField(max_length=100)
    student_last_name = models.CharField(max_length=100)
    student_email = models.EmailField()
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    student_phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # Special requirements
    special_requirements = models.TextField(blank=True, help_text="Dietary, accessibility, etc.")
    loan_camera = models.BooleanField(
        default=False,
        help_text='Student has requested a loan camera for this place.',
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    booking_reference = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Pricing (snapshot at booking time)
    list_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Workshop price before voucher discount',
    )
    voucher_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='gd_voucher.id applied at checkout (redeemed after payment)',
    )
    voucher_code = models.CharField(max_length=255, blank=True, default='')
    voucher_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    voucher_redeemed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the voucher was marked redeemed against this booking',
    )
    price_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bookings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_reference']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['workshop', 'status']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_reference} - {self.student_first_name} {self.student_last_name}"
    
    def generate_booking_reference(self):
        """Generate unique booking reference."""
        import random
        import string
        while True:
            ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Booking.objects.filter(booking_reference=ref).exists():
                return ref
    
    def save(self, *args, **kwargs):
        """Auto-generate booking reference on creation."""
        if not self.booking_reference:
            self.booking_reference = self.generate_booking_reference()
        super().save(*args, **kwargs)
    
    @property
    def is_confirmed(self):
        """Check if booking is confirmed."""
        return self.status == 'confirmed' and self.payment and self.payment.status == 'succeeded'
    
    @property
    def can_cancel(self):
        """Check if booking can be cancelled."""
        return self.status in ['pending', 'confirmed'] and not self.is_past_course_start()
    
    def is_past_course_start(self):
        """Check if course has already started."""
        from django.utils import timezone
        return timezone.now() > self.workshop.start_date

    @property
    def used_voucher(self):
        return bool(self.voucher_id and self.voucher_code)


class BookingTermsAcceptance(models.Model):
    """Records that a customer accepted terms before basket checkout."""
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='terms_acceptances',
        null=True,
        blank=True,
    )
    basket_id = models.IntegerField(db_index=True, help_text='gd_basket.id for this checkout.')
    booking_ids = models.JSONField(default=list, blank=True)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    terms_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Terms and conditions page version at time of acceptance.',
    )

    class Meta:
        db_table = 'booking_terms_acceptance'
        ordering = ['-accepted_at']
        verbose_name = 'Terms acceptance'
        verbose_name_plural = 'Terms acceptances'

    def __str__(self):
        return f'Terms accepted for basket {self.basket_id} at {self.accepted_at:%Y-%m-%d %H:%M}'


class Voucher(models.Model):
    """
    Legacy gift voucher - maps to gd_voucher.
    Read-only admin view for voucher data.
    """
    id = models.AutoField(primary_key=True, db_column='id')
    basket_id = models.IntegerField(null=True, blank=True, db_column='basket_id')
    active = models.IntegerField(default=1, db_column='active')
    voucher_type_id = models.IntegerField(null=True, blank=True, db_column='voucher_type_id')
    use_once = models.IntegerField(default=0, db_column='use_once')
    voucher_group_id = models.IntegerField(null=True, blank=True, db_column='voucher_group_id')
    user_id = models.IntegerField(null=True, blank=True, db_column='user_id')
    customer_id = models.IntegerField(null=True, blank=True, db_column='customer_id')
    claimed_by_customer_id = models.IntegerField(null=True, blank=True, db_column='claimed_by_customer_id')
    claimed_on_booking_id = models.IntegerField(null=True, blank=True, db_column='claimed_on_booking_id')
    region_id = models.IntegerField(null=True, blank=True, db_column='region_id')
    course_ids = models.TextField(null=True, blank=True, db_column='course_ids')
    workshop_id = models.IntegerField(null=True, blank=True, db_column='workshop_id')
    actioned = models.IntegerField(default=0, db_column='actioned')
    email = models.CharField(max_length=255, null=True, blank=True, db_column='email')
    issue_date = SafeDateField(null=True, blank=True, db_column='issue_date')
    expiry_date = SafeDateField(null=True, blank=True, db_column='expiry_date')
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='value')
    voucher_code = models.CharField(max_length=255, default='', db_column='voucher_code')
    claimed_date = SafeDateField(null=True, blank=True, db_column='claimed_date')
    amount_claimed = models.DecimalField(max_digits=7, decimal_places=2, default=0, db_column='amount_claimed')
    payment_gateway_id = models.IntegerField(null=True, blank=True, db_column='payment_gateway_id')
    gateway_transaction_code = models.CharField(max_length=255, null=True, blank=True, db_column='gateway_transaction_code')
    transaction_percentage_on_creation = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, db_column='transaction_percentage_on_creation')
    notes = models.TextField(null=True, blank=True, db_column='notes')
    minimum_workshops = models.IntegerField(null=True, blank=True, db_column='minimum_workshops')
    allowed_course = models.IntegerField(null=True, blank=True, db_column='allowed_course')
    createdby_id = models.IntegerField(null=True, blank=True, db_column='createdby_id')
    updatedby_id = models.IntegerField(null=True, blank=True, db_column='updatedby_id')
    created_at = SafeDateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = SafeDateTimeField(null=True, blank=True, db_column='updated_at')

    class Meta:
        db_table = 'gd_voucher'
        managed = False
        ordering = ['-id']
        verbose_name = 'Voucher'
        verbose_name_plural = 'Vouchers'

    def __str__(self):
        return self.voucher_code or f'Voucher #{self.id}'


