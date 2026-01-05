"""
Survey Platform API - Python Integration Examples

This file contains working examples demonstrating how to integrate with the Survey Platform API.

Requirements:
    pip install requests

Usage:
    python examples.py

Note: Update BASE_URL, USER_EMAIL, and USER_PASSWORD with your actual values.
"""

import requests
import json
import time
from typing import Dict, Optional, List


# Configuration
BASE_URL = "http://localhost:8000"
USER_EMAIL = "testuser@example.com"
USER_PASSWORD = "SecurePassword123!"


class SurveyAPIClient:
    """Client for interacting with the Survey Platform API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    def _get_headers(self, authenticated: bool = True) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def register(self, email: str, password: str, first_name: str, last_name: str) -> Dict:
        """Register a new user."""
        url = f"{self.base_url}/api/v1/auth/register/"
        data = {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name
        }
        response = requests.post(url, json=data, headers=self._get_headers(authenticated=False))
        response.raise_for_status()
        result = response.json()
        
        # Store tokens
        self.access_token = result["access"]
        self.refresh_token = result["refresh"]
        
        return result
    
    def login(self, email: str, password: str) -> Dict:
        """Login and obtain tokens."""
        url = f"{self.base_url}/api/v1/auth/login/"
        data = {"email": email, "password": password}
        response = requests.post(url, json=data, headers=self._get_headers(authenticated=False))
        response.raise_for_status()
        result = response.json()
        
        # Store tokens
        self.access_token = result["access"]
        self.refresh_token = result["refresh"]
        
        return result
    
    def refresh_access_token(self) -> Dict:
        """Refresh the access token."""
        url = f"{self.base_url}/api/v1/auth/token/refresh/"
        data = {"refresh": self.refresh_token}
        response = requests.post(url, json=data, headers=self._get_headers(authenticated=False))
        response.raise_for_status()
        result = response.json()
        
        # Update access token
        self.access_token = result["access"]
        
        return result
    
    def logout(self) -> Dict:
        """Logout the current user."""
        url = f"{self.base_url}/api/v1/auth/logout/"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_profile(self) -> Dict:
        """Get current user profile."""
        url = f"{self.base_url}/api/v1/auth/me/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def _ensure_manager_role(self):
        """Ensure user has manager role (for testing purposes)."""
        # Note: In production, roles should be assigned by admins
        # This is a helper for examples/testing only
        try:
            from django.contrib.auth import get_user_model
            from users.models import Role, UserRole
            
            User = get_user_model()
            user = User.objects.get(email=USER_EMAIL)
            manager_role = Role.objects.get(name='manager')
            UserRole.objects.get_or_create(user=user, role=manager_role)
        except Exception:
            # If this fails, user needs to be assigned role manually
            pass
    
    def list_organizations(self) -> Dict:
        """List user's organizations."""
        url = f"{self.base_url}/api/v1/organizations/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_survey(self, title: str, description: str, organization_id: Optional[str] = None) -> Dict:
        """Create a new survey."""
        # If organization_id not provided, get user's first organization
        if not organization_id:
            orgs = self.list_organizations()
            if orgs.get('results') and len(orgs['results']) > 0:
                organization_id = orgs['results'][0]['id']
            else:
                raise ValueError("User has no organizations. Please create an organization first.")
        
        url = f"{self.base_url}/api/v1/surveys/"
        data = {
            "title": title,
            "description": description,
            "status": "draft",
            "organization": organization_id
        }
        response = requests.post(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_section(self, survey_id: str, title: str, description: str, order: int) -> Dict:
        """Add a section to a survey."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/sections/"
        data = {
            "title": title,
            "description": description,
            "order": order
        }
        response = requests.post(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_field(
        self, 
        survey_id: str, 
        section_id: str, 
        label: str, 
        field_type: str,
        is_required: bool = True,
        order: int = 1
    ) -> Dict:
        """Add a field to a section."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/sections/{section_id}/fields/"
        data = {
            "label": label,
            "field_type": field_type,
            "is_required": is_required,
            "order": order
        }
        response = requests.post(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_field_option(
        self,
        survey_id: str,
        section_id: str,
        field_id: str,
        label: str,
        value: str,
        order: int = 1
    ) -> Dict:
        """Add an option to a dropdown/radio field."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/sections/{section_id}/fields/{field_id}/options/"
        data = {
            "label": label,
            "value": value,
            "order": order
        }
        response = requests.post(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def publish_survey(self, survey_id: str) -> Dict:
        """Publish a survey."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/publish/"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_survey(self, survey_id: str) -> Dict:
        """Get survey details."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def list_surveys(self) -> Dict:
        """List all surveys."""
        url = f"{self.base_url}/api/v1/surveys/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_responses(self, survey_id: str) -> Dict:
        """Get responses for a survey."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/responses/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_analytics(self, survey_id: str) -> Dict:
        """Get analytics for a survey."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/responses/analytics/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def export_responses(self, survey_id: str, format: str = "csv") -> Dict:
        """Export survey responses."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/responses/export/"
        params = {"format": format}
        response = requests.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        return response.json()


class SurveySubmissionClient:
    """Client for submitting survey responses (anonymous access)."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_token: Optional[str] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with session token."""
        headers = {"Content-Type": "application/json"}
        if self.session_token:
            headers["X-Session-Token"] = self.session_token
        return headers
    
    def start_survey(self, survey_id: str) -> Dict:
        """Start a new survey submission session."""
        url = f"{self.base_url}/api/v1/surveys/{survey_id}/submissions/start/"
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()
        
        # Store session token
        self.session_token = result["session_token"]
        
        return result
    
    def get_current_section(self) -> Dict:
        """Get the current section to complete."""
        url = f"{self.base_url}/api/v1/submissions/current-section/"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def submit_section(self, section_id: str, answers: List[Dict]) -> Dict:
        """Submit answers for a section."""
        url = f"{self.base_url}/api/v1/submissions/submit-section/"
        data = {
            "section_id": section_id,
            "answers": answers
        }
        response = requests.post(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def finish_survey(self) -> Dict:
        """Complete the survey submission."""
        url = f"{self.base_url}/api/v1/submissions/finish/"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()


# ============================================================================
# Example Workflows
# ============================================================================

def example_1_authentication_flow():
    """Example 1: Complete authentication flow."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Authentication Flow")
    print("="*60)
    
    client = SurveyAPIClient(BASE_URL)
    
    # Try to login, if fails, register first
    print("\n1. Attempting to login...")
    try:
        login_result = client.login(USER_EMAIL, USER_PASSWORD)
        print(f"   ✓ Logged in as: {login_result['user']['email']}")
    except requests.exceptions.HTTPError:
        print("   ⚠ User doesn't exist, registering new user...")
        register_result = client.register(
            email=USER_EMAIL,
            password=USER_PASSWORD,
            first_name="Test",
            last_name="User"
        )
        print(f"   ✓ Registered and logged in as: {register_result['user']['email']}")
        login_result = register_result
    
    # Get profile
    print("\n2. Getting user profile...")
    profile = client.get_profile()
    print(f"   ✓ Name: {profile['first_name']} {profile['last_name']}")
    
    # Refresh token
    print("\n3. Refreshing access token...")
    client.refresh_access_token()
    print("   ✓ Token refreshed successfully")
    
    # Logout
    print("\n4. Logging out...")
    client.logout()
    print("   ✓ Logged out successfully")


def example_2_create_survey():
    """Example 2: Create a complete survey."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Create a Survey")
    print("="*60)
    
    client = SurveyAPIClient(BASE_URL)
    try:
        client.login(USER_EMAIL, USER_PASSWORD)
    except requests.exceptions.HTTPError:
        # Register if login fails
        client.register(
            email=USER_EMAIL,
            password=USER_PASSWORD,
            first_name="Test",
            last_name="User"
        )
    
    # Create survey
    print("\n1. Creating survey...")
    survey = client.create_survey(
        title="Customer Satisfaction Survey 2024",
        description="Help us improve our services"
    )
    survey_id = survey["id"]
    print(f"   ✓ Survey created: {survey['title']} (ID: {survey_id})")
    
    # Create first section
    print("\n2. Creating first section...")
    section1 = client.create_section(
        survey_id=survey_id,
        title="Personal Information",
        description="Tell us about yourself",
        order=1
    )
    section1_id = section1["id"]
    print(f"   ✓ Section created: {section1['title']}")
    
    # Add text field
    print("\n3. Adding text field...")
    name_field = client.create_field(
        survey_id=survey_id,
        section_id=section1_id,
        label="Full Name",
        field_type="text",
        is_required=True,
        order=1
    )
    print(f"   ✓ Field added: {name_field['label']}")
    
    # Add email field
    print("\n4. Adding email field...")
    email_field = client.create_field(
        survey_id=survey_id,
        section_id=section1_id,
        label="Email Address",
        field_type="text",
        is_required=True,
        order=2
    )
    print(f"   ✓ Field added: {email_field['label']}")
    
    # Create second section
    print("\n5. Creating second section...")
    section2 = client.create_section(
        survey_id=survey_id,
        title="Feedback",
        description="Share your thoughts",
        order=2
    )
    section2_id = section2["id"]
    print(f"   ✓ Section created: {section2['title']}")
    
    # Add dropdown field
    print("\n6. Adding satisfaction dropdown...")
    satisfaction_field = client.create_field(
        survey_id=survey_id,
        section_id=section2_id,
        label="How satisfied are you with our service?",
        field_type="dropdown",
        is_required=True,
        order=1
    )
    satisfaction_field_id = satisfaction_field["id"]
    print(f"   ✓ Field added: {satisfaction_field['label']}")
    
    # Add options to dropdown
    print("\n7. Adding dropdown options...")
    options = [
        ("Very Satisfied", "very_satisfied", 1),
        ("Satisfied", "satisfied", 2),
        ("Neutral", "neutral", 3),
        ("Dissatisfied", "dissatisfied", 4),
        ("Very Dissatisfied", "very_dissatisfied", 5),
    ]
    
    for label, value, order in options:
        client.create_field_option(
            survey_id=survey_id,
            section_id=section2_id,
            field_id=satisfaction_field_id,
            label=label,
            value=value,
            order=order
        )
        print(f"   ✓ Option added: {label}")
    
    # Publish survey
    print("\n8. Publishing survey...")
    publish_result = client.publish_survey(survey_id)
    print(f"   ✓ {publish_result['detail']}")
    
    print(f"\n✅ Survey ready! ID: {survey_id}")
    return survey_id


def example_3_submit_survey(survey_id: str):
    """Example 3: Submit a survey response."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Submit Survey Response")
    print("="*60)
    
    client = SurveySubmissionClient(BASE_URL)
    
    # Start survey
    print("\n1. Starting survey...")
    start_result = client.start_survey(survey_id)
    print(f"   ✓ Session token: {start_result['session_token'][:20]}...")
    
    # Get first section
    print("\n2. Getting first section...")
    current_section_data = client.get_current_section()
    current_section = current_section_data["current_section"]
    section_id = current_section["section_id"]
    fields = current_section["fields"]
    print(f"   ✓ Section: {current_section['title']}")
    print(f"   ✓ Fields: {len(fields)}")
    
    # Submit first section
    print("\n3. Submitting first section...")
    answers = [
        {"field_id": fields[0]["field_id"], "value": "John Doe"},
        {"field_id": fields[1]["field_id"], "value": "john.doe@example.com"}
    ]
    submit_result = client.submit_section(section_id, answers)
    print(f"   ✓ {submit_result['message']}")
    print(f"   ✓ Progress: {submit_result['progress']['percentage']:.1f}%")
    
    # Get second section
    print("\n4. Getting second section...")
    current_section_data = client.get_current_section()
    current_section = current_section_data["current_section"]
    section_id = current_section["section_id"]
    fields = current_section["fields"]
    print(f"   ✓ Section: {current_section['title']}")
    
    # Submit second section
    print("\n5. Submitting second section...")
    answers = [
        {"field_id": fields[0]["field_id"], "value": "very_satisfied"}
    ]
    submit_result = client.submit_section(section_id, answers)
    print(f"   ✓ {submit_result['message']}")
    print(f"   ✓ Progress: {submit_result['progress']['percentage']:.1f}%")
    
    # Finish survey
    print("\n6. Finishing survey...")
    finish_result = client.finish_survey()
    print(f"   ✓ {finish_result.get('message', 'Survey completed successfully')}")
    if 'response_id' in finish_result:
        print(f"   ✓ Response ID: {finish_result['response_id']}")


def example_4_view_analytics(survey_id: str):
    """Example 4: View survey analytics."""
    print("\n" + "="*60)
    print("EXAMPLE 4: View Analytics")
    print("="*60)
    
    client = SurveyAPIClient(BASE_URL)
    try:
        client.login(USER_EMAIL, USER_PASSWORD)
    except requests.exceptions.HTTPError:
        # Register if login fails
        client.register(
            email=USER_EMAIL,
            password=USER_PASSWORD,
            first_name="Test",
            last_name="User"
        )
    
    # Get responses
    print("\n1. Getting responses...")
    responses = client.get_responses(survey_id)
    print(f"   ✓ Total responses: {responses['count']}")
    
    # Get analytics
    print("\n2. Getting analytics...")
    analytics = client.get_analytics(survey_id)
    print(f"   ✓ Total responses: {analytics['total_responses']}")
    print(f"   ✓ Completed: {analytics['completed_responses']}")
    print(f"   ✓ In progress: {analytics['in_progress_responses']}")
    print(f"   ✓ Completion rate: {analytics['completion_rate']:.2f}%")
    
    # Display field analytics
    if analytics.get('field_analytics'):
        print("\n3. Field-level analytics:")
        for field_stat in analytics['field_analytics']:
            print(f"\n   Field: {field_stat['field_label']}")
            if field_stat.get('response_distribution'):
                print("   Distribution:")
                for option, count in field_stat['response_distribution'].items():
                    print(f"     - {option}: {count}")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Survey Platform API - Python Examples")
    print("="*60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"User: {USER_EMAIL}")
    
    try:
        # Example 1: Authentication
        example_1_authentication_flow()
        
        # Example 2: Create survey
        survey_id = example_2_create_survey()
        
        # Wait a moment
        time.sleep(1)
        
        # Example 3: Submit response
        example_3_submit_survey(survey_id)
        
        # Wait for processing
        time.sleep(1)
        
        # Example 4: View analytics
        example_4_view_analytics(survey_id)
        
        print("\n" + "="*60)
        print("✅ All examples completed successfully!")
        print("="*60 + "\n")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()

