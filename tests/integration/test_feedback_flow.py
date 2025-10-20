"""Integration tests for feedback flow (draft save/load/delete, submission)."""

import pytest

from app.services.feedback import delete_draft, load_draft, save_draft


class TestFeedbackDraftFlow:
    """Integration tests for feedback draft workflows."""

    @pytest.mark.asyncio
    async def test_save_draft(self, clean_db, sample_interview_event):
        """Test saving feedback draft to database."""
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]
        form_values = {
            "overall_score": "3",
            "notes": "Strong technical skills",
            "communication": "Excellent",
        }

        await save_draft(event_id, interviewer_id, form_values)

        # Verify draft was saved
        loaded = await load_draft(event_id, interviewer_id)
        assert loaded["overall_score"] == "3"
        assert loaded["notes"] == "Strong technical skills"

    @pytest.mark.asyncio
    async def test_load_draft(self, clean_db, sample_interview_event):
        """Test loading existing draft from database."""
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]
        form_values = {"field1": "value1", "field2": "value2"}

        # First save a draft
        await save_draft(event_id, interviewer_id, form_values)

        # Now load it
        loaded_draft = await load_draft(event_id, interviewer_id)

        assert loaded_draft is not None
        assert loaded_draft["field1"] == "value1"
        assert loaded_draft["field2"] == "value2"

    @pytest.mark.asyncio
    async def test_load_nonexistent_draft(self, clean_db, sample_interview_event):
        """Test loading draft that doesn't exist returns empty dict."""
        from uuid import uuid4

        # Use real IDs but don't create a draft
        loaded_draft = await load_draft(
            sample_interview_event["event_id"], str(uuid4())  # Non-existent interviewer
        )

        assert loaded_draft == {}

    @pytest.mark.asyncio
    async def test_delete_draft(self, clean_db, sample_interview_event):
        """Test deleting draft after successful submission."""
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]
        form_values = {"test_field": "test_value"}

        # Save draft
        await save_draft(event_id, interviewer_id, form_values)

        # Verify it exists
        loaded = await load_draft(event_id, interviewer_id)
        assert loaded != {}

        # Delete it
        await delete_draft(event_id, interviewer_id)

        # Verify it's gone
        loaded_after_delete = await load_draft(event_id, interviewer_id)
        assert loaded_after_delete == {}

    @pytest.mark.asyncio
    async def test_update_existing_draft(self, clean_db, sample_interview_event):
        """Test that saving draft twice updates same record."""
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Save initial draft
        initial_values = {"field1": "initial_value"}
        await save_draft(event_id, interviewer_id, initial_values)

        # Update with new values
        updated_values = {"field1": "updated_value", "field2": "new_field"}
        await save_draft(event_id, interviewer_id, updated_values)

        # Load and verify values
        loaded = await load_draft(event_id, interviewer_id)
        assert loaded["field1"] == "updated_value"
        assert loaded["field2"] == "new_field"

    @pytest.mark.asyncio
    async def test_empty_draft_not_saved(self, clean_db, sample_interview_event):
        """Test that empty form values don't create draft."""
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]
        empty_values = {}

        await save_draft(event_id, interviewer_id, empty_values)

        # Verify no draft was created
        loaded = await load_draft(event_id, interviewer_id)
        assert loaded == {}

    @pytest.mark.asyncio
    async def test_draft_timestamps(self, clean_db, sample_interview_event):
        """Test that draft timestamps are recorded correctly."""
        import asyncio

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Save initial draft
        await save_draft(event_id, interviewer_id, {"field": "value1"})

        async with clean_db.acquire() as conn:
            initial_row = await conn.fetchrow(
                """
                SELECT created_at, updated_at FROM feedback_drafts
                WHERE event_id = $1::uuid AND interviewer_id = $2::uuid
                """,
                event_id,
                interviewer_id,
            )

            initial_created = initial_row["created_at"]
            initial_updated = initial_row["updated_at"]

        # Wait a moment and update
        await asyncio.sleep(0.1)
        await save_draft(event_id, interviewer_id, {"field": "value2"})

        async with clean_db.acquire() as conn:
            updated_row = await conn.fetchrow(
                """
                SELECT created_at, updated_at FROM feedback_drafts
                WHERE event_id = $1::uuid AND interviewer_id = $2::uuid
                """,
                event_id,
                interviewer_id,
            )

            updated_created = updated_row["created_at"]
            updated_updated = updated_row["updated_at"]

        # created_at should stay the same
        assert updated_created == initial_created
        # updated_at should be newer
        assert updated_updated > initial_updated


class TestFeedbackSubmission:
    """Integration tests for feedback submission flow."""

    @pytest.mark.asyncio
    async def test_draft_deleted_after_submission(
        self, clean_db, sample_interview_event
    ):
        """Test that draft is deleted when submission is marked as sent."""
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Save a draft
        await save_draft(event_id, interviewer_id, {"score": "4"})

        # Verify it exists
        draft = await load_draft(event_id, interviewer_id)
        assert draft != {}

        # Simulate submission (delete draft)
        await delete_draft(event_id, interviewer_id)

        # Verify draft is gone
        draft_after = await load_draft(event_id, interviewer_id)
        assert draft_after == {}


class TestDraftAutoSaveOnEnter:
    """Integration tests for Enter-key draft auto-save mechanism."""

    @pytest.mark.asyncio
    async def test_draft_auto_save_on_enter_key(self, clean_db, sample_interview_event):
        """Test that drafts save when user presses Enter in text field."""
        import json

        from app.api.slack_interactions import handle_dispatch_auto_save

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # Simulate dispatch_action payload
        payload = {
            "type": "block_actions",
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": str(event_id),
                        "interviewer_id": str(interviewer_id),
                    }
                ),
                "state": {
                    "values": {
                        "field_overall_notes": {
                            "overall_notes": {
                                "type": "plain_text_input",
                                "value": "Partial feedback text",
                            }
                        }
                    }
                },
            },
            "actions": [
                {"action_id": "field_overall_notes", "type": "plain_text_input"}
            ],
        }

        # Call handler
        await handle_dispatch_auto_save(payload)

        # Verify draft was saved
        draft = await load_draft(event_id, interviewer_id)
        assert draft["overall_notes"] == "Partial feedback text"

    @pytest.mark.asyncio
    async def test_multiple_enter_key_presses_update_draft(
        self, clean_db, sample_interview_event
    ):
        """Test that multiple Enter key presses update the same draft."""
        import json

        from app.api.slack_interactions import handle_dispatch_auto_save

        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # First Enter key press
        payload1 = {
            "type": "block_actions",
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": str(event_id),
                        "interviewer_id": str(interviewer_id),
                    }
                ),
                "state": {
                    "values": {
                        "field_notes": {
                            "notes": {
                                "type": "plain_text_input",
                                "value": "First draft",
                            }
                        }
                    }
                },
            },
            "actions": [{"action_id": "field_notes", "type": "plain_text_input"}],
        }

        await handle_dispatch_auto_save(payload1)

        # Second Enter key press with updated text
        payload2 = {
            "type": "block_actions",
            "view": {
                "private_metadata": json.dumps(
                    {
                        "event_id": str(event_id),
                        "interviewer_id": str(interviewer_id),
                    }
                ),
                "state": {
                    "values": {
                        "field_notes": {
                            "notes": {
                                "type": "plain_text_input",
                                "value": "First draft updated",
                            }
                        }
                    }
                },
            },
            "actions": [{"action_id": "field_notes", "type": "plain_text_input"}],
        }

        await handle_dispatch_auto_save(payload2)

        # Verify draft was updated
        draft = await load_draft(event_id, interviewer_id)
        assert draft["notes"] == "First draft updated"
