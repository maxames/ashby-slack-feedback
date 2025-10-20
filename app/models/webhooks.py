"""Pydantic models for webhook payloads."""

from typing import Any

from pydantic import BaseModel


class AshbyWebhookPayload(BaseModel):
    """
    Ashby webhook payload structure.

    Minimal validation - just ensure required fields exist.
    Based on Ashby's actual webhook format.
    """

    action: str  # e.g., "interviewScheduleUpdate"
    data: dict[str, Any]  # Keep as dict - structure varies by action

    # Optional fields that may or may not be present
    webhookId: str | None = None
    webhookToken: str | None = None

    class Config:
        """Pydantic configuration."""

        extra = "allow"  # Allow additional fields


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: str | None = None
