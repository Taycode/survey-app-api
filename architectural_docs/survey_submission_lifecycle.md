# Survey Submission Lifecycle Documentation

## Table of Contents
1. [Product Overview](#product-overview)
2. [User Journey (Product Perspective)](#user-journey-product-perspective)
3. [Technical Architecture (Engineering Perspective)](#technical-architecture-engineering-perspective)
4. [API Flow Diagram](#api-flow-diagram)
5. [State Management](#state-management)
6. [Conditional Logic & Dependencies](#conditional-logic--dependencies)
7. [Navigation & Editing](#navigation--editing)
8. [Error Handling](#error-handling)
9. [Security Considerations](#security-considerations)

---

## Product Overview

### What is the Survey Submission Lifecycle?

The Survey Submission Lifecycle is the complete journey a user takes from discovering a survey to completing it. This system supports:

- **Multi-step surveys** organized into logical sections
- **Dynamic content** that adapts based on user responses
- **Resumable sessions** allowing users to pause and continue later
- **Navigation** enabling users to review and edit previous answers
- **Real-time validation** ensuring data quality and completeness

### Key Product Features

1. **Anonymous Access**: Users can start surveys without authentication
2. **Session Management**: Secure token-based sessions for resumable responses
3. **Progressive Disclosure**: Sections appear based on conditional logic
4. **Smart Validation**: Field-level and cross-section validation
5. **Progress Tracking**: Real-time progress indicators
6. **Data Integrity**: Encrypted storage for sensitive information

---

## User Journey (Product Perspective)

### Phase 1: Survey Discovery & Initiation

**User Action**: User receives a survey link or accesses it through a platform

**What Happens**:
1. User clicks the survey link
2. Frontend requests survey details to display title, description, estimated time
3. User clicks "Start Survey" button
4. Frontend calls `POST /api/v1/surveys/{survey_id}/submissions/start/` (survey ID in URL)
5. System creates a new session and generates a unique session token
6. Frontend stores the session token and calls `GET /current-section/` to get the first section

**Product Goals**:
- Zero-friction entry (no registration required)
- Clear expectations (time estimate, number of sections)
- Secure session creation

### Phase 2: Section-by-Section Completion

**User Action**: User answers questions section by section

**What Happens**:
1. User views current section with all visible fields
2. User fills in answers (text, numbers, dates, selections)
3. User clicks "Next" or "Continue"
4. System validates answers (required fields, data types, conditional rules)
5. If valid: Answers are saved, progress updates, next section appears
6. If invalid: Errors are shown, user corrects and resubmits
7. Process repeats until all visible sections are completed

**Product Goals**:
- Smooth progression through survey
- Clear validation feedback
- Automatic saving prevents data loss
- Conditional logic creates personalized experience

### Phase 3: Conditional Logic Activation

**User Action**: User's answers trigger conditional rules

**What Happens**:
1. User answers a question (e.g., "Are you a customer?" → "Yes")
2. System evaluates conditional rules based on this answer
3. New sections or fields become visible
4. Field options may change based on dependencies
5. User sees new content appear dynamically

**Product Goals**:
- Relevant questions only (reduces survey fatigue)
- Personalized experience
- Logical flow based on user profile

### Phase 4: Navigation & Editing

**User Action**: User wants to review or change previous answers

**What Happens**:
1. User clicks "Back" or selects a previous section from navigation
2. System retrieves the section with pre-filled answers
3. User edits answers
4. User submits updated answers
5. System re-evaluates conditional logic (sections may appear/disappear)
6. User continues from updated state

**Product Goals**:
- User control and flexibility
- Ability to correct mistakes
- Transparent editing process

### Phase 5: Completion

**User Action**: User completes final section

**What Happens**:
1. User submits last section
2. System validates final answers
3. System marks survey as complete
4. User sees completion screen with thank you message
5. Session token remains valid for viewing results (if applicable)

**Product Goals**:
- Clear completion confirmation
- Sense of accomplishment
- Option to review submitted data

---

## Technical Architecture (Engineering Perspective)

### System Components

```
┌─────────────┐
│   Frontend  │
│  (React/Vue)│
└──────┬──────┘
       │ HTTP/REST
       │
┌──────▼─────────────────────────────────────────┐
│         Django REST Framework API              │
│  ┌──────────────────────────────────────────┐  │
│  │  SubmissionViewSet                       │  │
│  │  - start_survey()                        │  │
│  │  - get_current_section()                 │  │
│  │  - submit_section()                      │  │
│  │  - get_section() [navigation]            │  │
│  │  - get_survey_details()                  │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │  ConditionalLogicService                 │  │
│  │  - evaluate_rule()                       │  │
│  │  - get_visible_sections()                │  │
│  │  - get_visible_fields()                  │  │
│  │  - get_field_options()                   │  │
│  │  - validate_submission()                 │  │
│  └──────────────────────────────────────────┘  │
└──────┬─────────────────────────────────────────┘
       │
┌──────▼─────────────────────────────────────────┐
│            Database Layer                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Survey   │  │ SurveyResponse│ │FieldAnswer│ │
│  │ Section  │  │              │  │          │ │
│  │ Field    │  │              │  │          │ │
│  │ Rule     │  │              │  │          │ │
│  └──────────┘  └──────────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
```

### API Endpoints

#### 1. Start Survey Session
**Endpoint**: `POST /api/v1/surveys/{survey_id}/submissions/start/`

**Purpose**: Initialize a new survey response session

**URL Parameters**:
- `survey_id` (UUID, path parameter): The ID of the survey to start. Survey must be published.

**Request Body**: None (empty body)

**Response**:
```json
{
  "session_token": "uuid"
}
```

**Technical Details**:
- Creates `SurveyResponse` record with `IN_PROGRESS` status
- Generates UUID session token
- Stores IP address and user agent for analytics
- No authentication required (anonymous access)
- Survey ID is passed in URL path, not request body

**Database Operations**:
- `INSERT INTO SurveyResponse`

---

#### 2. Get Current Section
**Endpoint**: `GET /api/v1/submissions/current-section/`

**Purpose**: Retrieve the next section the user should complete

**Headers**: `X-Session-Token: uuid`

**Response**:
```json
{
  "current_section": {
    "section_id": "uuid",
    "title": "Section Title",
    "order": 1,
    "fields": [
      {
        "field_id": "uuid",
        "label": "Question?",
        "field_type": "text",
        "is_required": true,
        "options": [{"label": "Option", "value": "opt"}]
      }
    ]
  },
  "is_complete": false,
  "progress": {
    "sections_completed": 1,
    "total_sections": 3,
    "sections_remaining": 2,
    "percentage": 33
  }
}
```

**Technical Details**:
- Validates session token
- Evaluates conditional rules to determine visible sections
- Finds first incomplete visible section
- Filters field options based on dependencies
- Calculates progress metrics

**Database Operations**:
- `SELECT SurveyResponse WHERE session_token = ?`
- `SELECT Section WHERE survey_id = ? ORDER BY order`
- `SELECT FieldAnswer WHERE response_id = ?` (for progress calculation)
- `SELECT ConditionalRule WHERE survey_id = ?`
- `SELECT FieldDependency WHERE field_id = ?`

**Service Layer**:
- `ConditionalLogicService.get_current_section()`
- `ConditionalLogicService.get_visible_sections()`
- `ConditionalLogicService.get_visible_fields()`
- `ConditionalLogicService.get_field_options()`

---

#### 3. Submit Section
**Endpoint**: `POST /api/v1/submissions/submit-section/`

**Purpose**: Save answers for a section and validate against business rules

**Headers**: `X-Session-Token: uuid`

**Request**:
```json
{
  "section_id": "uuid",
  "answers": [
    {"field_id": "uuid", "value": "answer"},
    {"field_id": "uuid", "value": 42}
  ]
}
```

**Response (Success)**:
```json
{
  "status": "success",
  "message": "Section saved successfully",
  "is_complete": false,
  "progress": {
    "sections_completed": 2,
    "total_sections": 3,
    "sections_remaining": 1,
    "percentage": 66
  }
}
```

**Response (Validation Error)**:
```json
{
  "status": "error",
  "errors": {
    "field_id": "This field is required.",
    "field_id_2": "Value 'invalid' is not a valid option."
  }
}
```

**Technical Details**:
- Validates session token and section ownership
- Checks section/field visibility (conditional logic)
- Validates required fields
- Validates data types and constraints
- Validates option values (for dropdowns/radios)
- Saves answers using `update_or_create()` (supports editing)
- Updates progress tracking
- Re-evaluates conditional logic after save

**Database Operations**:
- `SELECT SurveyResponse WHERE session_token = ?`
- `SELECT Section WHERE id = ? AND survey_id = ?`
- `SELECT Field WHERE section_id = ?`
- `SELECT FieldOption WHERE field_id = ? AND value = ?` (validation)
- `INSERT/UPDATE FieldAnswer` (for each answer)
- `UPDATE SurveyResponse SET last_section = ?, updated_at = ?`

**Service Layer**:
- `ConditionalLogicService.validate_submission()`
- `ConditionalLogicService.get_survey_progress()`
- `ConditionalLogicService.is_survey_complete()`

**Validation Layers**:
1. **Session Validation**: Token exists and response is IN_PROGRESS
2. **Section Validation**: Section belongs to survey
3. **Visibility Validation**: Section and fields are visible (conditional logic)
4. **Required Field Validation**: All required fields have values
5. **Type Validation**: Values match field types (number, date, etc.)
6. **Option Validation**: Selected options exist for dropdown/radio fields
7. **Dependency Validation**: Selected options are valid based on dependencies

---

#### 4. Get Specific Section (Navigation)
**Endpoint**: `GET /api/v1/submissions/sections/{section_id}/`

**Purpose**: Retrieve a specific section with pre-filled answers for editing

**Headers**: `X-Session-Token: uuid`

**Response**:
```json
{
  "section": {
    "section_id": "uuid",
    "title": "Section Title",
    "order": 1,
    "fields": [
      {
        "field_id": "uuid",
        "label": "Question?",
        "field_type": "text",
        "is_required": true,
        "current_value": "previous answer",  // Pre-filled!
        "options": [...]
      }
    ]
  },
  "is_editable": true,
  "progress": {
    "sections_completed": 2,
    "total_sections": 3,
    "percentage": 66
  }
}
```

**Technical Details**:
- Validates session token
- Checks section visibility (cannot edit hidden sections)
- Retrieves existing answers for pre-filling
- Returns section with `current_value` for each field

**Database Operations**:
- `SELECT SurveyResponse WHERE session_token = ?`
- `SELECT Section WHERE id = ? AND survey_id = ?`
- `SELECT FieldAnswer WHERE response_id = ? AND field_id = ?`
- `SELECT ConditionalRule WHERE section_id = ?` (visibility check)

**Service Layer**:
- `ConditionalLogicService.get_section()`
- `ConditionalLogicService.get_section_with_fields(include_current_values=True)`

---

#### 5. Get Survey Details
**Endpoint**: `GET /api/v1/submissions/survey-details/`

**Purpose**: Get overview of survey state, progress, and metadata

**Headers**: `X-Session-Token: uuid`

**Response**:
```json
{
  "survey": {
    "id": "uuid",
    "title": "Survey Title",
    "description": "Survey description"
  },
  "status": "IN_PROGRESS",
  "progress": {
    "sections_completed": 2,
    "total_sections": 3,
    "sections_remaining": 1,
    "percentage": 66
  },
  "started_at": "2024-01-01T10:00:00Z",
  "last_updated": "2024-01-01T10:15:00Z",
  "completed_at": null
}
```

**Technical Details**:
- Provides high-level survey state
- Useful for resume flow or progress display
- Does not include field-level details

---

### State Machine

```
┌─────────────┐
│   NOT_STARTED│
└──────┬──────┘
       │ POST /start/
       ▼
┌─────────────┐
│ IN_PROGRESS │◄──────────────┐
└──────┬──────┘                │
       │                       │
       │ GET /current-section/ │
       │ POST /submit-section/ │
       │                       │
       │                       │
       │ (all sections done)   │
       ▼                       │
┌─────────────┐                │
│  COMPLETED  │                │
└─────────────┘                │
                                │
                    (navigation/edit)
                                │
                                └─────────────┘
```

**States**:
- `NOT_STARTED`: Survey not initiated
- `IN_PROGRESS`: Survey started, sections being completed
- `COMPLETED`: All sections submitted

**Transitions**:
- `NOT_STARTED` → `IN_PROGRESS`: `POST /surveys/{id}/submissions/start/`
- `IN_PROGRESS` → `IN_PROGRESS`: `POST /submit-section/` (partial completion)
- `IN_PROGRESS` → `COMPLETED`: `POST /submit-section/` (last section)
- `COMPLETED` → `IN_PROGRESS`: Navigation/edit (if allowed)

---

## API Flow Diagram

### Happy Path: Complete Survey Flow

```
Frontend                          Backend                          Database
   │                                │                                │
   │ POST /surveys/{id}/submissions/start/│                         │
   │ (no body)                      │                                │
   ├───────────────────────────────>│                                │
   │                                │ Create SurveyResponse          │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │ {session_token}                │                                │
   │<───────────────────────────────┤                                │
   │                                │                                │
   │ GET /current-section/           │                                │
   │ X-Session-Token                │                                │
   ├───────────────────────────────>│                                │
   │                                │ Get visible sections           │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │ Get current section            │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │ {current_section, progress}    │                                │
   │<───────────────────────────────┤                                │
   │                                │                                │
   │ POST /submit-section/          │                                │
   │ {section_id, answers}          │                                │
   ├───────────────────────────────>│                                │
   │                                │ Validate answers               │
   │                                │ Save answers                   │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │ Update progress                │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │ {status, is_complete, progress}│                                │
   │<───────────────────────────────┤                                │
   │                                │                                │
   │ [If not complete]              │                                │
   │ GET /current-section/          │                                │
   │ [Repeat until complete]        │                                │
   │                                │                                │
   │ [When complete]                │                                │
   │ Show completion screen         │                                │
   │                                │                                │
```

### Navigation Flow: Going Back to Edit

```
Frontend                          Backend                          Database
   │                                │                                │
   │ GET /sections/{section_id}/    │                                │
   │ X-Session-Token                │                                │
   ├───────────────────────────────>│                                │
   │                                │ Get section                    │
   │                                ├───────────────────────────────>│
   │                                │ Get existing answers           │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │ {section with pre-filled}      │                                │
   │<───────────────────────────────┤                                │
   │                                │                                │
   │ User edits answers             │                                │
   │                                │                                │
   │ POST /submit-section/          │                                │
   │ {section_id, updated_answers}  │                                │
   ├───────────────────────────────>│                                │
   │                                │ Update answers                 │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │ Re-evaluate conditional logic   │
   │                                ├───────────────────────────────>│
   │                                │<───────────────────────────────┤
   │                                │                                │
   │ {status, progress}             │                                │
   │<───────────────────────────────┤                                │
   │                                │                                │
   │ GET /current-section/          │                                │
   │ [Continue from updated state]  │                                │
   │                                │                                │
```

---

## State Management

### SurveyResponse Model States

```python
class Status(models.TextChoices):
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    ABANDONED = 'ABANDONED', 'Abandoned'  # Future: timeout-based
```

### Progress Calculation

**Formula**:
```
sections_completed = COUNT(DISTINCT FieldAnswer.field.section WHERE response_id = ?)
total_sections = COUNT(Section WHERE survey_id = ? AND visible = true)
sections_remaining = total_sections - sections_completed
percentage = (sections_completed / total_sections) * 100
```

**Note**: Only visible sections count toward progress. Hidden sections are excluded.

### Session Token Lifecycle

1. **Generation**: Created on `POST /start/` as UUID v4
2. **Validation**: Required in `X-Session-Token` header for all subsequent requests
3. **Scope**: One token per `SurveyResponse` record
4. **Expiration**: Currently no expiration (future: configurable timeout)
5. **Security**: Token is cryptographically random, not guessable

---

## Conditional Logic & Dependencies

### Conditional Rules

**Purpose**: Show/hide sections or fields based on previous answers

**Example Rule**:
```
IF Field "Are you a customer?" = "Yes"
THEN Show Section "Customer Details"
```

**Technical Implementation**:
- `ConditionalRule` model stores rule definitions
- `evaluate_rule()` method evaluates rule against current answers
- Rules support: `equals`, `not_equals`, `contains`, `greater_than`, `less_than`

**Evaluation Flow**:
1. Get all answers for survey response
2. For each rule, evaluate condition against answers
3. If condition true → mark target section/field as visible
4. If condition false → mark target section/field as hidden

### Field Dependencies

**Purpose**: Dynamically filter options based on other field answers

**Example Dependency**:
```
IF Field "Country" = "USA"
THEN Field "State" options = ["California", "New York", ...]
ELSE Field "State" options = []
```

**Technical Implementation**:
- `FieldDependency` model stores dependency rules
- `get_field_options()` filters options based on dependencies
- Options are filtered in real-time during `get_current_section()`

**Evaluation Flow**:
1. Get all answers for survey response
2. For each field dependency, check trigger field answer
3. Filter options based on dependency rule
4. Return filtered options to frontend

### Validation Order

1. **Section Visibility**: Is section visible? (conditional rules)
2. **Field Visibility**: Are fields visible? (conditional rules)
3. **Required Fields**: Are all required visible fields answered?
4. **Data Types**: Do values match field types?
5. **Options**: Are selected options valid? (dropdowns/radios)
6. **Dependencies**: Are selected options valid based on dependencies?

---

## Navigation & Editing

### Editing Previous Sections

**Use Case**: User wants to change an answer in Section 1 after completing Section 3

**Flow**:
1. User navigates to Section 1 (via UI navigation or "Back" button)
2. Frontend calls `GET /sections/{section_id}/`
3. Backend returns section with pre-filled answers (`current_value`)
4. User edits answers
5. Frontend calls `POST /submit-section/` with updated answers
6. Backend updates `FieldAnswer` records (using `update_or_create()`)
7. Backend re-evaluates conditional logic
8. Frontend calls `GET /current-section/` to see updated state

### Conditional Logic Re-evaluation

**Important**: When editing previous sections, conditional logic re-evaluates

**Example**:
- User answers "Are you a customer?" = "No" → Section 2 hidden
- User completes Section 3
- User goes back, changes answer to "Yes" → Section 2 becomes visible
- User must now complete Section 2 before finishing

**Technical Details**:
- `validate_submission()` re-evaluates all rules after save
- `get_current_section()` finds first incomplete visible section
- Progress recalculates based on new visibility

### Pre-filling Answers

**Implementation**:
- `get_section_with_fields(include_current_values=True)`
- Merges `FieldAnswer` records with field definitions
- Returns `current_value` for each field with existing answer

**Frontend Handling**:
- Check for `current_value` in field object
- Pre-populate form inputs with `current_value`
- User can edit or clear values

---

## Error Handling

### Validation Errors

**Structure**:
```json
{
  "status": "error",
  "errors": {
    "field_id": "Error message",
    "field_id_2": "Another error"
  }
}
```

**Error Types**:
1. **Required Field Missing**: "This field is required."
2. **Invalid Type**: "Value 'abc' is not a valid number."
3. **Invalid Option**: "Value 'invalid' is not a valid option."
4. **Hidden Section**: "This section is not visible based on your previous answers."
5. **Hidden Field**: "This field is not visible based on your previous answers."
6. **Invalid Dependency**: "Selected option is not available based on your previous answers."

### HTTP Status Codes

- `200 OK`: Success (submit section, get section)
- `201 Created`: Success (start survey)
- `400 Bad Request`: Validation error
- `404 Not Found`: Session not found, section not found
- `403 Forbidden`: Cannot access hidden section

### Error Recovery

**Frontend Strategy**:
1. Display field-level errors
2. Highlight invalid fields
3. Allow user to correct and resubmit
4. Maintain form state (don't lose other answers)

**Backend Strategy**:
1. Validate all fields before saving any
2. Return all errors at once (not fail-fast)
3. Don't save partial data on validation failure
4. Maintain session state even on errors

---

## Security Considerations

### Session Token Security

**Generation**:
- UUID v4 (cryptographically random)
- Generated server-side only
- Never exposed in URLs (use headers)

**Validation**:
- Required for all submission endpoints
- Validated on every request
- No token = 400 Bad Request

**Scope**:
- One token per survey response
- Token tied to specific `SurveyResponse` record
- Cannot be reused across surveys

### Data Protection

**Sensitive Fields**:
- Fields marked `is_sensitive=True` are encrypted
- Encryption key stored in environment variable
- AES-256 encryption for field values

**IP Address & User Agent**:
- Stored for analytics and fraud detection
- Not used for authentication
- Can be used for session validation (future)

### Access Control

**Current**: Anonymous access (no authentication required)

**Future Enhancements**:
- Optional user authentication
- Rate limiting per IP
- Session expiration
- CSRF protection for authenticated users

### Input Validation

**Layers**:
1. **Serializer Validation**: Type checking, required fields
2. **Business Logic Validation**: Conditional rules, dependencies
3. **Database Constraints**: Foreign keys, unique constraints

**Protection Against**:
- SQL Injection: Django ORM parameterized queries
- XSS: Frontend responsibility (sanitize input)
- Mass Assignment: Explicit serializer fields only

---

## Performance Considerations

### Database Optimization

**Query Optimization**:
- `select_related()` for foreign keys (SurveyResponse → Survey)
- `prefetch_related()` for reverse relations (Section → Fields)
- Indexes on: `session_token`, `survey_id`, `section_id`, `field_id`

**Caching Strategy** (Future):
- Cache survey structure (sections, fields, rules)
- Cache conditional rule evaluation results
- Invalidate cache on survey updates

### Scalability

**Horizontal Scaling**:
- Stateless API (session token in database)
- Can run multiple Django instances
- Shared database (PostgreSQL)

**Async Processing** (Future):
- Celery tasks for:
  - Conditional logic evaluation (complex surveys)
  - Progress calculation (large surveys)
  - Analytics aggregation

---

## Future Enhancements

### Planned Features

1. **Session Expiration**: Auto-expire sessions after inactivity
2. **Partial Save**: Auto-save answers as user types (debounced)
3. **Offline Support**: Queue submissions when offline
4. **Real-time Collaboration**: Multiple users editing same survey (admin)
5. **Version Control**: Track survey structure changes
6. **A/B Testing**: Multiple survey versions

### Technical Debt

1. **Query Optimization**: Add `select_related`/`prefetch_related` to all views
2. **Caching**: Implement Redis caching for survey structure
3. **Rate Limiting**: Add rate limiting middleware
4. **Monitoring**: Add APM (Application Performance Monitoring)
5. **Logging**: Structured logging for all operations

---

## Appendix: API Reference Summary

### Survey Submission Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/surveys/{id}/submissions/start/` | POST | Start survey session | None |
| `/submissions/current-section/` | GET | Get next section to complete | Session Token (Header) |
| `/submissions/submit-section/` | POST | Save section answers | Session Token (Header) |
| `/submissions/sections/{id}/` | GET | Get specific section (navigation) | Session Token (Header) |
| `/submissions/survey-details/` | GET | Get survey overview | Session Token (Header) |

**Base URLs**:
- Start endpoint: `/api/v1/surveys/{survey_id}/submissions/start/`
- Other endpoints: `/api/v1/submissions/`

**Session Token Header**: `X-Session-Token: uuid` (required for all endpoints except start)
