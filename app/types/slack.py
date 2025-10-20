"""Type definitions for Slack API payloads."""

from datetime import datetime
from typing import Any, NotRequired, TypedDict


class SlackUserTD(TypedDict):
    """Slack user minimal info."""

    id: str
    name: str
    email: NotRequired[str]


class SlackButtonMetadataTD(TypedDict):
    """Metadata embedded in Slack button value (JSON string)."""

    event_id: str
    form_definition_id: str
    application_id: str
    interviewer_id: str
    candidate_id: str


class SlackModalMetadataTD(TypedDict):
    """Metadata embedded in Slack modal private_metadata (JSON string)."""

    event_id: str
    form_definition_id: str
    application_id: str
    interviewer_id: str
    candidate_id: str


class InterviewDataTD(TypedDict):
    """Interview data dict used internally for building views.

    This is NOT from external API - it's our internal format.
    Uses datetime objects internally; converted to strings at API boundaries.
    """

    event_id: str
    interview_title: str
    start_time: datetime  # datetime object, converted to string at Slack boundary
    form_definition_id: str
    application_id: str
    interviewer_id: str
    end_time: NotRequired[datetime | None]  # datetime or None
    meeting_link: NotRequired[str | None]
    location: NotRequired[str | None]
    feedback_link: NotRequired[str | None]
    instructions_plain: NotRequired[str | None]


class FormValuesDictTD(TypedDict, total=False):
    """Form values dict (field_path -> value).

    Keys are dynamic field paths, values vary by field type.
    Using total=False makes all keys optional.
    """

    pass  # Acts as dict[str, Any] but with a type name


# Slack Block Kit Types (partial coverage for common blocks)


class SlackTextTD(TypedDict):
    """Slack text object."""

    type: str  # "mrkdwn" or "plain_text"
    text: str


class SlackBlockBaseTD(TypedDict):
    """Base for all Slack blocks."""

    type: str


class SlackSectionTD(SlackBlockBaseTD):
    """Slack section block."""

    text: NotRequired[SlackTextTD]
    fields: NotRequired[list[SlackTextTD]]
    accessory: NotRequired[dict[str, Any]]


class SlackDividerTD(SlackBlockBaseTD):
    """Slack divider block."""

    pass  # Only has type field


class SlackActionsTD(SlackBlockBaseTD):
    """Slack actions block."""

    elements: list[dict[str, Any]]  # Button/select elements too varied


class SlackContextTD(SlackBlockBaseTD):
    """Slack context block."""

    elements: list[dict[str, Any]]


# Union type for all block types we use
SlackBlockTD = SlackSectionTD | SlackDividerTD | SlackActionsTD | SlackContextTD
