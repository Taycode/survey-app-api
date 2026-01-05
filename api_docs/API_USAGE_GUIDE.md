# Survey Platform API - Usage Guide

## Table of Contents

1. [Authentication Flow](#authentication-flow)
2. [Creating a Survey](#creating-a-survey)
3. [Submitting Survey Responses](#submitting-survey-responses)
4. [Managing Responses](#managing-responses)
5. [Analytics](#analytics)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)

---

## Authentication Flow

The Survey Platform API uses JWT (JSON Web Tokens) for authentication. Here's the complete authentication workflow:

### 1. Register a New User

**Endpoint:** `POST /api/v1/auth/register/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

**Response:**
```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "analyst"
  },
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### 2. Login

**Endpoint:** `POST /api/v1/auth/login/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

**Response:** Same as registration

### 3. Using Access Tokens

Include the access token in the Authorization header for all authenticated requests:

```bash
curl -X GET http://localhost:8000/api/v1/surveys/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

**Token Lifetimes:**
- Access Token: 15 minutes
- Refresh Token: 7 days

### 4. Refreshing Access Tokens

**Endpoint:** `POST /api/v1/auth/token/refresh/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }'
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### 5. Logout

**Endpoint:** `POST /api/v1/auth/logout/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

---

## Creating a Survey

### Step 1: Create Survey

**Endpoint:** `POST /api/v1/surveys/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/surveys/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Customer Satisfaction Survey",
    "description": "Help us improve our services",
    "status": "draft"
  }'
```

**Response:**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "title": "Customer Satisfaction Survey",
  "description": "Help us improve our services",
  "status": "draft",
  "created_by": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Step 2: Add Sections

**Endpoint:** `POST /api/v1/surveys/{survey_id}/sections/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/surveys/7c9e6679-7425-40de-944b-e07fc1f90ae7/sections/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Personal Information",
    "description": "Basic information about you",
    "order": 1
  }'
```

**Response:**
```json
{
  "id": "8c9e6679-7425-40de-944b-e07fc1f90ae7",
  "survey": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "title": "Personal Information",
  "description": "Basic information about you",
  "order": 1
}
```

### Step 3: Add Fields to Section

**Endpoint:** `POST /api/v1/surveys/{survey_id}/sections/{section_id}/fields/`

**Example: Text Field**
```bash
curl -X POST http://localhost:8000/api/v1/surveys/7c9e6679.../sections/8c9e6679.../fields/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Full Name",
    "field_type": "text",
    "is_required": true,
    "order": 1
  }'
```

**Example: Dropdown Field with Options**
```bash
curl -X POST http://localhost:8000/api/v1/surveys/7c9e6679.../sections/8c9e6679.../fields/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "How satisfied are you with our service?",
    "field_type": "dropdown",
    "is_required": true,
    "order": 2
  }'
```

### Step 4: Add Options to Dropdown/Radio Fields

**Endpoint:** `POST /api/v1/surveys/{survey_id}/sections/{section_id}/fields/{field_id}/options/`

```bash
curl -X POST http://localhost:8000/api/v1/surveys/.../sections/.../fields/.../options/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Very Satisfied",
    "value": "very_satisfied",
    "order": 1
  }'
```

### Step 5: Publish Survey

**Endpoint:** `POST /api/v1/surveys/{survey_id}/publish/`

```bash
curl -X POST http://localhost:8000/api/v1/surveys/7c9e6679-7425-40de-944b-e07fc1f90ae7/publish/ \
  -H "Authorization: Bearer <access_token>"
```

**Response:**
```json
{
  "detail": "Survey published successfully"
}
```

---

## Submitting Survey Responses

Survey submission is a multi-step process that doesn't require authentication, making it accessible to anonymous users.

### Step 1: Start Survey Session

**Endpoint:** `POST /api/v1/surveys/{survey_id}/submissions/start/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/surveys/7c9e6679-7425-40de-944b-e07fc1f90ae7/submissions/start/
```

**Response:**
```json
{
  "session_token": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
}
```

**Important:** Save this `session_token` - you'll need it for all subsequent requests.

### Step 2: Get Current Section

**Endpoint:** `GET /api/v1/submissions/current-section/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/submissions/current-section/ \
  -H "X-Session-Token: 6ba7b810-9dad-11d1-80b4-00c04fd430c8"
```

**Response:**
```json
{
  "section": {
    "id": "8c9e6679-7425-40de-944b-e07fc1f90ae7",
    "title": "Personal Information",
    "description": "Basic information about you",
    "order": 1
  },
  "fields": [
    {
      "id": "9c9e6679-7425-40de-944b-e07fc1f90ae7",
      "label": "Full Name",
      "field_type": "text",
      "is_required": true,
      "order": 1
    },
    {
      "id": "ac9e6679-7425-40de-944b-e07fc1f90ae7",
      "label": "How satisfied are you?",
      "field_type": "dropdown",
      "is_required": true,
      "order": 2,
      "options": [
        {"label": "Very Satisfied", "value": "very_satisfied"},
        {"label": "Satisfied", "value": "satisfied"},
        {"label": "Neutral", "value": "neutral"}
      ]
    }
  ],
  "progress": {
    "current_section": 1,
    "total_sections": 3,
    "percentage": 0
  }
}
```

### Step 3: Submit Section Answers

**Endpoint:** `POST /api/v1/submissions/submit-section/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/submissions/submit-section/ \
  -H "X-Session-Token: 6ba7b810-9dad-11d1-80b4-00c04fd430c8" \
  -H "Content-Type: application/json" \
  -d '{
    "section_id": "8c9e6679-7425-40de-944b-e07fc1f90ae7",
    "answers": [
      {
        "field_id": "9c9e6679-7425-40de-944b-e07fc1f90ae7",
        "value": "John Doe"
      },
      {
        "field_id": "ac9e6679-7425-40de-944b-e07fc1f90ae7",
        "value": "very_satisfied"
      }
    ]
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Section saved successfully",
  "is_complete": false,
  "progress": {
    "sections_completed": 1,
    "total_sections": 3,
    "sections_remaining": 2,
    "percentage": 33.33
  }
}
```

### Step 4: Repeat for All Sections

Continue calling:
1. `GET /api/v1/submissions/current-section/` to get the next section
2. `POST /api/v1/submissions/submit-section/` to submit answers

### Step 5: Finish Survey

**Endpoint:** `POST /api/v1/submissions/finish/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/submissions/finish/ \
  -H "X-Session-Token: 6ba7b810-9dad-11d1-80b4-00c04fd430c8"
```

**Response:**
```json
{
  "status": "success",
  "message": "Survey completed successfully",
  "response_id": "bc9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

---

## Managing Responses

**Permission Required:** `view_responses` (Manager or Viewer role)

### List All Responses for a Survey

**Endpoint:** `GET /api/v1/surveys/{survey_id}/responses/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/surveys/7c9e6679-7425-40de-944b-e07fc1f90ae7/responses/ \
  -H "Authorization: Bearer <access_token>"
```

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/surveys/7c9e6679.../responses/?page=2",
  "previous": null,
  "results": [
    {
      "id": "bc9e6679-7425-40de-944b-e07fc1f90ae7",
      "survey": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "status": "completed",
      "started_at": "2024-01-15T14:30:00Z",
      "completed_at": "2024-01-15T14:35:00Z",
      "ip_address": "192.168.1.1"
    }
  ]
}
```

### Get Single Response Details

**Endpoint:** `GET /api/v1/responses/{response_id}/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/responses/bc9e6679-7425-40de-944b-e07fc1f90ae7/ \
  -H "Authorization: Bearer <access_token>"
```

**Response:**
```json
{
  "id": "bc9e6679-7425-40de-944b-e07fc1f90ae7",
  "survey": {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "title": "Customer Satisfaction Survey"
  },
  "status": "completed",
  "started_at": "2024-01-15T14:30:00Z",
  "completed_at": "2024-01-15T14:35:00Z",
  "answers": [
    {
      "field": {
        "id": "9c9e6679-7425-40de-944b-e07fc1f90ae7",
        "label": "Full Name"
      },
      "value": "John Doe"
    },
    {
      "field": {
        "id": "ac9e6679-7425-40de-944b-e07fc1f90ae7",
        "label": "How satisfied are you?"
      },
      "value": "very_satisfied"
    }
  ]
}
```

### Export Responses

**Endpoint:** `GET /api/v1/surveys/{survey_id}/responses/export/?format=csv`

**Permission Required:** `export_responses`

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/surveys/7c9e6679-7425-40de-944b-e07fc1f90ae7/responses/export/?format=csv" \
  -H "Authorization: Bearer <access_token>"
```

**Response:**
```json
{
  "message": "Export started. You will receive an email with the download link.",
  "task_id": "celery-task-uuid"
}
```

**Note:** Export is processed asynchronously. You'll receive an email with the download link when it's ready.

---

## Analytics

**Permission Required:** `view_analytics`

**Endpoint:** `GET /api/v1/surveys/{survey_id}/responses/analytics/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/surveys/7c9e6679-7425-40de-944b-e07fc1f90ae7/responses/analytics/ \
  -H "Authorization: Bearer <access_token>"
```

**Response:**
```json
{
  "survey_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "total_responses": 150,
  "completed_responses": 142,
  "in_progress_responses": 8,
  "completion_rate": 94.67,
  "average_completion_time_seconds": 180,
  "field_analytics": [
    {
      "field_id": "ac9e6679-7425-40de-944b-e07fc1f90ae7",
      "field_label": "How satisfied are you?",
      "field_type": "dropdown",
      "response_distribution": {
        "very_satisfied": 85,
        "satisfied": 45,
        "neutral": 12
      }
    }
  ]
}
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request
Invalid input data or validation errors.

```json
{
  "detail": "Validation error",
  "errors": {
    "email": ["This field is required."],
    "password": ["Password must be at least 8 characters."]
  }
}
```

#### 401 Unauthorized
Missing or invalid authentication token.

```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### 403 Forbidden
Insufficient permissions to access the resource.

```json
{
  "detail": "You do not have permission to perform this action."
}
```

#### 404 Not Found
Resource not found.

```json
{
  "detail": "Not found."
}
```

#### 500 Internal Server Error
Server error - contact support if this persists.

```json
{
  "detail": "Internal server error."
}
```

---

## Best Practices

### 1. Token Management

- Store tokens securely (e.g., httpOnly cookies, secure storage)
- Implement automatic token refresh before expiration
- Clear tokens on logout
- Never expose tokens in URLs or logs

### 2. Survey Submission

- Always validate the session token before each request
- Handle network errors gracefully with retry logic
- Save progress locally before submission
- Implement proper error feedback for users

### 3. Performance

- Use pagination for large result sets
- Cache frequently accessed data (survey templates)
- Implement request debouncing for user inputs
- Use async exports for large datasets

### 4. Security

- Always use HTTPS in production
- Validate all user inputs
- Implement rate limiting for public endpoints
- Monitor for unusual access patterns

### 5. Error Handling

- Implement comprehensive error handling
- Provide clear error messages to users
- Log errors for debugging
- Implement retry logic for transient failures

---

## Rate Limiting

To ensure fair usage and system stability:

- **Authentication endpoints:** 5 requests per minute per IP
- **Survey creation:** 10 requests per minute per user
- **Survey submission:** 100 requests per minute per IP
- **Analytics:** 20 requests per minute per user

Exceeded rate limits return `429 Too Many Requests`.

---

## Support

For additional help:

- **API Documentation:** http://localhost:8000/api/docs/
- **ReDoc Documentation:** http://localhost:8000/api/redoc/
- **Email Support:** support@surveyplatform.com
- **GitHub Issues:** [project-url]/issues

---

## Next Steps

1. Review the [Versioning Policy](VERSIONING_POLICY.md)
2. Check out [Working Examples](examples.py)
3. Read the [Project Requirements](../architectural_docs/project_requirements.md)
4. Explore the [Submission Lifecycle](../architectural_docs/survey_submission_lifecycle.md)

