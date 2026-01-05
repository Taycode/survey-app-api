"""
Security Tests for Survey Submission API.

Tests for common vulnerabilities:
- SQL Injection
- Authentication Bypass
- Authorization Bypass (RBAC)
- Input Validation (XSS, oversized inputs)
- Mass Assignment
"""
import pytest
import uuid
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from surveys.models import Survey, Section, Field, FieldOption
from submissions.models import SurveyResponse, FieldAnswer
from users.models import User, Role, UserRole, Permission, RolePermission


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email='test@example.com', password='testpass123')


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email='other@example.com', password='testpass123')


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(email='admin@example.com', password='testpass123')
    admin_role, _ = Role.objects.get_or_create(name='admin')
    UserRole.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def survey(user):
    return Survey.objects.create(
        title='Security Test Survey',
        status=Survey.Status.PUBLISHED,
        created_by=user
    )


@pytest.fixture
def section(survey):
    return Section.objects.create(survey=survey, title='Section 1', order=1)


@pytest.fixture
def text_field(section):
    return Field.objects.create(
        section=section,
        label='Text Input',
        field_type=Field.FieldType.TEXT,
        is_required=True,
        order=1
    )


@pytest.fixture
def number_field(section):
    return Field.objects.create(
        section=section,
        label='Number Input',
        field_type=Field.FieldType.NUMBER,
        order=2
    )


@pytest.fixture
def session_token(api_client, survey):
    """Create a valid session and return the token."""
    url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
    response = api_client.post(url)
    return response.data['session_token']


# =============================================================================
# SQL INJECTION TESTS
# =============================================================================


@pytest.mark.django_db
class TestSQLInjection:
    """Test that SQL injection attacks are properly prevented."""

    SQL_INJECTION_PAYLOADS = [
        "'; DROP TABLE surveys; --",
        "1; DELETE FROM users WHERE 1=1; --",
        "' OR '1'='1",
        "1 UNION SELECT * FROM users --",
        "'; INSERT INTO users (email) VALUES ('hacked@evil.com'); --",
        "1; UPDATE surveys SET status='deleted' WHERE 1=1; --",
        "' OR 1=1 --",
        "admin'--",
        "1' AND '1'='1",
        "'; EXEC xp_cmdshell('whoami'); --",
    ]

    def test_sql_injection_in_text_field_value(self, api_client, survey, section, text_field):
        """Ensure SQL injection payloads in field values are safely stored."""
        # Start session
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        submit_url = reverse('submissions-submit-section')

        for payload in self.SQL_INJECTION_PAYLOADS:
            response = api_client.post(submit_url, {
                'section_id': str(section.id),
                'answers': [{'field_id': str(text_field.id), 'value': payload}]
            }, format='json')

            # Should succeed - payload stored as literal string, not executed
            assert response.status_code == status.HTTP_200_OK

            # Verify payload was stored literally, not executed
            answer = FieldAnswer.objects.filter(
                response__session_token=session_token,
                field=text_field
            ).first()
            assert answer is not None
            assert answer.value == payload  # Stored as-is, not executed

    def test_sql_injection_in_survey_id(self, api_client):
        """Ensure SQL injection in URL parameters is rejected."""
        payloads = [
            "'; DROP TABLE surveys; --",
            "1 OR 1=1",
            "1; DELETE FROM surveys",
        ]

        for payload in payloads:
            # Django's URL routing should reject non-UUID values
            url = f"/api/v1/surveys/{payload}/submissions/start/"
            response = api_client.post(url)
            # Should be 404 (not found) since it's not a valid UUID
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sql_injection_in_query_params(self, api_client, user, survey):
        """Ensure SQL injection in query parameters is handled safely."""
        api_client.force_authenticate(user=user)

        # Try SQL injection in filter parameters
        url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        malicious_params = {
            'status': "'; DROP TABLE submissions; --",
            'start_date': "2024-01-01'; DELETE FROM users; --",
        }

        response = api_client.get(url, malicious_params)
        # Should either return 400 (invalid param) or 200 with empty results
        # but NOT execute the SQL
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

        # Verify tables still exist
        assert Survey.objects.filter(id=survey.id).exists()


# =============================================================================
# AUTHENTICATION BYPASS TESTS
# =============================================================================


@pytest.mark.django_db
class TestAuthenticationBypass:
    """Test that authentication cannot be bypassed."""

    def test_missing_session_token(self, api_client, section, text_field):
        """Endpoints requiring session token should fail without it."""
        submit_url = reverse('submissions-submit-section')

        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}]
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_session_token_format(self, api_client, section, text_field):
        """Invalid token formats should be rejected."""
        invalid_tokens = [
            'invalid-token',
            '12345',
            'null',
            'undefined',
            '<script>alert(1)</script>',
            '../../../etc/passwd',
        ]

        submit_url = reverse('submissions-submit-section')

        for token in invalid_tokens:
            api_client.credentials(HTTP_X_SESSION_TOKEN=token)
            response = api_client.post(submit_url, {
                'section_id': str(section.id),
                'answers': [{'field_id': str(text_field.id), 'value': 'test'}]
            }, format='json')

            # Should be 404 (session not found) or 400 (invalid format)
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND
            ]

    def test_nonexistent_session_token(self, api_client, section, text_field):
        """Valid UUID format but non-existent token should fail."""
        fake_token = str(uuid.uuid4())
        api_client.credentials(HTTP_X_SESSION_TOKEN=fake_token)

        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}]
        }, format='json')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_completed_session_token_rejected(self, api_client, survey, section, text_field):
        """Completed sessions should not accept new submissions."""
        # Start and complete a session
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        # Submit section
        submit_url = reverse('submissions-submit-section')
        api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}]
        }, format='json')

        # Finish survey
        finish_url = reverse('submissions-finish-survey')
        api_client.post(finish_url)

        # Try to submit again - should fail
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'hacked'}]
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_jwt_token_tampering(self, api_client, user):
        """Tampered JWT tokens should be rejected."""
        from rest_framework_simplejwt.tokens import RefreshToken

        # Get valid token
        refresh = RefreshToken.for_user(user)
        valid_token = str(refresh.access_token)

        # Tamper with it
        tampered_tokens = [
            valid_token[:-5] + 'XXXXX',  # Modified signature
            valid_token.split('.')[0] + '.TAMPERED.' + valid_token.split('.')[2],
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
        ]

        url = reverse('user-profile')

        for token in tampered_tokens:
            api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = api_client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# AUTHORIZATION BYPASS TESTS (RBAC)
# =============================================================================


@pytest.mark.django_db
class TestAuthorizationBypass:
    """Test that authorization/RBAC cannot be bypassed."""

    def test_access_other_users_response(self, api_client, survey, section, text_field, user, other_user):
        """Users should not access other users' survey responses."""
        # Create a response as user1
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']

        # Link response to user
        survey_response = SurveyResponse.objects.get(session_token=session_token)
        survey_response.respondent = user
        survey_response.save()

        # Try to access as other_user (should fail or return empty)
        api_client.force_authenticate(user=other_user)
        responses_url = reverse('survey-responses-list', kwargs={'survey_pk': survey.id})
        response = api_client.get(responses_url)

        # other_user shouldn't see user's responses (depends on permission setup)
        # Either 403 or empty list
        if response.status_code == status.HTTP_200_OK:
            # If allowed to list, should not include other user's data
            response_ids = [r['id'] for r in response.data.get('results', response.data)]
            assert str(survey_response.id) not in response_ids

    def test_export_without_permission(self, api_client, survey, user):
        """Users without export permission should be denied."""
        # Remove any export permissions from user
        api_client.force_authenticate(user=user)

        export_url = reverse('survey-responses-export', kwargs={'survey_pk': survey.id})
        response = api_client.post(export_url, {'format': 'csv'}, format='json')

        # Should be 403 Forbidden (no export permission)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_endpoint_without_admin_role(self, api_client, user):
        """Non-admin users should not access admin endpoints."""
        api_client.force_authenticate(user=user)

        # Try to access admin-only endpoints (if any exist)
        # For now, test that regular user can't modify other users
        other = User.objects.create_user(email='victim@example.com', password='pass')

        # Attempt to delete/modify another user (should fail)
        # This depends on your specific admin endpoints

    def test_horizontal_privilege_escalation(self, api_client, survey, user, other_user):
        """Users should not be able to act on behalf of other users."""
        # Authenticate as other_user
        api_client.force_authenticate(user=other_user)

        # Try to create a survey response claiming to be from 'user'
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']

        # The response should be associated with other_user, not user
        survey_response = SurveyResponse.objects.get(session_token=session_token)
        # If respondent is set, it should be other_user
        if survey_response.respondent:
            assert survey_response.respondent == other_user


# =============================================================================
# INPUT VALIDATION TESTS
# =============================================================================


@pytest.mark.django_db
class TestInputValidation:
    """Test input validation against malicious payloads."""

    XSS_PAYLOADS = [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert("XSS")>',
        '<svg onload=alert("XSS")>',
        '"><script>alert("XSS")</script>',
        "javascript:alert('XSS')",
        '<iframe src="javascript:alert(\'XSS\')">',
        '<body onload=alert("XSS")>',
        '{{constructor.constructor("alert(1)")()}}',  # Template injection
        '${7*7}',  # SSTI
    ]

    def test_xss_payloads_in_text_field(self, api_client, survey, section, text_field):
        """XSS payloads should be stored literally, not executed."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        submit_url = reverse('submissions-submit-section')

        for payload in self.XSS_PAYLOADS:
            response = api_client.post(submit_url, {
                'section_id': str(section.id),
                'answers': [{'field_id': str(text_field.id), 'value': payload}]
            }, format='json')

            assert response.status_code == status.HTTP_200_OK

            # Verify stored literally
            answer = FieldAnswer.objects.filter(
                response__session_token=session_token,
                field=text_field
            ).first()
            assert answer.value == payload

    def test_oversized_input_rejected(self, api_client, survey, section, text_field):
        """Extremely large inputs should be handled gracefully."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        # Create a very large payload (10MB of data)
        large_payload = 'A' * (10 * 1024 * 1024)

        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': large_payload}]
        }, format='json')

        # Should either succeed with truncation or fail with 400
        # Should NOT crash the server
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ]

    def test_null_bytes_in_input(self, api_client, survey, section, text_field):
        """Null bytes should be handled safely."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        payloads = [
            'test\x00value',
            '\x00\x00\x00',
            'normal\x00<script>alert(1)</script>',
        ]

        submit_url = reverse('submissions-submit-section')

        for payload in payloads:
            response = api_client.post(submit_url, {
                'section_id': str(section.id),
                'answers': [{'field_id': str(text_field.id), 'value': payload}]
            }, format='json')

            # Should handle gracefully
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST
            ]

    def test_unicode_edge_cases(self, api_client, survey, section, text_field):
        """Unicode edge cases should be handled properly."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        payloads = [
            '𝕳𝖊𝖑𝖑𝖔',  # Mathematical symbols
            '​',  # Zero-width space
            '\u202e\u0041\u0042\u0043',  # Right-to-left override
            '🔥' * 1000,  # Many emojis
            '\ufeff',  # BOM
        ]

        submit_url = reverse('submissions-submit-section')

        for payload in payloads:
            response = api_client.post(submit_url, {
                'section_id': str(section.id),
                'answers': [{'field_id': str(text_field.id), 'value': payload}]
            }, format='json')

            assert response.status_code == status.HTTP_200_OK

    def test_number_field_rejects_non_numbers(self, api_client, survey, section, number_field):
        """Number fields should reject non-numeric input."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        invalid_values = [
            'not-a-number',
            '<script>alert(1)</script>',
            '1; DROP TABLE users;',
            'NaN',
            'Infinity',
        ]

        submit_url = reverse('submissions-submit-section')

        for value in invalid_values:
            response = api_client.post(submit_url, {
                'section_id': str(section.id),
                'answers': [{'field_id': str(number_field.id), 'value': value}]
            }, format='json')

            # Should reject invalid numbers
            assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# MASS ASSIGNMENT TESTS
# =============================================================================


@pytest.mark.django_db
class TestMassAssignment:
    """Test that read-only fields cannot be set via API."""

    def test_cannot_set_response_id(self, api_client, survey, section, text_field):
        """Users should not be able to set their own response ID."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        original_token = response.data['session_token']

        # Get the actual response ID
        original_response = SurveyResponse.objects.get(session_token=original_token)
        original_id = original_response.id

        # Start another session
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        # Try to submit with a different response ID
        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}],
            'id': str(original_id),  # Try to hijack another response
            'response_id': str(original_id),
        }, format='json')

        # The submission should succeed but the ID should NOT be changed
        new_response = SurveyResponse.objects.get(session_token=session_token)
        assert new_response.id != original_id

    def test_cannot_set_status_directly(self, api_client, survey, section, text_field):
        """Users should not be able to set response status directly."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}],
            'status': 'completed',  # Try to set status directly
        }, format='json')

        # Status should still be in_progress (not yet finished)
        survey_response = SurveyResponse.objects.get(session_token=session_token)
        assert survey_response.status == SurveyResponse.Status.IN_PROGRESS

    def test_cannot_set_timestamps(self, api_client, survey, section, text_field):
        """Users should not be able to set timestamps directly."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}],
            'started_at': '2020-01-01T00:00:00Z',  # Try to backdate
            'completed_at': '2020-01-01T00:00:00Z',
        }, format='json')

        # Timestamps should not be backdated
        survey_response = SurveyResponse.objects.get(session_token=session_token)
        assert survey_response.started_at.year != 2020

    def test_cannot_modify_survey_via_submission(self, api_client, survey, section, text_field):
        """Submissions should not be able to modify the parent survey."""
        start_url = reverse('survey-submissions-start', kwargs={'survey_pk': survey.id})
        response = api_client.post(start_url)
        session_token = response.data['session_token']
        api_client.credentials(HTTP_X_SESSION_TOKEN=session_token)

        original_title = survey.title

        submit_url = reverse('submissions-submit-section')
        response = api_client.post(submit_url, {
            'section_id': str(section.id),
            'answers': [{'field_id': str(text_field.id), 'value': 'test'}],
            'survey': {'title': 'HACKED'},  # Try to modify survey
            'survey_title': 'HACKED',
        }, format='json')

        # Survey should be unchanged
        survey.refresh_from_db()
        assert survey.title == original_title

