"""Feedback service for draft management and submission."""

from __future__ import annotations

import json

from structlog import get_logger

from app.clients import ashby
from app.core.database import db
from app.types.ashby import FieldSubmissionTD
from app.types.slack import FormValuesDictTD

logger = get_logger()


async def load_draft(event_id: str, interviewer_id: str) -> FormValuesDictTD:
    """
    Load feedback draft from database.

    Args:
        event_id: Interview event UUID
        interviewer_id: Ashby interviewer UUID

    Returns:
        Dict of form values or empty dict if no draft exists
    """
    draft = await db.fetchrow(
        """
        SELECT form_values
        FROM feedback_drafts
        WHERE event_id = $1 AND interviewer_id = $2
    """,
        event_id,
        interviewer_id,
    )

    if draft:
        logger.info("draft_loaded", event_id=event_id, interviewer_id=interviewer_id)
        return json.loads(draft["form_values"])

    return {}


async def save_draft(
    event_id: str, interviewer_id: str, form_values: FormValuesDictTD
) -> None:
    """
    Save or update feedback draft in database.

    Args:
        event_id: Interview event UUID
        interviewer_id: Ashby interviewer UUID
        form_values: Dict of field_path → value mappings
    """
    # Business rule: Only save if there's actual content
    if not form_values:
        logger.info("skipping_empty_draft", event_id=event_id)
        return

    await db.execute(
        """
        INSERT INTO feedback_drafts (event_id, interviewer_id, form_values, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (event_id, interviewer_id)
        DO UPDATE SET
            form_values = EXCLUDED.form_values,
            updated_at = NOW()
    """,
        event_id,
        interviewer_id,
        json.dumps(form_values),
    )

    logger.info("draft_saved", event_id=event_id, interviewer_id=interviewer_id)


async def delete_draft(event_id: str, interviewer_id: str) -> None:
    """
    Delete feedback draft from database.

    Args:
        event_id: Interview event UUID
        interviewer_id: Ashby interviewer UUID
    """
    await db.execute(
        """
        DELETE FROM feedback_drafts
        WHERE event_id = $1 AND interviewer_id = $2
    """,
        event_id,
        interviewer_id,
    )

    logger.info("draft_deleted", event_id=event_id, interviewer_id=interviewer_id)


async def submit_feedback(
    event_id: str,
    form_definition_id: str,
    application_id: str,
    interviewer_id: str,
    field_submissions: list[FieldSubmissionTD],
) -> None:
    """
    Submit feedback to Ashby and mark as complete.

    Steps:
    1. Submit feedback via Ashby API
    2. Update feedback_reminders_sent.submitted_at
    3. Delete draft (no longer needed)

    Args:
        event_id: Interview event UUID
        form_definition_id: Ashby form definition UUID
        application_id: Ashby application UUID
        interviewer_id: Ashby interviewer UUID
        field_submissions: List of {path, value} dicts for Ashby API

    Raises:
        Exception: If Ashby API submission fails
    """
    # Submit to Ashby
    await ashby.ashby_client.post(
        "applicationFeedback.submit",
        {
            "formDefinitionId": form_definition_id,
            "applicationId": application_id,
            "userId": interviewer_id,
            "interviewEventId": event_id,
            "feedbackForm": {"fieldSubmissions": field_submissions},
        },
    )

    logger.info(
        "feedback_submitted_to_ashby",
        event_id=event_id,
        interviewer_id=interviewer_id,
        form_id=form_definition_id,
    )

    # Mark as submitted in database
    await db.execute(
        """
        UPDATE feedback_reminders_sent
        SET submitted_at = NOW()
        WHERE event_id = $1 AND interviewer_id = $2
    """,
        event_id,
        interviewer_id,
    )

    # Delete draft (no longer needed)
    await delete_draft(event_id, interviewer_id)

    logger.info("feedback_submission_complete", event_id=event_id)
