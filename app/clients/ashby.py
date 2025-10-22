"""Ashby API client for feedback forms and candidate information."""

from __future__ import annotations

import base64
from typing import Any, cast

import aiohttp
from structlog import get_logger

from app.core.config import settings
from app.types.ashby import CandidateTD

logger = get_logger()


class AshbyClient:
    """HTTP client for Ashby API with Basic Auth."""

    def __init__(self) -> None:
        """Initialize Ashby client with API key from settings."""
        self.api_key = settings.ashby_api_key
        self.base_url = "https://api.ashbyhq.com"

        # Basic auth: base64(api_key:)
        credentials = base64.b64encode(f"{self.api_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json; version=1",
            "Content-Type": "application/json",
        }

    async def post(self, endpoint: str, json_data: dict[str, Any]) -> dict[str, Any]:
        """
        Make POST request to Ashby API.

        Args:
            endpoint: API endpoint (e.g., "candidate.info")
            json_data: Request body

        Returns:
            Response JSON dict

        Raises:
            aiohttp.ClientError: On request failure
        """
        url = f"{self.base_url}/{endpoint}"

        logger.info("ashby_api_request", endpoint=endpoint)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=json_data, headers=self.headers
            ) as response:
                response.raise_for_status()
                result: dict[str, Any] = await response.json()

                if not result.get("success"):
                    # Extract error from multiple possible fields
                    error_msg = (
                        result.get("errors") or result.get("error") or "Unknown error"
                    )
                    error_info = result.get("errorInfo", {})

                    logger.error(
                        "ashby_api_error",
                        endpoint=endpoint,
                        errors=error_msg,
                        error_code=(
                            error_info.get("code")
                            if isinstance(error_info, dict)
                            else None
                        ),
                        request_id=(
                            error_info.get("requestId")
                            if isinstance(error_info, dict)
                            else None
                        ),
                    )

                    # Raise exception to stop execution
                    error_display = (
                        error_msg if isinstance(error_msg, str) else str(error_msg)
                    )
                    raise Exception(
                        f"Ashby API request failed ({endpoint}): {error_display}"
                    )

                return result


# Module-level singleton
ashby_client = AshbyClient()


async def fetch_candidate_info(candidate_id: str) -> CandidateTD:
    """
    Fetch candidate details from Ashby API.

    Args:
        candidate_id: Ashby candidate UUID

    Returns:
        Candidate data (typed)

    Raises:
        Exception: If API call fails
    """
    response = await ashby_client.post("candidate.info", {"id": candidate_id})

    if not response["success"]:
        raise Exception(f"Failed to fetch candidate info: {response.get('error')}")

    data = response["results"]

    # Sanity check critical fields
    if "id" not in data or "name" not in data:
        raise ValueError(f"Invalid candidate payload for {candidate_id}")

    return cast(CandidateTD, data)


async def fetch_resume_url(file_handle: str) -> str | None:
    """
    Convert Ashby file handle to actual S3 URL.

    Args:
        file_handle: Ashby file handle

    Returns:
        S3 URL or None if fetch fails
    """
    try:
        response = await ashby_client.post("file.info", {"handle": file_handle})

        if response["success"]:
            return str(response["results"]["url"])

        logger.warning("file_info_failed", handle=file_handle)
        return None
    except Exception as e:
        logger.error("file_fetch_error", error=str(e))
        return None
