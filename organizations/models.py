import uuid
from django.db import models
from django.conf import settings


class Organization(models.Model):
    """
    Organization/Tenant model for multi-tenancy support.
    Users can belong to multiple organizations via OrganizationMembership.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Many-to-many with User through OrganizationMembership
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='OrganizationMembership',
        related_name='organizations'
    )
    
    class Meta:
        db_table = 'organizations'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """
    Through model for User-Organization many-to-many relationship.
    Tracks user roles within organizations.
    """
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        MEMBER = 'member', 'Member'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'organization_memberships'
        unique_together = [['user', 'organization']]  # User can't join same org twice
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"
