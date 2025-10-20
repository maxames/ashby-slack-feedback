"""Feedback reminder service for sending interview reminders via Slack."""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from app.clients.ashby import fetch_candidate_info, fetch_resume_url
from app.clients.slack import slack_client
from app.clients.slack_views import build_reminder_message
from app.core.database import db

logger = get_logger()


async def send_feedback_reminders() -> None:
    """
    Find interviews starting in 4-20 minutes and send reminder DMs.
    Runs every 5 minutes via scheduler.

    Query logic:
    - Start time between NOW() + 4 minutes and NOW() + 20 minutes
    - Status = 'Scheduled'
    - Not already sent (NOT EXISTS in feedback_reminders_sent)
    - Has Slack user mapping (INNER JOIN slack_users)

    Wide window (4-20 min) ensures no interviews fall through the cracks
    with 5-min job intervals. Duplicates prevented by feedback_reminders_sent check.
    """
    try:
        query = """
            SELECT
                ie.event_id,
                ie.start_time,
                ie.end_time,
                ie.meeting_link,
                ie.location,
                ie.feedback_link,
                ia.interviewer_id,
                ia.email AS interviewer_email,
                ia.first_name,
                ia.last_name,
                su.slack_user_id,
                i.title AS interview_title,
                i.instructions_plain,
                i.job_id,
                i.feedback_form_definition_id,
                s.candidate_id,
                s.application_id,
                s.interview_stage_id
            FROM interview_events ie
            JOIN interview_assignments ia ON ie.event_id = ia.event_id
            JOIN interviews i ON ie.interview_id = i.interview_id
            JOIN interview_schedules s ON ie.schedule_id = s.schedule_id
            JOIN slack_users su ON ia.email = su.email
            WHERE ie.start_time BETWEEN NOW() + INTERVAL '4 minutes'
                                    AND NOW() + INTERVAL '20 minutes'
              AND s.status = 'Scheduled'
              AND NOT EXISTS (
                  SELECT 1 FROM feedback_reminders_sent frs
                  WHERE frs.event_id = ie.event_id
                    AND frs.interviewer_id = ia.interviewer_id
              )
        """

        results = await db.fetch(query)

        if not results:
            logger.info("no_reminders_to_send")
            return

        logger.info("processing_reminders", count=len(results))

        for row in results:
            try:
                # Convert asyncpg.Record to plain dict
                row_dict = {str(k): v for k, v in dict(row).items()}
                await send_single_reminder(row_dict)
            except Exception as e:
                logger.error(
                    "failed_to_send_single_reminder",
                    event_id=row["event_id"],
                    error=str(e),
                )

        logger.info("reminders_batch_complete", sent=len(results))

    except Exception:
        logger.exception("send_feedback_reminders_job_failed")


async def send_single_reminder(row: dict[str, Any]) -> None:
    """
    Send a single feedback reminder DM.

    Args:
        row: Database row with interview and interviewer data
    """
    event_id = row["event_id"]

    # Fetch candidate information
    candidate_data = await fetch_candidate_info(row["candidate_id"])

    # Fetch job title if available (with caching)
    from app.services.sync import sync_job_info

    job_title = None
    if row.get("job_id"):
        job_info = await sync_job_info(row["job_id"])
        if job_info:
            job_title = job_info.get("title")

    # Fetch resume URL if available
    resume_url = None
    file_external_id = None
    if candidate_data.get("resumeFileHandle"):
        resume_url = await fetch_resume_url(candidate_data["resumeFileHandle"]["handle"])

        # Register remote file with Slack
        if resume_url:
            file_external_id = await slack_client.register_remote_file(
                external_id=f"resume_{row['candidate_id']}",
                url=resume_url,
                title=candidate_data["resumeFileHandle"]["name"],
            )

    # Build comprehensive reminder message
    blocks = build_reminder_message(
        candidate_data=candidate_data,
        interview_data={
            "event_id": event_id,
            "interview_title": row["interview_title"],
            "start_time": row["start_time"],
            "end_time": row.get("end_time"),
            "meeting_link": row.get("meeting_link"),
            "location": row.get("location"),
            "feedback_link": row.get("feedback_link"),
            "instructions_plain": row.get("instructions_plain"),
            "form_definition_id": row["feedback_form_definition_id"],
            "application_id": row["application_id"],
            "interviewer_id": row["interviewer_id"],
        },
        file_external_id=file_external_id,
        job_title=job_title,
    )

    # Send DM
    response = await slack_client.send_dm(
        user_id=row["slack_user_id"],
        text=f"Interview feedback reminder for {candidate_data['name']}",
        blocks=blocks,
    )

    # Track reminder sent
    await db.execute(
        """
        INSERT INTO feedback_reminders_sent
        (event_id, interviewer_id, slack_user_id, slack_channel_id,
         slack_message_ts, sent_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
    """,
        event_id,
        row["interviewer_id"],
        row["slack_user_id"],
        response["channel"],
        response["ts"],
    )

    logger.info(
        "feedback_reminder_sent",
        event_id=event_id,
        interviewer_id=row["interviewer_id"],
    )
