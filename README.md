# Survey API Platform

Advanced Dynamic Survey Platform - Enterprise-level REST API for creating, deploying, and analyzing surveys.

## 📚 API Documentation

**Interactive Documentation:**
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

**Code Examples:**
```bash
python api_docs/examples.py
```

See [api_docs/](api_docs/) for working Python examples.

---

## Features

- **Dynamic Survey Builder** - Multi-step surveys with sections, various field types, conditional logic, and field dependencies
- **Survey Submission** - Real-time validation, partial response saving, resumable sessions
- **Data Security** - AES-256-GCM encryption for sensitive fields, RBAC permissions
- **Async Processing** - Celery-powered exports, batch invitations
- **Analytics** - Survey-level statistics with caching
- **Comprehensive Documentation** - OpenAPI/Swagger with detailed guides and examples

## Tech Stack

- **Framework**: Django 6.0 + Django REST Framework
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Task Queue**: Celery 5.6
- **Auth**: JWT (SimpleJWT)

---

## Quick Start (Docker)

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone and Setup

```bash
git clone <repository-url>
cd survey-api-app

# Create environment file
cp .env.example .env
```

### 2. Generate Encryption Key

```bash
# Generate a secure encryption key and add to .env
docker compose run --rm web python manage.py generate_encryption_key
```

Copy the output to `FIELD_ENCRYPTION_KEY` in your `.env` file.

### 3. Start Services

```bash
docker compose up -d
```

This starts:
- **web** - Django API server at http://localhost:8000
- **db** - PostgreSQL database
- **redis** - Redis for caching and Celery broker
- **celery** - Background task worker
- **celery-beat** - Scheduled tasks

### 4. Create Superuser

```bash
docker compose exec web python manage.py createsuperuser
```

### 5. Access the API

- **API Root**: http://localhost:8000/api/v1/
- **Swagger Docs**: http://localhost:8000/api/docs/
- **Admin Panel**: http://localhost:8000/admin/

---

## Local Development (Poetry)

### Prerequisites

- Python 3.12+
- Poetry
- PostgreSQL (or use Docker for DB only)
- Redis (or use Docker for Redis only)

### 1. Install Dependencies

```bash
# Install Poetry if not installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install
```

### 2. Setup Environment

```bash
cp .env.example .env
# Edit .env with your local settings
```

### 3. Database Setup

Option A - Use Docker for PostgreSQL and Redis only:
```bash
docker compose up -d db redis
```

Option B - Use local PostgreSQL:
```bash
# Update .env with your local PostgreSQL credentials
```

### 4. Run Migrations

```bash
poetry run python manage.py migrate
```

### 5. Generate Encryption Key

```bash
poetry run python manage.py generate_encryption_key
# Add the output to FIELD_ENCRYPTION_KEY in .env
```

### 6. Start Development Server

```bash
# Django server
poetry run python manage.py runserver

# In separate terminal - Celery worker
poetry run celery -A config worker -l info

# Optional - Celery beat for scheduled tasks
poetry run celery -A config beat -l info
```

---

## API Overview

### Authentication

```bash
# Register
POST /api/v1/auth/register/

# Login (returns JWT tokens)
POST /api/v1/auth/login/

# Refresh token
POST /api/v1/auth/token/refresh/

# Use token in requests
Authorization: Bearer <access_token>
```

### Surveys

```bash
# List/Create surveys
GET/POST /api/v1/surveys/

# Survey details
GET/PATCH/DELETE /api/v1/surveys/{id}/

# Publish survey
POST /api/v1/surveys/{id}/publish/
```

### Survey Submission (Public)

```bash
# Start survey session
POST /api/v1/surveys/{id}/submissions/start/

# Get current section
GET /api/v1/submissions/current-section/
# Header: X-Session-Token: <token>

# Submit section answers
POST /api/v1/submissions/submit-section/

# Finish survey
POST /api/v1/submissions/finish/
```

### Response Management (Auth Required)

```bash
# List responses
GET /api/v1/surveys/{id}/responses/

# Export responses (async, emailed)
GET /api/v1/surveys/{id}/responses/export/?format=csv

# Analytics
GET /api/v1/surveys/{id}/responses/analytics/
```

**For complete documentation**: Visit http://localhost:8000/api/docs/

---

## Testing

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest submissions/tests.py -v

# Run with coverage
poetry run pytest --cov=. --cov-report=html
```

### Load Testing

```bash
# Start Locust
poetry run locust -f load_tests/locustfile.py

# Open http://localhost:8089
```

---

## Project Structure

```
survey-api-app/
├── config/              # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── users/               # User auth, RBAC, sessions
├── surveys/             # Survey builder models & API
├── submissions/         # Response handling, exports, analytics
├── audit/               # Audit logging
├── load_tests/          # Locust load testing
├── architectural_docs/  # System documentation
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml       # Poetry dependencies
└── .env.example
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | (required) |
| `DEBUG` | Debug mode | `True` |
| `DB_ENGINE` | Database engine | `postgresql` |
| `DB_NAME` | Database name | `survey_db` |
| `DB_USER` | Database user | `survey_user` |
| `DB_PASSWORD` | Database password | `survey_password` |
| `DB_HOST` | Database host | `localhost` |
| `REDIS_URL` | Redis URL for caching | `redis://localhost:6379/1` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |
| `FIELD_ENCRYPTION_KEY` | AES-256 key for sensitive fields | (required) |

See `.env.example` for all options.

---

## License

MIT

