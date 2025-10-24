"""Integration tests for Ashby webhook API endpoint."""

import hmac
import json
from unittest.mock import AsyncMock

import pytest

from tests.fixtures.factories import create_ashby_webhook_payload


def create_webhook_request(body: bytes, signature: str | None = None):
    """Helper to create a proper Starlette Request for webhook tests."""
    from starlette.requests import Request

    headers = []
    if signature:
        headers.append([b"ashby-signature", signature.encode()])

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/ashby",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 8000),
        "server": ("localhost", 8000),
    }

    async def receive():
        return {"type": "http.request", "body": body}

    return Request(scope, receive=receive)


class TestWebhookEndpoint:
    """Test Ashby webhook endpoint security and routing."""

    @pytest.mark.asyncio
    async def test_webhook_endpoint_with_valid_signature(
        self, mock_ashby_client, clean_db, sample_interview
    ):
        """Test successful webhook processing with valid signature."""
        from app.api.webhooks import handle_ashby_webhook
        from app.core.config import settings

        # Create webhook payload
        payload = create_ashby_webhook_payload()
        schedule_id = payload["data"]["interviewSchedule"]["id"]
        payload["data"]["interviewSchedule"]["interviewEvents"][0]["interviewId"] = (
            sample_interview["interview_id"]
        )
        body = json.dumps(payload).encode()

        # Calculate valid signature
        secret = settings.ashby_webhook_secret
        hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()
        signature = f"sha256={hex_digest}"

        request = create_webhook_request(body, signature)

        # Setup Ashby API mock for interview fetch
        mock_ashby_client.add_response(
            "interview.info",
            {
                "success": True,
                "results": {
                    "id": sample_interview["interview_id"],
                    "title": "Test Interview",
                    "feedbackFormDefinitionId": sample_interview["form_definition_id"],
                },
            },
        )

        # Call webhook endpoint
        response = await handle_ashby_webhook(request)

        # Verify response
        assert response.status_code == 204

        # Verify schedule was created in database
        from app.core.database import db

        schedule_row = await db.fetchrow(
            "SELECT * FROM interview_schedules WHERE schedule_id = $1",
            schedule_id,
        )
        assert schedule_row is not None

    @pytest.mark.asyncio
    async def test_webhook_endpoint_invalid_signature_returns_401(self):
        """Test that invalid signature is rejected."""
        from fastapi import HTTPException

        from app.api.webhooks import handle_ashby_webhook

        payload = create_ashby_webhook_payload()
        body = json.dumps(payload).encode()

        # Create invalid signature
        invalid_signature = "sha256=invalid_signature_value"
        request = create_webhook_request(body, invalid_signature)

        # Call webhook endpoint - should raise 401
        with pytest.raises(HTTPException) as exc_info:
            await handle_ashby_webhook(request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_endpoint_missing_signature_returns_401(self):
        """Test that missing signature is rejected."""
        from fastapi import HTTPException

        from app.api.webhooks import handle_ashby_webhook

        payload = create_ashby_webhook_payload()
        body = json.dumps(payload).encode()

        request = create_webhook_request(body, None)  # No signature

        # Call webhook endpoint - should raise 401
        with pytest.raises(HTTPException) as exc_info:
            await handle_ashby_webhook(request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_endpoint_ping_no_signature_required(self):
        """Test that ping/test webhooks don't require signature."""
        from app.api.webhooks import handle_ashby_webhook

        # Create ping payload
        payload = {"action": "ping", "type": "ping"}
        body = json.dumps(payload).encode()

        request = create_webhook_request(body, None)  # No signature

        # Call webhook endpoint
        response = await handle_ashby_webhook(request)

        # Verify ping response
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_endpoint_invalid_json_returns_400(self):
        """Test that malformed JSON is rejected."""
        from fastapi import HTTPException

        from app.api.webhooks import handle_ashby_webhook

        # Invalid JSON
        body = b"not valid json {"

        request = create_webhook_request(body, None)

        # Call webhook endpoint - should raise 400
        with pytest.raises(HTTPException) as exc_info:
            await handle_ashby_webhook(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_endpoint_invalid_payload_structure_returns_400(self):
        """Test that invalid payload structure is rejected."""
        from fastapi import HTTPException

        from app.api.webhooks import handle_ashby_webhook
        from app.core.config import settings

        # Valid JSON but invalid structure (missing required fields)
        payload = {"invalid": "structure"}
        body = json.dumps(payload).encode()

        # Calculate valid signature for invalid payload
        secret = settings.ashby_webhook_secret
        hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()
        signature = f"sha256={hex_digest}"

        request = create_webhook_request(body, signature)

        # Call webhook endpoint - should raise 400
        with pytest.raises(HTTPException) as exc_info:
            await handle_ashby_webhook(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_endpoint_logs_to_audit_table(
        self, mock_ashby_client, clean_db, sample_interview
    ):
        """Test that webhooks are logged to audit table."""
        from app.api.webhooks import handle_ashby_webhook
        from app.core.config import settings
        from app.core.database import db

        payload = create_ashby_webhook_payload()
        schedule_id = payload["data"]["interviewSchedule"]["id"]
        payload["data"]["interviewSchedule"]["interviewEvents"][0]["interviewId"] = (
            sample_interview["interview_id"]
        )
        body = json.dumps(payload).encode()

        # Calculate valid signature
        secret = settings.ashby_webhook_secret
        hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()
        signature = f"sha256={hex_digest}"

        request = create_webhook_request(body, signature)

        # Setup mock
        mock_ashby_client.add_response(
            "interview.info",
            {
                "success": True,
                "results": {
                    "id": sample_interview["interview_id"],
                    "title": "Test Interview",
                },
            },
        )

        # Call webhook
        await handle_ashby_webhook(request)

        # Verify audit log entry
        audit_row = await db.fetchrow(
            """
            SELECT * FROM ashby_webhook_payloads
            WHERE schedule_id = $1
            ORDER BY received_at DESC
            LIMIT 1
            """,
            schedule_id,
        )

        assert audit_row is not None
        assert audit_row["action"] == "interviewScheduleUpdate"

    @pytest.mark.asyncio
    async def test_webhook_endpoint_calls_service_layer(
        self, mock_ashby_client, clean_db, sample_interview, monkeypatch
    ):
        """Test that webhook calls the service layer for processing."""
        from app.api.webhooks import handle_ashby_webhook
        from app.core.config import settings

        # Track service layer calls
        process_called = []

        async def mock_process_schedule_update(schedule):
            process_called.append(schedule)

        monkeypatch.setattr(
            "app.services.interviews.process_schedule_update",
            mock_process_schedule_update,
        )

        payload = create_ashby_webhook_payload()
        schedule_id = payload["data"]["interviewSchedule"]["id"]
        body = json.dumps(payload).encode()

        # Calculate valid signature
        secret = settings.ashby_webhook_secret
        hex_digest = hmac.new(secret.encode(), body, digestmod="sha256").hexdigest()
        signature = f"sha256={hex_digest}"

        request = create_webhook_request(body, signature)

        # Call webhook
        await handle_ashby_webhook(request)

        # Verify service layer was called
        assert len(process_called) == 1
        assert process_called[0]["id"] == schedule_id


class TestWebhookRateLimiting:
    """Test rate limiting on webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_endpoint_rate_limiting(self):
        """Test that rate limiting is applied (basic check)."""
        # Note: Full rate limiting test would require many requests
        # This is a smoke test to ensure rate limiter is configured
        from app.api.webhooks import limiter

        assert limiter is not None
        assert hasattr(limiter, "limit")
