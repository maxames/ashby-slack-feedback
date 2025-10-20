"""Slack Block Kit views for modals and messages."""

from __future__ import annotations

import json
from typing import Any

from structlog import get_logger

from app.clients.slack_field_builders import build_input_block_from_field
from app.types.ashby import CandidateTD, FeedbackFormTD
from app.types.slack import FormValuesDictTD, InterviewDataTD
from app.utils.time import format_slack_timestamp

logger = get_logger()


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length with ellipsis if needed."""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."


def validate_message_length(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Ensure message doesn't exceed Slack's ~40KB limit.

    Args:
        blocks: List of Slack Block Kit blocks

    Returns:
        Validated blocks (truncated if needed)
    """
    message_size = len(json.dumps(blocks))

    if message_size > 35000:  # Leave 5KB buffer
        logger.warning("message_too_large", size=message_size)
        # Remove optional sections if needed
        # For now, just log the warning

    return blocks


async def build_feedback_modal(
    form_definition: FeedbackFormTD,
    candidate_data: CandidateTD,
    interview_data: InterviewDataTD,
    draft_values: FormValuesDictTD | None = None,
) -> dict[str, Any]:  # Slack modal structure is too complex to type fully
    """
    Build Slack modal view with feedback form inputs and candidate context.

    Args:
        form_definition: Ashby form definition structure
        candidate_data: Candidate info from Ashby
        interview_data: Interview details (title, time, meeting link, etc.)
        draft_values: Pre-loaded draft values (optional)

    Returns:
        Slack modal view dict
    """
    if draft_values is None:
        draft_values = {}

    blocks = []

    # Candidate header section
    candidate_name = candidate_data.get("name", "Candidate")
    position = candidate_data.get("position", "")
    company = candidate_data.get("company", "")
    interview_title = interview_data.get("interview_title", "Interview")

    header_text = f"*{candidate_name}* • {interview_title}"
    if position and company:
        header_text += f"\n{position} at {company}"

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": header_text}})

    # Links section
    links = []
    if candidate_data.get("resumeFileHandle"):
        links.append("📄 Resume")
    for social in candidate_data.get("socialLinks", [])[:3]:  # Limit to 3
        links.append(social.get("type", "Link"))
    if candidate_data.get("profileUrl"):
        links.append("Ashby Profile")

    if links:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " • ".join(links)}],
            }
        )

    # Meeting info
    start_time = interview_data.get("start_time")
    end_time = interview_data.get("end_time")
    meeting_link = interview_data.get("meeting_link")

    if start_time:
        duration_text = ""
        if end_time:
            duration_mins = int((end_time - start_time).total_seconds() / 60)
            duration_text = f" ({duration_mins} min)"

        meeting_text = f"⏰ {format_slack_timestamp(start_time)}{duration_text}"
        if meeting_link:
            meeting_text += f" • <{meeting_link}|Join Meeting>"

        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": meeting_text}]})

    # Full interview instructions (not truncated in modal)
    instructions = interview_data.get("instructions_plain")
    if instructions:
        # Limit to 500 chars in modal to avoid overwhelming
        truncated_instructions = (
            instructions[:500] + "..." if len(instructions) > 500 else instructions
        )
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📝 Instructions:*\n{truncated_instructions}",
                },
            }
        )

    blocks.append({"type": "divider"})  # Separate header from form

    # Extract the actual form definition structure
    # Ashby API returns: {id, title, formDefinition: {sections: [...]}}
    form_def = form_definition.get("formDefinition", form_definition)

    # Build dynamic input blocks from form definition
    for section in form_def.get("sections", []):
        # Section header (if present)
        if section.get("title"):
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{section['title']}*"},
                }
            )

        # Add input blocks for each field
        for field_config in section.get("fields", []):
            field = field_config["field"]
            input_block = build_input_block_from_field(
                field, field_config, draft_values.get(field["path"])
            )
            if input_block:
                blocks.append(input_block)

    # Draft info
    blocks.append({"type": "divider"})

    if draft_values:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "💾 _Draft auto-saved previously_"}],
            }
        )
    else:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_💾 Tip: Press Enter to save your progress as you work_",
                    }
                ],
            }
        )

    # Build modal view
    event_id = interview_data.get("event_id", "")
    form_definition_id = interview_data.get("form_definition_id", "")
    application_id = interview_data.get("application_id", "")
    interviewer_id = interview_data.get("interviewer_id", "")

    modal_view = {
        "type": "modal",
        "callback_id": "submit_feedback",
        "notify_on_close": True,
        "private_metadata": json.dumps(
            {
                "event_id": event_id,
                "form_definition_id": form_definition_id,
                "application_id": application_id,
                "interviewer_id": interviewer_id,
                "candidate_id": candidate_data.get("id", ""),
            }
        ),
        "title": {"type": "plain_text", "text": "Interview Feedback"},
        "submit": {"type": "plain_text", "text": "Submit Feedback"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }

    return modal_view


def build_reminder_message(
    candidate_data: CandidateTD,
    interview_data: InterviewDataTD,
    file_external_id: str | None,
    job_title: str | None = None,
) -> list[dict[str, Any]]:  # Slack blocks are too dynamic to type fully
    """
    Build comprehensive Slack Block Kit message for feedback reminder.

    Args:
        candidate_data: Candidate info from Ashby
        interview_data: All interview fields (title, times, links, etc.)
        file_external_id: Slack file ID if resume registered
        job_title: Optional job title from job.info API

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    # Section 1: Header
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📋 Interview Feedback Reminder"},
        }
    )

    # Section 2: Candidate Information
    candidate_name = candidate_data.get("name", "Candidate")
    primary_email = candidate_data.get("primaryEmailAddress", {}).get("value", "")
    primary_phone = candidate_data.get("primaryPhoneNumber", {}).get("value", "")
    location = candidate_data.get("location", {}).get("locationSummary", "")
    timezone = candidate_data.get("timezone", "")
    position = candidate_data.get("position", "")
    company = candidate_data.get("company", "")
    school = candidate_data.get("school", "")

    info_text = f"*{candidate_name}*\n"
    if primary_email:
        info_text += f"📧 {primary_email}\n"
    if primary_phone:
        info_text += f"📱 {primary_phone}\n"
    if position and company:
        info_text += f"💼 {position} at {company}\n"
    if school:
        info_text += f"🎓 {school}\n"
    if location:
        info_text += f"📍 {location}"
    if timezone:
        info_text += f" • {timezone}"

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": info_text}})

    # Section 3: Social Links
    links = []
    for social in candidate_data.get("socialLinks", []):
        url = social.get("url", "")
        link_type = social.get("type", "Link")
        if url:
            links.append(f"<{url}|{link_type}>")

    profile_url = candidate_data.get("profileUrl")
    if profile_url:
        links.append(f"<{profile_url}|Ashby Profile>")

    if links:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " • ".join(links)}],
            }
        )

    # Section 4: Resume
    if file_external_id:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📄 *Resume:* <slack://file?id={file_external_id}|View Resume>",
                },
            }
        )

    # Section 5: Interview Details
    blocks.append({"type": "divider"})

    # Calculate duration
    start_time = interview_data["start_time"]
    end_time = interview_data.get("end_time")
    duration_text = ""
    if end_time:
        duration_mins = int((end_time - start_time).total_seconds() / 60)
        duration_text = f" ({duration_mins} min)"

    # Build interview details
    interview_title = interview_data.get("interview_title", "Interview")
    interview_text = f"*📅 {interview_title}*\n"

    if job_title:
        interview_text += f"Position: {job_title}\n"

    interview_text += f"Start: {format_slack_timestamp(start_time)}\n"

    if end_time:
        interview_text += f"End: {format_slack_timestamp(end_time)}{duration_text}\n"

    location_str = interview_data.get("location")
    if location_str:
        interview_text += f"📍 {location_str}\n"

    meeting_link = interview_data.get("meeting_link")
    if meeting_link:
        interview_text += f"🔗 <{meeting_link}|Join Meeting>"

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": interview_text}})

    # Section 6: Interview Instructions
    instructions = interview_data.get("instructions_plain")
    if instructions:
        # Show truncated with note about full version in modal
        truncated = truncate_text(instructions, 200)

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*📝 Instructions:*\n{truncated}"},
            }
        )

        # If instructions were truncated, add note
        if len(instructions) > 200:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": (
                                "_Full instructions will be shown when you open the feedback form_"
                            ),
                        }
                    ],
                }
            )

    # Section 7: Action Button & Footer
    blocks.append({"type": "divider"})

    # Submit feedback button
    button_value = json.dumps(
        {
            "event_id": str(interview_data["event_id"]),
            "form_definition_id": str(interview_data["form_definition_id"]),
            "application_id": str(interview_data["application_id"]),
            "interviewer_id": str(interview_data["interviewer_id"]),
            "candidate_id": str(candidate_data["id"]),
        }
    )

    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Submit Feedback"},
                    "style": "primary",
                    "action_id": "open_feedback_modal",
                    "value": button_value,
                }
            ],
        }
    )

    # Footer with alternative options
    footer_text = "_Click the button above to provide your interview feedback_"
    feedback_link = interview_data.get("feedback_link")
    if feedback_link:
        footer_text += f" or <{feedback_link}|use Ashby directly>"

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer_text}]})

    # Validate message length before returning
    return validate_message_length(blocks)
