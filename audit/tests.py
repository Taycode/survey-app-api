import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from rest_framework import status
from surveys.models import Survey
from audit.models import AuditLog
from users.models import User

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(email='audit_tester@example.com', password='pass')

@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.mark.django_db
class TestAuditLog:
    """Test audit logging via SurveyViewSet."""

    def test_audit_logs_lifecycle(self, auth_client, user):
        # 1. CREATE Survey
        url = reverse('survey-list')
        response = auth_client.post(url, {
            'title': 'Audit Survey',
            'description': 'Testing logs'
        })
        assert response.status_code == status.HTTP_201_CREATED
        survey_id = response.data['id']
        
        # Verify Create Log
        log = AuditLog.objects.filter(resource_id=survey_id, action=AuditLog.Action.CREATED).first()
        assert log is not None
        assert log.user == user
        assert log.resource_type == AuditLog.ResourceType.SURVEY
        
        # 2. UPDATE Survey
        detail_url = reverse('survey-detail', kwargs={'pk': survey_id})
        response = auth_client.patch(detail_url, {
            'title': 'Audit Survey Updated'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Verify Update Log and Diff
        log = AuditLog.objects.filter(resource_id=survey_id, action=AuditLog.Action.UPDATED).first()
        assert log is not None
        assert 'title' in log.changes
        assert log.changes['title']['old'] == 'Audit Survey'
        assert log.changes['title']['new'] == 'Audit Survey Updated'
        
        # 3. DELETE Survey
        response = auth_client.delete(detail_url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify Delete Log
        log = AuditLog.objects.filter(resource_id=survey_id, action=AuditLog.Action.DELETED).first()
        assert log is not None
