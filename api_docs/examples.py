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

def complete_survey_workflow():
    """
    Complete End-to-End Survey Workflow
    
    This example demonstrates:
    1. User registration/login
    2. Creating a survey with multiple sections
    3. Adding various field types (text, dropdown, radio)
    4. Adding conditional rules (show/hide based on answers)
    5. Publishing the survey
    6. Anonymous user submitting a response
    7. Viewing analytics as the survey owner
    """
    print("\n" + "="*70)
    print("COMPLETE SURVEY WORKFLOW - End-to-End Example")
    print("="*70)
    
    # =========================================================================
    # PHASE 1: AUTHENTICATION
    # =========================================================================
    print("\n" + "-"*70)
    print("PHASE 1: USER AUTHENTICATION")
    print("-"*70)
    
    admin_client = SurveyAPIClient(BASE_URL)
    
    print("\n[1.1] Registering/Logging in user...")
    try:
        login_result = admin_client.login(USER_EMAIL, USER_PASSWORD)
        print(f"      ✓ Logged in as: {login_result['user']['email']}")
    except requests.exceptions.HTTPError:
        print("      → User doesn't exist, registering...")
        register_result = admin_client.register(
            email=USER_EMAIL,
            password=USER_PASSWORD,
            first_name="Survey",
            last_name="Admin"
        )
        print(f"      ✓ Registered: {register_result['user']['email']}")
    
    print("\n[1.2] Fetching user profile...")
    profile = admin_client.get_profile()
    print(f"      ✓ User: {profile['first_name']} {profile['last_name']}")
    print(f"      ✓ Roles: {profile.get('roles', ['admin'])}")
    
    print("\n[1.3] Fetching user organizations...")
    orgs = admin_client.list_organizations()
    if orgs.get('results'):
        org = orgs['results'][0]
        print(f"      ✓ Organization: {org['name']} (ID: {org['id']})")
        organization_id = org['id']
    else:
        raise Exception("No organization found. User should have a default organization.")
    
    # =========================================================================
    # PHASE 2: CREATE SURVEY STRUCTURE
    # =========================================================================
    print("\n" + "-"*70)
    print("PHASE 2: CREATE SURVEY STRUCTURE")
    print("-"*70)
    
    # Create Survey
    print("\n[2.1] Creating survey...")
    survey = admin_client.create_survey(
        title="Employee Satisfaction Survey 2024",
        description="Annual survey to understand employee satisfaction and gather feedback",
        organization_id=organization_id
    )
    survey_id = survey["id"]
    print(f"      ✓ Survey created: {survey['title']}")
    print(f"      ✓ Survey ID: {survey_id}")
    print(f"      ✓ Organization: {survey.get('organization_name', 'N/A')}")
    
    # -------------------------------------------------------------------------
    # Section 1: Basic Information
    # -------------------------------------------------------------------------
    print("\n[2.2] Creating Section 1: Basic Information...")
    section1 = admin_client.create_section(
        survey_id=survey_id,
        title="Basic Information",
        description="Tell us about yourself",
        order=1
    )
    section1_id = section1["id"]
    print(f"      ✓ Section created: {section1['title']}")
    
    # Field: Name
    print("\n[2.3] Adding fields to Section 1...")
    name_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section1_id,
        label="Your Name",
        field_type="text",
        is_required=True,
        order=1
    )
    print(f"      ✓ Field: {name_field['label']} (text, required)")
    
    # Field: Department (dropdown)
    department_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section1_id,
        label="Department",
        field_type="dropdown",
        is_required=True,
        order=2
    )
    department_field_id = department_field["id"]
    print(f"      ✓ Field: {department_field['label']} (dropdown, required)")
    
    # Add department options
    departments = [
        ("Engineering", "engineering", 1),
        ("Sales", "sales", 2),
        ("Marketing", "marketing", 3),
        ("Human Resources", "hr", 4),
        ("Finance", "finance", 5),
    ]
    for label, value, order in departments:
        admin_client.create_field_option(
            survey_id=survey_id,
            section_id=section1_id,
            field_id=department_field_id,
            label=label,
            value=value,
            order=order
        )
    print(f"      ✓ Added {len(departments)} department options")
    
    # Field: Employment Type (radio)
    employment_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section1_id,
        label="Employment Type",
        field_type="radio",
        is_required=True,
        order=3
    )
    employment_field_id = employment_field["id"]
    print(f"      ✓ Field: {employment_field['label']} (radio, required)")
    
    # Add employment options
    employment_types = [
        ("Full-time", "full_time", 1),
        ("Part-time", "part_time", 2),
        ("Contract", "contract", 3),
    ]
    for label, value, order in employment_types:
        admin_client.create_field_option(
            survey_id=survey_id,
            section_id=section1_id,
            field_id=employment_field_id,
            label=label,
            value=value,
            order=order
        )
    print(f"      ✓ Added {len(employment_types)} employment type options")
    
    # -------------------------------------------------------------------------
    # Section 2: Job Satisfaction
    # -------------------------------------------------------------------------
    print("\n[2.4] Creating Section 2: Job Satisfaction...")
    section2 = admin_client.create_section(
        survey_id=survey_id,
        title="Job Satisfaction",
        description="Rate your satisfaction with various aspects of your job",
        order=2
    )
    section2_id = section2["id"]
    print(f"      ✓ Section created: {section2['title']}")
    
    print("\n[2.5] Adding fields to Section 2...")
    
    # Field: Overall Satisfaction
    satisfaction_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section2_id,
        label="Overall Job Satisfaction",
        field_type="radio",
        is_required=True,
        order=1
    )
    satisfaction_field_id = satisfaction_field["id"]
    print(f"      ✓ Field: {satisfaction_field['label']} (radio, required)")
    
    satisfaction_options = [
        ("Very Satisfied", "very_satisfied", 1),
        ("Satisfied", "satisfied", 2),
        ("Neutral", "neutral", 3),
        ("Dissatisfied", "dissatisfied", 4),
        ("Very Dissatisfied", "very_dissatisfied", 5),
    ]
    for label, value, order in satisfaction_options:
        admin_client.create_field_option(
            survey_id=survey_id,
            section_id=section2_id,
            field_id=satisfaction_field_id,
            label=label,
            value=value,
            order=order
        )
    print(f"      ✓ Added {len(satisfaction_options)} satisfaction options")
    
    # Field: Would Recommend
    recommend_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section2_id,
        label="Would you recommend this company as a good place to work?",
        field_type="radio",
        is_required=True,
        order=2
    )
    recommend_field_id = recommend_field["id"]
    print(f"      ✓ Field: {recommend_field['label']} (radio, required)")
    
    yes_no_options = [
        ("Yes", "yes", 1),
        ("No", "no", 2),
        ("Maybe", "maybe", 3),
    ]
    for label, value, order in yes_no_options:
        admin_client.create_field_option(
            survey_id=survey_id,
            section_id=section2_id,
            field_id=recommend_field_id,
            label=label,
            value=value,
            order=order
        )
    print(f"      ✓ Added {len(yes_no_options)} recommendation options")
    
    # -------------------------------------------------------------------------
    # Section 3: Improvement Feedback (Conditional - shown if dissatisfied)
    # -------------------------------------------------------------------------
    print("\n[2.6] Creating Section 3: Improvement Feedback (Conditional)...")
    section3 = admin_client.create_section(
        survey_id=survey_id,
        title="Areas for Improvement",
        description="Help us understand what we can do better",
        order=3
    )
    section3_id = section3["id"]
    print(f"      ✓ Section created: {section3['title']}")
    
    print("\n[2.7] Adding fields to Section 3...")
    
    # Field: What needs improvement
    improvement_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section3_id,
        label="What areas need the most improvement?",
        field_type="checkbox",
        is_required=False,
        order=1
    )
    improvement_field_id = improvement_field["id"]
    print(f"      ✓ Field: {improvement_field['label']} (checkbox)")
    
    improvement_options = [
        ("Work-Life Balance", "work_life_balance", 1),
        ("Compensation", "compensation", 2),
        ("Career Growth", "career_growth", 3),
        ("Management", "management", 4),
        ("Team Collaboration", "team_collaboration", 5),
        ("Tools & Resources", "tools_resources", 6),
    ]
    for label, value, order in improvement_options:
        admin_client.create_field_option(
            survey_id=survey_id,
            section_id=section3_id,
            field_id=improvement_field_id,
            label=label,
            value=value,
            order=order
        )
    print(f"      ✓ Added {len(improvement_options)} improvement options")
    
    # Field: Additional Comments
    comments_field = admin_client.create_field(
        survey_id=survey_id,
        section_id=section3_id,
        label="Additional Comments or Suggestions",
        field_type="text",
        is_required=False,
        order=2
    )
    print(f"      ✓ Field: {comments_field['label']} (text, optional)")
    
    # -------------------------------------------------------------------------
    # Add Conditional Rule: Show Section 3 if dissatisfied
    # -------------------------------------------------------------------------
    print("\n[2.8] Creating conditional rule...")
    print("      → Rule: Show 'Areas for Improvement' section when satisfaction is 'Dissatisfied' or 'Very Dissatisfied'")
    
    # Note: In a real implementation, you would create conditional rules here
    # The API endpoint would be: POST /api/v1/surveys/{survey_id}/rules/
    # For now, we'll skip this as it requires the rule creation endpoint
    print("      ⚠ Conditional rules require the rules endpoint (skipped for this example)")
    
    # =========================================================================
    # PHASE 3: PUBLISH SURVEY
    # =========================================================================
    print("\n" + "-"*70)
    print("PHASE 3: PUBLISH SURVEY")
    print("-"*70)
    
    print("\n[3.1] Publishing survey...")
    publish_result = admin_client.publish_survey(survey_id)
    print(f"      ✓ {publish_result['detail']}")
    print(f"      ✓ Survey is now available for submissions!")
    
    # =========================================================================
    # PHASE 4: ANONYMOUS USER SUBMITS RESPONSE
    # =========================================================================
    print("\n" + "-"*70)
    print("PHASE 4: ANONYMOUS USER SUBMITS RESPONSE")
    print("-"*70)
    
    submission_client = SurveySubmissionClient(BASE_URL)
    
    print("\n[4.1] Starting survey session (anonymous)...")
    start_result = submission_client.start_survey(survey_id)
    print(f"      ✓ Session started!")
    print(f"      ✓ Session Token: {start_result['session_token'][:16]}...")
    
    # Submit Section 1
    print("\n[4.2] Getting Section 1...")
    section_data = submission_client.get_current_section()
    current_section = section_data["current_section"]
    print(f"      ✓ Section: {current_section['title']}")
    print(f"      ✓ Fields: {len(current_section['fields'])}")
    
    # Display fields
    fields = current_section["fields"]
    for f in fields:
        print(f"        - {f['label']} ({f['field_type']})")
    
    print("\n[4.3] Submitting Section 1 answers...")
    section1_answers = [
        {"field_id": fields[0]["field_id"], "value": "Alice Johnson"},
        {"field_id": fields[1]["field_id"], "value": "engineering"},
        {"field_id": fields[2]["field_id"], "value": "full_time"},
    ]
    result = submission_client.submit_section(current_section["section_id"], section1_answers)
    print(f"      ✓ {result['message']}")
    print(f"      ✓ Progress: {result['progress']['percentage']:.1f}%")
    
    # Submit Section 2
    print("\n[4.4] Getting Section 2...")
    section_data = submission_client.get_current_section()
    current_section = section_data["current_section"]
    print(f"      ✓ Section: {current_section['title']}")
    
    fields = current_section["fields"]
    for f in fields:
        print(f"        - {f['label']} ({f['field_type']})")
    
    print("\n[4.5] Submitting Section 2 answers...")
    section2_answers = [
        {"field_id": fields[0]["field_id"], "value": "satisfied"},
        {"field_id": fields[1]["field_id"], "value": "yes"},
    ]
    result = submission_client.submit_section(current_section["section_id"], section2_answers)
    print(f"      ✓ {result['message']}")
    print(f"      ✓ Progress: {result['progress']['percentage']:.1f}%")
    
    # Submit Section 3 (optional feedback)
    print("\n[4.6] Getting Section 3...")
    section_data = submission_client.get_current_section()
    
    if section_data.get("current_section"):
        current_section = section_data["current_section"]
        print(f"      ✓ Section: {current_section['title']}")
        
        fields = current_section["fields"]
        for f in fields:
            print(f"        - {f['label']} ({f['field_type']})")
        
        print("\n[4.7] Submitting Section 3 answers...")
        section3_answers = [
            {"field_id": fields[0]["field_id"], "value": ["career_growth", "tools_resources"]},
            {"field_id": fields[1]["field_id"], "value": "Great company overall! Would love more learning opportunities."},
        ]
        result = submission_client.submit_section(current_section["section_id"], section3_answers)
        print(f"      ✓ {result['message']}")
        print(f"      ✓ Progress: {result['progress']['percentage']:.1f}%")
    else:
        print("      ✓ No more sections (survey complete)")
    
    # Finish Survey
    print("\n[4.8] Finishing survey submission...")
    finish_result = submission_client.finish_survey()
    print(f"      ✓ {finish_result.get('message', 'Survey completed!')}")
    print(f"      ✓ Completed at: {finish_result.get('completed_at', 'N/A')}")
    
    # =========================================================================
    # PHASE 5: VIEW ANALYTICS (AS SURVEY OWNER)
    # =========================================================================
    print("\n" + "-"*70)
    print("PHASE 5: VIEW ANALYTICS (AS SURVEY OWNER)")
    print("-"*70)
    
    print("\n[5.1] Fetching survey responses...")
    responses = admin_client.get_responses(survey_id)
    print(f"      ✓ Total responses: {responses.get('count', len(responses.get('results', [])))}")
    
    if responses.get('results'):
        for resp in responses['results'][:3]:  # Show first 3
            print(f"        - Response {resp['id'][:8]}... | Status: {resp['status']} | Started: {resp['started_at'][:10]}")
    
    print("\n[5.2] Fetching survey analytics...")
    try:
        analytics = admin_client.get_analytics(survey_id)
        print(f"      ✓ Total Responses: {analytics['total_responses']}")
        print(f"      ✓ Completed: {analytics['completed_responses']}")
        print(f"      ✓ In Progress: {analytics['in_progress_responses']}")
        print(f"      ✓ Completion Rate: {analytics['completion_rate']:.1f}%")
        
        if analytics.get('average_completion_time_seconds'):
            avg_time = analytics['average_completion_time_seconds']
            print(f"      ✓ Avg. Completion Time: {avg_time:.1f} seconds")
    except Exception as e:
        print(f"      ⚠ Analytics error: {e}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*70)
    print("WORKFLOW COMPLETE!")
    print("="*70)
    print(f"""
Summary:
  • Survey ID: {survey_id}
  • Survey Title: Employee Satisfaction Survey 2024
  • Sections: 3 (Basic Info, Job Satisfaction, Improvement Feedback)
  • Total Fields: 7
  • Status: Published
  • Responses Collected: 1

API Endpoints Used:
  • POST /api/v1/auth/register/ - Register user
  • POST /api/v1/auth/login/ - Login user
  • GET  /api/v1/auth/me/ - Get profile
  • GET  /api/v1/organizations/ - List organizations
  • POST /api/v1/surveys/ - Create survey
  • POST /api/v1/surveys/{{id}}/sections/ - Create section
  • POST /api/v1/surveys/{{id}}/sections/{{id}}/fields/ - Create field
  • POST /api/v1/surveys/{{id}}/sections/{{id}}/fields/{{id}}/options/ - Create option
  • POST /api/v1/surveys/{{id}}/publish/ - Publish survey
  • POST /api/v1/surveys/{{id}}/submissions/start/ - Start submission
  • GET  /api/v1/submissions/current-section/ - Get current section
  • POST /api/v1/submissions/submit-section/ - Submit answers
  • POST /api/v1/submissions/finish/ - Finish submission
  • GET  /api/v1/surveys/{{id}}/responses/ - List responses
  • GET  /api/v1/surveys/{{id}}/responses/analytics/ - Get analytics
""")
    
    return survey_id


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
    """Run the complete survey workflow example."""
    print("\n" + "="*70)
    print("Survey Platform API - Python Integration Examples")
    print("="*70)
    print(f"\nBase URL: {BASE_URL}")
    print(f"User: {USER_EMAIL}")
    print("\nThis example demonstrates the complete survey lifecycle:")
    print("  1. User authentication (register/login)")
    print("  2. Survey creation with sections, fields, and options")
    print("  3. Anonymous user submitting a response")
    print("  4. Survey owner viewing analytics")
    
    try:
        # Run the complete workflow
        survey_id = complete_survey_workflow()
        
        print("\n" + "="*70)
        print("✅ EXAMPLE COMPLETED SUCCESSFULLY!")
        print("="*70 + "\n")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        try:
            print(f"Response: {e.response.text}")
        except:
            pass
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def run_individual_examples():
    """Run the original individual examples."""
    print("\n" + "="*60)
    print("Running Individual Examples")
    print("="*60)
    
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

