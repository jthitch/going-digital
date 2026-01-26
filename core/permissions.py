"""
Permission helpers for franchise owners and platform admins.
"""
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from franchises.models import Franchise, Location
from core.models import User


def platform_admin_required(view_func):
    """Decorator to require platform admin access."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_platform_admin:
            raise PermissionDenied("Platform admin access required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def franchise_owner_required(view_func):
    """Decorator to require franchise owner access."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_franchise_owner:
            raise PermissionDenied("Franchise owner access required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class FranchiseOwnerMixin:
    """
    Mixin to restrict views to franchise owners.
    Optionally restrict to specific franchise via franchise_id or franchise_slug in kwargs.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        
        # Platform admins have full access
        if request.user.is_platform_admin:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user is franchise owner
        if not request.user.is_franchise_owner:
            raise PermissionDenied("Franchise owner access required.")
        
        # If specific franchise is requested, check ownership
        franchise_id = kwargs.get('franchise_id')
        franchise_slug = kwargs.get('franchise_slug')
        
        if franchise_id:
            franchise = get_object_or_404(Franchise, id=franchise_id)
            if not request.user.has_franchise_access(franchise):
                raise PermissionDenied("You do not have access to this franchise.")
        elif franchise_slug:
            franchise = get_object_or_404(Franchise, slug=franchise_slug)
            if not request.user.has_franchise_access(franchise):
                raise PermissionDenied("You do not have access to this franchise.")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Filter queryset to only show franchise owner's data."""
        queryset = super().get_queryset()
        
        # Platform admins see everything
        if self.request.user.is_platform_admin:
            return queryset
        
        # Franchise owners see only their franchises
        if self.request.user.is_franchise_owner:
            return queryset.filter(franchise__owner=self.request.user)
        
        return queryset.none()


class PlatformAdminMixin:
    """Mixin to restrict views to platform admins only."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_platform_admin:
            raise PermissionDenied("Platform admin access required.")
        return super().dispatch(request, *args, **kwargs)
