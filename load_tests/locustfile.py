"""
Load Testing for Survey Platform API.

Usage:
    1. Start Django: python manage.py runserver
    2. Run Locust:   locust -f load_tests/locustfile.py --host=http://localhost:8000
    3. Open:         http://localhost:8089

A test survey is auto-created on startup and cleaned up on shutdown.
"""
import os
import sys
import random

from locust import HttpUser, task, between, events

# =============================================================================
# DJANGO SETUP
# =============================================================================

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from surveys.models import Survey, Section, Field, FieldOption
from users.models import User

# =============================================================================
# CONFIGURATION
# =============================================================================

# Use existing survey ID, or leave empty to auto-create one
TEST_SURVEY_ID = os.getenv("TEST_SURVEY_ID", "")

# Task weights: higher = more frequent
WEIGHT_START_SURVEY = 3      # Starting new surveys
WEIGHT_GET_SECTION = 5       # Reading current section
WEIGHT_SUBMIT_SECTION = 5    # Submitting answers

# Wait time between tasks (seconds)
WAIT_TIME_MIN = 1
WAIT_TIME_MAX = 3

# Internal state
_created_survey_id = None

# =============================================================================
# TEST SURVEY SETUP & CLEANUP
# =============================================================================


def create_test_survey():
    """Create a test survey with sections and fields for load testing."""
    global _created_survey_id

    user, _ = User.objects.get_or_create(
        email='loadtest@example.com',
        defaults={'is_active': True}
    )

    survey, created = Survey.objects.get_or_create(
        title='Load Test Survey',
        defaults={
            'description': 'Auto-generated for load testing',
            'status': Survey.Status.PUBLISHED,
            'created_by': user
        }
    )

    if created:
        _create_survey_fields(survey)
        print(f"✓ Created test survey: {survey.id}")
    else:
        print(f"✓ Using existing test survey: {survey.id}")

    _created_survey_id = str(survey.id)
    return _created_survey_id


def _create_survey_fields(survey):
    """Create sections and fields for the test survey."""
    # Section 1: Basic Info
    section1 = Section.objects.create(survey=survey, title='Basic Info', order=1)

    Field.objects.create(
        section=section1, label='Name', field_type=Field.FieldType.TEXT,
        is_required=True, order=1
    )
    Field.objects.create(
        section=section1, label='Age', field_type=Field.FieldType.NUMBER,
        is_required=True, order=2
    )
    radio_field = Field.objects.create(
        section=section1, label='Preference', field_type=Field.FieldType.RADIO,
        is_required=True, order=3
    )
    for i, label in enumerate(['Option A', 'Option B', 'Option C'], 1):
        FieldOption.objects.create(
            field=radio_field, label=label, value=f'option{i}', order=i
        )

    # Section 2: Details
    section2 = Section.objects.create(survey=survey, title='Details', order=2)

    Field.objects.create(
        section=section2, label='Comments', field_type=Field.FieldType.TEXT,
        is_required=False, order=1
    )


def cleanup_test_survey():
    """Delete the auto-created test survey."""
    global _created_survey_id

    if not _created_survey_id:
        return

    try:
        survey = Survey.objects.filter(id=_created_survey_id).first()
        if survey and survey.title == 'Load Test Survey':
            survey.delete()
            print(f"✓ Cleaned up test survey: {_created_survey_id}")
            _created_survey_id = None
    except Exception as e:
        print(f"⚠ Could not clean up survey: {e}", file=sys.stderr)


def get_survey_id():
    """Get the survey ID for testing (env var or auto-created)."""
    return TEST_SURVEY_ID or _created_survey_id


# =============================================================================
# LOCUST EVENT HANDLERS
# =============================================================================


@events.init.add_listener
def on_init(environment, **kwargs):
    """Set up test survey when Locust starts."""
    if TEST_SURVEY_ID:
        print(f"\n{'='*50}")
        print(f"Using survey: {TEST_SURVEY_ID}")
        print(f"{'='*50}\n")
    else:
        try:
            survey_id = create_test_survey()
            print(f"\n{'='*50}")
            print(f"Test Survey ID: {survey_id}")
            print(f"{'='*50}\n")
        except Exception as e:
            print(f"ERROR: Could not create test survey: {e}", file=sys.stderr)
            sys.exit(1)


@events.test_stop.add_listener
def on_stop(environment, **kwargs):
    """Clean up test survey when Locust stops (only if auto-created)."""
    if not TEST_SURVEY_ID:
        cleanup_test_survey()


# =============================================================================
# ANSWER GENERATION
# =============================================================================


def generate_answer(field_type, options=None):
    """Generate a random test answer based on field type."""
    generators = {
        'TEXT': lambda: f"Answer {random.randint(1, 1000)}",
        'NUMBER': lambda: str(random.randint(1, 100)),
        'DATE': lambda: "2024-01-15",
        'RADIO': lambda: _get_first_option(options),
        'DROPDOWN': lambda: _get_first_option(options),
        'CHECKBOX': lambda: _get_checkbox_values(options),
    }
    # Normalize to uppercase to handle API returning lowercase field types
    normalized_type = field_type.upper() if field_type else ''
    return generators.get(normalized_type, lambda: "test")()


def _get_first_option(options):
    """Get the first option value from a list of options."""
    if options:
        return options[0].get('value') or options[0].get('label', 'option1')
    return 'option1'


def _get_checkbox_values(options):
    """Get first two option values for checkbox fields."""
    if options and len(options) >= 2:
        return [opt.get('value') or opt.get('label') for opt in options[:2]]
    return ['option1', 'option2']


# =============================================================================
# LOAD TEST USER
# =============================================================================


class SurveyUser(HttpUser):
    """
    Simulates a user completing a survey.

    Flow: Start survey -> Get section -> Submit answers -> Repeat
    """
    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)

    def on_start(self):
        """Initialize user state."""
        self.survey_id = get_survey_id()
        self.session_token = None

    @task(WEIGHT_START_SURVEY)
    def start_survey(self):
        """Start a new survey session."""
        if not self.survey_id:
            return

        response = self.client.post(
            f"/api/v1/surveys/{self.survey_id}/submissions/start/",
            name="Start Survey"
        )

        if response.status_code == 201:
            self.session_token = response.json().get('session_token')
        elif response.status_code == 404:
            self.survey_id = None

    @task(WEIGHT_GET_SECTION)
    def get_current_section(self):
        """Get the current section to complete."""
        if not self._ensure_session():
            return

        response = self.client.get(
            "/api/v1/submissions/current-section/",
            headers={"X-Session-Token": self.session_token},
            name="Get Current Section"
        )

        if response.status_code == 404:
            self.session_token = None

    @task(WEIGHT_SUBMIT_SECTION)
    def submit_section(self):
        """Submit answers for the current section."""
        if not self._ensure_session():
            return

        section_data = self._fetch_current_section()
        if not section_data:
            return

        answers = self._build_answers(section_data.get('fields', []))
        if not answers:
            return

        self._submit_answers(section_data['section_id'], answers)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _ensure_session(self):
        """Ensure we have a valid session, starting one if needed."""
        if not self.survey_id:
            return False
        if not self.session_token:
            self.start_survey()
        return bool(self.session_token)

    def _fetch_current_section(self):
        """Fetch current section data. Returns None if survey is complete."""
        response = self.client.get(
            "/api/v1/submissions/current-section/",
            headers={"X-Session-Token": self.session_token},
            name="Get Section (for submit)"
        )

        if response.status_code != 200:
            self.session_token = None
            return None

        current_section = response.json().get('current_section')
        if not current_section:
            self.session_token = None  # Survey complete, reset for new one
            return None

        return current_section

    def _build_answers(self, fields):
        """Build answer payload from field definitions."""
        answers = []
        for field in fields:
            if not field.get('is_required'):
                continue
            if not field.get('field_id'):
                continue

            answers.append({
                "field_id": str(field['field_id']),
                "value": generate_answer(field['field_type'], field.get('options'))
            })
        return answers

    def _submit_answers(self, section_id, answers):
        """Submit answers to the API."""
        with self.client.post(
            "/api/v1/submissions/submit-section/",
            json={"section_id": str(section_id), "answers": answers},
            headers={"X-Session-Token": self.session_token},
            name="Submit Section",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 400:
                error = self._extract_error(response)
                response.failure(f"Validation: {error}")
            else:
                response.failure(f"HTTP {response.status_code}")

    def _extract_error(self, response):
        """Extract error message from validation response."""
        try:
            errors = response.json().get('errors', {})
            if errors:
                key, val = next(iter(errors.items()))
                return f"{key}: {val}"
        except Exception:
            pass
        return "unknown"
