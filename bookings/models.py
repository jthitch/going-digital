"""
Booking models for course reservations.
"""
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from decimal import Decimal
from core.models import User
from courses.models import CourseInstance
from payments.models import Payment


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
    
    course_instance = models.ForeignKey(
        CourseInstance,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='bookings')
    payment = models.OneToOneField(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking'
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
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    booking_reference = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Pricing (snapshot at booking time)
    price_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
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
            models.Index(fields=['course_instance', 'status']),
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
        return timezone.now() > self.course_instance.start_date
