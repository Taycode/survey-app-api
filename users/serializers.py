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
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'password_confirm', 'first_name', 'last_name']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
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
