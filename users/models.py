import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model using email instead of username.
    Supports role-based access control (RBAC).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email
    
    def has_permission(self, permission_codename):
        """
        Check if user has a specific permission via any of their roles.
        
        Args:
            permission_codename: String codename of the permission
            
        Returns:
            True if user has the permission, False otherwise
        """
        if self.is_superuser:
            return True
        
        return UserRole.objects.filter(
            user=self,
            role__role_permissions__permission__codename=permission_codename
        ).exists()
    
    def has_role(self, role_name):
        """
        Check if user has a specific role.
        
        Args:
            role_name: String name of the role
            
        Returns:
            True if user has the role, False otherwise
        """
        return UserRole.objects.filter(
            user=self,
            role__name=role_name
        ).exists()
    
    def get_permissions(self):
        """
        Get all permissions for this user (via roles).
        
        Returns:
            QuerySet of Permission objects
        """
        if self.is_superuser:
            # Superusers have all permissions
            return Permission.objects.all()
        
        # Get all permissions via user's roles
        return Permission.objects.filter(
            role_permissions__role__user_roles__user=self
        ).distinct()


class Role(models.Model):
    """
    Predefined roles for access control.
    Examples: admin, analyst, data_viewer
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        ordering = ['name']

    def __str__(self):
        return self.name


class Permission(models.Model):
    """
    Granular permissions that can be assigned to roles.
    Examples: create_survey, view_responses, export_data
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'custom_permissions'
        ordering = ['codename']

    def __str__(self):
        return self.codename


class UserRole(models.Model):
    """
    Many-to-many relationship between users and roles.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_roles'
        unique_together = ['user', 'role']

    def __str__(self):
        return f'{self.user.email} - {self.role.name}'


class RolePermission(models.Model):
    """
    Many-to-many relationship between roles and permissions.
    """
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )

    class Meta:
        db_table = 'role_permissions'
        unique_together = ['role', 'permission']

    def __str__(self):
        return f'{self.role.name} - {self.permission.codename}'


class UserSession(models.Model):
    """
    Tracks user login sessions. Each login creates a session.
    JWT tokens include session_id - on logout, session is deactivated,
    making all tokens with that session_id invalid immediately.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    is_active = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logged_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f'{self.user.email} - {status} - {self.created_at}'
