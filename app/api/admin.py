"""Admin endpoints for operational tasks."""

from __future__ import annotations

from fastapi import APIRouter
from structlog import get_logger

from app.core.database import db
from app.services.sync import sync_feedback_forms, sync_slack_users

logger = get_logger()
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sync-forms")
async def admin_sync_forms() -> dict[str, str]:
    """
    Manually trigger feedback form sync from Ashby.

    Useful for immediate refresh after form changes.
    """
    logger.info("admin_sync_forms_triggered")
    await sync_feedback_forms()
    return {"status": "completed", "message": "Feedback forms synced"}


@router.post("/sync-slack-users")
async def admin_sync_slack_users() -> dict[str, str]:
    """
    Manually trigger Slack user sync.

    Useful after new employees join or email changes.
    """
    logger.info("admin_sync_slack_users_triggered")
    await sync_slack_users()
    return {"status": "completed", "message": "Slack users synced"}


@router.get("/stats")
async def admin_stats() -> dict[str, int]:
    """
    Get application statistics.

    Returns:
        Dict with counts of reminders, pending feedback, drafts, forms, and users
    """
    stats = {}

    # Count reminders sent
    stats["reminders_sent"] = await db.fetchval(
        """
        SELECT COUNT(*) FROM feedback_reminders_sent
    """
    )

    # Count pending feedback
    stats["pending_feedback"] = await db.fetchval(
        """
        SELECT COUNT(*) FROM feedback_reminders_sent
        WHERE submitted_at IS NULL
    """
    )

    # Count active drafts
    stats["active_drafts"] = await db.fetchval(
        """
        SELECT COUNT(*) FROM feedback_drafts
    """
    )

    # Count feedback forms
    stats["feedback_forms"] = await db.fetchval(
        """
        SELECT COUNT(*) FROM feedback_form_definitions
        WHERE NOT is_archived
    """
    )

    # Count Slack users
    stats["slack_users"] = await db.fetchval(
        """
        SELECT COUNT(*) FROM slack_users
        WHERE NOT deleted
    """
    )

    logger.info("admin_stats_retrieved", **stats)
    return stats
