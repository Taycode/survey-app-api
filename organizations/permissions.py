"""
Custom permission classes for organization access control.
"""
from rest_framework import permissions
from .models import OrganizationMembership


class IsOrganizationOwner(permissions.BasePermission):
    """
    Permission check: User must be owner of the organization.
    Used for destructive operations like deleting org or removing members.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.memberships.filter(
            user=request.user,
            role=OrganizationMembership.Role.OWNER
        ).exists()


class IsOrganizationMember(permissions.BasePermission):
    """
    Permission check: User must be a member of the organization.
    Used for read operations and basic organization access.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.members.filter(id=request.user.id).exists()


class IsOrganizationOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission check: Owner can edit, members can read.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for any member
        if request.method in permissions.SAFE_METHODS:
            return obj.members.filter(id=request.user.id).exists()
        
        # Write permissions only for owners
        return obj.memberships.filter(
            user=request.user,
            role=OrganizationMembership.Role.OWNER
        ).exists()

