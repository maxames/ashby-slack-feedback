"""Slack client for sending messages and opening modals."""

from __future__ import annotations

from typing import Any

from slack_sdk.web.async_client import AsyncSlackResponse, AsyncWebClient
from structlog import get_logger

from app.core.config import settings

logger = get_logger()


class SlackClient:
    """Wrapper around Slack SDK for app-specific operations."""

    def __init__(self):
        self.client = AsyncWebClient(token=settings.slack_bot_token)

    async def send_dm(
        self, user_id: str, text: str, blocks: list[dict[str, Any]] | None = None
    ) -> AsyncSlackResponse:
        """
        Send direct message to user.

        Args:
            user_id: Slack user ID (U123456)
            text: Fallback text
            blocks: Block Kit blocks

        Returns:
            Slack API response

        Raises:
            Exception: If message send fails
        """
        try:
            response = await self.client.chat_postMessage(channel=user_id, text=text, blocks=blocks)
            logger.info("slack_dm_sent", user_id=user_id)
            return response
        except Exception as e:
            logger.error("slack_dm_failed", user_id=user_id, error=str(e))
            raise

    async def open_modal(self, trigger_id: str, view: dict[str, Any]) -> AsyncSlackResponse:
        """
        Open a modal view.

        Args:
            trigger_id: Trigger ID from interaction payload
            view: Modal view definition

        Returns:
            Slack API response
        """
        return await self.client.views_open(trigger_id=trigger_id, view=view)

    async def register_remote_file(self, external_id: str, url: str, title: str) -> str | None:
        """
        Register remote file with Slack.

        Args:
            external_id: Unique identifier for file
            url: URL to file
            title: Display title

        Returns:
            external_id if successful, None otherwise
        """
        try:
            response = await self.client.files_remote_add(
                external_id=external_id,
                external_url=url,
                title=title,
                filetype="pdf",
            )
            return external_id if response["ok"] else None
        except Exception as e:
            logger.error("slack_file_register_failed", error=str(e))
            return None


# Module singleton
slack_client = SlackClient()
