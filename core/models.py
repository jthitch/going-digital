"""
Core models including User with role-based permissions.
Maps to legacy gd_user table.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class GdUserManager(BaseUserManager):
    def create_user(self, email, password=None, **kwargs):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **kwargs):
        kwargs.setdefault('user_type_id', 1)
        kwargs.setdefault('active', 1)
        kwargs.setdefault('firstname', '')
        kwargs.setdefault('lastname', '')
        return self.create_user(email, password, **kwargs)


class User(AbstractBaseUser):
    """
    Custom User model mapping to legacy gd_user table.
    Uses email for login. user_type_id: 1=Super User, 2=Administrator, 3=Franchisee.
    """
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = GdUserManager()

    id = models.BigAutoField(primary_key=True, db_column='id')
    password = models.CharField(max_length=255, db_column='password')
    last_login = models.DateTimeField(null=True, blank=True, db_column='last_login_date')
    FID = models.IntegerField(null=True, blank=True, db_column='FID')
    RID = models.IntegerField(null=True, blank=True, db_column='RID')
    user_type_id = models.IntegerField(null=True, blank=True, db_column='user_type_id')
    region_id = models.IntegerField(null=True, blank=True, db_column='region_id')
    active = models.SmallIntegerField(default=1, db_column='active')
    is_franchisee = models.SmallIntegerField(null=True, blank=True, db_column='is_franchisee')
    guid = models.CharField(max_length=32, null=True, blank=True, db_column='guid')
    firstname = models.CharField(max_length=255, default='', db_column='firstname')
    lastname = models.CharField(max_length=255, default='', db_column='lastname')
    email = models.CharField(max_length=255, unique=True, db_column='email')
    # password from AbstractBaseUser - map to gd_user.password
    secure_code = models.CharField(max_length=255, null=True, blank=True, db_column='secure_code')
    company = models.CharField(max_length=255, null=True, blank=True, db_column='company')
    address = models.TextField(null=True, blank=True, db_column='address')
    address1 = models.CharField(max_length=255, null=True, blank=True, db_column='address1')
    address2 = models.CharField(max_length=255, null=True, blank=True, db_column='address2')
    town_city = models.CharField(max_length=255, null=True, blank=True, db_column='town_city')
    postcode = models.CharField(max_length=255, null=True, blank=True, db_column='postcode')
    telephone = models.CharField(max_length=255, null=True, blank=True, db_column='telephone')
    mobile = models.CharField(max_length=255, null=True, blank=True, db_column='mobile')
    created_at = models.DateTimeField(null=True, blank=True, db_column='created_at')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='updated_at')

    class Meta:
        db_table = 'gd_user'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    # Compatibility properties
    @property
    def username(self):
        """Django login form uses 'username' - we use email."""
        return self.email or ''

    @property
    def first_name(self):
        return self.firstname or ''

    @property
    def last_name(self):
        return self.lastname or ''

    @property
    def is_active(self):
        return self.active == 1

    @property
    def is_staff(self):
        """Staff can access Django admin (super users, admins, franchisees)."""
        if self.active != 1:
            return False
        if self.user_type_id in (1, 2, 3):
            return True
        return self.is_franchisee == 1

    @property
    def is_superuser(self):
        return self.user_type_id == 1

    ROLE_CHOICES = [
        ('platform_admin', 'Platform Admin'),
        ('franchise_owner', 'Franchise Owner'),
        ('staff', 'Staff'),
        ('customer', 'Customer'),
    ]

    @property
    def role(self):
        """Map user_type_id to Django role."""
        return {1: 'platform_admin', 2: 'staff', 3: 'franchise_owner'}.get(
            self.user_type_id, 'customer'
        )

    def get_role_display(self):
        for val, label in self.ROLE_CHOICES:
            if val == self.role:
                return label
        return 'Customer'

    USER_TYPE_LABELS = {1: 'Super User', 2: 'Administrator', 3: 'Franchisee'}

    def get_user_type_display(self):
        """Return user_type label from gd_user_type (1=Super User, 2=Administrator, 3=Franchisee)."""
        return self.USER_TYPE_LABELS.get(self.user_type_id, '—')

    get_user_type_display.short_description = 'User type'
    get_user_type_display.admin_order_field = 'user_type_id'

    @property
    def is_platform_admin(self):
        return self.role == 'platform_admin' or self.is_superuser

    @property
    def is_franchise_owner(self):
        return self.role == 'franchise_owner'

    def has_franchise_access(self, franchise):
        if self.is_platform_admin:
            return True
        if self.is_franchise_owner:
            return hasattr(self, 'owned_franchises') and franchise in self.owned_franchises.all()
        return False

    @property
    def is_region_scoped(self):
        """Franchisees (user_type_id=3) are limited to assigned gd_region rows."""
        return self.user_type_id == 3 and not self.is_superuser

    def get_region_ids(self):
        """
        Region ids this user may access (from gd_region_user).
        Falls back to gd_user.region_id when no junction rows exist.
        """
        from courses.models import RegionUser

        ids = list(
            RegionUser.objects.filter(user_id=self.pk)
            .values_list('region_id', flat=True)
            .distinct()
        )
        ids = [i for i in ids if i is not None]
        if not ids and self.region_id:
            ids = [self.region_id]
        return ids

    def get_full_name(self):
        return f"{self.firstname} {self.lastname}".strip() or self.email

    def get_short_name(self):
        return self.firstname or self.email

    FRANCHISEE_PERMS = frozenset({
        'courses.view_course',
        'courses.view_workshop',
        'courses.add_workshop',
        'courses.change_workshop',
        'courses.delete_workshop',
        'courses.view_venue',
        'courses.add_venue',
        'courses.change_venue',
        'courses.view_venuemedia',
        'courses.add_venuemedia',
        'courses.change_venuemedia',
        'courses.delete_venuemedia',
        'payments.view_payment',
    })

    def has_perm(self, perm, obj=None):
        if self.is_superuser or self.user_type_id == 2:
            return True
        if self.is_region_scoped and perm in self.FRANCHISEE_PERMS:
            return True
        return False

    def has_module_perms(self, app_label):
        if not self.is_staff:
            return False
        if self.is_superuser or self.user_type_id == 2:
            return True
        if self.is_region_scoped and app_label in ('courses', 'payments'):
            return bool(self.get_region_ids())
        return False

    def get_all_permissions(self, obj=None):
        """Required by Jazzmin/admin. Superusers get all permissions."""
        if self.is_superuser:
            from django.contrib.auth.models import Permission
            return set(
                f"{p.content_type.app_label}.{p.codename}"
                for p in Permission.objects.all()
            )
        return set()
