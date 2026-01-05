# How the Survey Platform Works

> A plain-language guide to understanding the Survey Platform for product managers, frontend engineers, and anyone curious about how the system works.

---

## What is This App?

The Survey Platform is a complete system for creating, distributing, and analyzing surveys. Think of it like Google Forms or Typeform, but as an API that you can build any frontend on top of.

**Key capabilities:**
- Create dynamic surveys with multiple question types
- Collect anonymous responses from anyone
- Smart surveys that adapt based on answers (skip logic)
- Analyze results and export data
- Team collaboration with organizations

---

## Who Uses This System?

### 1. Survey Creators (Authenticated Users)
People who create and manage surveys. They need to:
- Sign up and log in
- Create surveys with questions
- Publish surveys to collect responses
- View and export responses
- See analytics

### 2. Survey Respondents (Anonymous Users)
People who answer surveys. They:
- Don't need to sign up
- Click a survey link and start answering
- Can pause and resume later
- See their progress as they go

---

## The Big Picture

```
┌────────────────────────────────────────────────────────────────┐
│                        SURVEY PLATFORM                          │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│   👤 SURVEY CREATORS                    👥 RESPONDENTS          │
│   ─────────────────                    ────────────────         │
│   • Sign up / Log in                   • No login needed        │
│   • Create surveys                     • Start survey           │
│   • Add questions                      • Answer questions       │
│   • Publish surveys                    • Submit responses       │
│   • View responses                                              │
│   • Export data                                                 │
│   • See analytics                                               │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## User Stories

### Story 1: Creating a Survey

**As a survey creator, I want to create a customer feedback survey.**

**Steps:**
1. **Sign up** for an account (or log in if returning)
2. **Create a survey** with a title and description
3. **Add sections** to organize questions (e.g., "About You", "Your Experience")
4. **Add questions** to each section (text, dropdowns, ratings, etc.)
5. **Add answer options** for multiple-choice questions
6. **Set up skip logic** (optional) - e.g., "If they say 'No', skip the next section"
7. **Publish** the survey to make it live

```
Example Survey Structure:
─────────────────────────
📋 Customer Feedback Survey
├── 📁 Section 1: About You
│   ├── ❓ What's your name? (text)
│   ├── ❓ How old are you? (number)
│   └── ❓ Are you a customer? (yes/no)
│
├── 📁 Section 2: Your Experience [Shows only if "customer" = yes]
│   ├── ❓ How satisfied are you? (dropdown: Very/Somewhat/Not)
│   └── ❓ Would you recommend us? (yes/no)
│
└── 📁 Section 3: Final Thoughts
    └── ❓ Any other comments? (text)
```

---

### Story 2: Answering a Survey

**As a respondent, I want to complete a survey I received via email.**

**Steps:**
1. **Click the survey link** - no login needed
2. **Start the survey** - get a session token (like a ticket number)
3. **Answer section by section** - see questions, fill in answers, click "Next"
4. **See progress** - "You're 33% done, 2 sections left"
5. **Go back if needed** - edit previous answers
6. **Finish** - submit and see confirmation

```
Respondent Journey:
───────────────────
[Click Link] → [Start Survey] → [Answer Section 1] → [Answer Section 2] → [Finish] → [Thank You!]
                    ↑                                        │
                    └────────────── [Go Back & Edit] ────────┘
```

---

### Story 3: Viewing Results

**As a survey creator, I want to see who responded and what they said.**

**Steps:**
1. **Log in** to your account
2. **Go to your survey**
3. **View responses** - see list of all submissions
4. **Click a response** - see individual answers
5. **Export data** - download as CSV or JSON (sent to your email)
6. **View analytics** - see completion rates, averages, etc.

---

## Key Concepts

### Organizations
Users belong to **organizations** (like teams or companies). Surveys belong to organizations too. This keeps data separate between teams.

```
🏢 Acme Corp (Organization)
├── 👤 Alice (Owner)
├── 👤 Bob (Member)
└── 📋 Customer Survey
    └── 📊 150 responses
```

### Session Tokens
When someone starts a survey, they get a **session token** - like a claim ticket. They use this token for all their answers. This lets them:
- Continue later if they close the browser
- Not need to create an account
- Keep their answers private

### Conditional Logic (Skip Logic)
Surveys can be **smart** - questions or sections appear/disappear based on previous answers.

**Example:**
- Question: "Do you have children?"
- If "Yes" → Show "How many children?" 
- If "No" → Skip to next section

### Sensitive Data
Some questions collect sensitive information (SSN, medical info, etc.). These answers are **encrypted** before storing, so even database administrators can't read them.

---

## API Overview for Frontend Engineers

### Authentication Endpoints

| What you want to do | Endpoint | Method |
|---------------------|----------|--------|
| Create an account | `/api/v1/auth/register/` | POST |
| Log in | `/api/v1/auth/login/` | POST |
| Log out | `/api/v1/auth/logout/` | POST |
| Refresh expired token | `/api/v1/auth/token/refresh/` | POST |
| Get my profile | `/api/v1/auth/me/` | GET |

**How authentication works:**
1. User logs in → gets `access` and `refresh` tokens
2. Include `access` token in header: `Authorization: Bearer <token>`
3. Access token expires in 15 minutes → use `refresh` token to get a new one
4. Refresh token expires in 7 days → user must log in again

---

### Survey Management Endpoints (Requires Login)

| What you want to do | Endpoint | Method |
|---------------------|----------|--------|
| List my surveys | `/api/v1/surveys/` | GET |
| Create a survey | `/api/v1/surveys/` | POST |
| Get survey details | `/api/v1/surveys/{id}/` | GET |
| Update a survey | `/api/v1/surveys/{id}/` | PATCH |
| Delete a survey | `/api/v1/surveys/{id}/` | DELETE |
| Publish a survey | `/api/v1/surveys/{id}/publish/` | POST |
| Close a survey | `/api/v1/surveys/{id}/close/` | POST |

---

### Building Survey Structure (Requires Login)

| What you want to do | Endpoint | Method |
|---------------------|----------|--------|
| **Sections** | | |
| List sections | `/api/v1/surveys/{survey_id}/sections/` | GET |
| Add a section | `/api/v1/surveys/{survey_id}/sections/` | POST |
| Update a section | `/api/v1/surveys/{survey_id}/sections/{id}/` | PATCH |
| Delete a section | `/api/v1/surveys/{survey_id}/sections/{id}/` | DELETE |
| **Questions (Fields)** | | |
| List questions | `/api/v1/surveys/{survey_id}/sections/{section_id}/fields/` | GET |
| Add a question | `/api/v1/surveys/{survey_id}/sections/{section_id}/fields/` | POST |
| Update a question | `/api/v1/surveys/{survey_id}/sections/{section_id}/fields/{id}/` | PATCH |
| Delete a question | `/api/v1/surveys/{survey_id}/sections/{section_id}/fields/{id}/` | DELETE |
| **Answer Options** | | |
| List options | `/api/v1/surveys/.../fields/{field_id}/options/` | GET |
| Add an option | `/api/v1/surveys/.../fields/{field_id}/options/` | POST |
| Update an option | `/api/v1/surveys/.../fields/{field_id}/options/{id}/` | PATCH |
| Delete an option | `/api/v1/surveys/.../fields/{field_id}/options/{id}/` | DELETE |

**Question Types:**
- `text` - Free text input
- `number` - Numbers only
- `date` - Date picker
- `dropdown` - Single selection from list
- `radio` - Single selection with buttons
- `checkbox` - Multiple selections

---

### Skip Logic & Dependencies (Requires Login)

| What you want to do | Endpoint | Method |
|---------------------|----------|--------|
| **Conditional Rules** (show/hide sections or fields) | | |
| List rules | `/api/v1/surveys/{survey_id}/conditional-rules/` | GET |
| Create a rule | `/api/v1/surveys/{survey_id}/conditional-rules/` | POST |
| Update a rule | `/api/v1/surveys/{survey_id}/conditional-rules/{id}/` | PATCH |
| Delete a rule | `/api/v1/surveys/{survey_id}/conditional-rules/{id}/` | DELETE |
| **Field Dependencies** (change options based on another answer) | | |
| List dependencies | `/api/v1/surveys/{survey_id}/field-dependencies/` | GET |
| Create a dependency | `/api/v1/surveys/{survey_id}/field-dependencies/` | POST |

**Conditional Rule Example:**
"Show Section 2 only when 'Are you a customer?' equals 'yes'"

**Field Dependency Example:**
"When 'Country' = 'USA', show American states in the 'State' dropdown"

---

### Taking a Survey (No Login Required)

| What you want to do | Endpoint | Method | Header |
|---------------------|----------|--------|--------|
| Start the survey | `/api/v1/surveys/{id}/submissions/start/` | POST | - |
| Get current section | `/api/v1/submissions/current-section/` | GET | X-Session-Token |
| Submit section answers | `/api/v1/submissions/submit-section/` | POST | X-Session-Token |
| Go back to a section | `/api/v1/submissions/sections/{section_id}/` | GET | X-Session-Token |
| Finish the survey | `/api/v1/submissions/finish/` | POST | X-Session-Token |

**The Flow:**

```
1. POST /surveys/{id}/submissions/start/
   → Returns: { "session_token": "abc-123..." }
   → Save this token!

2. GET /submissions/current-section/
   Header: X-Session-Token: abc-123...
   → Returns: Section 1 with questions

3. POST /submissions/submit-section/
   Header: X-Session-Token: abc-123...
   Body: { "section_id": "...", "answers": [...] }
   → Returns: { "is_complete": false, "progress": { "percentage": 33 } }

4. Repeat steps 2-3 until is_complete = true

5. POST /submissions/finish/
   Header: X-Session-Token: abc-123...
   → Returns: { "message": "Survey completed successfully" }
```

---

### Viewing Responses (Requires Login + Permission)

| What you want to do | Endpoint | Method | Permission Needed |
|---------------------|----------|--------|-------------------|
| List all responses | `/api/v1/surveys/{id}/responses/` | GET | view_responses |
| Get one response | `/api/v1/responses/{response_id}/` | GET | view_responses |
| Export responses | `/api/v1/surveys/{id}/responses/export/` | GET | export_responses |
| Get analytics | `/api/v1/surveys/{id}/responses/analytics/` | GET | view_analytics |
| Send invitations | `/api/v1/surveys/{id}/invitations/` | POST | publish_survey |

**Export:** When you export, the file is generated in the background and **emailed to you** (because it might take a while for large datasets).

**Analytics Response:**
```json
{
  "total_responses": 150,
  "completed_responses": 120,
  "in_progress_responses": 30,
  "completion_rate": 80.0,
  "average_completion_time_seconds": 342
}
```

---

## Common Scenarios

### Scenario: Building a Simple Survey

```
1. Login
   POST /api/v1/auth/login/
   Body: { "email": "you@example.com", "password": "..." }
   → Save the access token

2. Create Survey
   POST /api/v1/surveys/
   Header: Authorization: Bearer <token>
   Body: { "title": "Feedback Survey", "organization": "<org-id>" }
   → Save the survey ID

3. Add Section
   POST /api/v1/surveys/<survey-id>/sections/
   Body: { "title": "Your Opinion", "order": 1 }
   → Save the section ID

4. Add Question
   POST /api/v1/surveys/<survey-id>/sections/<section-id>/fields/
   Body: { "label": "How do you like our product?", "field_type": "dropdown", "is_required": true, "order": 1 }
   → Save the field ID

5. Add Options
   POST /api/v1/surveys/<survey-id>/sections/<section-id>/fields/<field-id>/options/
   Body: { "label": "Love it!", "value": "love", "order": 1 }
   (repeat for other options)

6. Publish
   POST /api/v1/surveys/<survey-id>/publish/
   → Survey is now live!
```

---

### Scenario: Respondent Completes Survey

```
1. Start Survey
   POST /api/v1/surveys/<survey-id>/submissions/start/
   → { "session_token": "abc123" }

2. Get First Section
   GET /api/v1/submissions/current-section/
   Header: X-Session-Token: abc123
   → Returns questions for Section 1

3. Submit Answers
   POST /api/v1/submissions/submit-section/
   Header: X-Session-Token: abc123
   Body: {
     "section_id": "...",
     "answers": [
       { "field_id": "...", "value": "love" }
     ]
   }
   → { "is_complete": false, "progress": { "percentage": 50 } }

4. Get Next Section (or finish if complete)
   GET /api/v1/submissions/current-section/
   → Returns Section 2 or { "is_complete": true }

5. Finish
   POST /api/v1/submissions/finish/
   → Survey completed!
```

---

## Permissions

Not everyone can do everything. Here's what each permission allows:

| Permission | What it allows |
|------------|----------------|
| `create_survey` | Create new surveys |
| `edit_survey` | Edit survey structure (sections, fields, options) |
| `delete_survey` | Delete surveys |
| `publish_survey` | Publish surveys, send invitations |
| `view_responses` | See who responded and their answers |
| `export_responses` | Download response data as CSV/JSON |
| `view_analytics` | See aggregated statistics |

---

## Error Handling

When something goes wrong, you'll get a helpful error:

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad request | Missing required field, invalid value |
| 401 | Not logged in | Token expired or missing |
| 403 | Not allowed | Don't have permission for this action |
| 404 | Not found | Survey/section/field doesn't exist |

**Example error response:**
```json
{
  "status": "error",
  "errors": {
    "email": "This field is required.",
    "password": "Password must be at least 8 characters."
  }
}
```

---

## Quick Reference Card

### For Respondents (No Login)
```
Start:    POST /api/v1/surveys/{id}/submissions/start/
Section:  GET  /api/v1/submissions/current-section/        [X-Session-Token header]
Submit:   POST /api/v1/submissions/submit-section/         [X-Session-Token header]
Navigate: GET  /api/v1/submissions/sections/{id}/          [X-Session-Token header]
Finish:   POST /api/v1/submissions/finish/                 [X-Session-Token header]
```

### For Survey Creators (Login Required)
```
Auth:     POST /api/v1/auth/login/
Surveys:  GET|POST /api/v1/surveys/
Survey:   GET|PATCH|DELETE /api/v1/surveys/{id}/
Publish:  POST /api/v1/surveys/{id}/publish/
Sections: GET|POST /api/v1/surveys/{id}/sections/
Fields:   GET|POST /api/v1/surveys/{id}/sections/{id}/fields/
Options:  GET|POST /api/v1/surveys/.../fields/{id}/options/
Responses: GET /api/v1/surveys/{id}/responses/
Export:   GET /api/v1/surveys/{id}/responses/export/
Analytics: GET /api/v1/surveys/{id}/responses/analytics/
```

---

## Need More Details?

- **API Documentation** (auto-generated): `/api/docs/` or `/api/redoc/`
- **Technical Architecture**: See `survey_submission_lifecycle.md`
- **Database Structure**: See `database_structure.md`
- **Working Code Examples**: See `api_docs/examples.py`

---

*Last updated: January 2026*

