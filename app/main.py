"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.slack_interactions import router as slack_router
from app.api.webhooks import limiter
from app.api.webhooks import router as webhook_router
from app.core.database import db
from app.core.logging import logger, setup_logging
from app.services.scheduler import setup_scheduler, shutdown_scheduler, start_scheduler
from app.services.sync import sync_feedback_forms, sync_interviews, sync_slack_users

# Configure logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    logger.info("application_starting")
    await db.connect()
    setup_scheduler()
    start_scheduler()

    try:
        await sync_feedback_forms()
        await sync_interviews()
        await sync_slack_users()
    except Exception:
        logger.exception("initial_sync_failed")

    logger.info("application_ready")

    yield

    # Shutdown
    logger.info("application_shutting_down")
    shutdown_scheduler()
    await db.disconnect()
    logger.info("application_stopped")


# Create FastAPI app
app = FastAPI(
    title="Ashby Slack Feedback",
    description="Interview feedback reminders via Slack",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(webhook_router)
app.include_router(slack_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint.

    Verifies database connectivity and reports pool stats.

    Returns:
        dict: Health status with database and connection pool information

    Raises:
        HTTPException: 503 if database is unavailable
    """
    try:
        await db.fetchval("SELECT 1")

        # Get connection pool stats
        if not db.pool:
            raise RuntimeError("Database pool not initialized")

        pool_size = db.pool.get_size()
        pool_free = db.pool.get_idle_size()

        return {
            "status": "healthy",
            "database": "connected",
            "pool": {
                "size": pool_size,
                "free": pool_free,
                "in_use": pool_size - pool_free,
            },
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Database unavailable") from e


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Ashby Slack Feedback Application"}
