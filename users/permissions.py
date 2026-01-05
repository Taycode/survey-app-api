"""
Custom permission classes for RBAC (Role-Based Access Control).

These permission classes check if a user has specific permissions via their roles.
"""
from typing import Optional
from rest_framework import permissions
from .models import UserRole


def user_has_permission(user, permission_codename):
    """
    Check if user has permission via any of their roles.
    
    Args:
        user: User instance
        permission_codename: String codename of the permission
        
    Returns:
        True if user has the permission, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusers bypass all permission checks
    if user.is_superuser:
        return True
    
    # Check if user has permission via any of their roles
    return UserRole.objects.filter(
        user=user,
        role__role_permissions__permission__codename=permission_codename
    ).exists()


class HasRBACPermission(permissions.BasePermission):
    """
    Base permission class for RBAC permission checking.
    
    Subclasses should set the `permission_codename` attribute.
    """
    permission_codename: Optional[str] = None
    
    def has_permission(self, request, view):
        """Check if user has the required permission."""
        if not request.user or not request.user.is_authenticated:
            return False
        return user_has_permission(request.user, self.permission_codename)


class CanCreateSurvey(HasRBACPermission):
    """Permission to create surveys."""
    permission_codename = 'create_survey'


class CanEditSurvey(permissions.BasePermission):
    """Permission to edit surveys. Also allows if user is the creator."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has edit_survey permission
        if user_has_permission(request.user, 'edit_survey'):
            return True
        
        # For object-level checks, allow if user is creator
        if hasattr(view, 'get_object'):
            try:
                obj = view.get_object()
                if hasattr(obj, 'created_by'):
                    return obj.created_by == request.user
            except Exception:
                pass
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Check if user can edit this specific survey."""
        # User has edit_survey permission
        if user_has_permission(request.user, 'edit_survey'):
            return True
        
        # User is the creator
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class CanDeleteSurvey(permissions.BasePermission):
    """Permission to delete surveys. Also allows if user is the creator."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has delete_survey permission
        if user_has_permission(request.user, 'delete_survey'):
            return True
        
        # For object-level checks, allow if user is creator
        if hasattr(view, 'get_object'):
            try:
                obj = view.get_object()
                if hasattr(obj, 'created_by'):
                    return obj.created_by == request.user
            except Exception:
                pass
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Check if user can delete this specific survey."""
        # User has delete_survey permission
        if user_has_permission(request.user, 'delete_survey'):
            return True
        
        # User is the creator
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class CanPublishSurvey(HasRBACPermission):
    """Permission to publish surveys."""
    permission_codename = 'publish_survey'


class CanViewResponses(HasRBACPermission):
    """Permission to view survey responses."""
    permission_codename = 'view_responses'


class CanExportResponses(HasRBACPermission):
    """Permission to export survey responses."""
    permission_codename = 'export_responses'


class CanViewAnalytics(HasRBACPermission):
    """Permission to view analytics dashboards."""
    permission_codename = 'view_analytics'

