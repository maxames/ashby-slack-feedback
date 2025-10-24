"""Mock client classes for testing external API interactions."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock


class MockAshbyClient:
    """Mock Ashby API client with queue-based response system."""

    def __init__(self) -> None:
        """Initialize mock client with empty response queue."""
        self.responses: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.api_key = "test_api_key"
        self.base_url = "https://api.ashbyhq.com"
        self.headers = {
            "Authorization": "Basic dGVzdF9hcGlfa2V5Og==",
            "Accept": "application/json; version=1",
            "Content-Type": "application/json",
        }

    def add_response(self, endpoint: str, response: dict[str, Any]) -> None:
        """
        Add a response to the queue for a specific endpoint.

        Args:
            endpoint: API endpoint (e.g., "candidate.info")
            response: Response dict to return
        """
        if endpoint not in self.responses:
            self.responses[endpoint] = []
        self.responses[endpoint].append(response)

    async def post(self, endpoint: str, json_data: dict[str, Any]) -> dict[str, Any]:
        """
        Mock POST request that returns queued responses.

        Args:
            endpoint: API endpoint
            json_data: Request body

        Returns:
            Next response in queue for this endpoint

        Raises:
            Exception: If no response configured for endpoint
        """
        self.calls.append((endpoint, json_data))

        if endpoint not in self.responses or not self.responses[endpoint]:
            raise Exception(f"No mock response configured for endpoint: {endpoint}")

        return self.responses[endpoint].pop(0)

    def was_called(self, endpoint: str) -> bool:
        """
        Check if endpoint was called.

        Args:
            endpoint: API endpoint to check

        Returns:
            True if endpoint was called
        """
        return any(call[0] == endpoint for call in self.calls)

    def get_call_count(self, endpoint: str) -> int:
        """
        Get number of calls to endpoint.

        Args:
            endpoint: API endpoint to count

        Returns:
            Number of times endpoint was called
        """
        return sum(1 for call in self.calls if call[0] == endpoint)

    def get_last_call(self, endpoint: str) -> dict[str, Any] | None:
        """
        Get the last call data for an endpoint.

        Args:
            endpoint: API endpoint

        Returns:
            Last call data or None if not called
        """
        for call in reversed(self.calls):
            if call[0] == endpoint:
                return call[1]
        return None

    def reset(self) -> None:
        """Reset all responses and call history."""
        self.responses.clear()
        self.calls.clear()


class MockSlackClient:
    """Mock Slack client with configurable responses."""

    def __init__(self) -> None:
        """Initialize mock Slack client."""
        self.dm_responses: list[dict[str, Any]] = []
        self.modal_responses: list[dict[str, Any]] = []
        self.file_responses: list[str] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.client = AsyncMock()

        # Setup default mocks for Slack SDK methods
        self.client.users_list = AsyncMock(return_value={"ok": True, "members": []})

    def add_dm_response(self, response: dict[str, Any]) -> None:
        """
        Add a DM send response.

        Args:
            response: Response dict (should include 'channel' and 'ts')
        """
        self.dm_responses.append(response)

    def add_modal_response(self, response: dict[str, Any]) -> None:
        """
        Add a modal open response.

        Args:
            response: Response dict from Slack
        """
        self.modal_responses.append(response)

    def add_file_response(self, external_id: str) -> None:
        """
        Add a file registration response.

        Args:
            external_id: External file ID to return
        """
        self.file_responses.append(external_id)

    async def open_modal(self, trigger_id: str, view: dict[str, Any]) -> dict[str, Any]:
        """
        Mock modal opening.

        Args:
            trigger_id: Slack trigger ID
            view: Modal view definition

        Returns:
            Mock response
        """
        self.calls.append(("open_modal", {"trigger_id": trigger_id, "view": view}))

        if not self.modal_responses:
            return {"ok": True}

        return self.modal_responses.pop(0)

    async def views_open(self, trigger_id: str, view: dict[str, Any]) -> dict[str, Any]:
        """
        Compatibility method for Slack SDK views.open API.

        Args:
            trigger_id: Slack trigger ID
            view: Modal view definition

        Returns:
            Mock response
        """
        return await self.open_modal(trigger_id, view)

    async def send_dm(
        self, user_id: str, text: str, blocks: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Mock DM sending.

        Args:
            user_id: Slack user ID
            text: Message text
            blocks: Optional Block Kit blocks

        Returns:
            Mock response with channel and ts
        """
        self.calls.append(
            ("send_dm", {"user_id": user_id, "text": text, "blocks": blocks})
        )

        if not self.dm_responses:
            return {
                "ok": True,
                "channel": f"D{user_id[1:]}",
                "ts": "1234567890.123456",
            }

        return self.dm_responses.pop(0)

    async def register_remote_file(
        self, external_id: str, url: str, title: str
    ) -> str | None:
        """
        Mock remote file registration.

        Args:
            external_id: External file identifier
            url: File URL
            title: File title

        Returns:
            External file ID
        """
        self.calls.append(
            (
                "register_remote_file",
                {"external_id": external_id, "url": url, "title": title},
            )
        )

        if not self.file_responses:
            return external_id

        return self.file_responses.pop(0)

    def was_called(self, method: str) -> bool:
        """
        Check if method was called.

        Args:
            method: Method name to check

        Returns:
            True if method was called
        """
        return any(call[0] == method for call in self.calls)

    def get_call_count(self, method: str) -> int:
        """
        Get number of calls to method.

        Args:
            method: Method name to count

        Returns:
            Number of times method was called
        """
        return sum(1 for call in self.calls if call[0] == method)

    def get_last_call(self, method: str) -> dict[str, Any] | None:
        """
        Get the last call data for a method.

        Args:
            method: Method name

        Returns:
            Last call data or None if not called
        """
        for call in reversed(self.calls):
            if call[0] == method:
                return call[1]
        return None

    def reset(self) -> None:
        """Reset all responses and call history."""
        self.dm_responses.clear()
        self.modal_responses.clear()
        self.file_responses.clear()
        self.calls.clear()

        # Reset Slack SDK client mock to default state
        self.client = AsyncMock()
        self.client.users_list = AsyncMock(return_value={"ok": True, "members": []})


def create_ashby_success_response(results: Any) -> dict[str, Any]:
    """
    Create a successful Ashby API response.

    Args:
        results: Results data

    Returns:
        Ashby API response dict
    """
    return {"success": True, "results": results}


def create_ashby_error_response(
    error: str, error_code: str | None = None
) -> dict[str, Any]:
    """
    Create an error Ashby API response.

    Args:
        error: Error message
        error_code: Optional error code

    Returns:
        Ashby API error response dict
    """
    response: dict[str, Any] = {"success": False, "error": error}
    if error_code:
        response["errorInfo"] = {"code": error_code}
    return response


def create_ashby_paginated_response(
    results: list[Any], next_cursor: str | None = None
) -> dict[str, Any]:
    """
    Create a paginated Ashby API response.

    Args:
        results: List of result items
        next_cursor: Optional cursor for next page

    Returns:
        Ashby API paginated response dict
    """
    response: dict[str, Any] = {
        "success": True,
        "results": results,
        "moreDataAvailable": next_cursor is not None,
    }
    if next_cursor:
        response["nextCursor"] = next_cursor
    return response
