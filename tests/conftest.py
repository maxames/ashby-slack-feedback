"""Pytest configuration for tests."""

import os
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock
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


@pytest.fixture
def mock_ashby_client(monkeypatch):
    """Create and inject mocked Ashby client."""
    from tests.fixtures.mock_clients import MockAshbyClient

    mock_client = MockAshbyClient()

    # Add helper methods first before referencing them
    async def fetch_candidate_info(candidate_id: str):
        response = await mock_client.post("candidate.info", {"id": candidate_id})
        return response["results"]

    async def fetch_resume_url(file_handle: str):
        response = await mock_client.post("file.info", {"handle": file_handle})
        if response.get("success"):
            return response["results"].get("url")
        return None

    mock_client.fetch_candidate_info = fetch_candidate_info
    mock_client.fetch_resume_url = fetch_resume_url

    # Patch the module-level singleton
    monkeypatch.setattr("app.clients.ashby.ashby_client", mock_client)

    # Also patch imports in other modules
    monkeypatch.setattr("app.services.sync.ashby_client", mock_client)

    # Patch individual functions in reminders module
    monkeypatch.setattr(
        "app.services.reminders.fetch_candidate_info", fetch_candidate_info
    )
    monkeypatch.setattr("app.services.reminders.fetch_resume_url", fetch_resume_url)

    yield mock_client

    mock_client.reset()


@pytest.fixture
def mock_slack_client(monkeypatch):
    """Create and inject mocked Slack client."""
    from tests.fixtures.mock_clients import MockSlackClient

    mock_client = MockSlackClient()

    # Patch the module-level singleton
    monkeypatch.setattr("app.clients.slack.slack_client", mock_client)

    # Also patch imports in other modules that use slack_client
    monkeypatch.setattr("app.api.slack_interactions.slack.slack_client", mock_client)
    monkeypatch.setattr("app.services.reminders.slack_client", mock_client)
    monkeypatch.setattr("app.services.sync.slack_client", mock_client)

    yield mock_client

    mock_client.reset()


@pytest.fixture
def mock_http_request():
    """Create a mock FastAPI Request object."""
    from unittest.mock import MagicMock

    from starlette.datastructures import Headers
    from starlette.requests import Request

    # Create a mock scope that looks like a real ASGI scope
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/ashby",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 8000),
        "server": ("localhost", 8000),
    }

    # Create a real Request object with mock receive
    async def mock_receive():
        return {"type": "http.request", "body": b'{"test": "data"}'}

    request = Request(scope, receive=mock_receive)

    # Override methods we need for testing
    original_body = request.body
    original_form = request.form

    async def custom_body():
        return b'{"test": "data"}'

    async def custom_form():
        return {"payload": '{"type": "test"}'}

    request.body = custom_body
    request.form = custom_form

    return request


@pytest.fixture
def ashby_responses():
    """Common Ashby API response templates."""
    from tests.fixtures.mock_clients import (
        create_ashby_error_response,
        create_ashby_paginated_response,
        create_ashby_success_response,
    )

    return {
        "candidate_info": lambda candidate_id="candidate_test": create_ashby_success_response(
            {
                "id": candidate_id,
                "name": "Test Candidate",
                "emailAddresses": [{"value": "test@example.com"}],
                "resumeFileHandle": {
                    "handle": "file_handle_test",
                    "name": "resume.pdf",
                },
            }
        ),
        "feedback_form": lambda form_id="form_def_test": create_ashby_success_response(
            {
                "id": form_id,
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
                                },
                                {
                                    "field": {
                                        "path": "notes",
                                        "type": "RichText",
                                        "title": "Interview Notes",
                                    },
                                    "isRequired": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ),
        "interview_info": lambda interview_id="interview_test": create_ashby_success_response(
            {
                "id": interview_id,
                "title": "Technical Interview",
                "feedbackFormDefinitionId": "form_def_test",
                "jobId": "job_test",
                "instructionsPlain": "Focus on problem solving",
            }
        ),
        "job_info": lambda job_id="job_test": create_ashby_success_response(
            {
                "id": job_id,
                "title": "Software Engineer",
            }
        ),
        "file_info": lambda file_handle="file_handle_test": create_ashby_success_response(
            {
                "handle": file_handle,
                "url": f"https://s3.amazonaws.com/ashby/{file_handle}",
            }
        ),
        "feedback_submit": lambda: create_ashby_success_response(
            {
                "id": "feedback_submission_test",
                "createdAt": "2024-10-20T10:00:00.000Z",
            }
        ),
        "forms_list": lambda forms_count=2: create_ashby_paginated_response(
            [
                {
                    "id": f"form_{i}",
                    "title": f"Form {i}",
                    "formDefinition": {"sections": []},
                }
                for i in range(forms_count)
            ]
        ),
        "interviews_list": lambda interviews_count=2: create_ashby_paginated_response(
            [
                {
                    "id": f"interview_{i}",
                    "title": f"Interview {i}",
                }
                for i in range(interviews_count)
            ]
        ),
        "error": lambda error_msg="API error": create_ashby_error_response(error_msg),
    }
