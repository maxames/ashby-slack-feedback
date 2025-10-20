"""Interview schedule processing business logic."""

from __future__ import annotations

import json
from typing import Any

from structlog import get_logger

from app.core.database import db

logger = get_logger()


async def process_schedule_update(schedule: dict[str, Any]) -> None:
    """
    Process interview schedule update from webhook.

    Implements business rules and full-replace strategy for idempotency:
    - Validates schedule status
    - Handles cancellations (delete)
    - Handles Scheduled/Complete (upsert with full replace)

    Args:
        schedule: Interview schedule data from Ashby webhook

    Raises:
        RuntimeError: If database pool not initialized
    """
    schedule_id: str = schedule["id"]
    status: str = schedule["status"]

    logger.info("processing_schedule_update", schedule_id=schedule_id, status=status)

    # Business rule: Status validation
    if status not in ("Scheduled", "Complete", "Cancelled"):
        logger.info("schedule_status_ignored", status=status)
        return

    # Business rule: Cancellation handling
    if status == "Cancelled":
        await delete_schedule(schedule_id)
        return

    # Business rule: Full replace for Scheduled/Complete
    await upsert_schedule_with_events(schedule, schedule_id, status)


async def delete_schedule(schedule_id: str) -> None:
    """
    Delete schedule and cascading related records.

    Args:
        schedule_id: Schedule UUID
    """
    await db.execute(
        """
        DELETE FROM interview_schedules WHERE schedule_id = $1
    """,
        schedule_id,
    )
    logger.info("schedule_deleted", schedule_id=schedule_id)


async def upsert_schedule_with_events(
    schedule: dict[str, Any], schedule_id: str, status: str
) -> None:
    """
    Upsert schedule with full-replace strategy for events and assignments.

    Args:
        schedule: Schedule data from webhook
        schedule_id: Schedule UUID
        status: Schedule status

    Raises:
        RuntimeError: If database pool not initialized
    """
    if not db.pool:
        raise RuntimeError("Database pool not initialized")

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            # Upsert schedule
            await conn.execute(
                """
                INSERT INTO interview_schedules
                (schedule_id, application_id, interview_stage_id, status, candidate_id, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (schedule_id) DO UPDATE SET
                    application_id = EXCLUDED.application_id,
                    interview_stage_id = EXCLUDED.interview_stage_id,
                    status = EXCLUDED.status,
                    candidate_id = EXCLUDED.candidate_id,
                    updated_at = NOW()
            """,
                schedule_id,
                schedule.get("applicationId"),
                schedule.get("interviewStageId"),
                status,
                schedule.get("candidateId"),
            )

            # Delete existing events (full replace strategy)
            await conn.execute(
                """
                DELETE FROM interview_events WHERE schedule_id = $1
            """,
                schedule_id,
            )

            # Insert events and assignments
            for event in schedule.get("interviewEvents", []):
                await insert_event_with_assignments(conn, event, schedule_id)

    logger.info("schedule_updated", schedule_id=schedule_id, status=status)


async def insert_event_with_assignments(conn: Any, event: dict[str, Any], schedule_id: str) -> None:
    """
    Insert interview event and associated interviewer assignments.

    Args:
        conn: Database connection from transaction
        event: Event data from webhook
        schedule_id: Schedule UUID
    """
    event_id: str = event["id"]

    # Get interview_id (either from nested interview object or direct reference)
    interview_id = event.get("interviewId")
    if not interview_id and event.get("interview"):
        interview_id = event["interview"]["id"]

    if not interview_id:
        logger.warning("event_missing_interview_id", event_id=event_id)
        return

    # Fetch/update interview definition via API (ensures fresh data)
    # Import here to avoid circular dependency
    from app.clients.ashby import ashby_client

    try:
        response = await ashby_client.post("interview.info", {"id": interview_id})

        if response["success"]:
            interview: dict[str, Any] = response["results"]
            await conn.execute(
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

    # Insert event
    await conn.execute(
        """
        INSERT INTO interview_events
        (event_id, schedule_id, interview_id, created_at, updated_at,
         start_time, end_time, feedback_link, location, meeting_link,
         has_submitted_feedback, extra_data)
        VALUES (
            $1, $2, $3,
            $4::text::timestamptz,
            $5::text::timestamptz,
            $6::text::timestamptz,
            $7::text::timestamptz,
            $8, $9, $10, $11, $12
        )
    """,
        event_id,
        schedule_id,
        interview_id,
        event.get("createdAt"),
        event.get("updatedAt"),
        event.get("startTime"),
        event.get("endTime"),
        event.get("feedbackLink"),
        event.get("location"),
        event.get("meetingLink"),
        event.get("hasSubmittedFeedback", False),
        json.dumps(event.get("extraData", {})),
    )

    # Insert interviewer assignments
    for interviewer in event.get("interviewers", []):
        # Extract nested interviewer pool data
        interviewer_pool = interviewer.get("interviewerPool", {})

        await conn.execute(
            """
            INSERT INTO interview_assignments
            (event_id, interviewer_id, first_name, last_name, email,
             global_role, training_role, is_enabled, manager_id,
             interviewer_pool_id, interviewer_pool_title,
             interviewer_pool_is_archived, training_path, interviewer_updated_at)
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                $14::text::timestamptz
            )
        """,
            event_id,
            interviewer["id"],
            interviewer.get("firstName"),
            interviewer.get("lastName"),
            interviewer.get("email"),
            interviewer.get("globalRole"),
            interviewer.get("trainingRole"),
            interviewer.get("isEnabled", True),
            interviewer.get("managerId"),
            interviewer_pool.get("id"),
            interviewer_pool.get("title"),
            interviewer_pool.get("isArchived", False),
            json.dumps(interviewer_pool.get("trainingPath", {})),
            interviewer.get("updatedAt"),
        )
