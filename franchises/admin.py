from django.contrib import admin
from .models import Franchise, Location


class FranchiseAdmin(admin.ModelAdmin):
    """Custom admin with franchise owner restrictions."""
    list_display = ['name', 'owner', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'owner__email', 'owner__firstname', 'owner__lastname']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Filter queryset based on user permissions."""
        qs = super().get_queryset(request)
        
        # Platform admins see everything
        if request.user.is_platform_admin:
            return qs
        
        # Franchise owners see only their franchises
        if request.user.is_franchise_owner:
            return qs.filter(owner=request.user)
        
        return qs.none()
    
    def has_add_permission(self, request):
        """Only platform admins can add franchises."""
        return request.user.is_platform_admin
    
    def has_change_permission(self, request, obj=None):
        """Platform admins can change all, franchise owners can change their own."""
        if request.user.is_platform_admin:
            return True
        if request.user.is_franchise_owner:
            if obj is None:
                return True
            return obj.owner == request.user
        return False

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


class LocationAdmin(admin.ModelAdmin):
    """Custom admin with franchise owner restrictions."""
    list_display = ['name', 'city', 'franchise', 'is_active']
    list_filter = ['franchise', 'city', 'is_active']
    search_fields = ['name', 'city', 'address_line_1']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Filter queryset based on user permissions."""
        qs = super().get_queryset(request)
        
        # Platform admins see everything
        if request.user.is_platform_admin:
            return qs
        
        # Franchise owners see only their locations
        if request.user.is_franchise_owner:
            return qs.filter(franchise__owner=request.user)
        
        return qs.none()
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_platform_admin:
            return True
        if request.user.is_franchise_owner:
            if obj is None:
                return True
            return obj.franchise.owner == request.user
        return False

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restrict franchise selection for franchise owners."""
        if db_field.name == "franchise" and not request.user.is_platform_admin:
            if request.user.is_franchise_owner:
                kwargs["queryset"] = Franchise.objects.filter(owner=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


from django.contrib import admin
from .models import Franchise, Location


class FranchiseAdmin(admin.ModelAdmin):
    """Custom admin with franchise owner restrictions (not exposed in admin UI)."""
    list_display = ['name', 'owner', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'owner__email', 'owner__firstname', 'owner__lastname']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Filter queryset based on user permissions."""
        qs = super().get_queryset(request)
        
        # Platform admins see everything
        if request.user.is_platform_admin:
            return qs
        
        # Franchise owners see only their franchises
        if request.user.is_franchise_owner:
            return qs.filter(owner=request.user)
        
        return qs.none()
    
    def has_add_permission(self, request):
        """Only platform admins can add franchises."""
        return request.user.is_platform_admin
    
    def has_change_permission(self, request, obj=None):
        """Platform admins can change all, franchise owners can change their own."""
        if request.user.is_platform_admin:
            return True
        if request.user.is_franchise_owner:
            if obj is None:
                return True
            return obj.owner == request.user
        return False

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


class LocationAdmin(admin.ModelAdmin):
    """Custom admin with franchise owner restrictions (not exposed in admin UI)."""
    list_display = ['name', 'city', 'franchise', 'is_active']
    list_filter = ['franchise', 'city', 'is_active']
    search_fields = ['name', 'city', 'address_line_1']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Filter queryset based on user permissions."""
        qs = super().get_queryset(request)
        
        # Platform admins see everything
        if request.user.is_platform_admin:
            return qs
        
        # Franchise owners see only their locations
        if request.user.is_franchise_owner:
            return qs.filter(franchise__owner=request.user)
        
        return qs.none()
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_platform_admin:
            return True
        if request.user.is_franchise_owner:
            if obj is None:
                return True
            return obj.franchise.owner == request.user
        return False

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restrict franchise selection for franchise owners."""
        if db_field.name == "franchise" and not request.user.is_platform_admin:
            if request.user.is_franchise_owner:
                kwargs["queryset"] = Franchise.objects.filter(owner=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Legacy franchise/location models are not managed via admin (venues use gd_venue).
