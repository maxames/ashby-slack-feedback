"""Sync operations for Ashby and Slack data."""

from __future__ import annotations

import json
from typing import Any, cast

from structlog import get_logger

from app.clients.ashby import ashby_client
from app.clients.slack import slack_client
from app.core.database import db
from app.types.ashby import FeedbackFormTD, JobInfoTD
from app.utils.time import is_stale

logger = get_logger()


async def sync_feedback_forms() -> None:
    """
    Sync all feedback form definitions from Ashby.

    Runs on startup and every 6 hours via scheduler.
    """
    logger.info("sync_feedback_forms_started")

    cursor: str | None = None
    forms_synced = 0

    try:
        while True:
            response = await ashby_client.post(
                "feedbackFormDefinition.list", {"cursor": cursor, "limit": 100}
            )

            if not response["success"]:
                logger.error("feedback_form_sync_failed", error=response.get("error"))
                break

            for form in response["results"]:
                form_dict: dict[str, Any] = form
                await db.execute(
                    """
                    INSERT INTO feedback_form_definitions
                    (form_definition_id, title, definition, is_archived, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (form_definition_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        definition = EXCLUDED.definition,
                        is_archived = EXCLUDED.is_archived,
                        updated_at = NOW()
                """,
                    form_dict["id"],
                    form_dict.get("title"),
                    json.dumps(form_dict),
                    form_dict.get("isArchived", False),
                )
                forms_synced += 1

            if not response.get("moreDataAvailable"):
                break

            cursor = response.get("nextCursor")

        logger.info("sync_feedback_forms_completed", count=forms_synced)

    except Exception:
        logger.exception("sync_feedback_forms_error")


async def sync_interviews() -> None:
    """
    Sync all interview definitions from Ashby.

    Runs on startup and every 12 hours via scheduler.
    """
    logger.info("sync_interviews_started")

    cursor = None
    interviews_synced = 0

    try:
        while True:
            response = await ashby_client.post("interview.list", {"cursor": cursor, "limit": 100})

            if not response["success"]:
                logger.error("interview_sync_failed", error=response.get("error"))
                break

            for interview in response["results"]:
                interview_dict: dict[str, Any] = interview
                await db.execute(
                    """
                    INSERT INTO interviews
                    (interview_id, title, external_title, is_archived, is_debrief,
                     instructions_html, instructions_plain, job_id,
                     feedback_form_definition_id, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    ON CONFLICT (interview_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        external_title = EXCLUDED.external_title,
                        is_archived = EXCLUDED.is_archived,
                        is_debrief = EXCLUDED.is_debrief,
                        instructions_html = EXCLUDED.instructions_html,
                        instructions_plain = EXCLUDED.instructions_plain,
                        job_id = EXCLUDED.job_id,
                        feedback_form_definition_id = EXCLUDED.feedback_form_definition_id,
                        updated_at = NOW()
                """,
                    interview_dict["id"],
                    interview_dict.get("title"),
                    interview_dict.get("externalTitle"),
                    interview_dict.get("isArchived", False),
                    interview_dict.get("isDebrief", False),
                    interview_dict.get("instructionsHtml"),
                    interview_dict.get("instructionsPlain"),
                    interview_dict.get("jobId"),
                    interview_dict.get("feedbackFormDefinitionId"),
                )
                interviews_synced += 1

            if not response.get("moreDataAvailable"):
                break

            cursor = response.get("nextCursor")

        logger.info("sync_interviews_completed", count=interviews_synced)

    except Exception:
        logger.exception("sync_interviews_error")


async def get_feedback_form_definition(
    form_definition_id: str,
) -> FeedbackFormTD | None:
    """
    Get feedback form from DB, refresh if stale (>24 hours).

    Args:
        form_definition_id: Form definition UUID

    Returns:
        Form definition dict or None
    """
    form = await db.fetchrow(
        """
        SELECT definition, updated_at
        FROM feedback_form_definitions
        WHERE form_definition_id = $1
    """,
        form_definition_id,
    )

    # If not found or stale, fetch from Ashby
    if not form or is_stale(form["updated_at"], hours=24):
        response = await ashby_client.post(
            "feedbackFormDefinition.info",
            {"feedbackFormDefinitionId": form_definition_id},
        )

        if response["success"]:
            form_data = cast(FeedbackFormTD, response["results"])
            await db.execute(
                """
                INSERT INTO feedback_form_definitions
                (form_definition_id, title, definition, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (form_definition_id) DO UPDATE SET
                    definition = EXCLUDED.definition,
                    updated_at = NOW()
            """,
                form_definition_id,
                form_data.get("title"),
                json.dumps(form_data),
            )

            return form_data

    return cast(FeedbackFormTD, json.loads(str(form["definition"]))) if form else None


async def fetch_and_update_interview(interview_id: str) -> None:
    """
    Fetch and update a single interview definition from Ashby API.

    Called when processing webhooks to ensure interview data is current.

    Args:
        interview_id: Interview UUID
    """
    try:
        response = await ashby_client.post("interview.info", {"id": interview_id})

        if response["success"]:
            interview: dict[str, Any] = response["results"]
            await db.execute(
                """
                INSERT INTO interviews
                (interview_id, title, external_title, is_archived, is_debrief,
                 instructions_html, instructions_plain, job_id,
                 feedback_form_definition_id, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (interview_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    external_title = EXCLUDED.external_title,
                    is_archived = EXCLUDED.is_archived,
                    is_debrief = EXCLUDED.is_debrief,
                    instructions_html = EXCLUDED.instructions_html,
                    instructions_plain = EXCLUDED.instructions_plain,
                    job_id = EXCLUDED.job_id,
                    feedback_form_definition_id = EXCLUDED.feedback_form_definition_id,
                    updated_at = NOW()
            """,
                interview["id"],
                interview.get("title"),
                interview.get("externalTitle"),
                interview.get("isArchived", False),
                interview.get("isDebrief", False),
                interview.get("instructionsHtml"),
                interview.get("instructionsPlain"),
                interview.get("jobId"),
                interview.get("feedbackFormDefinitionId"),
            )
            logger.info("interview_fetched_and_updated", interview_id=interview_id)
        else:
            logger.warning(
                "interview_fetch_failed",
                interview_id=interview_id,
                error=response.get("error"),
            )

    except Exception:
        logger.exception("interview_fetch_error", interview_id=interview_id)


async def sync_job_info(job_id: str) -> JobInfoTD | None:
    """
    Fetch job information from Ashby API.

    Used to get job title for display in messages. Could be cached in
    a jobs table if performance becomes an issue, similar to interviews table.

    Args:
        job_id: Ashby job UUID

    Returns:
        Job data dict or None if not found
    """
    try:
        response = await ashby_client.post("job.info", {"id": job_id})
        if response["success"]:
            return cast(JobInfoTD, response["results"])
    except Exception:
        logger.exception("failed_to_fetch_job_info", job_id=job_id)
    return None


async def sync_slack_users() -> None:
    """
    Sync all Slack users to enable email → slack_user_id mapping.
    Runs on startup and every 12 hours via scheduler.

    Filters out:
    - Bots (is_bot=True)
    - Deleted users (deleted=True)
    - Users without email addresses
    """
    logger.info("sync_slack_users_started")

    try:
        response = await slack_client.client.users_list()

        if not response["ok"]:
            logger.error("slack_users_list_failed", error=response["error"])
            return

        users_synced = 0
        users: list[dict[str, Any]] = response.get("members", [])

        for user in users:
            # Skip bots and deleted users
            if user.get("is_bot") or user.get("deleted"):
                continue

            email = user.get("profile", {}).get("email")
            if not email:
                continue

            await db.execute(
                """
                INSERT INTO slack_users
                (slack_user_id, email, real_name, display_name, is_bot, deleted, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (slack_user_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    real_name = EXCLUDED.real_name,
                    display_name = EXCLUDED.display_name,
                    is_bot = EXCLUDED.is_bot,
                    deleted = EXCLUDED.deleted,
                    updated_at = NOW()
            """,
                user["id"],
                email,
                user.get("real_name"),
                user.get("profile", {}).get("display_name"),
                user.get("is_bot", False),
                user.get("deleted", False),
            )
            users_synced += 1

        logger.info("sync_slack_users_completed", count=users_synced)

    except Exception:
        logger.exception("sync_slack_users_error")
