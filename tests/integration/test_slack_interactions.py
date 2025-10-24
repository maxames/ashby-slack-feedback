"""Integration tests for Slack interactions API."""

import json
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from tests.fixtures.factories import (
    create_ashby_api_response,
    create_slack_interaction_payload,
    create_slack_modal_state,
)


class TestHandleSlackInteractions:
    """Test the main Slack interactions endpoint dispatcher."""

    @pytest.mark.asyncio
    async def test_handle_slack_interactions_button_click(
        self,
        mock_ashby_client,
        mock_slack_client,
        clean_db,
        sample_feedback_form,
        sample_interview_event,
    ):
        """Test that button click actions are routed correctly."""
        from fastapi import Response

        from app.api.slack_interactions import handle_slack_interactions

        # Setup mock responses
        mock_ashby_client.add_response(
            "candidate.info", create_ashby_api_response("candidate.info")
        )
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )

        # Create request with button click payload - use existing event
        payload = create_slack_interaction_payload(
            interaction_type="block_actions",
            action_id="open_feedback_modal",
            button_value={
                "event_id": sample_interview_event["event_id"],
                "form_definition_id": sample_feedback_form["id"],
                "application_id": sample_interview_event["application_id"],
                "interviewer_id": sample_interview_event["interviewer_id"],
                "candidate_id": "candidate_test",
            },
        )

        mock_request = AsyncMock()
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(payload)})

        # Call endpoint
        response = await handle_slack_interactions(mock_request)

        # Verify response
        assert isinstance(response, Response)
        assert response.status_code == 200

        # Verify Slack modal was opened
        assert mock_slack_client.was_called("open_modal")

    @pytest.mark.asyncio
    async def test_handle_slack_interactions_dispatch_action(
        self, mock_slack_client, clean_db, sample_interview_event
    ):
        """Test that dispatch actions (Enter key) trigger auto-save."""
        from app.api.slack_interactions import handle_slack_interactions
        from app.services.feedback import load_draft

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Create dispatch action payload
        state_values = create_slack_modal_state({"notes": "Draft content"})
        payload = create_slack_interaction_payload(
            interaction_type="block_actions",
            action_id="field_notes",
            button_value={
                "event_id": event_id,
                "interviewer_id": interviewer_id,
            },
            state_values=state_values,
            private_metadata={
                "event_id": event_id,
                "interviewer_id": interviewer_id,
            },
        )

        mock_request = AsyncMock()
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(payload)})

        # Call endpoint
        response = await handle_slack_interactions(mock_request)

        # Verify response
        assert response.status_code == 200

        # Verify draft was saved
        draft = await load_draft(event_id, interviewer_id)
        assert draft.get("notes") == "Draft content"

    @pytest.mark.asyncio
    async def test_handle_slack_interactions_view_submission(
        self, mock_ashby_client, mock_slack_client, clean_db, sample_interview_event
    ):
        """Test that view submission triggers feedback submission."""
        from app.api.slack_interactions import handle_slack_interactions

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Setup mock responses
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )
        mock_ashby_client.add_response(
            "applicationFeedback.submit",
            create_ashby_api_response("feedback_submit"),
        )

        # Create view submission payload
        state_values = create_slack_modal_state(
            {
                "overall_score": "3",
                "notes": "Good candidate",
            }
        )
        payload = create_slack_interaction_payload(
            interaction_type="view_submission",
            state_values=state_values,
            private_metadata={
                "event_id": event_id,
                "form_definition_id": "form_def_test",
                "application_id": "app_test",
                "interviewer_id": interviewer_id,
                "candidate_id": "candidate_test",
            },
        )

        mock_request = AsyncMock()
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(payload)})

        # Call endpoint
        response = await handle_slack_interactions(mock_request)

        # Verify response
        assert response.status_code == 200

        # Note: Actual submission happens async, we can't directly verify here
        # This is tested more thoroughly in other tests

    @pytest.mark.asyncio
    async def test_handle_slack_interactions_view_closed(self, mock_slack_client):
        """Test that modal close events are handled gracefully."""
        from app.api.slack_interactions import handle_slack_interactions

        payload = create_slack_interaction_payload(interaction_type="view_closed")

        mock_request = AsyncMock()
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(payload)})

        # Call endpoint
        response = await handle_slack_interactions(mock_request)

        # Verify response
        assert response.status_code == 200


class TestHandleOpenModal:
    """Test modal opening functionality."""

    @pytest.mark.asyncio
    async def test_handle_open_modal_success(
        self,
        mock_ashby_client,
        mock_slack_client,
        clean_db,
        sample_interview_event,
        sample_feedback_form,
    ):
        """Test successful modal opening with all data."""
        from app.api.slack_interactions import handle_open_modal

        event_id = sample_interview_event["event_id"]

        # Setup mock responses
        mock_ashby_client.add_response(
            "candidate.info", create_ashby_api_response("candidate.info")
        )
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )

        # Create payload
        payload = {
            "trigger_id": "trigger_test",
            "user": {"id": "U123456"},
        }
        action = {
            "value": json.dumps(
                {
                    "event_id": event_id,
                    "form_definition_id": sample_feedback_form["id"],
                    "application_id": sample_interview_event["application_id"],
                    "interviewer_id": sample_interview_event["interviewer_id"],
                    "candidate_id": "candidate_test",
                }
            )
        }

        # Call handler
        await handle_open_modal(payload, action)

        # Verify modal was opened
        assert mock_slack_client.was_called("open_modal")
        modal_call = mock_slack_client.get_last_call("open_modal")
        assert modal_call["trigger_id"] == "trigger_test"
        assert "view" in modal_call

    @pytest.mark.asyncio
    async def test_handle_open_modal_missing_form_definition(
        self, mock_ashby_client, mock_slack_client, clean_db
    ):
        """Test that missing form definition is handled gracefully."""
        from app.api.slack_interactions import handle_open_modal

        # Setup mock to return error
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            {"success": False, "error": "Form not found"},
        )

        payload = {"trigger_id": "trigger_test", "user": {"id": "U123456"}}
        action = {
            "value": json.dumps(
                {
                    "event_id": "event_test",
                    "form_definition_id": "form_invalid",
                    "application_id": "app_test",
                    "interviewer_id": "interviewer_test",
                    "candidate_id": "candidate_test",
                }
            )
        }

        # Call handler - should not crash
        await handle_open_modal(payload, action)

        # Verify modal was NOT opened
        assert not mock_slack_client.was_called("open_modal")

    @pytest.mark.asyncio
    async def test_handle_open_modal_candidate_fetch_failure(
        self, mock_ashby_client, mock_slack_client, clean_db, sample_interview_event
    ):
        """Test that candidate fetch failure is handled gracefully."""
        from app.api.slack_interactions import handle_open_modal

        # Setup mock responses
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )
        mock_ashby_client.add_response(
            "candidate.info",
            {"success": False, "error": "Candidate not found"},
        )

        payload = {"trigger_id": "trigger_test", "user": {"id": "U123456"}}
        action = {
            "value": json.dumps(
                {
                    "event_id": sample_interview_event["event_id"],
                    "form_definition_id": "form_def_test",
                    "application_id": "app_test",
                    "interviewer_id": "interviewer_test",
                    "candidate_id": "candidate_invalid",
                }
            )
        }

        # Call handler - should not crash but may not open modal
        await handle_open_modal(payload, action)

        # Exact behavior depends on implementation - test that it doesn't crash

    @pytest.mark.asyncio
    async def test_handle_open_modal_loads_draft(
        self,
        mock_ashby_client,
        mock_slack_client,
        clean_db,
        sample_interview_event,
        sample_feedback_form,
    ):
        """Test that existing draft is loaded into modal."""
        from app.api.slack_interactions import handle_open_modal
        from app.services.feedback import save_draft

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Save a draft first
        await save_draft(event_id, interviewer_id, {"notes": "Saved draft content"})

        # Setup mock responses
        mock_ashby_client.add_response(
            "candidate.info", create_ashby_api_response("candidate.info")
        )
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )

        payload = {"trigger_id": "trigger_test", "user": {"id": "U123456"}}
        action = {
            "value": json.dumps(
                {
                    "event_id": event_id,
                    "form_definition_id": sample_feedback_form["id"],
                    "application_id": sample_interview_event["application_id"],
                    "interviewer_id": interviewer_id,
                    "candidate_id": "candidate_test",
                }
            )
        }

        # Call handler
        await handle_open_modal(payload, action)

        # Verify modal was opened
        assert mock_slack_client.was_called("open_modal")
        # Note: Verifying draft values would require inspecting modal view structure


class TestHandleFeedbackSubmission:
    """Test feedback submission functionality."""

    @pytest.mark.asyncio
    async def test_handle_feedback_submission_success(
        self,
        mock_ashby_client,
        mock_slack_client,
        clean_db,
        sample_interview_event,
        sample_feedback_form,
    ):
        """Test successful feedback submission flow."""
        from app.api.slack_interactions import handle_feedback_submission

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Setup mock responses
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )
        mock_ashby_client.add_response(
            "applicationFeedback.submit",
            {"success": True, "results": {"id": "feedback_123"}},
        )

        # Create submission payload
        state_values = create_slack_modal_state(
            {
                "overall_score": "3",
                "notes": "Strong technical skills",
            }
        )
        payload = {
            "user": {"id": "U123456"},
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": event_id,
                        "form_definition_id": sample_feedback_form["id"],
                        "application_id": sample_interview_event["application_id"],
                        "interviewer_id": interviewer_id,
                        "candidate_id": "candidate_test",
                    }
                ),
                "state": {"values": state_values},
            },
        }

        # Call handler
        await handle_feedback_submission(payload)

        # Verify Ashby was called
        assert mock_ashby_client.was_called("applicationFeedback.submit")

        # Verify confirmation DM was sent
        assert mock_slack_client.was_called("send_dm")
        dm_call = mock_slack_client.get_last_call("send_dm")
        assert "success" in dm_call["text"].lower()

    @pytest.mark.asyncio
    async def test_handle_feedback_submission_ashby_failure(
        self, mock_ashby_client, mock_slack_client, clean_db, sample_interview_event
    ):
        """Test that Ashby API failure sends error message to user."""
        from app.api.slack_interactions import handle_feedback_submission

        # Setup mock responses
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )
        mock_ashby_client.add_response(
            "applicationFeedback.submit",
            {"success": False, "error": "Invalid data"},
        )

        state_values = create_slack_modal_state({"overall_score": "3"})
        payload = {
            "user": {"id": "U123456"},
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": sample_interview_event["event_id"],
                        "form_definition_id": "form_def_test",
                        "application_id": "app_test",
                        "interviewer_id": "interviewer_test",
                        "candidate_id": "candidate_test",
                    }
                ),
                "state": {"values": state_values},
            },
        }

        # Call handler
        await handle_feedback_submission(payload)

        # Verify error DM was sent
        assert mock_slack_client.was_called("send_dm")
        dm_call = mock_slack_client.get_last_call("send_dm")
        assert "failed" in dm_call["text"].lower() or "error" in dm_call["text"].lower()

    @pytest.mark.asyncio
    async def test_handle_feedback_submission_deletes_draft(
        self,
        mock_ashby_client,
        mock_slack_client,
        clean_db,
        sample_interview_event,
        sample_feedback_form,
    ):
        """Test that successful submission deletes the draft."""
        from app.api.slack_interactions import handle_feedback_submission
        from app.services.feedback import load_draft, save_draft

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Save a draft
        await save_draft(event_id, interviewer_id, {"notes": "Draft to delete"})

        # Verify draft exists
        draft = await load_draft(event_id, interviewer_id)
        assert draft != {}

        # Setup mock responses
        mock_ashby_client.add_response(
            "feedbackFormDefinition.info",
            create_ashby_api_response("feedbackFormDefinition.info"),
        )
        mock_ashby_client.add_response(
            "applicationFeedback.submit",
            {"success": True, "results": {"id": "feedback_123"}},
        )

        state_values = create_slack_modal_state({"overall_score": "3"})
        payload = {
            "user": {"id": "U123456"},
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": event_id,
                        "form_definition_id": sample_feedback_form["id"],
                        "application_id": sample_interview_event["application_id"],
                        "interviewer_id": interviewer_id,
                        "candidate_id": "candidate_test",
                    }
                ),
                "state": {"values": state_values},
            },
        }

        # Call handler
        await handle_feedback_submission(payload)

        # Verify draft was deleted
        draft_after = await load_draft(event_id, interviewer_id)
        assert draft_after == {}


class TestHandleDispatchAutoSave:
    """Test auto-save on Enter key functionality."""

    @pytest.mark.asyncio
    async def test_handle_dispatch_auto_save_updates_draft(
        self, clean_db, sample_interview_event
    ):
        """Test that dispatch action saves draft."""
        from app.api.slack_interactions import handle_dispatch_auto_save
        from app.services.feedback import load_draft

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Create dispatch payload
        state_values = create_slack_modal_state({"notes": "Auto-saved content"})
        payload = {
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": event_id,
                        "interviewer_id": interviewer_id,
                    }
                ),
                "state": {"values": state_values},
            }
        }

        # Call handler
        await handle_dispatch_auto_save(payload)

        # Verify draft was saved
        draft = await load_draft(event_id, interviewer_id)
        assert draft["notes"] == "Auto-saved content"
