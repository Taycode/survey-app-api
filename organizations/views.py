from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from .models import Organization, OrganizationMembership
from .serializers import (
    OrganizationSerializer,
    OrganizationCreateSerializer,
    OrganizationMembershipSerializer,
    AddMemberSerializer,
)
from .permissions import IsOrganizationOwner, IsOrganizationMember, IsOrganizationOwnerOrReadOnly
from users.models import User


@extend_schema_view(
    list=extend_schema(
        tags=["Organizations"],
        summary="List user's organizations",
        description="Retrieve all organizations the authenticated user belongs to."
    ),
    retrieve=extend_schema(
        tags=["Organizations"],
        summary="Get organization details",
        description="Retrieve details of a specific organization the user is a member of."
    ),
    create=extend_schema(
        tags=["Organizations"],
        summary="Create organization",
        description="Create a new organization. The creator becomes the owner."
    ),
    partial_update=extend_schema(
        tags=["Organizations"],
        summary="Update organization",
        description="Update organization details. Only owners can update."
    ),
    destroy=extend_schema(
        tags=["Organizations"],
        summary="Delete organization",
        description="Delete an organization. Only owners can delete."
    ),
)
class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizations.
    Users can belong to multiple organizations with different roles.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """User sees all organizations they belong to."""
        return self.request.user.organizations.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrganizationCreateSerializer
        return OrganizationSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['update', 'partial_update', 'destroy', 'add_member', 'remove_member']:
            return [IsAuthenticated(), IsOrganizationOwner()]
        elif self.action in ['retrieve', 'members']:
            return [IsAuthenticated(), IsOrganizationMember()]
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create organization and make the creator the owner."""
        organization = serializer.save()
        
        # Make the creator the owner
        OrganizationMembership.objects.create(
            user=self.request.user,
            organization=organization,
            role=OrganizationMembership.Role.OWNER
        )
    
    @extend_schema(
        tags=["Organizations"],
        summary="List organization members",
        description="Retrieve all members of an organization with their roles.",
        responses={200: OrganizationMembershipSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """List all members of the organization."""
        organization = self.get_object()
        memberships = organization.memberships.all()
        serializer = OrganizationMembershipSerializer(memberships, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        tags=["Organizations"],
        summary="Add member to organization",
        description="""
        Add an existing user to the organization by email.
        Only organization owners can add members.
        
        **Request Body:**
        ```json
        {
          "email": "user@example.com",
          "role": "member"  // Options: "owner" or "member"
        }
        ```
        """,
        request=AddMemberSerializer,
        responses={
            201: OrganizationMembershipSerializer,
            400: OpenApiResponse(description="Invalid data or user already member"),
            404: OpenApiResponse(description="User not found")
        }
    )
    @action(detail=True, methods=['post'], url_path='add-member')
    def add_member(self, request, pk=None):
        """Add a member to the organization."""
        organization = self.get_object()
        
        serializer = AddMemberSerializer(
            data=request.data,
            context={'organization': organization}
        )
        serializer.is_valid(raise_exception=True)
        
        # Get user and create membership
        user = User.objects.get(email=serializer.validated_data['email'])
        membership = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=serializer.validated_data['role']
        )
        
        response_serializer = OrganizationMembershipSerializer(membership)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        tags=["Organizations"],
        summary="Remove member from organization",
        description="""
        Remove a member from the organization.
        Only organization owners can remove members.
        Owners cannot remove themselves if they're the last owner.
        """,
        responses={
            204: OpenApiResponse(description="Member removed successfully"),
            400: OpenApiResponse(description="Cannot remove last owner"),
            404: OpenApiResponse(description="Member not found")
        }
    )
    @action(detail=True, methods=['delete'], url_path='members/(?P<user_id>[^/.]+)')
    def remove_member(self, request, pk=None, user_id=None):
        """Remove a member from the organization."""
        organization = self.get_object()
        
        # Get the membership
        membership = get_object_or_404(
            OrganizationMembership,
            organization=organization,
            user__id=user_id
        )
        
        # Prevent removing the last owner
        if membership.role == OrganizationMembership.Role.OWNER:
            owner_count = organization.memberships.filter(
                role=OrganizationMembership.Role.OWNER
            ).count()
            
            if owner_count <= 1:
                return Response(
                    {'detail': 'Cannot remove the last owner of the organization'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
