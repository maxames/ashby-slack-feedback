"""Slack interactions API layer for handling button clicks, modal submissions, and closures."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.datastructures import UploadFile
from structlog import get_logger

from app.clients import ashby, slack
from app.clients.slack_parsers import (
    extract_field_submissions_for_ashby,
    extract_form_values,
)
from app.clients.slack_views import build_feedback_modal
from app.services import feedback
from app.services.sync import get_feedback_form_definition
from app.types.ashby import CandidateTD, FeedbackFormTD
from app.types.slack import InterviewDataTD

logger = get_logger()
router = APIRouter()


@router.post("/slack/interactions")
async def handle_slack_interactions(request: Request) -> Response:
    """
    Handle all interactive component submissions from Slack.

    Thin adapter layer - extracts data and calls service layer.

    Handles:
    - block_actions: Button clicks (open modal) and dispatch actions (Enter key)
    - view_submission: Final feedback submission
    - view_closed: Modal dismissal (logging only)
    """
    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str or isinstance(payload_str, UploadFile):
        return Response(status_code=400)
    payload = json.loads(payload_str)

    # Handle button clicks (open modal)
    if payload["type"] == "block_actions":
        action = payload["actions"][0]

        if action["action_id"] == "open_feedback_modal":
            await handle_open_modal(payload, action)
        elif action["action_id"].startswith("field_"):
            # Handle Enter key press in text fields (dispatch action)
            await handle_dispatch_auto_save(payload)

        return Response(status_code=200)

    # Handle modal submission (final submit)
    elif payload["type"] == "view_submission":
        if payload["view"]["callback_id"] == "submit_feedback":
            # Run async to avoid blocking Slack's 3-second timeout
            asyncio.create_task(handle_feedback_submission(payload))

        return Response(status_code=200)

    # Handle modal close/dismissal
    elif payload["type"] == "view_closed":
        # Log only - view_closed doesn't include state values
        logger.info("modal_closed_by_user")
        return Response(status_code=200)

    return Response(status_code=200)


async def handle_open_modal(payload: dict[str, Any], action: dict[str, Any]) -> None:
    """
    Open feedback modal with candidate context when user clicks 'Submit Feedback' button.

    API layer: Extracts Slack payload → Fetches candidate/interview data → Builds modal.

    Args:
        payload: Slack interaction payload
        action: Button action data
    """
    try:
        # Extract data from button value (Slack-specific)
        button_data = json.loads(action["value"])
        event_id = button_data["event_id"]
        form_definition_id = button_data["form_definition_id"]
        application_id = button_data["application_id"]
        interviewer_id = button_data["interviewer_id"]
        candidate_id = button_data["candidate_id"]

        # Get feedback form definition (business logic)
        form_def: FeedbackFormTD | None = await get_feedback_form_definition(form_definition_id)

        if not form_def:
            logger.error("form_definition_not_found", form_id=form_definition_id)
            return

        # Load existing draft if any (business logic)
        draft_values = await feedback.load_draft(event_id, interviewer_id)

        # Fetch candidate data
        candidate_data: CandidateTD = await ashby.fetch_candidate_info(candidate_id)

        # Fetch interview data from database
        from app.core.database import db

        interview_row = await db.fetchrow(
            """
            SELECT ie.start_time, ie.end_time, ie.meeting_link,
                   i.title AS interview_title, i.instructions_plain
            FROM interview_events ie
            JOIN interviews i ON ie.interview_id = i.interview_id
            WHERE ie.event_id = $1
            """,
            event_id,
        )

        interview_data: InterviewDataTD = {
            "event_id": event_id,
            "form_definition_id": form_definition_id,
            "application_id": application_id,
            "interviewer_id": interviewer_id,
            "interview_title": (interview_row["interview_title"] if interview_row else "Interview"),
            "start_time": (interview_row["start_time"] if interview_row else datetime.now(UTC)),
            "end_time": interview_row["end_time"] if interview_row else None,
            "meeting_link": interview_row["meeting_link"] if interview_row else None,
            "instructions_plain": (interview_row["instructions_plain"] if interview_row else None),
        }

        # Build modal view with candidate and interview context
        modal_view = await build_feedback_modal(
            form_definition=form_def,
            candidate_data=candidate_data,
            interview_data=interview_data,
            draft_values=draft_values,
        )

        # Open modal using trigger_id from button click (Slack-specific)
        await slack.slack_client.open_modal(trigger_id=payload["trigger_id"], view=modal_view)

        logger.info("feedback_modal_opened", event_id=event_id)

    except Exception as e:
        logger.exception("failed_to_open_feedback_modal", error=str(e))


async def handle_dispatch_auto_save(payload: dict[str, Any]) -> None:
    """
    Auto-save draft when user hits Enter in a multiline text field.

    Triggered by dispatch_action_config on RichText fields.

    Args:
        payload: Slack block_actions payload with view state
    """
    try:
        # Extract metadata from modal (Slack-specific)
        metadata = json.loads(payload["view"]["private_metadata"])
        event_id = metadata["event_id"]
        interviewer_id = metadata["interviewer_id"]

        # Extract current form values from modal state (Slack-specific)
        state_values = payload["view"]["state"]["values"]
        form_values = extract_form_values(state_values)

        # Save draft (business logic)
        await feedback.save_draft(event_id, interviewer_id, form_values)

        logger.info("draft_auto_saved_on_enter", event_id=event_id)

    except Exception as e:
        logger.error("failed_to_auto_save_on_enter", error=str(e))


async def handle_feedback_submission(payload: dict[str, Any]) -> None:
    """
    Process final feedback form submission.

    API layer: Extracts Slack payload → Calls service layer → Sends confirmation.

    Args:
        payload: Slack view_submission payload
    """
    try:
        # Extract metadata from modal (Slack-specific)
        metadata = json.loads(payload["view"]["private_metadata"])
        event_id = metadata["event_id"]
        form_definition_id = metadata["form_definition_id"]
        application_id = metadata["application_id"]
        interviewer_id = metadata["interviewer_id"]
        slack_user_id = payload["user"]["id"]

        # Extract form values and transform for Ashby (Slack-specific)
        state_values = payload["view"]["state"]["values"]
        field_submissions = extract_field_submissions_for_ashby(state_values)

        # Submit feedback to Ashby (business logic)
        await feedback.submit_feedback(
            event_id=event_id,
            form_definition_id=form_definition_id,
            application_id=application_id,
            interviewer_id=interviewer_id,
            field_submissions=field_submissions,
        )

        # Send confirmation DM to user (Slack-specific)
        await slack.slack_client.send_dm(
            slack_user_id,
            (
                "✅ *Feedback submitted successfully*\n\n"
                "Thank you for completing the interview feedback!"
            ),
        )

        logger.info("feedback_submitted_successfully", event_id=event_id)

    except Exception as e:
        logger.exception("failed_to_process_feedback_submission", error=str(e))

        # Notify user of error (Slack-specific, best effort)
        try:
            await slack.slack_client.send_dm(
                payload["user"]["id"],
                f"❌ *Failed to submit feedback*\n\n{str(e)}",
            )
        except Exception:
            # Suppress errors in error notification to avoid cascading failures
            pass
