"""Ashby webhook handler."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from structlog import get_logger

from app.core.config import settings
from app.core.database import db
from app.models.webhooks import AshbyWebhookPayload
from app.utils.security import verify_ashby_signature

logger = get_logger()
router = APIRouter()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@router.post("/webhooks/ashby")
@limiter.limit("100/minute")
async def handle_ashby_webhook(request: Request) -> Response:
    """
    Receive and process Ashby webhook events.

    Handles:
    - Ping/test webhooks (returns 200 for setup verification)
    - Interview schedule updates with signature verification

    Returns 200/204 on success, 401/400 on errors.
    """
    # Get raw body
    body = await request.body()

    # Parse payload first to check if it's a ping
    try:
        payload_dict = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error("webhook_invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    # Handle ping/test webhook (no signature required)
    # Ashby sends this during webhook setup to verify the URL works
    if payload_dict.get("action") == "ping" or payload_dict.get("type") == "ping":
        logger.info("webhook_ping_received")
        return Response(status_code=200, content=json.dumps({"status": "ok"}))

    # For real webhooks, require signature
    # Ashby uses "Ashby-Signature" header (not "X-Ashby-Signature")
    signature = request.headers.get("Ashby-Signature")

    if not signature:
        logger.warning("webhook_missing_signature_header")
        raise HTTPException(status_code=401, detail="Missing Ashby-Signature header")

    # Verify signature (constant-time comparison)
    if not verify_ashby_signature(settings.ashby_webhook_secret, body, signature):
        logger.warning("webhook_signature_verification_failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Validate payload structure
    try:
        payload = AshbyWebhookPayload(**payload_dict)
    except Exception as e:
        logger.error("webhook_validation_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid payload structure") from e

    logger.info(
        "webhook_received",
        action=payload.action,
        schedule_id=payload.data.get("interviewSchedule", {}).get("id"),
    )

    # Log to audit table
    schedule_id = payload.data.get("interviewSchedule", {}).get("id")
    await db.execute(
        """
        INSERT INTO ashby_webhook_payloads (schedule_id, received_at, action, payload)
        VALUES ($1, NOW(), $2, $3)
    """,
        schedule_id,
        payload.action,
        json.dumps(payload_dict),
    )

    # Process based on action
    if payload.action == "interviewScheduleUpdate":
        await handle_interview_schedule_update(payload.data)
    else:
        logger.info("webhook_action_ignored", action=payload.action)

    return Response(status_code=204)


async def handle_interview_schedule_update(data: dict[str, Any]) -> None:
    """
    Process interviewScheduleUpdate webhook.

    Thin adapter: extract data and call service layer.
    """
    from app.services.interviews import process_schedule_update

    schedule: dict[str, Any] | None = data.get("interviewSchedule")
    if not schedule:
        logger.error("webhook_missing_schedule_data")
        return

    # Call business logic layer
    await process_schedule_update(schedule)
