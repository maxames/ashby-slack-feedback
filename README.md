# Ashby Slack Feedback

> Automated interview feedback reminders via Slack for Ashby ATS

[![CI](https://github.com/maxames/ashby-slack-feedback/workflows/CI/badge.svg)](https://github.com/maxames/ashby-slack-feedback/actions)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A FastAPI application that automates the interview feedback collection process by sending timely reminders to interviewers via Slack, providing interactive feedback forms, and automatically submitting responses back to Ashby ATS.

## Features

- Webhook Integration: Real-time ingestion of interview schedule updates from Ashby
- Smart Reminders: Automatic Slack DMs sent 4-20 minutes before interviews
- Interactive Forms: Dynamic Slack modal forms matching Ashby feedback form definitions
- Auto-Save Drafts: Press Enter while typing to save your progress automatically
- Idempotent Processing: Safe handling of duplicate webhooks and submissions
- Resume Access: One-click candidate resume viewing directly from Slack
- Comprehensive Logging: Structured logging with `structlog` for observability
- Rate Limiting: Built-in protection against webhook spam
- Clean Architecture: Clear separation of concerns for easy maintenance

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Slack workspace with admin access
- Ashby ATS account with API access

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/maxames/ashby-slack-feedback.git
   cd ashby-slack-feedback
   ```

2. Create virtual environment
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up database
   ```bash
   createdb ashby_feedback
   psql $DATABASE_URL -f database/schema.sql
   ```

5. Configure environment
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and secrets
   ```

6. Run the application
   ```bash
   uvicorn app.main:app --reload
   ```

The application will be available at `http://localhost:8000`. Visit `/docs` for interactive API documentation.

## Docker Setup

For the easiest setup, use Docker Compose:

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app
```

This starts the application and PostgreSQL database with automatic schema initialization.

## Architecture

The application follows clean architecture principles with clear separation of concerns:

```
app/
├── api/          # HTTP handlers (FastAPI routes)
├── clients/      # External API clients (Ashby, Slack)
├── services/     # Business logic and orchestration
├── core/         # Infrastructure (database, config, logging)
├── models/       # Pydantic models for request validation
├── types/        # TypedDict definitions for external APIs
└── utils/        # Generic helpers (security, time)
```

**Data Flow:**
1. Webhook Ingestion: Ashby → API → Services → Database
2. Reminder Scheduling: Scheduler → Services → Slack Client → Slack
3. Feedback Submission: Slack → API → Services → Ashby Client → Ashby

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed system design.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and separation of concerns
- [API Reference](docs/API.md) - Endpoint documentation with examples
- [Deployment Guide](docs/DEPLOYMENT.md) - Deploy to Render, Railway, Fly.io, or manual

## Configuration

All configuration is managed through environment variables. See [.env.example](.env.example) for required variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `ASHBY_API_KEY` | Ashby API key for authentication | Yes |
| `ASHBY_WEBHOOK_SECRET` | Secret for webhook signature verification | Yes |
| `SLACK_BOT_TOKEN` | Slack bot token (xoxb-...) | Yes |
| `SLACK_SIGNING_SECRET` | Slack signing secret for request verification | Yes |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No (default: INFO) |

## Testing

Run the test suite:

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/contracts/      # Contract tests only
```

Test coverage includes:
- Unit tests for security, time utilities, and field builders
- Integration tests for webhook processing, feedback flow, and reminders
- Contract tests validating Ashby/Slack payload structures

## Development

Set up the development environment:

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run linter
ruff check app/

# Run type checker
pyright app/

# Run formatter
ruff format app/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security

For security concerns, please see [SECURITY.md](SECURITY.md).

## How It Works

1. Setup: Configure Ashby webhook to send interview schedule updates to your deployment
2. Ingestion: Application receives and validates webhooks, storing interview data
3. Scheduling: Background scheduler checks every 5 minutes for upcoming interviews
4. Reminders: Interviewers receive Slack DMs 4-20 minutes before their interviews
5. Feedback: Interviewers click to open a modal form with comprehensive candidate context
   - Full candidate profile with contact info and social links
   - Interview details with meeting links and instructions
   - Auto-saves progress when pressing Enter in text fields
6. Submission: Completed feedback is submitted directly to Ashby via API
7. Tracking: Application tracks reminder delivery and submission status

## Monitoring

The application provides several monitoring endpoints:

- `GET /health` - Health check with database connectivity and connection pool stats
- `GET /admin/stats` - System statistics (interviews, reminders, forms)
- Structured logging for observability (JSON format in production)

## Roadmap

- [ ] Implement reminder escalation for overdue feedback
- [ ] Add analytics dashboard for feedback metrics
- [ ] Support for custom reminder timing windows
- [ ] Slack thread replies for feedback status updates

## Support

For questions or issues:
- Open a GitHub issue
- Check the [documentation](docs/)
- Review the [deployment guide](docs/DEPLOYMENT.md)

---

Built using FastAPI, asyncpg, and the Slack SDK
