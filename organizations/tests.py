import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from organizations.models import Organization, OrganizationMembership


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    """Create a user without organization (for manual testing)."""
    return User.objects.create_user(
        email='test@example.com',
        password='TestPass123!',
        first_name='Test',
        last_name='User',
    )


@pytest.fixture
def user_with_org(db):
    """Create a user with their own organization."""
    user = User.objects.create_user(
        email='owner@example.com',
        password='TestPass123!',
        first_name='Owner',
        last_name='User',
    )
    org = Organization.objects.create(name="Owner's Organization")
    OrganizationMembership.objects.create(
        user=user,
        organization=org,
        role=OrganizationMembership.Role.OWNER
    )
    return user


@pytest.fixture
def another_user(db):
    """Create another user for member testing."""
    return User.objects.create_user(
        email='member@example.com',
        password='TestPass123!',
        first_name='Member',
        last_name='User',
    )


@pytest.fixture
def auth_client(user_with_org, api_client):
    """Authenticated API client."""
    api_client.force_authenticate(user=user_with_org)
    return api_client


@pytest.mark.django_db
class TestOrganizationRegistration:
    """Test organization creation during user registration."""
    
    def test_registration_creates_organization(self, api_client):
        """Test that registering a user automatically creates an organization."""
        url = reverse('register')
        data = {
            'email': 'newuser@example.com',
            'password': 'NewUserPass123!',
            'first_name': 'New',
            'last_name': 'User',
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Check user was created
        user = User.objects.get(email='newuser@example.com')
        assert user is not None
        
        # Check organization was created
        orgs = user.organizations.all()
        assert orgs.count() == 1
        assert orgs.first().name == "New's Organization"
        
        # Check membership with owner role
        membership = OrganizationMembership.objects.get(user=user)
        assert membership.role == OrganizationMembership.Role.OWNER


@pytest.mark.django_db
class TestOrganizationAPI:
    """Test organization CRUD operations."""
    
    def test_list_organizations(self, auth_client, user_with_org):
        """Test listing user's organizations."""
        url = reverse('organization-list')
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == "Owner's Organization"
        assert response.data['results'][0]['user_role'] == 'owner'
    
    def test_create_organization(self, auth_client):
        """Test creating a new organization."""
        url = reverse('organization-list')
        data = {'name': 'New Company'}
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Company'
        
        # Check membership was created with owner role
        org = Organization.objects.get(name='New Company')
        membership = OrganizationMembership.objects.get(organization=org)
        assert membership.role == OrganizationMembership.Role.OWNER
    
    def test_update_organization(self, auth_client, user_with_org):
        """Test updating organization name."""
        org = user_with_org.organizations.first()
        url = reverse('organization-detail', kwargs={'pk': org.id})
        data = {'name': 'Updated Name'}
        
        response = auth_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        org.refresh_from_db()
        assert org.name == 'Updated Name'
    
    def test_delete_organization(self, auth_client, user_with_org):
        """Test deleting an organization."""
        org = user_with_org.organizations.first()
        url = reverse('organization-detail', kwargs={'pk': org.id})
        
        response = auth_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Organization.objects.filter(id=org.id).exists()
    
    def test_non_member_cannot_view_organization(self, api_client, user_with_org, another_user):
        """Test that non-members cannot view organization details."""
        api_client.force_authenticate(user=another_user)
        org = user_with_org.organizations.first()
        url = reverse('organization-detail', kwargs={'pk': org.id})
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOrganizationMembers:
    """Test organization member management."""
    
    def test_list_members(self, auth_client, user_with_org):
        """Test listing organization members."""
        org = user_with_org.organizations.first()
        url = reverse('organization-members', kwargs={'pk': org.id})
        
        response = auth_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['user_email'] == user_with_org.email
        assert response.data[0]['role'] == 'owner'
    
    def test_add_member(self, auth_client, user_with_org, another_user):
        """Test adding a member to organization."""
        org = user_with_org.organizations.first()
        url = reverse('organization-add-member', kwargs={'pk': org.id})
        data = {
            'email': another_user.email,
            'role': 'member'
        }
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['user_email'] == another_user.email
        assert response.data['role'] == 'member'
        
        # Verify membership was created
        assert OrganizationMembership.objects.filter(
            user=another_user,
            organization=org,
            role=OrganizationMembership.Role.MEMBER
        ).exists()
    
    def test_add_member_already_member(self, auth_client, user_with_org, another_user):
        """Test adding a user who is already a member."""
        org = user_with_org.organizations.first()
        
        # Add user first time
        OrganizationMembership.objects.create(
            user=another_user,
            organization=org,
            role=OrganizationMembership.Role.MEMBER
        )
        
        # Try to add again
        url = reverse('organization-add-member', kwargs={'pk': org.id})
        data = {'email': another_user.email, 'role': 'member'}
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_add_nonexistent_user(self, auth_client, user_with_org):
        """Test adding a user that doesn't exist."""
        org = user_with_org.organizations.first()
        url = reverse('organization-add-member', kwargs={'pk': org.id})
        data = {'email': 'nonexistent@example.com', 'role': 'member'}
        
        response = auth_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_remove_member(self, auth_client, user_with_org, another_user):
        """Test removing a member from organization."""
        org = user_with_org.organizations.first()
        
        # Add member first
        OrganizationMembership.objects.create(
            user=another_user,
            organization=org,
            role=OrganizationMembership.Role.MEMBER
        )
        
        # Remove member
        url = reverse('organization-remove-member', kwargs={'pk': org.id, 'user_id': another_user.id})
        response = auth_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not OrganizationMembership.objects.filter(
            user=another_user,
            organization=org
        ).exists()
    
    def test_cannot_remove_last_owner(self, auth_client, user_with_org):
        """Test that the last owner cannot be removed."""
        org = user_with_org.organizations.first()
        url = reverse('organization-remove-member', kwargs={'pk': org.id, 'user_id': user_with_org.id})
        
        response = auth_client.delete(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'last owner' in response.data['detail'].lower()
    
    def test_member_cannot_add_members(self, api_client, user_with_org, another_user):
        """Test that regular members cannot add other members."""
        org = user_with_org.organizations.first()
        
        # Make another_user a member
        OrganizationMembership.objects.create(
            user=another_user,
            organization=org,
            role=OrganizationMembership.Role.MEMBER
        )
        
        # Try to add a third user as a member
        api_client.force_authenticate(user=another_user)
        third_user = User.objects.create_user(
            email='third@example.com',
            password='TestPass123!',
            first_name='Third',
            last_name='User',
        )
        
        url = reverse('organization-add-member', kwargs={'pk': org.id})
        data = {'email': third_user.email, 'role': 'member'}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestOrganizationPermissions:
    """Test organization-level permissions."""
    
    def test_owner_can_update_organization(self, auth_client, user_with_org):
        """Test that owners can update organization."""
        org = user_with_org.organizations.first()
        url = reverse('organization-detail', kwargs={'pk': org.id})
        data = {'name': 'Updated by Owner'}
        
        response = auth_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_member_cannot_update_organization(self, api_client, user_with_org, another_user):
        """Test that regular members cannot update organization."""
        org = user_with_org.organizations.first()
        
        # Make another_user a member
        OrganizationMembership.objects.create(
            user=another_user,
            organization=org,
            role=OrganizationMembership.Role.MEMBER
        )
        
        api_client.force_authenticate(user=another_user)
        url = reverse('organization-detail', kwargs={'pk': org.id})
        data = {'name': 'Updated by Member'}
        
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
