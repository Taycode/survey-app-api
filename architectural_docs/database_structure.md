# Database Structure

This document outlines the database schema for the Advanced Dynamic Survey Platform.

---

## Overview

The database is structured into 6 main categories:

| Category | Tables | Purpose |
|----------|--------|---------|
| Survey Structure | Survey, Section, Field, FieldOption | Core survey building blocks |
| Logic | ConditionalRule, FieldDependency | Dynamic behavior based on answers |
| Responses | SurveyResponse, FieldAnswer, Invitation | Storing user submissions and invitations |
| Organizations | Organization, OrganizationMembership | Multi-tenancy support |
| RBAC | User, Role, UserRole, Permission, RolePermission, UserSession | Access control and session management |
| Audit | AuditLog | Compliance and tracking |

**Total: 17 Tables**

---

## Entity Relationship Diagram

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐
│ Organization │─────│ OrganizationMembership│─────│     User     │
└──────────────┘     └──────────────────────┘     └──────────────┘
       │                                                 │
       │                                    ┌────────────┼────────────┐
       │                                    │            │            │
       │                             ┌───────────┐ ┌───────────┐ ┌─────────────┐
       │                             │ UserRole  │ │UserSession│ │  AuditLog   │
       │                             └───────────┘ └───────────┘ └─────────────┘
       │                                    │
       │                             ┌───────────┐
       │                             │   Role    │
       │                             └───────────┘
       │                                    │
       │                          ┌─────────────────┐
       │                          │ RolePermission  │
       │                          └─────────────────┘
       │                                    │
       │                             ┌───────────┐
       │                             │Permission │
       │                             └───────────┘
       │
       ▼
┌─────────┐
│ Survey  │───────────────────────────────────────┐
└─────────┘                                       │
     │                                            │
     ├─────────────────┐                          │
     │                 │                          │
     ▼                 ▼                          ▼
┌─────────┐     ┌────────────┐            ┌────────────┐
│ Section │     │ Invitation │            │SurveyResponse│
└─────────┘     └────────────┘            └────────────┘
     │                                           │
     ▼                                           ▼
┌─────────┐                               ┌─────────────┐
│  Field  │───────────────────────────────│ FieldAnswer │
└─────────┘                               └─────────────┘
     │
     ├─────────────────┐
     │                 │
     ▼                 ▼
┌─────────────┐  ┌─────────────────┐
│ FieldOption │  │ ConditionalRule │
└─────────────┘  └─────────────────┘
     │
     ▼
┌─────────────────┐
│ FieldDependency │
└─────────────────┘
```

---

## 1. Survey Structure Tables

### 1.1 Survey

The parent entity representing a complete survey.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| title | VARCHAR(255) | NOT NULL | Survey name |
| description | TEXT | NULLABLE | Survey description |
| status | ENUM | NOT NULL, DEFAULT 'draft' | One of: `draft`, `published`, `closed` |
| created_by | UUID | FK → User, ON DELETE SET NULL, NULLABLE | User who created the survey |
| organization | UUID | FK → Organization, ON DELETE CASCADE, NULLABLE | Organization the survey belongs to |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, AUTO UPDATE | Last modification timestamp |

**Indexes:**
- `idx_survey_status` on `status` (for filtering published surveys)
- `idx_survey_created_by` on `created_by` (for user's surveys lookup)
- `idx_survey_organization` on `organization` (for organization's surveys lookup)

---

### 1.2 Section

Logical groupings within a survey.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| survey_id | UUID | FK → Survey, ON DELETE CASCADE | Parent survey |
| title | VARCHAR(255) | NOT NULL | Section name |
| description | TEXT | NULLABLE | Section description/instructions |
| order | INTEGER | NOT NULL | Display order within survey (1-indexed) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Indexes:**
- `idx_section_survey_order` on `(survey_id, order)` (for ordered retrieval)

**Constraints:**
- UNIQUE on `(survey_id, order)` — no duplicate ordering within a survey

---

### 1.3 Field

Individual questions/inputs within a section.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| section_id | UUID | FK → Section, ON DELETE CASCADE | Parent section |
| label | VARCHAR(500) | NOT NULL | Question text |
| field_type | ENUM | NOT NULL | One of: `text`, `number`, `date`, `dropdown`, `checkbox`, `radio` |
| is_required | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether answer is mandatory |
| is_sensitive | BOOLEAN | NOT NULL, DEFAULT FALSE | If TRUE, value will be encrypted |
| order | INTEGER | NOT NULL | Display order within section |
| config | JSONB | DEFAULT {} | Additional configuration (see below) |
| has_dependencies | BOOLEAN | NOT NULL, DEFAULT FALSE | True if this field's options depend on another field |

**`config` JSONB Structure (examples):**
```json
// For text field
{
  "placeholder": "Enter your name",
  "min_length": 2,
  "max_length": 100
}

// For number field
{
  "min_value": 0,
  "max_value": 120,
  "decimal_places": 0
}

// For date field
{
  "min_date": "2020-01-01",
  "max_date": "2030-12-31",
  "format": "YYYY-MM-DD"
}
```

**Indexes:**
- `idx_field_section_order` on `(section_id, order)` (for ordered retrieval)

---

### 1.4 FieldOption

Predefined options for dropdown, checkbox, and radio fields.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| field_id | UUID | FK → Field, ON DELETE CASCADE | Parent field |
| label | VARCHAR(255) | NOT NULL | Display text shown to user |
| value | VARCHAR(255) | NOT NULL | Stored value when selected |
| order | INTEGER | NOT NULL | Display order |

**Indexes:**
- `idx_fieldoption_field_order` on `(field_id, order)`

**Constraints:**
- UNIQUE on `(field_id, value)` — no duplicate values within a field

---

## 2. Logic Tables

### 2.1 ConditionalRule

Rules that control visibility of sections or fields based on previous answers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| target_type | ENUM | NOT NULL | One of: `section`, `field` |
| target_id | UUID | NOT NULL | ID of the section or field to show/hide |
| source_field_id | UUID | FK → Field, ON DELETE CASCADE | The field whose answer triggers this rule |
| operator | ENUM | NOT NULL | One of: `equals`, `not_equals`, `greater_than`, `less_than`, `contains`, `in`, `is_empty`, `is_not_empty` |
| value | VARCHAR(500) | NULLABLE | The value to compare against (NULL for is_empty/is_not_empty) |
| action | ENUM | NOT NULL, DEFAULT 'show' | One of: `show`, `hide` |

**Usage Example:**
> "Show Section 3 only if Field 'employed' equals 'yes'"

```
target_type: section
target_id: <section_3_id>
source_field_id: <employed_field_id>
operator: equals
value: "yes"
action: show
```

**Indexes:**
- `idx_conditionalrule_target` on `(target_type, target_id)` (for finding rules affecting a target)
- `idx_conditionalrule_source` on `source_field_id` (for finding rules triggered by a field)

---

### 2.2 FieldDependency

Rules that change the available options in a field based on another field's answer.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| dependent_field_id | UUID | FK → Field, ON DELETE CASCADE | The field whose options change |
| source_field_id | UUID | FK → Field, ON DELETE CASCADE | The field that triggers the change |
| source_value | VARCHAR(255) | NOT NULL | When source field equals this value... |
| dependent_options | JSONB | NOT NULL | ...show these options |

**`dependent_options` JSONB Structure:**
```json
[
  {"label": "Engineering", "value": "engineering"},
  {"label": "Sales", "value": "sales"},
  {"label": "Marketing", "value": "marketing"}
]
```

**Usage Example:**
> "When 'country' = 'USA', show American departments in the 'department' field"

```
dependent_field_id: <department_field_id>
source_field_id: <country_field_id>
source_value: "USA"
dependent_options: [{"label": "Engineering", "value": "eng"}, ...]
```

**Indexes:**
- `idx_fielddependency_dependent` on `dependent_field_id`
- `idx_fielddependency_source` on `(source_field_id, source_value)`

---

### ConditionalRule vs FieldDependency

| Aspect | ConditionalRule | FieldDependency |
|--------|-----------------|-----------------|
| **Purpose** | Show/hide entire fields or sections | Change options within a dropdown/radio/checkbox field |
| **Example** | "Show 'spouse name' field only if 'married' = yes" | "Show different cities based on selected country" |
| **Affects** | Visibility | Content/Options |

---

## 3. Response Tables

### 3.1 SurveyResponse

A single user's submission (complete or partial) to a survey.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| survey_id | UUID | FK → Survey, ON DELETE CASCADE | The survey being answered |
| respondent_id | UUID | FK → User, ON DELETE SET NULL, NULLABLE | If user is authenticated |
| session_token | VARCHAR(255) | NULLABLE | For anonymous/resumable sessions |
| status | ENUM | NOT NULL, DEFAULT 'in_progress' | One of: `in_progress`, `completed` |
| started_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | When response began |
| completed_at | TIMESTAMP | NULLABLE | When response was submitted |
| last_section_id | UUID | FK → Section, ON DELETE SET NULL, NULLABLE | For resuming partial responses |
| ip_address | VARCHAR(45) | NULLABLE | Client IP address |
| user_agent | TEXT | NULLABLE | Client user agent |

**Indexes:**
- `idx_surveyresponse_survey` on `survey_id` (for analytics)
- `idx_surveyresponse_respondent` on `respondent_id` (for user's responses)
- `idx_surveyresponse_session` on `session_token` (for resuming)
- `idx_surveyresponse_status` on `status` (for filtering)

**Constraints:**
- CHECK: At least one of `respondent_id` or `session_token` must be NOT NULL (`response_has_identifier`)

---

### 3.2 FieldAnswer

Individual answers to fields within a response.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| response_id | UUID | FK → SurveyResponse, ON DELETE CASCADE | Parent response |
| field_id | UUID | FK → Field, ON DELETE CASCADE | The field being answered |
| value | TEXT | NULLABLE | The answer (plaintext, for non-sensitive) |
| encrypted_value | BYTEA | NULLABLE | The answer (encrypted, for sensitive fields) |
| answered_at | TIMESTAMP | NOT NULL, AUTO UPDATE | When this answer was saved |

**Indexes:**
- `idx_fieldanswer_response` on `response_id`
- `idx_fieldanswer_field` on `field_id` (for analytics/aggregation)

**Constraints:**
- UNIQUE on `(response_id, field_id)` — one answer per field per response

**Encryption Behavior:**
- On save, if `field.is_sensitive` is `True` and `value` is provided:
  - Value is encrypted and stored in `encrypted_value`
  - `value` field is cleared
- If `field.is_sensitive` is `False`:
  - Value is stored in plaintext in `value`
  - `encrypted_value` is cleared

---

### 3.3 Invitation

Tracks survey invitations sent to recipients.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| survey_id | UUID | FK → Survey, ON DELETE CASCADE | The survey being invited to |
| email | VARCHAR(254) | NOT NULL | Email address invitation was sent to |
| sent_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | When the invitation email was sent |
| sent_by | UUID | FK → User, ON DELETE SET NULL, NULLABLE | User who triggered the invitation |

**Indexes:**
- `idx_invitation_survey` on `survey_id`
- `idx_invitation_email` on `email`
- `idx_invitation_sent_at` on `sent_at`

---

## 4. Organization Tables

### 4.1 Organization

Organization/Tenant model for multi-tenancy support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(255) | NOT NULL | Organization name |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, AUTO UPDATE | Last modification timestamp |

---

### 4.2 OrganizationMembership

Through model for User-Organization many-to-many relationship.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | FK → User, ON DELETE CASCADE | The member user |
| organization_id | UUID | FK → Organization, ON DELETE CASCADE | The organization |
| role | ENUM | NOT NULL, DEFAULT 'member' | One of: `owner`, `member` |
| joined_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | When user joined the organization |

**Constraints:**
- UNIQUE on `(user_id, organization_id)` — user can't join same org twice

---

## 5. RBAC Tables

### 5.1 User

System users (survey creators, analysts, admins).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier |
| password | VARCHAR(255) | NOT NULL | Hashed password |
| first_name | VARCHAR(100) | NULLABLE | User's first name |
| last_name | VARCHAR(100) | NULLABLE | User's last name |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Account status |
| is_staff | BOOLEAN | NOT NULL, DEFAULT FALSE | Staff access to admin |
| is_superuser | BOOLEAN | NOT NULL, DEFAULT FALSE | Superuser status |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Registration timestamp |
| updated_at | TIMESTAMP | NOT NULL, AUTO UPDATE | Last modification timestamp |

**Indexes:**
- `idx_user_email` on `email` (for login lookup)

**Methods:**
- `has_permission(permission_codename)` — Check if user has permission via roles
- `has_role(role_name)` — Check if user has a specific role
- `get_permissions()` — Get all permissions for this user via roles

---

### 5.2 Role

Predefined roles for access control.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(50) | UNIQUE, NOT NULL | Role name |
| description | TEXT | NULLABLE | Role description |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Default Roles:**
- `admin` — Full access to all features
- `analyst` — View responses, run reports, export data
- `data_viewer` — View responses only (no export)

---

### 5.3 UserRole

Many-to-many relationship between users and roles.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| user_id | UUID | FK → User, ON DELETE CASCADE | |
| role_id | UUID | FK → Role, ON DELETE CASCADE | |
| assigned_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | When role was assigned |

**Constraints:**
- UNIQUE on `(user_id, role_id)`

---

### 5.4 Permission

Granular permissions that can be assigned to roles.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| codename | VARCHAR(100) | UNIQUE, NOT NULL | Permission identifier |
| description | TEXT | NULLABLE | What this permission allows |

**Default Permissions:**
- `create_survey`
- `edit_survey`
- `delete_survey`
- `publish_survey`
- `view_responses`
- `export_responses`
- `view_analytics`
- `manage_users`
- `view_audit_logs`

---

### 5.5 RolePermission

Many-to-many relationship between roles and permissions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| role_id | UUID | FK → Role, ON DELETE CASCADE | |
| permission_id | UUID | FK → Permission, ON DELETE CASCADE | |

**Constraints:**
- UNIQUE on `(role_id, permission_id)`

---

### 5.6 UserSession

Tracks user login sessions for secure authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier (used as session_id in JWT) |
| user_id | UUID | FK → User, ON DELETE CASCADE | The authenticated user |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Session validity status |
| ip_address | VARCHAR(45) | NULLABLE | Client IP address at login |
| user_agent | VARCHAR(500) | NULLABLE | Client user agent at login |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Session creation (login time) |
| last_activity | TIMESTAMP | NOT NULL, AUTO UPDATE | Last activity timestamp |
| logged_out_at | TIMESTAMP | NULLABLE | When session was invalidated |

**Indexes:**
- `idx_usersession_user_active` on `(user_id, is_active)` (for active session lookup)

**Usage:**
- JWT tokens include `session_id`
- On logout, session `is_active` is set to `False`
- All tokens with that `session_id` become invalid immediately

---

## 6. Audit Table

### 6.1 AuditLog

Tracks all user actions for compliance and security.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | FK → User, ON DELETE SET NULL, NULLABLE | Who performed the action |
| action | VARCHAR(20) | NOT NULL | One of: `created`, `updated`, `deleted`, `viewed`, `exported` |
| resource_type | VARCHAR(20) | NOT NULL | One of: `survey`, `section`, `field`, `response`, `user`, `role` |
| resource_id | UUID | NOT NULL | ID of the affected resource |
| changes | JSONB | NULLABLE | Before/after values (for updates) |
| ip_address | VARCHAR(45) | NULLABLE | Client IP address |
| user_agent | VARCHAR(500) | NULLABLE | Client user agent |
| timestamp | TIMESTAMP | NOT NULL, DEFAULT NOW() | When action occurred |

**`changes` JSONB Structure (for updates):**
```json
{
  "before": {"title": "Old Survey Name", "status": "draft"},
  "after": {"title": "New Survey Name", "status": "published"}
}
```

**Indexes:**
- `idx_auditlog_user` on `user_id`
- `idx_auditlog_resource` on `(resource_type, resource_id)`
- `idx_auditlog_timestamp` on `timestamp` (for date range queries)
- `idx_auditlog_action` on `action`

---

## Database Tables Summary

| # | Table Name | Database Name | Description |
|---|------------|---------------|-------------|
| 1 | Survey | `surveys` | Core survey entity |
| 2 | Section | `sections` | Logical groupings within surveys |
| 3 | Field | `fields` | Individual questions/inputs |
| 4 | FieldOption | `field_options` | Options for choice-based fields |
| 5 | ConditionalRule | `conditional_rules` | Visibility rules |
| 6 | FieldDependency | `field_dependencies` | Dynamic option rules |
| 7 | SurveyResponse | `survey_responses` | User submissions |
| 8 | FieldAnswer | `field_answers` | Individual answers |
| 9 | Invitation | `invitations` | Email invitations |
| 10 | Organization | `organizations` | Multi-tenant organizations |
| 11 | OrganizationMembership | `organization_memberships` | User-organization relationships |
| 12 | User | `users` | System users |
| 13 | Role | `roles` | Access control roles |
| 14 | Permission | `custom_permissions` | Granular permissions |
| 15 | UserRole | `user_roles` | User-role assignments |
| 16 | RolePermission | `role_permissions` | Role-permission assignments |
| 17 | UserSession | `user_sessions` | Login sessions |
| 18 | AuditLog | `audit_logs` | Action tracking |

---

## Performance Considerations

### Indexing Strategy

1. **Primary lookups**: All foreign keys are indexed
2. **Filtering**: Status, timestamps, and action columns are indexed
3. **Ordering**: Composite indexes on `(parent_id, order)` for ordered retrieval

### Partitioning (for high volume)

Consider partitioning these tables by date/time when data grows:
- `SurveyResponse` — partition by `started_at` (monthly)
- `FieldAnswer` — partition by `answered_at` (monthly)
- `AuditLog` — partition by `timestamp` (monthly)

### Encryption

Fields marked with `is_sensitive = TRUE`:
- Values stored in `FieldAnswer.encrypted_value` (BYTEA)
- Encryption at application layer using AES-256 (Fernet)
- Encryption keys stored separately (environment variables or secrets manager)

---

## Migration Notes

When implementing in Django:

1. Use `UUIDField` with `default=uuid.uuid4` for all primary keys
2. Use custom encryption service with Fernet for field-level encryption
3. Create initial data migration for default roles and permissions
4. Use `GenericIPAddressField` for IP address storage
5. Use `JSONField` for flexible configuration storage

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-02 | - | Initial schema design |
| 2.0 | 2026-01-05 | - | Added Organizations, Invitations, UserSession; Updated Survey, Field, SurveyResponse, AuditLog |
