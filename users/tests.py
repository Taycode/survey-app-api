import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from users.models import User, UserSession


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_data():
    return {
        'email': 'test@example.com',
        'password': 'TestPass123!',
        'first_name': 'Test',
        'last_name': 'User',
    }


@pytest.fixture
def created_user(db):
    return User.objects.create_user(
        email='existing@example.com',
        password='ExistingPass123!',
        first_name='Existing',
        last_name='User',
    )


@pytest.mark.django_db
class TestRegistration:
    """Tests for user registration endpoint."""

    def test_register_success(self, api_client, user_data):
        """Test successful user registration."""
        url = reverse('register')
        response = api_client.post(url, user_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'user' in response.data
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert response.data['user']['email'] == user_data['email']

    def test_register_creates_session(self, api_client, user_data):
        """Test that registration creates a user session."""
        url = reverse('register')
        response = api_client.post(url, user_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email=user_data['email'])
        assert UserSession.objects.filter(user=user, is_active=True).exists()
    
    def test_register_creates_organization(self, api_client, user_data):
        """Test that registration automatically creates an organization for the user."""
        from organizations.models import Organization, OrganizationMembership
        
        url = reverse('register')
        response = api_client.post(url, user_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email=user_data['email'])
        
        # Check organization was created
        orgs = user.organizations.all()
        assert orgs.count() == 1
        assert orgs.first().name == f"{user.first_name}'s Organization"
        
        # Check membership with owner role
        membership = OrganizationMembership.objects.get(user=user)
        assert membership.role == OrganizationMembership.Role.OWNER

    def test_register_duplicate_email(self, api_client, user_data, created_user):
        """Test registration fails with duplicate email."""
        user_data['email'] = created_user.email
        url = reverse('register')
        response = api_client.post(url, user_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogin:
    """Tests for user login endpoint."""

    def test_login_success(self, api_client, created_user):
        """Test successful login."""
        url = reverse('login')
        response = api_client.post(url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'user' in response.data
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_creates_session(self, api_client, created_user):
        """Test that login creates a user session."""
        url = reverse('login')
        response = api_client.post(url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert UserSession.objects.filter(user=created_user, is_active=True).exists()

    def test_login_wrong_password(self, api_client, created_user):
        """Test login fails with wrong password."""
        url = reverse('login')
        response = api_client.post(url, {
            'email': 'existing@example.com',
            'password': 'WrongPassword!',
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogout:
    """Tests for user logout endpoint."""

    def test_logout_success(self, api_client, created_user):
        """Test successful logout deactivates session."""
        # Login first
        login_url = reverse('login')
        login_response = api_client.post(login_url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')
        access_token = login_response.data['access']

        # Logout
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_url = reverse('logout')
        response = api_client.post(logout_url)

        assert response.status_code == status.HTTP_200_OK
        
        # Verify session is deactivated
        session = UserSession.objects.filter(user=created_user).latest('created_at')
        assert session.is_active is False

    def test_logout_token_invalid_after_logout(self, api_client, created_user):
        """Test that token becomes invalid after logout."""
        # Login first
        login_url = reverse('login')
        login_response = api_client.post(login_url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')
        access_token = login_response.data['access']

        # Logout
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_url = reverse('logout')
        api_client.post(logout_url)

        # Try to access protected endpoint
        profile_url = reverse('profile')
        response = api_client.get(profile_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenRefresh:
    """Tests for token refresh endpoint."""

    def test_refresh_token_success(self, api_client, created_user):
        """Test successful token refresh."""
        # Login first
        login_url = reverse('login')
        login_response = api_client.post(login_url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')
        refresh_token = login_response.data['refresh']

        # Refresh token
        refresh_url = reverse('token-refresh')
        response = api_client.post(refresh_url, {
            'refresh': refresh_token,
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_refresh_token_fails_after_logout(self, api_client, created_user):
        """Test that refresh token fails after logout."""
        # Login first
        login_url = reverse('login')
        login_response = api_client.post(login_url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']

        # Logout
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_url = reverse('logout')
        api_client.post(logout_url)

        # Try to refresh
        api_client.credentials()
        refresh_url = reverse('token-refresh')
        response = api_client.post(refresh_url, {
            'refresh': refresh_token,
        }, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestProfile:
    """Tests for user profile endpoint."""

    def test_get_profile(self, api_client, created_user):
        """Test getting user profile."""
        # Login first
        login_url = reverse('login')
        login_response = api_client.post(login_url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')
        access_token = login_response.data['access']

        # Get profile
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('profile')
        response = api_client.get(profile_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == created_user.email

    def test_update_profile(self, api_client, created_user):
        """Test updating user profile."""
        # Login first
        login_url = reverse('login')
        login_response = api_client.post(login_url, {
            'email': 'existing@example.com',
            'password': 'ExistingPass123!',
        }, format='json')
        access_token = login_response.data['access']

        # Update profile
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('profile')
        response = api_client.patch(profile_url, {
            'first_name': 'Updated',
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'Updated'

    def test_profile_requires_auth(self, api_client):
        """Test that profile endpoint requires authentication."""
        profile_url = reverse('profile')
        response = api_client.get(profile_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
