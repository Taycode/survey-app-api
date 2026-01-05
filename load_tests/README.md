# Load Testing Guide

Run load tests on the Survey Platform API using Locust.

## Quick Start

```bash
# 1. Install Locust
pip install locust

# 2. Start Django server (in one terminal)
python manage.py runserver

# 3. Run Locust (in another terminal)
locust -f load_tests/locustfile.py --host=http://localhost:8000

# 4. Open http://localhost:8089 and start the test
```

A test survey is automatically created on startup and cleaned up when done.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `TEST_SURVEY_ID` | (auto) | Use a specific survey instead of auto-creating |

```bash
# Optional: Use an existing survey
export TEST_SURVEY_ID="your-survey-id-here"
```

## What Gets Auto-Created

When no `TEST_SURVEY_ID` is provided, the locust test will:

1. Create a test user (`loadtest@example.com`)
2. Create a test organization (`Load Test Organization`)
3. Add the user as owner of the organization
4. Create a test survey with:
   - **Section 1**: "Basic Info" with Name (text), Age (number), Preference (radio)
   - **Section 2**: "Details" with Comments (text, optional)
5. Publish the survey

Everything is cleaned up when the test stops.

## Running Tests

### Interactive Mode (Recommended)

1. Open `http://localhost:8089`
2. Set **Number of users** (start with 50)
3. Set **Spawn rate** (10 users/second)
4. Click "Start swarming"

### Headless Mode

```bash
# Normal load: 50 users, 5 minutes
locust -f load_tests/locustfile.py --headless -u 50 -r 10 -t 5m --html results/normal.html

# Peak load: 200 users, 5 minutes
locust -f load_tests/locustfile.py --headless -u 200 -r 20 -t 5m --html results/peak.html

# Stress test: 500 users, 10 minutes
locust -f load_tests/locustfile.py --headless -u 500 -r 50 -t 10m --html results/stress.html
```

### Using Docker

If you're running the API via Docker:

```bash
# Use the Docker host URL
locust -f load_tests/locustfile.py --host=http://localhost:8000
```

## What Gets Tested

Each simulated user follows this flow:

1. **Start Survey** (`POST /api/v1/surveys/{id}/submissions/start/`) - Creates a new session
2. **Get Current Section** (`GET /api/v1/submissions/current-section/`) - Fetches the next section
3. **Submit Section** (`POST /api/v1/submissions/submit-section/`) - Submits answers for required fields
4. Repeat until complete, then starts a new survey

### Task Weights

| Task | Weight | Description |
|------|--------|-------------|
| Start Survey | 3 | Starting new survey sessions |
| Get Section | 5 | Fetching current section to display |
| Submit Section | 5 | Submitting section answers |

## Performance Goals

| Metric | Target |
|--------|--------|
| Response Time (p95) | < 500ms |
| Throughput | 50+ req/sec |
| Error Rate | < 1% |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Survey not found" | Check Django server is running and database is migrated |
| Connection errors | Verify host URL in Locust matches your server |
| No data in results | Check startup message for survey creation errors |
| "Session not found" errors | This is expected - sessions expire after survey completion |
| Import errors | Ensure you're in the project root directory |
| Database errors | Run migrations: `python manage.py migrate` |

## Understanding Results

### Key Metrics

- **Requests/s**: How many API calls are being handled
- **p95 Response Time**: 95% of requests complete within this time
- **Failures**: Count of failed requests (should be < 1%)

### Expected Behavior

- Some 404 errors are normal when sessions complete
- Error rate should stabilize after initial ramp-up
- Response times should stay consistent under load
