"""
Franchise models for multi-admin permission handling.
"""
from django.db import models
from django.core.validators import RegexValidator
from core.models import User


class Franchise(models.Model):
    """Franchise entity - can have multiple locations."""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_franchises',
        limit_choices_to={'role': 'franchise_owner'}
    )
    email = models.EmailField()
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'franchises'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Location(models.Model):
    """Location where courses are held - belongs to a franchise."""
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='US')
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations'
        unique_together = [['franchise', 'slug']]
        ordering = ['city', 'name']
    
    def __str__(self):
        return f"{self.name}, {self.city}"
    
    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        return ", ".join(parts)
