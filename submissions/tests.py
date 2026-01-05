import pytest
from unittest.mock import patch, MagicMock, mock_open
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from surveys.models import Survey, Section, Field, FieldOption, ConditionalRule
from submissions.models import SurveyResponse, FieldAnswer


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    from users.models import User
    return User.objects.create_user(email='test@example.com', password='pass')


@pytest.fixture
def survey(user):
    return Survey.objects.create(
        title='Customer Feedback',
        status=Survey.Status.PUBLISHED,
        created_by=user
    )


@pytest.fixture
def section(survey):
    return Section.objects.create(
        survey=survey,
        title='Section 1',
        order=1
    )


@pytest.fixture
def field(section):
    return Field.objects.create(
        section=section,
        label='Name',
        field_type=Field.FieldType.TEXT,
        order=1
    )


@pytest.mark.django_db
class TestSubmissionFlow:
    """Tests for the full survey submission flow."""

    def test_full_submission_flow(self, api_client, survey, section, field):
        # 1. Start Survey
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        
        assert response.status_code == status.HTTP_201_CREATED
        session_token = response.data['session_token']
        assert session_token is not None
        
        # Verify DB record
        assert SurveyResponse.objects.filter(session_token=session_token).exists()

        # 2. Get Current Section
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        current_section_url = reverse('submissions-get-current-section')
        response = api_client.get(current_section_url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'current_section' in response.data
        assert 'is_complete' in response.data
        assert 'progress' in response.data
        assert response.data['current_section'] is not None
        assert response.data['is_complete'] is False

        # 3. Submit Section
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': section.id,
            'answers': [
                {'field_id': field.id, 'value': 'John Doe'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'success'
        assert 'is_complete' in response.data
        assert 'progress' in response.data
        assert 'message' in response.data
        
        # Verify Answer Saved
        assert FieldAnswer.objects.filter(
            response__session_token=session_token,
            field=field,
            value='John Doe'
        ).exists()

        # 4. Finish Survey
        finish_url = reverse('submissions-finish-survey')
        response = api_client.post(finish_url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'completed_at' in response.data
        
        # Verify Status
        survey_response = SurveyResponse.objects.get(session_token=session_token)
        assert survey_response.status == SurveyResponse.Status.COMPLETED

    def test_start_survey_invalid_id(self, api_client):
        url = reverse('survey-submissions-start', kwargs={'survey_pk': '00000000-0000-0000-0000-000000000000'})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_submit_without_token(self, api_client):
        url = reverse('submissions-submit-section')
        response = api_client.post(url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_submit_invalid_token(self, api_client):
        url = reverse('submissions-submit-section')
        api_client.credentials(HTTP_X_SESSION_TOKEN='invalid-token')
        # The view should return 400 for validation error since section_id is missing
        # OR 404 if it checks token first. 
        # But let's send valid data to ensure it fails on token lookup
        response = api_client.post(url, {
            'section_id': '00000000-0000-0000-0000-000000000000', 
            'answers': []
        })
        # My view implementation checks token first, so it should be 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_validation_number_field(self, api_client, survey, section):
        # Create a number field
        num_field = Field.objects.create(
            section=section,
            label='Age',
            field_type=Field.FieldType.NUMBER,
            order=2
        )
        
        # Start session
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Submit invalid number
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': section.id,
            'answers': [
                {'field_id': num_field.id, 'value': 'abc'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert str(num_field.id) in response.data['errors']

    def test_get_current_section(self, api_client, survey, section, field):
        """Test getting current section endpoint."""
        # Start survey
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Get current section
        current_section_url = reverse('submissions-get-current-section')
        response = api_client.get(current_section_url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'current_section' in response.data
        assert 'is_complete' in response.data
        assert 'progress' in response.data
        assert response.data['current_section'] is not None
        assert response.data['is_complete'] is False
        assert response.data['current_section']['section_id'] == section.id
        assert len(response.data['current_section']['fields']) == 1
        assert response.data['current_section']['fields'][0]['field_id'] == field.id
        
        # Submit section
        submit_url = reverse('submissions-submit-section')
        api_client.post(submit_url, {
            'section_id': section.id,
            'answers': [{'field_id': field.id, 'value': 'Test Answer'}]
        }, format='json')
        
        # Get current section again (should be complete)
        response = api_client.get(current_section_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_complete'] is True
        assert response.data['current_section'] is None
        assert response.data['progress']['sections_completed'] == 1
        assert response.data['progress']['total_sections'] == 1
        assert response.data['progress']['percentage'] == 100.0

    def test_get_section_navigation(self, api_client, survey, section, field):
        """Test getting specific section for navigation with pre-filled answers."""
        # Start survey and submit section
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Submit section with answer
        submit_url = reverse('submissions-submit-section')
        api_client.post(submit_url, {
            'section_id': section.id,
            'answers': [{'field_id': field.id, 'value': 'My Answer'}]
        }, format='json')
        
        # Get section for navigation
        get_section_url = reverse('submissions-get-section', kwargs={'section_id': section.id})
        response = api_client.get(get_section_url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'section' in response.data
        assert 'is_editable' in response.data
        assert 'progress' in response.data
        assert response.data['section']['section_id'] == section.id
        assert len(response.data['section']['fields']) == 1
        assert response.data['section']['fields'][0]['field_id'] == field.id
        assert response.data['section']['fields'][0]['current_value'] == 'My Answer'
        assert response.data['is_editable'] is True

    def test_get_section_without_token(self, api_client, survey, section):
        """Test getting section without session token."""
        get_section_url = reverse('submissions-get-section', kwargs={'section_id': section.id})
        response = api_client.get(get_section_url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_current_section_without_token(self, api_client):
        """Test getting current section without session token."""
        current_section_url = reverse('submissions-get-current-section')
        response = api_client.get(current_section_url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_submit_section_returns_progress(self, api_client, survey, section, field):
        """Test that submit_section returns progress information."""
        # Start survey
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Submit section
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': section.id,
            'answers': [{'field_id': field.id, 'value': 'Test'}]
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'success'
        assert 'message' in response.data
        assert 'is_complete' in response.data
        assert 'progress' in response.data
        assert response.data['is_complete'] is True  # Only one section
        assert response.data['progress']['sections_completed'] == 1
        assert response.data['progress']['total_sections'] == 1
        assert response.data['progress']['sections_remaining'] == 0
        assert response.data['progress']['percentage'] == 100.0


@pytest.mark.django_db
class TestConditionalLogic:
    """Tests for conditional logic validation."""
    
    def test_hidden_section_cannot_be_submitted(self, api_client, survey, user):
        """Test that a hidden section cannot be submitted."""
        # Create Section 1 with a question
        section1 = Section.objects.create(survey=survey, title='Section 1', order=1)
        field1 = Field.objects.create(
            section=section1,
            label='Are you a customer?',
            field_type=Field.FieldType.RADIO,
            order=1
        )
        # Create options for radio field
        FieldOption.objects.create(field=field1, label='Yes', value='yes', order=1)
        FieldOption.objects.create(field=field1, label='No', value='no', order=2)
        
        # Create Section 2 (should be hidden if field1 = 'no')
        section2 = Section.objects.create(survey=survey, title='Section 2', order=2)
        field2 = Field.objects.create(
            section=section2,
            label='Customer details',
            field_type=Field.FieldType.TEXT,
            order=1
        )
        
        # Create conditional rule: Hide Section 2 if field1 = 'no'
        ConditionalRule.objects.create(
            source_field=field1,
            target_type=ConditionalRule.TargetType.SECTION,
            target_id=section2.id,
            operator=ConditionalRule.Operator.EQUALS,
            value='no',
            action=ConditionalRule.Action.HIDE
        )
        
        # Start survey
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Submit Section 1 with answer 'no'
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': section1.id,
            'answers': [
                {'field_id': field1.id, 'value': 'no'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Try to submit Section 2 (should fail - it's hidden)
        response = api_client.post(submit_url, {
            'section_id': section2.id,
            'answers': [
                {'field_id': field2.id, 'value': 'Some details'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert 'section' in response.data['errors'] or str(section2.id) in response.data['errors']
    
    def test_visible_section_can_be_submitted(self, api_client, survey, user):
        """Test that a visible section can be submitted."""
        # Create Section 1 with a question
        section1 = Section.objects.create(survey=survey, title='Section 1', order=1)
        field1 = Field.objects.create(
            section=section1,
            label='Are you a customer?',
            field_type=Field.FieldType.RADIO,
            order=1
        )
        # Create options for radio field
        FieldOption.objects.create(field=field1, label='Yes', value='yes', order=1)
        FieldOption.objects.create(field=field1, label='No', value='no', order=2)
        
        # Create Section 2 (should be visible if field1 = 'yes')
        section2 = Section.objects.create(survey=survey, title='Section 2', order=2)
        field2 = Field.objects.create(
            section=section2,
            label='Customer details',
            field_type=Field.FieldType.TEXT,
            order=1
        )
        
        # Create conditional rule: Show Section 2 if field1 = 'yes'
        ConditionalRule.objects.create(
            source_field=field1,
            target_type=ConditionalRule.TargetType.SECTION,
            target_id=section2.id,
            operator=ConditionalRule.Operator.EQUALS,
            value='yes',
            action=ConditionalRule.Action.SHOW
        )
        
        # Start survey
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Submit Section 1 with answer 'yes'
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': section1.id,
            'answers': [
                {'field_id': field1.id, 'value': 'yes'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Submit Section 2 (should succeed - it's visible)
        response = api_client.post(submit_url, {
            'section_id': section2.id,
            'answers': [
                {'field_id': field2.id, 'value': 'Some details'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'success'
        assert 'is_complete' in response.data
        assert 'progress' in response.data


# ============ ENCRYPTION TESTS ============

@pytest.mark.django_db
class TestFieldEncryption:
    """Tests for field encryption functionality."""

    @pytest.fixture
    def encryption_key(self, monkeypatch):
        """Set up encryption key for tests."""
        from submissions.encryption import EncryptionService
        key = EncryptionService.generate_key()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', key)
        # Reload settings
        from django.conf import settings
        settings.FIELD_ENCRYPTION_KEY = key
        return key

    @pytest.fixture
    def sensitive_field(self, section):
        """Create a sensitive field."""
        return Field.objects.create(
            section=section,
            label='SSN',
            field_type=Field.FieldType.TEXT,
            is_sensitive=True,
            order=1
        )

    @pytest.fixture
    def normal_field(self, section):
        """Create a normal (non-sensitive) field."""
        return Field.objects.create(
            section=section,
            label='Name',
            field_type=Field.FieldType.TEXT,
            is_sensitive=False,
            order=2
        )

    def test_sensitive_field_encrypted_on_save(self, encryption_key, survey, sensitive_field, user):
        """Test that sensitive fields are encrypted when saved."""
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        answer = FieldAnswer(
            response=response,
            field=sensitive_field,
            value='123-45-6789'
        )
        answer.save()
        
        # Value should be encrypted
        assert answer.encrypted_value is not None
        assert answer.value is None
        assert answer.encrypted_value != b'123-45-6789'  # Should be encrypted
        
        # Decrypted value should match original
        assert answer.decrypted_value == '123-45-6789'

    def test_non_sensitive_field_not_encrypted(self, encryption_key, survey, normal_field, user):
        """Test that normal fields are not encrypted."""
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        answer = FieldAnswer(
            response=response,
            field=normal_field,
            value='John Doe'
        )
        answer.save()
        
        # Value should remain plaintext
        assert answer.value == 'John Doe'
        assert answer.encrypted_value is None

    def test_decrypt_sensitive_field(self, encryption_key, survey, sensitive_field, user):
        """Test decryption of sensitive fields."""
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        answer = FieldAnswer.objects.create(
            response=response,
            field=sensitive_field,
            value='secret-data'
        )
        
        # Reload from DB to ensure encryption happened
        answer.refresh_from_db()
        
        # Should be able to decrypt
        assert answer.decrypted_value == 'secret-data'
        assert answer.value is None  # Plaintext cleared

    def test_encryption_key_required(self, monkeypatch, survey, sensitive_field, user):
        """Test that encryption fails without key."""
        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        from django.conf import settings
        settings.FIELD_ENCRYPTION_KEY = ''
        
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        answer = FieldAnswer(
            response=response,
            field=sensitive_field,
            value='test'
        )
        
        with pytest.raises(Exception):  # Should raise ImproperlyConfigured or EncryptionError
            answer.save()

    def test_encryption_in_submission_flow(self, encryption_key, api_client, survey, section, sensitive_field):
        """Test encryption works in full submission flow."""
        # Start survey
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        start_resp = api_client.post(start_url)
        session_token = start_resp.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)
        
        # Submit section with sensitive field
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': section.id,
            'answers': [
                {'field_id': sensitive_field.id, 'value': '123-45-6789'}
            ]
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that answer was encrypted
        survey_response = SurveyResponse.objects.get(session_token=session_token)
        answer = FieldAnswer.objects.get(response=survey_response, field=sensitive_field)
        
        assert answer.encrypted_value is not None
        assert answer.value is None
        assert answer.decrypted_value == '123-45-6789'

    def test_conditional_logic_with_encrypted_fields(self, encryption_key, survey, section, sensitive_field, user):
        """Test that conditional logic works with encrypted fields."""
        # Create a conditional rule based on sensitive field
        target_section = Section.objects.create(
            survey=survey,
            title='Target Section',
            order=2
        )
        
        ConditionalRule.objects.create(
            source_field=sensitive_field,
            target_type='section',
            target_id=target_section.id,
            operator='equals',
            value='123-45-6789',
            action='show'
        )
        
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        # Save encrypted answer
        FieldAnswer.objects.create(
            response=response,
            field=sensitive_field,
            value='123-45-6789'
        )
        
        # Conditional logic should work with decrypted value
        from submissions.services import ConditionalLogicService
        service = ConditionalLogicService()
        visible_sections = service.get_visible_sections(response)
        
        # Target section should be visible
        assert str(target_section.id) in visible_sections

    def test_update_sensitive_field(self, encryption_key, survey, sensitive_field, user):
        """Test updating an encrypted field."""
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        # Create initial answer
        answer = FieldAnswer.objects.create(
            response=response,
            field=sensitive_field,
            value='old-value'
        )
        answer.refresh_from_db()
        old_encrypted = answer.encrypted_value
        
        # Update answer
        answer.value = 'new-value'
        answer.save()
        answer.refresh_from_db()
        
        # Should have new encrypted value
        assert answer.encrypted_value != old_encrypted
        assert answer.decrypted_value == 'new-value'


@pytest.mark.django_db
class TestResponseViewing:
    """Tests for response viewing endpoints with RBAC."""
    
    @pytest.fixture
    def manager_user(self, db):
        """Create a user with manager role."""
        from users.models import User, Role, UserRole
        
        user = User.objects.create_user(email='manager@example.com', password='pass')
        manager_role = Role.objects.get(name='manager')
        UserRole.objects.create(user=user, role=manager_role)
        return user
    
    @pytest.fixture
    def viewer_user(self, db):
        """Create a user with viewer role."""
        from users.models import User, Role, UserRole
        
        user = User.objects.create_user(email='viewer@example.com', password='pass')
        viewer_role = Role.objects.get(name='viewer')
        UserRole.objects.create(user=user, role=viewer_role)
        return user
    
    @pytest.fixture
    def regular_user(self, db):
        """Create a regular user without special permissions."""
        from users.models import User
        return User.objects.create_user(email='regular@example.com', password='pass')
    
    @pytest.fixture
    def survey_response(self, survey, section, field):
        """Create a survey response with answers."""
        response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.COMPLETED
        )
        FieldAnswer.objects.create(
            response=response,
            field=field,
            value='Test Answer'
        )
        return response
    
    def test_manager_can_list_responses(self, api_client, manager_user, survey, survey_response):
        """Manager can view all responses."""
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(survey_response.id)
    
    def test_viewer_can_list_responses(self, api_client, viewer_user, survey, survey_response):
        """Viewer can view all responses."""
        api_client.force_authenticate(user=viewer_user)
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
    
    def test_regular_user_cannot_view_responses(self, api_client, regular_user, survey, survey_response):
        """Regular user without permission cannot view responses."""
        api_client.force_authenticate(user=regular_user)
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_responses_pagination(self, api_client, manager_user, survey):
        """Test pagination for list responses."""
        # Create multiple responses
        for i in range(25):
            SurveyResponse.objects.create(survey=survey, status=SurveyResponse.Status.COMPLETED)
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 20  # Default page size
        assert 'next' in response.data
    
    def test_list_responses_filtering(self, api_client, manager_user, survey):
        """Test filtering responses by status."""
        completed_response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.COMPLETED
        )
        in_progress_response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        
        # Filter by completed
        response = api_client.get(url, {'status': 'completed'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(completed_response.id)
        
        # Filter by in_progress
        response = api_client.get(url, {'status': 'in_progress'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(in_progress_response.id)
    
    def test_retrieve_response_with_decryption(self, api_client, manager_user, survey, section):
        """Test retrieving response with decrypted sensitive fields."""
        from surveys.models import Field
        
        # Create sensitive field
        sensitive_field = Field.objects.create(
            section=section,
            label='SSN',
            field_type=Field.FieldType.TEXT,
            is_sensitive=True,
            order=1
        )
        
        # Create response with sensitive answer
        response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.COMPLETED
        )
        FieldAnswer.objects.create(
            response=response,
            field=sensitive_field,
            value='123-45-6789'
        )
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('responses-detail', kwargs={'pk': response.id})
        response_data = api_client.get(url)
        
        assert response_data.status_code == status.HTTP_200_OK
        assert len(response_data.data['answers']) == 1
        assert response_data.data['answers'][0]['value'] == '123-45-6789'
        assert response_data.data['answers'][0]['is_sensitive'] is True
    
    def test_export_csv(self, api_client, manager_user, survey, section, field):
        """Test CSV export functionality."""
        # Create response
        survey_response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.COMPLETED
        )
        FieldAnswer.objects.create(
            response=survey_response,
            field=field,
            value='Test Answer'
        )
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.get(url, {'format': 'csv'})
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/csv'
        assert 'attachment' in response['Content-Disposition']
        
        # Check CSV content
        content = response.content.decode('utf-8')
        assert 'Response ID' in content
        assert 'Test Answer' in content
    
    def test_export_json(self, api_client, manager_user, survey, section, field):
        """Test JSON export functionality."""
        # Create response
        survey_response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.COMPLETED
        )
        FieldAnswer.objects.create(
            response=survey_response,
            field=field,
            value='Test Answer'
        )
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.get(url, {'format': 'json'})
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/json'
        
        # Parse JSON
        import json
        data = json.loads(response.content.decode('utf-8'))
        assert 'export_date' in data
        assert 'total_count' in data
        assert len(data['responses']) == 1
    
    def test_manager_can_export(self, api_client, manager_user, survey, survey_response):
        """Manager can export responses."""
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_viewer_cannot_export(self, api_client, viewer_user, survey, survey_response):
        """Viewer cannot export responses (no permission)."""
        api_client.force_authenticate(user=viewer_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_export_includes_decrypted_fields(self, api_client, manager_user, survey, section):
        """Test that exported CSV includes decrypted sensitive fields."""
        from surveys.models import Field
        
        # Create sensitive field
        sensitive_field = Field.objects.create(
            section=section,
            label='SSN',
            field_type=Field.FieldType.TEXT,
            is_sensitive=True,
            order=1
        )
        
        # Create response
        survey_response = SurveyResponse.objects.create(
            survey=survey,
            status=SurveyResponse.Status.COMPLETED
        )
        FieldAnswer.objects.create(
            response=survey_response,
            field=sensitive_field,
            value='123-45-6789'
        )
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.get(url, {'format': 'csv'})
        
        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode('utf-8')
        assert '123-45-6789' in content
    
    def test_list_responses_requires_authentication(self, api_client, survey):
        """Test that list responses requires authentication."""
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_retrieve_response_requires_authentication(self, api_client, survey_response):
        """Test that retrieve response requires authentication."""
        url = reverse('responses-detail', kwargs={'pk': survey_response.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAsyncExport:
    """Tests for async export functionality."""
    
    @pytest.fixture
    def manager_user(self, db):
        """Create a user with manager role."""
        from users.models import User, Role, UserRole
        
        user = User.objects.create_user(email='manager@example.com', password='pass')
        manager_role = Role.objects.get(name='manager')
        UserRole.objects.create(user=user, role=manager_role)
        return user
    
    @pytest.fixture
    def large_survey(self, manager_user):
        """Create a survey with many responses."""
        from surveys.models import Survey, Section, Field
        
        survey = Survey.objects.create(
            title='Large Survey',
            status=Survey.Status.PUBLISHED,
            created_by=manager_user
        )
        section = Section.objects.create(survey=survey, title='Section 1', order=1)
        field = Field.objects.create(
            section=section,
            label='Name',
            field_type=Field.FieldType.TEXT,
            order=1
        )
        
        # Create 1500 responses to trigger async mode
        for i in range(1500):
            response = SurveyResponse.objects.create(
                survey=survey,
                status=SurveyResponse.Status.COMPLETED
            )
            FieldAnswer.objects.create(
                response=response,
                field=field,
                value=f'Response {i}'
            )
        
        return survey
    
    def test_export_always_async(self, api_client, manager_user, survey, section, field):
        """All exports are async and return confirmation."""
        # Create a few responses
        for i in range(5):
            response = SurveyResponse.objects.create(
                survey=survey,
                status=SurveyResponse.Status.COMPLETED
            )
            FieldAnswer.objects.create(
                response=response,
                field=field,
                value=f'Answer {i}'
            )
        
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        
        with patch('submissions.views.export_responses_async.delay') as mock_task:
            response = api_client.get(url, {'format': 'csv'})
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert 'email' in response.data
        assert 'message' in response.data
        assert mock_task.called
    
    def test_large_export_async(self, api_client, manager_user, large_survey):
        """Large dataset triggers async task and returns email confirmation."""
        api_client.force_authenticate(user=manager_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': large_survey.id})
        
        with patch('submissions.views.export_responses_async.delay') as mock_task:
            response = api_client.get(url, {'format': 'csv'})
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert 'message' in response.data
        assert 'email' in response.data
        assert response.data['email'] == manager_user.email
        assert mock_task.called
    
    def test_async_export_permission(self, api_client, survey):
        """Regular user without permission cannot trigger async export."""
        from users.models import User
        
        regular_user = User.objects.create_user(email='regular@example.com', password='pass')
        api_client.force_authenticate(user=regular_user)
        url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.get(url, {'async': 'true'})
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_async_export_sends_email(self, api_client, manager_user, large_survey):
        """Test that async export task sends email when completed."""
        from django.core import mail
        from submissions.tasks import export_responses_async
        
        # Clear mail outbox
        mail.outbox = []
        
        # Execute task synchronously for testing
        export_responses_async(
            survey_id=str(large_survey.id),
            user_id=str(manager_user.id),
            export_format='csv',
            filters={}
        )
        
        # Check email was sent
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [manager_user.email]
        assert 'Survey Export Ready' in mail.outbox[0].subject
        assert len(mail.outbox[0].attachments) == 1


# =============================================================================
# ANALYTICS TESTS
# =============================================================================


@pytest.fixture
def analytics_user(db):
    """Create user with view_analytics permission."""
    from users.models import User, Role, Permission, UserRole, RolePermission
    user = User.objects.create_user(email='analytics@example.com', password='testpass123')
    
    # Create analytics role with view_analytics permission
    analytics_role, _ = Role.objects.get_or_create(name='analyst')
    view_analytics, _ = Permission.objects.get_or_create(codename='view_analytics')
    view_responses, _ = Permission.objects.get_or_create(codename='view_responses')
    
    RolePermission.objects.get_or_create(role=analytics_role, permission=view_analytics)
    RolePermission.objects.get_or_create(role=analytics_role, permission=view_responses)
    UserRole.objects.create(user=user, role=analytics_role)
    
    return user


@pytest.fixture
def analytics_client(api_client, analytics_user):
    """Authenticated client with analytics permissions."""
    from users.models import UserSession
    from users.serializers import get_tokens_for_user_with_session
    
    session = UserSession.objects.create(user=analytics_user)
    tokens = get_tokens_for_user_with_session(analytics_user, session)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    return api_client


@pytest.fixture
def survey_with_responses(user):
    """Create a survey with completed and in-progress responses."""
    from django.utils import timezone
    from datetime import timedelta
    
    survey = Survey.objects.create(
        title='Analytics Test Survey',
        status=Survey.Status.PUBLISHED,
        created_by=user
    )
    
    section = Section.objects.create(
        survey=survey,
        title='Section 1',
        order=1
    )
    
    field = Field.objects.create(
        section=section,
        label='Name',
        field_type=Field.FieldType.TEXT,
        order=1
    )
    
    # Create completed responses
    for i in range(5):
        started = timezone.now() - timedelta(hours=i+1)
        completed = started + timedelta(minutes=5+i)  # 5-10 minute completion times
        response = SurveyResponse.objects.create(
            survey=survey,
            session_token=f'completed-token-{i}',
            status=SurveyResponse.Status.COMPLETED,
            started_at=started,
            completed_at=completed
        )
        FieldAnswer.objects.create(
            response=response,
            field=field,
            value=f'Answer {i}'
        )
    
    # Create in-progress responses
    for i in range(3):
        response = SurveyResponse.objects.create(
            survey=survey,
            session_token=f'in-progress-token-{i}',
            status=SurveyResponse.Status.IN_PROGRESS
        )
    
    return survey


@pytest.mark.django_db
class TestSurveyAnalytics:
    """Tests for survey-specific analytics endpoint."""
    
    def test_get_survey_analytics(self, analytics_client, survey_with_responses):
        """Test getting analytics for a specific survey."""
        url = reverse('survey-responses-analytics', kwargs={'survey_pk': survey_with_responses.id})
        response = analytics_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['survey_id'] == str(survey_with_responses.id)
        assert response.data['survey_title'] == survey_with_responses.title
        assert response.data['total_responses'] == 8  # 5 completed + 3 in-progress
        assert response.data['completed_responses'] == 5
        assert response.data['in_progress_responses'] == 3
        assert response.data['completion_rate'] == 62.5  # 5/8 * 100
        assert response.data['average_completion_time_seconds'] is not None
        assert response.data['last_response_at'] is not None
    
    def test_analytics_requires_authentication(self, api_client, survey_with_responses):
        """Test that analytics endpoint requires authentication."""
        url = reverse('survey-responses-analytics', kwargs={'survey_pk': survey_with_responses.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_analytics_requires_permission(self, api_client, survey_with_responses, user):
        """Test that analytics endpoint requires view_analytics permission."""
        from users.models import UserSession
        from users.serializers import get_tokens_for_user_with_session
        
        # User without analytics permission
        session = UserSession.objects.create(user=user)
        tokens = get_tokens_for_user_with_session(user, session)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        
        url = reverse('survey-responses-analytics', kwargs={'survey_pk': survey_with_responses.id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_analytics_not_found(self, analytics_client):
        """Test analytics for non-existent survey returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        url = reverse('survey-responses-analytics', kwargs={'survey_pk': fake_id})
        response = analytics_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_analytics_empty_survey(self, analytics_client, survey):
        """Test analytics for a survey with no responses."""
        url = reverse('survey-responses-analytics', kwargs={'survey_pk': survey.id})
        response = analytics_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_responses'] == 0
        assert response.data['completed_responses'] == 0
        assert response.data['in_progress_responses'] == 0
        assert response.data['completion_rate'] == 0.0
        assert response.data['average_completion_time_seconds'] is None


@pytest.mark.django_db
class TestAnalyticsService:
    """Tests for the AnalyticsService class."""
    
    def test_get_survey_analytics_caching(self, survey_with_responses):
        """Test that analytics results are cached."""
        from django.core.cache import cache
        from submissions.services import AnalyticsService
        
        service = AnalyticsService()
        cache_key = f"survey_analytics_{survey_with_responses.id}"
        
        # Clear cache
        cache.delete(cache_key)
        
        # First call should populate cache
        result1 = service.get_survey_analytics(str(survey_with_responses.id))
        assert result1 is not None
        
        # Check cache is populated
        cached = cache.get(cache_key)
        assert cached is not None
        assert cached['total_responses'] == result1['total_responses']
        
        # Second call should use cache
        result2 = service.get_survey_analytics(str(survey_with_responses.id))
        assert result1 == result2
    
    def test_bypass_cache(self, survey_with_responses):
        """Test bypassing cache."""
        from django.core.cache import cache
        from submissions.services import AnalyticsService
        
        service = AnalyticsService()
        cache_key = f"survey_analytics_{survey_with_responses.id}"
        
        # Pre-populate cache with stale data
        cache.set(cache_key, {'total_responses': 999, 'survey_id': 'fake'}, 60)
        
        # Call with use_cache=False should bypass cache
        result = service.get_survey_analytics(str(survey_with_responses.id), use_cache=False)
        assert result['total_responses'] == 8  # Real data, not cached 999
    
    def test_invalidate_survey_cache(self, survey_with_responses):
        """Test cache invalidation."""
        from django.core.cache import cache
        from submissions.services import AnalyticsService
        
        service = AnalyticsService()
        cache_key = f"survey_analytics_{survey_with_responses.id}"
        
        # Populate cache
        service.get_survey_analytics(str(survey_with_responses.id))
        assert cache.get(cache_key) is not None
        
        # Invalidate
        service.invalidate_survey_cache(str(survey_with_responses.id))
        assert cache.get(cache_key) is None
    
    def test_completion_rate_calculation(self, user):
        """Test completion rate is calculated correctly."""
        from submissions.services import AnalyticsService
        
        # Create survey with specific completion ratio
        survey = Survey.objects.create(
            title='Completion Test',
            status=Survey.Status.PUBLISHED,
            created_by=user
        )
        
        # 3 completed, 1 in-progress = 75% completion rate
        for i in range(3):
            SurveyResponse.objects.create(
                survey=survey,
                session_token=f'complete-{i}',
                status=SurveyResponse.Status.COMPLETED
            )
        
        SurveyResponse.objects.create(
            survey=survey,
            session_token='incomplete-1',
            status=SurveyResponse.Status.IN_PROGRESS
        )
        
        service = AnalyticsService()
        result = service.get_survey_analytics(str(survey.id), use_cache=False)
        
        assert result['total_responses'] == 4
        assert result['completed_responses'] == 3
        assert result['in_progress_responses'] == 1
        assert result['completion_rate'] == 75.0


# ============ INVITATION TESTS ============

@pytest.fixture
def user_with_publish_permission(db):
    """Create a user with publish_survey permission."""
    from users.models import User, Role, Permission, RolePermission, UserRole
    
    user = User.objects.create_user(email='publisher@example.com', password='pass')
    
    # Create or get publish_survey permission
    permission, _ = Permission.objects.get_or_create(
        codename='publish_survey',
        defaults={'description': 'Can publish surveys'}
    )
    
    # Create role with the permission
    role, _ = Role.objects.get_or_create(
        name='Publisher',
        defaults={'description': 'Can publish surveys'}
    )
    RolePermission.objects.get_or_create(role=role, permission=permission)
    
    # Assign role to user
    UserRole.objects.get_or_create(user=user, role=role)
    
    return user


@pytest.mark.django_db
class TestInvitationEndpoint:
    """Tests for the batch invitation endpoint."""
    
    def test_send_invitations_success(self, api_client, survey, user_with_publish_permission):
        """Test successful invitation sending."""
        from users.models import User
        
        # Refresh user from database to ensure permission data is loaded
        user = User.objects.get(pk=user_with_publish_permission.pk)
        api_client.force_authenticate(user=user)
        
        url = reverse('survey-invitations', kwargs={'survey_pk': survey.id})
        
        with patch('submissions.views.send_survey_invitations.delay') as mock_task:
            response = api_client.post(url, {
                'emails': ['user1@example.com', 'user2@example.com', 'user3@example.com']
            }, format='json')
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['recipient_count'] == 3
        assert response.data['survey'] == survey.title
        assert 'Sending invitations to 3 recipients' in response.data['message']
        
        # Verify task was called
        mock_task.assert_called_once()
        call_kwargs = mock_task.call_args[1]
        assert call_kwargs['survey_id'] == str(survey.id)
        assert call_kwargs['emails'] == ['user1@example.com', 'user2@example.com', 'user3@example.com']
        assert call_kwargs['sent_by_user_id'] == str(user.id)
    
    def test_send_invitations_deduplicates_emails(self, api_client, survey, user_with_publish_permission):
        """Test that duplicate emails are removed."""
        api_client.force_authenticate(user=user_with_publish_permission)
        
        url = reverse('survey-invitations', kwargs={'survey_pk': survey.id})
        
        with patch('submissions.views.send_survey_invitations.delay') as mock_task:
            response = api_client.post(url, {
                'emails': [
                    'user@example.com',
                    'USER@EXAMPLE.COM',  # Duplicate (case insensitive)
                    'other@example.com'
                ]
            }, format='json')
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['recipient_count'] == 2  # Deduplicated
        
        call_kwargs = mock_task.call_args[1]
        assert len(call_kwargs['emails']) == 2
    
    def test_send_invitations_requires_authentication(self, api_client, survey):
        """Test that unauthenticated requests are rejected."""
        url = reverse('survey-invitations', kwargs={'survey_pk': survey.id})
        
        response = api_client.post(url, {
            'emails': ['user@example.com']
        }, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_send_invitations_requires_permission(self, api_client, survey, user):
        """Test that users without permission are rejected."""
        api_client.force_authenticate(user=user)
        
        url = reverse('survey-invitations', kwargs={'survey_pk': survey.id})
        
        response = api_client.post(url, {
            'emails': ['user@example.com']
        }, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_send_invitations_survey_not_found(self, api_client, user_with_publish_permission):
        """Test sending invitations to non-existent survey."""
        import uuid
        api_client.force_authenticate(user=user_with_publish_permission)
        
        url = reverse('survey-invitations', kwargs={'survey_pk': uuid.uuid4()})
        
        response = api_client.post(url, {
            'emails': ['user@example.com']
        }, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_send_invitations_empty_emails(self, api_client, survey, user_with_publish_permission):
        """Test that empty email list is rejected."""
        api_client.force_authenticate(user=user_with_publish_permission)
        
        url = reverse('survey-invitations', kwargs={'survey_pk': survey.id})
        
        response = api_client.post(url, {
            'emails': []
        }, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_send_invitations_invalid_emails(self, api_client, survey, user_with_publish_permission):
        """Test that invalid emails are rejected."""
        api_client.force_authenticate(user=user_with_publish_permission)
        
        url = reverse('survey-invitations', kwargs={'survey_pk': survey.id})
        
        response = api_client.post(url, {
            'emails': ['not-an-email', 'valid@example.com']
        }, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestInvitationTask:
    """Tests for the batch invitation Celery task."""
    
    def test_send_survey_invitations_task(self, survey, user):
        """Test the send_survey_invitations task creates records."""
        from submissions.tasks import send_survey_invitations
        from submissions.models import Invitation
        
        emails = ['user1@example.com', 'user2@example.com']
        
        # Mock the task's update_state and _send_invitation_email
        with patch('submissions.tasks._send_invitation_email') as mock_send:
            with patch.object(send_survey_invitations, 'update_state'):
                result = send_survey_invitations(
                    survey_id=str(survey.id),
                    emails=emails,
                    sent_by_user_id=str(user.id)
                )
        
        assert result['status'] == 'SUCCESS'
        assert result['sent_count'] == 2
        assert result['failed_count'] == 0
        
        # Verify Invitation records were created
        invitations = Invitation.objects.filter(survey=survey)
        assert invitations.count() == 2
        
        # Verify email addresses
        invitation_emails = set(invitations.values_list('email', flat=True))
        assert invitation_emails == {'user1@example.com', 'user2@example.com'}
        
        # Verify sent_by is set
        assert all(inv.sent_by == user for inv in invitations)
    
    def test_send_survey_invitations_handles_failures(self, survey, user):
        """Test task handles email sending failures gracefully."""
        from submissions.tasks import send_survey_invitations
        from submissions.models import Invitation
        
        emails = ['good@example.com', 'bad@example.com', 'good2@example.com']
        
        def mock_send(email, *args, **kwargs):
            if 'bad' in email:
                raise Exception('Email delivery failed')
        
        with patch('submissions.tasks._send_invitation_email', side_effect=mock_send):
            with patch.object(send_survey_invitations, 'update_state'):
                result = send_survey_invitations(
                    survey_id=str(survey.id),
                    emails=emails,
                    sent_by_user_id=str(user.id)
                )
        
        assert result['status'] == 'SUCCESS'
        assert result['sent_count'] == 2
        assert result['failed_count'] == 1
        assert len(result['failed_emails']) == 1
        assert result['failed_emails'][0]['email'] == 'bad@example.com'
        
        # Only successful invitations should be recorded
        assert Invitation.objects.filter(survey=survey).count() == 2
    
    def test_send_survey_invitations_survey_not_found(self):
        """Test task handles non-existent survey."""
        import uuid
        from submissions.tasks import send_survey_invitations
        
        with patch.object(send_survey_invitations, 'update_state'):
            result = send_survey_invitations(
                survey_id=str(uuid.uuid4()),
                emails=['user@example.com'],
                sent_by_user_id=None
            )
        
        assert result['status'] == 'FAILED'
        assert 'not found' in result['error']
    
    def test_invitation_model(self, survey, user):
        """Test Invitation model creation and fields."""
        from submissions.models import Invitation
        
        invitation = Invitation.objects.create(
            survey=survey,
            email='invited@example.com',
            sent_by=user
        )
        
        assert invitation.id is not None
        assert invitation.survey == survey
        assert invitation.email == 'invited@example.com'
        assert invitation.sent_by == user
        assert invitation.sent_at is not None
        assert str(invitation) == f'{survey.title} -> invited@example.com'
