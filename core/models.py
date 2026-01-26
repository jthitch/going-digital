"""
Core models including User with role-based permissions.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """
    Custom User model with role-based permissions.
    Roles: platform_admin, franchise_owner, staff, customer
    """
    ROLE_CHOICES = [
        ('platform_admin', 'Platform Admin'),
        ('franchise_owner', 'Franchise Owner'),
        ('staff', 'Staff'),
        ('customer', 'Customer'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def is_platform_admin(self):
        """Check if user is a platform admin."""
        return self.role == 'platform_admin' or self.is_superuser
    
    @property
    def is_franchise_owner(self):
        """Check if user is a franchise owner."""
        return self.role == 'franchise_owner'
    
    def has_franchise_access(self, franchise):
        """
        Check if user can access a specific franchise.
        Platform admins have access to all franchises.
        """
        if self.is_platform_admin:
            return True
        if self.is_franchise_owner:
            # This will be checked via the FranchiseOwner relationship
            return hasattr(self, 'owned_franchises') and franchise in self.owned_franchises.all()
        return False
