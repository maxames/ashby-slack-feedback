"""Pytest configuration for tests."""

import os
from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from asyncpg import create_pool
from dotenv import load_dotenv

# Load .env.test file if it exists
env_test_path = Path(__file__).parent.parent / ".env.test"
if env_test_path.exists():
    load_dotenv(env_test_path)

# Set test environment variables before any imports (only if not already set)
os.environ.setdefault("ASHBY_WEBHOOK_SECRET", "test_webhook_secret")
os.environ.setdefault("ASHBY_API_KEY", "test_api_key")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test_signing_secret")
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/ashby_feedback_test")
os.environ.setdefault("LOG_LEVEL", "INFO")


@pytest_asyncio.fixture
async def db_pool():
    """Create a test database connection pool and initialize app's DB."""
    from app.core import database as db_module
    from app.core.config import settings

    pool = await create_pool(settings.database_url, min_size=1, max_size=5)

    # Initialize the app's database singleton so service functions work
    db_module.db.pool = pool

    yield pool

    # Clean up
    db_module.db.pool = None
    await pool.close()


@pytest_asyncio.fixture
async def clean_db(db_pool):
    """Clean database before each test."""
    async with db_pool.acquire() as conn:
        # Clear all tables in reverse dependency order
        await conn.execute("DELETE FROM interview_assignments")
        await conn.execute("DELETE FROM interview_events")
        await conn.execute("DELETE FROM interview_schedules")
        await conn.execute("DELETE FROM feedback_drafts")
        await conn.execute("DELETE FROM feedback_reminders_sent")
        await conn.execute("DELETE FROM feedback_form_definitions")
        await conn.execute("DELETE FROM interviews")
        await conn.execute("DELETE FROM slack_users")
        await conn.execute("DELETE FROM ashby_webhook_payloads")

    yield db_pool


@pytest_asyncio.fixture
async def sample_slack_user(clean_db):
    """Create a sample Slack user in the database."""
    async with clean_db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO slack_users
            (slack_user_id, email, real_name, display_name, is_bot, deleted, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """,
            "U123456",
            "test@example.com",
            "Test User",
            "testuser",
            False,
            False,
        )

    return {"slack_user_id": "U123456", "email": "test@example.com"}


@pytest_asyncio.fixture
async def sample_interview(clean_db):
    """Create a sample interview definition in the database."""
    interview_id = uuid4()
    form_def_id = uuid4()
    job_id = uuid4()

    async with clean_db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO interviews
            (interview_id, title, external_title, is_archived, is_debrief,
             instructions_html, instructions_plain, job_id,
             feedback_form_definition_id, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            """,
            interview_id,
            "Technical Interview",
            "Tech Screen",
            False,
            False,
            "<p>Instructions</p>",
            "Instructions",
            job_id,
            form_def_id,
        )

    return {
        "interview_id": str(interview_id),
        "form_definition_id": str(form_def_id),
        "job_id": str(job_id),
    }


@pytest_asyncio.fixture
async def sample_feedback_form(clean_db):
    """Create a sample feedback form definition in the database."""
    import json

    form_def_id = uuid4()

    form_definition = {
        "id": str(form_def_id),
        "title": "Technical Interview Feedback",
        "formDefinition": {
            "sections": [
                {
                    "title": "Assessment",
                    "fields": [
                        {
                            "field": {
                                "path": "overall_score",
                                "type": "Score",
                                "title": "Overall Score",
                            },
                            "isRequired": True,
                        }
                    ],
                }
            ]
        },
    }

    async with clean_db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO feedback_form_definitions
            (form_definition_id, title, definition, is_archived, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            form_def_id,
            "Technical Interview Feedback",
            json.dumps(form_definition),
            False,
        )

    return form_definition


@pytest_asyncio.fixture
async def sample_interview_event(
    clean_db, sample_interview, sample_slack_user
) -> dict[str, Any]:
    """Create a complete interview event for feedback tests."""
    schedule_id = uuid4()
    event_id = uuid4()
    application_id = uuid4()
    stage_id = uuid4()
    interviewer_id = uuid4()

    async with clean_db.acquire() as conn:
        # Create schedule
        await conn.execute(
            """
            INSERT INTO interview_schedules
            (schedule_id, application_id, interview_stage_id, status, candidate_id, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
            schedule_id,
            application_id,
            stage_id,
            "Scheduled",
            "candidate_test",
        )

        # Create event
        await conn.execute(
            """
            INSERT INTO interview_events
            (event_id, schedule_id, interview_id, created_at, updated_at,
             start_time, end_time, feedback_link, location, meeting_link,
             has_submitted_feedback, extra_data)
            VALUES ($1, $2, $3, NOW(), NOW(), NOW() + INTERVAL '1 hour', NOW() + INTERVAL '2 hours',
                    $4, $5, $6, $7, $8)
            """,
            event_id,
            schedule_id,
            UUID(sample_interview["interview_id"]),  # Convert string to UUID
            "https://ashby.com/feedback",
            "Zoom",
            "https://zoom.us/test",
            False,
            "{}",
        )

        # Create interviewer assignment
        await conn.execute(
            """
            INSERT INTO interview_assignments
            (event_id, interviewer_id, first_name, last_name, email,
             global_role, training_role, is_enabled, manager_id,
             interviewer_pool_id, interviewer_pool_title,
             interviewer_pool_is_archived, training_path, interviewer_updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
            """,
            event_id,
            interviewer_id,
            "Test",
            "User",
            "test@example.com",
            "Interviewer",
            "Trained",
            True,
            None,
            uuid4(),
            "Test Pool",
            False,
            "{}",
        )

    return {
        "event_id": str(event_id),
        "schedule_id": str(schedule_id),
        "interviewer_id": str(interviewer_id),
        "application_id": str(application_id),
    }
