from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_active', 'created_at', 'roles']
        read_only_fields = ['id', 'email', 'is_active', 'created_at', 'roles']

    def get_roles(self, obj):
        return list(obj.user_roles.values_list('role__name', flat=True))


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        from organizations.models import Organization, OrganizationMembership
        from users.models import Role, UserRole
        
        # Create user
        user = User.objects.create_user(**validated_data)
        
        # Create organization for new user
        organization = Organization.objects.create(
            name=f"{user.first_name}'s Organization"
        )
        
        # Make user the owner of the organization
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrganizationMembership.Role.OWNER
        )
        
        # Assign admin role to user (gives all permissions)
        try:
            admin_role = Role.objects.get(name='admin')
            UserRole.objects.create(user=user, role=admin_role)
        except Role.DoesNotExist:
            pass  # Role not seeded yet, user can be assigned role later
        
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError('Invalid email or password')
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')

        attrs['user'] = user
        return attrs


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for token refresh."""
    refresh = serializers.CharField()


def get_tokens_for_user_with_session(user, session):
    """Generate tokens with session_id included."""
    refresh = RefreshToken.for_user(user)
    
    # Add session_id to token payload
    refresh['session_id'] = str(session.id)
    refresh.access_token['session_id'] = str(session.id)
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
