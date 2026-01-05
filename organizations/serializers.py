from rest_framework import serializers
from .models import Organization, OrganizationMembership
from users.models import User


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    """Serializer for organization membership."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    
    class Meta:
        model = OrganizationMembership
        fields = ['id', 'user_id', 'user_email', 'user_name', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']
    
    def get_user_name(self, obj):
        return obj.user.get_full_name()


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for organization list/detail."""
    member_count = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'created_at', 'updated_at', 'member_count', 'user_role']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.members.count()
    
    def get_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=request.user).first()
        return membership.role if membership else None


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating organizations."""
    
    class Meta:
        model = Organization
        fields = ['name']


class AddMemberSerializer(serializers.Serializer):
    """Serializer for adding members to organization."""
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=OrganizationMembership.Role.choices,
        default=OrganizationMembership.Role.MEMBER
    )
    
    def validate_email(self, value):
        # Check user exists
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist")
        return value
    
    def validate(self, attrs):
        # Check if user is already a member
        organization = self.context.get('organization')
        user = User.objects.get(email=attrs['email'])
        
        if organization.members.filter(id=user.id).exists():
            raise serializers.ValidationError("User is already a member of this organization")
        
        return attrs

