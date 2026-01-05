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

## Running Tests

### Interactive Mode (Recommended)

1. Open `http://localhost:8089`
2. Set **Number of users** (start with 50)
3. Set **Spawn rate** (10 users/second)
4. Click "Start swarming"

### Headless Mode

```bash
# Normal load: 50 users, 5 minutes
locust -f locustfile.py --headless -u 50 -r 10 -t 5m --html results/normal.html

# Peak load: 200 users, 5 minutes
locust -f locustfile.py --headless -u 200 -r 20 -t 5m --html results/peak.html

# Stress test: 500 users, 10 minutes
locust -f locustfile.py --headless -u 500 -r 50 -t 10m --html results/stress.html
```

## What Gets Tested

Each simulated user follows this flow:

1. **Start Survey** - Creates a new session
2. **Get Current Section** - Fetches the next section
3. **Submit Section** - Submits answers for required fields
4. Repeat until complete, then starts a new survey

## Performance Goals

| Metric | Target |
|--------|--------|
| Response Time (p95) | < 500ms |
| Throughput | 50+ req/sec |
| Error Rate | < 1% |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Survey not found" | Check Django server is running |
| Connection errors | Verify host URL in Locust |
| No data in results | Check startup message for survey creation |
