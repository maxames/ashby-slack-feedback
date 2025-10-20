"""Database connection pool management."""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
from structlog import get_logger

from app.core.config import settings

logger = get_logger()


class Database:
    """Database connection pool manager."""

    def __init__(self) -> None:
        """Initialize database manager."""
        self.pool: asyncpg.Pool | None = None

    async def connect(self, max_retries: int = 3) -> None:
        """
        Create connection pool on startup with retry logic.

        Args:
            max_retries: Maximum number of connection attempts

        Raises:
            Exception: If connection fails after all retries
        """
        for attempt in range(1, max_retries + 1):
            try:
                self.pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                )
                logger.info("database_connected", min_size=2, max_size=10, attempt=attempt)
                return
            except Exception as e:
                logger.error("database_connection_failed", attempt=attempt, error=str(e))
                if attempt == max_retries:
                    logger.critical("database_connection_exhausted", max_retries=max_retries)
                    raise
                # Exponential backoff
                await asyncio.sleep(2**attempt)

    async def disconnect(self) -> None:
        """Close pool on shutdown."""
        if self.pool:
            await self.pool.close()
            logger.info("database_disconnected")

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Fetch multiple rows."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Fetch a single row."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch a single value."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


db = Database()
