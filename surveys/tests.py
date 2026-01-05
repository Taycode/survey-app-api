import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from users.models import User, Role, Permission, UserRole, RolePermission
from surveys.models import Survey, Section, Field, FieldOption, ConditionalRule, FieldDependency


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='test@example.com',
        password='TestPass123!',
    )


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated API client."""
    from users.models import UserSession
    from users.serializers import get_tokens_for_user_with_session
    
    session = UserSession.objects.create(user=user)
    tokens = get_tokens_for_user_with_session(user, session)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    return api_client


@pytest.fixture
def survey(user):
    return Survey.objects.create(
        title='Test Survey',
        description='A test survey',
        created_by=user,
    )


@pytest.fixture
def section(survey):
    return Section.objects.create(
        survey=survey,
        title='Section 1',
        order=1,
    )


@pytest.fixture
def field(section):
    return Field.objects.create(
        section=section,
        label='What is your name?',
        field_type=Field.FieldType.TEXT,
        order=1,
    )


# ============ SURVEY TESTS ============

@pytest.mark.django_db
class TestSurvey:
    """Tests for survey endpoints."""

    def test_create_survey(self, auth_client):
        """Test creating a survey."""
        url = reverse('survey-list')
        response = auth_client.post(url, {
            'title': 'My Survey',
            'description': 'A description',
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'My Survey'
        assert Survey.objects.filter(title='My Survey').exists()

    def test_list_surveys(self, auth_client, survey):
        """Test listing surveys."""
        url = reverse('survey-list')
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_get_survey_detail(self, auth_client, survey, section, field):
        """Test getting survey with sections and fields embedded."""
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == survey.title
        assert len(response.data['sections']) == 1
        assert len(response.data['sections'][0]['fields']) == 1

    def test_update_survey(self, auth_client, survey):
        """Test updating a survey."""
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = auth_client.patch(url, {
            'title': 'Updated Title',
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        survey.refresh_from_db()
        assert survey.title == 'Updated Title'

    def test_delete_survey(self, auth_client, survey):
        """Test deleting a survey."""
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Survey.objects.filter(id=survey.id).exists()

    def test_publish_survey(self, auth_client, survey):
        """Test publishing a survey."""
        url = reverse('survey-publish', kwargs={'pk': survey.id})
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        survey.refresh_from_db()
        assert survey.status == Survey.Status.PUBLISHED

    def test_surveys_require_auth(self, api_client):
        """Test that surveys require authentication."""
        url = reverse('survey-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============ SECTION TESTS ============

@pytest.mark.django_db
class TestSection:
    """Tests for section endpoints."""

    def test_create_section(self, auth_client, survey):
        """Test creating a section."""
        url = reverse('survey-sections-list', kwargs={'survey_pk': str(survey.id)})
        response = auth_client.post(url, {
            'title': 'New Section',
            'order': 1,
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Section'

    def test_list_sections(self, auth_client, survey, section):
        """Test listing sections."""
        url = reverse('survey-sections-list', kwargs={'survey_pk': str(survey.id)})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Response is paginated
        assert response.data['count'] == 1

    def test_update_section(self, auth_client, survey, section):
        """Test updating a section."""
        url = reverse('survey-sections-detail', kwargs={
            'survey_pk': str(survey.id),
            'pk': str(section.id),
        })
        response = auth_client.patch(url, {
            'title': 'Updated Section',
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        section.refresh_from_db()
        assert section.title == 'Updated Section'

    def test_delete_section(self, auth_client, survey, section):
        """Test deleting a section."""
        url = reverse('survey-sections-detail', kwargs={
            'survey_pk': str(survey.id),
            'pk': str(section.id),
        })
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT


# ============ FIELD TESTS ============

@pytest.mark.django_db
class TestField:
    """Tests for field endpoints."""

    def test_create_field(self, auth_client, survey, section):
        """Test creating a field."""
        url = reverse('section-fields-list', kwargs={
            'survey_pk': str(survey.id),
            'section_pk': str(section.id),
        })
        response = auth_client.post(url, {
            'label': 'What is your email?',
            'field_type': 'text',
            'order': 1,
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['label'] == 'What is your email?'

    def test_list_fields(self, auth_client, survey, section, field):
        """Test listing fields."""
        url = reverse('section-fields-list', kwargs={
            'survey_pk': str(survey.id),
            'section_pk': str(section.id),
        })
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Response is paginated
        assert response.data['count'] == 1

    def test_update_field(self, auth_client, survey, section, field):
        """Test updating a field."""
        url = reverse('section-fields-detail', kwargs={
            'survey_pk': str(survey.id),
            'section_pk': str(section.id),
            'pk': str(field.id),
        })
        response = auth_client.patch(url, {
            'label': 'Updated Question',
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        field.refresh_from_db()
        assert field.label == 'Updated Question'


# ============ FIELD OPTIONS TESTS ============

@pytest.mark.django_db
class TestFieldOption:
    """Tests for field options endpoints."""

    def test_create_field_option(self, auth_client, survey, section):
        """Test creating a field option."""
        # First create a dropdown field
        dropdown_field = Field.objects.create(
            section=section,
            label='Country',
            field_type=Field.FieldType.DROPDOWN,
            order=1,
        )

        url = reverse('field-options-list', kwargs={
            'survey_pk': str(survey.id),
            'section_pk': str(section.id),
            'field_pk': str(dropdown_field.id),
        })
        response = auth_client.post(url, {
            'label': 'USA',
            'value': 'usa',
            'order': 1,
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['label'] == 'USA'


# ============ CONDITIONAL RULES TESTS ============

@pytest.mark.django_db
class TestConditionalRule:
    """Tests for conditional rule endpoints."""

    def test_create_conditional_rule(self, auth_client, survey, section, field):
        """Test creating a conditional rule."""
        # Create a target section
        target_section = Section.objects.create(
            survey=survey,
            title='Conditional Section',
            order=2,
        )

        url = reverse('survey-rules-list', kwargs={'survey_pk': str(survey.id)})
        response = auth_client.post(url, {
            'target_type': 'section',
            'target_id': str(target_section.id),
            'source_field': str(field.id),
            'operator': 'equals',
            'value': 'yes',
            'action': 'show',
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED

    def test_list_conditional_rules(self, auth_client, survey, section, field):
        """Test listing conditional rules."""
        url = reverse('survey-rules-list', kwargs={'survey_pk': str(survey.id)})
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK


# ============ FIELD DEPENDENCIES TESTS ============

@pytest.mark.django_db
class TestFieldDependency:
    """Tests for field dependency endpoints."""

    def test_create_field_dependency(self, auth_client, survey, section):
        """Test creating a field dependency."""
        # Create source field (country)
        country_field = Field.objects.create(
            section=section,
            label='Country',
            field_type=Field.FieldType.DROPDOWN,
            order=1,
        )
        # Create dependent field (city)
        city_field = Field.objects.create(
            section=section,
            label='City',
            field_type=Field.FieldType.DROPDOWN,
            order=2,
        )

        url = reverse('survey-dependencies-list', kwargs={'survey_pk': str(survey.id)})
        response = auth_client.post(url, {
            'source_field': str(country_field.id),
            'dependent_field': str(city_field.id),
            'source_value': 'usa',
            'dependent_options': [
                {'label': 'New York', 'value': 'ny'},
                {'label': 'Los Angeles', 'value': 'la'},
            ],
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        # Verify dependent field is marked
        city_field.refresh_from_db()
        assert city_field.has_dependencies is True


# ============ RBAC TESTS ============

@pytest.mark.django_db
class TestRBAC:
    """Tests for Role-Based Access Control."""

    @pytest.fixture
    def admin_role(self, db):
        """Create admin role with all permissions."""
        role = Role.objects.create(name='admin', description='Admin role')
        permissions = Permission.objects.all()
        for perm in permissions:
            RolePermission.objects.create(role=role, permission=perm)
        return role

    @pytest.fixture
    def manager_role(self, db):
        """Create manager role with survey management permissions."""
        role = Role.objects.create(name='manager', description='Manager role')
        manager_perms = [
            'create_survey', 'edit_survey', 'delete_survey', 'publish_survey',
            'view_responses', 'export_responses', 'view_analytics'
        ]
        for codename in manager_perms:
            perm = Permission.objects.filter(codename=codename).first()
            if perm:
                RolePermission.objects.create(role=role, permission=perm)
        return role

    @pytest.fixture
    def viewer_role(self, db):
        """Create viewer role with view_responses permission only."""
        role = Role.objects.create(name='viewer', description='Viewer role')
        perm = Permission.objects.filter(codename='view_responses').first()
        if perm:
            RolePermission.objects.create(role=role, permission=perm)
        return role

    @pytest.fixture
    def admin_user(self, db, admin_role):
        """Create user with admin role."""
        user = User.objects.create_user(email='admin@example.com', password='TestPass123!')
        UserRole.objects.create(user=user, role=admin_role)
        return user

    @pytest.fixture
    def manager_user(self, db, manager_role):
        """Create user with manager role."""
        user = User.objects.create_user(email='manager@example.com', password='TestPass123!')
        UserRole.objects.create(user=user, role=manager_role)
        return user

    @pytest.fixture
    def viewer_user(self, db, viewer_role):
        """Create user with viewer role."""
        user = User.objects.create_user(email='viewer@example.com', password='TestPass123!')
        UserRole.objects.create(user=user, role=viewer_role)
        return user

    @pytest.fixture
    def regular_user(self, db):
        """Create user without any roles."""
        return User.objects.create_user(email='regular@example.com', password='TestPass123!')

    @pytest.fixture
    def admin_client(self, api_client, admin_user):
        """Authenticated API client for admin user."""
        from users.models import UserSession
        from users.serializers import get_tokens_for_user_with_session
        
        session = UserSession.objects.create(user=admin_user)
        tokens = get_tokens_for_user_with_session(admin_user, session)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        return api_client

    @pytest.fixture
    def manager_client(self, api_client, manager_user):
        """Authenticated API client for manager user."""
        from users.models import UserSession
        from users.serializers import get_tokens_for_user_with_session
        
        session = UserSession.objects.create(user=manager_user)
        tokens = get_tokens_for_user_with_session(manager_user, session)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        return api_client

    @pytest.fixture
    def viewer_client(self, api_client, viewer_user):
        """Authenticated API client for viewer user."""
        from users.models import UserSession
        from users.serializers import get_tokens_for_user_with_session
        
        session = UserSession.objects.create(user=viewer_user)
        tokens = get_tokens_for_user_with_session(viewer_user, session)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        return api_client

    @pytest.fixture
    def regular_client(self, api_client, regular_user):
        """Authenticated API client for regular user."""
        from users.models import UserSession
        from users.serializers import get_tokens_for_user_with_session
        
        session = UserSession.objects.create(user=regular_user)
        tokens = get_tokens_for_user_with_session(regular_user, session)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        return api_client

    def test_admin_can_create_survey(self, admin_client):
        """Test admin can create surveys."""
        url = reverse('survey-list')
        response = admin_client.post(url, {
            'title': 'Admin Survey',
            'description': 'A survey',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_manager_can_create_survey(self, manager_client):
        """Test manager can create surveys."""
        url = reverse('survey-list')
        response = manager_client.post(url, {
            'title': 'Manager Survey',
            'description': 'A survey',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_viewer_cannot_create_survey(self, viewer_client):
        """Test viewer cannot create surveys."""
        url = reverse('survey-list')
        response = viewer_client.post(url, {
            'title': 'Viewer Survey',
            'description': 'A survey',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_cannot_create_survey(self, regular_client):
        """Test regular user without permissions cannot create surveys."""
        url = reverse('survey-list')
        response = regular_client.post(url, {
            'title': 'Regular Survey',
            'description': 'A survey',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_can_edit_own_survey(self, manager_client, manager_user):
        """Test manager can edit surveys they created."""
        survey = Survey.objects.create(
            title='Manager Survey',
            description='A survey',
            created_by=manager_user,
        )
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = manager_client.patch(url, {
            'title': 'Updated Title',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_edit_other_survey(self, manager_client, regular_user):
        """Test manager can edit surveys created by others (has edit_survey permission)."""
        survey = Survey.objects.create(
            title='Other Survey',
            description='A survey',
            created_by=regular_user,
        )
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = manager_client.patch(url, {
            'title': 'Updated Title',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_viewer_cannot_edit_survey(self, viewer_client, regular_user):
        """Test viewer cannot edit surveys."""
        survey = Survey.objects.create(
            title='Other Survey',
            description='A survey',
            created_by=regular_user,
        )
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = viewer_client.patch(url, {
            'title': 'Updated Title',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_viewer_can_view_all_surveys(self, viewer_client, regular_user):
        """Test viewer can view all surveys (has view_responses permission)."""
        # Create survey by another user
        Survey.objects.create(
            title='Other Survey',
            description='A survey',
            created_by=regular_user,
        )
        url = reverse('survey-list')
        response = viewer_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] >= 1

    def test_regular_user_sees_only_own_surveys(self, regular_client, regular_user, manager_user):
        """Test regular user without permissions sees only their own surveys."""
        # Create survey by regular user
        Survey.objects.create(
            title='My Survey',
            description='A survey',
            created_by=regular_user,
        )
        # Create survey by manager
        Survey.objects.create(
            title='Manager Survey',
            description='A survey',
            created_by=manager_user,
        )
        url = reverse('survey-list')
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Should only see their own survey
        assert response.data['count'] == 1
        assert response.data['results'][0]['title'] == 'My Survey'

    def test_manager_can_publish_survey(self, manager_client, manager_user):
        """Test manager can publish surveys."""
        survey = Survey.objects.create(
            title='Manager Survey',
            description='A survey',
            created_by=manager_user,
        )
        url = reverse('survey-publish', kwargs={'pk': survey.id})
        response = manager_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        survey.refresh_from_db()
        assert survey.status == Survey.Status.PUBLISHED

    def test_viewer_cannot_publish_survey(self, viewer_client, regular_user):
        """Test viewer cannot publish surveys."""
        survey = Survey.objects.create(
            title='Other Survey',
            description='A survey',
            created_by=regular_user,
        )
        url = reverse('survey-publish', kwargs={'pk': survey.id})
        response = viewer_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_access_survey_without_permission(self, regular_client, regular_user):
        """Test owner can access their survey even without view_responses permission."""
        survey = Survey.objects.create(
            title='My Survey',
            description='A survey',
            created_by=regular_user,
        )
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = regular_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_owner_can_edit_survey_without_permission(self, regular_client, regular_user):
        """Test owner can edit their survey even without edit_survey permission."""
        survey = Survey.objects.create(
            title='My Survey',
            description='A survey',
            created_by=regular_user,
        )
        url = reverse('survey-detail', kwargs={'pk': survey.id})
        response = regular_client.patch(url, {
            'title': 'Updated Title',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_user_has_permission_method(self, manager_user, viewer_user, regular_user):
        """Test User.has_permission() method."""
        assert manager_user.has_permission('create_survey') is True
        assert manager_user.has_permission('edit_survey') is True
        assert viewer_user.has_permission('view_responses') is True
        assert viewer_user.has_permission('create_survey') is False
        assert regular_user.has_permission('create_survey') is False

    def test_user_has_role_method(self, manager_user, viewer_user, regular_user, manager_role, viewer_role):
        """Test User.has_role() method."""
        assert manager_user.has_role('manager') is True
        assert viewer_user.has_role('viewer') is True
        assert regular_user.has_role('manager') is False
        assert regular_user.has_role('viewer') is False
