"""Scheduler service for background jobs."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from structlog import get_logger

from app.services.reminders import send_feedback_reminders
from app.services.sync import sync_feedback_forms, sync_interviews, sync_slack_users

logger = get_logger()

# Create scheduler instance
scheduler = AsyncIOScheduler()


def setup_scheduler() -> None:
    """
    Configure scheduler with all background jobs.

    Jobs:
    - send_feedback_reminders: Every 5 minutes
    - sync_feedback_forms: Every 6 hours
    - sync_interviews: Every 12 hours
    - sync_slack_users: Every 12 hours

    All jobs use coalesce=True and max_instances=1 to prevent overlaps.
    """
    # Send interview reminders every 5 minutes
    scheduler.add_job(
        send_feedback_reminders,
        trigger="interval",
        minutes=5,
        id="feedback_reminders",
        replace_existing=True,
        coalesce=True,  # Skip if previous run still executing
        max_instances=1,  # Only one instance at a time
    )

    # Sync feedback form definitions every 6 hours
    scheduler.add_job(
        sync_feedback_forms,
        trigger="interval",
        hours=6,
        id="sync_feedback_forms",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # Sync interview definitions every 12 hours
    scheduler.add_job(
        sync_interviews,
        trigger="interval",
        hours=12,
        id="sync_interviews",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # Sync Slack users every 12 hours
    scheduler.add_job(
        sync_slack_users,
        trigger="interval",
        hours=12,
        id="sync_slack_users",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    logger.info("scheduler_configured", jobs=4)


def start_scheduler() -> None:
    """Start the scheduler."""
    scheduler.start()
    logger.info("scheduler_started")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    scheduler.shutdown(wait=True)
    logger.info("scheduler_shutdown")
