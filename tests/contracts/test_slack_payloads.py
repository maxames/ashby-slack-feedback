"""Contract tests for Slack interaction payload structure validation."""

import json

import pytest

from tests.fixtures.sample_payloads import (
    SLACK_BUTTON_CLICK,
    SLACK_MODAL_SUBMISSION,
)


class TestSlackInteractionPayloads:
    """Validate that sample Slack payloads match expected structure."""

    def test_button_click_structure(self):
        """Test button click payload has required fields."""
        payload = SLACK_BUTTON_CLICK

        # Top-level structure
        assert "type" in payload
        assert payload["type"] == "block_actions"
        assert "user" in payload
        assert "trigger_id" in payload
        assert "actions" in payload

        # User structure
        user = payload["user"]
        assert "id" in user
        assert "name" in user

        # Actions structure
        actions = payload["actions"]
        assert isinstance(actions, list)
        assert len(actions) > 0

        action = actions[0]
        assert "action_id" in action
        assert "value" in action

    def test_button_value_is_valid_json(self):
        """Test that button value can be parsed as JSON."""
        payload = SLACK_BUTTON_CLICK
        action = payload["actions"][0]
        value_str = action["value"]

        # Should be valid JSON
        value_dict = json.loads(value_str)

        # Should contain required metadata
        assert "event_id" in value_dict
        assert "form_definition_id" in value_dict
        assert "application_id" in value_dict
        assert "interviewer_id" in value_dict
        assert "candidate_id" in value_dict

    def test_modal_submission_structure(self):
        """Test modal submission payload has required fields."""
        payload = SLACK_MODAL_SUBMISSION

        # Top-level structure
        assert "type" in payload
        assert payload["type"] == "view_submission"
        assert "user" in payload
        assert "view" in payload

        view = payload["view"]
        assert "id" in view
        assert "callback_id" in view
        assert "private_metadata" in view
        assert "state" in view

    def test_modal_private_metadata_is_valid_json(self):
        """Test that private_metadata can be parsed as JSON."""
        payload = SLACK_MODAL_SUBMISSION
        metadata_str = payload["view"]["private_metadata"]

        # Should be valid JSON
        metadata = json.loads(metadata_str)

        # Should contain required fields
        assert "event_id" in metadata
        assert "form_definition_id" in metadata
        assert "application_id" in metadata
        assert "interviewer_id" in metadata
        assert "candidate_id" in metadata

    def test_modal_state_values_structure(self):
        """Test modal state values have expected structure."""
        payload = SLACK_MODAL_SUBMISSION
        state_values = payload["view"]["state"]["values"]

        assert isinstance(state_values, dict)

        # Each block_id should have action values
        for block_id, actions in state_values.items():
            assert isinstance(actions, dict)

            for action_id, action_data in actions.items():
                assert "type" in action_data


class TestSlackPayloadExtraction:
    """Test that we can extract data from Slack payloads correctly."""

    def test_extract_button_metadata(self):
        """Test extracting metadata from button click."""
        from tests.fixtures.sample_payloads import SLACK_BUTTON_CLICK

        action = SLACK_BUTTON_CLICK["actions"][0]
        metadata = json.loads(action["value"])

        assert metadata["event_id"] == "event_001"
        assert metadata["form_definition_id"] == "form_def_123"

    def test_extract_modal_form_values(self):
        """Test extracting form values from modal submission."""
        from app.clients.slack_parsers import extract_form_values
        from tests.fixtures.sample_payloads import SLACK_MODAL_SUBMISSION

        state_values = SLACK_MODAL_SUBMISSION["view"]["state"]["values"]
        form_values = extract_form_values(state_values)

        # Should extract the values
        assert "overall_score" in form_values or "notes" in form_values

    def test_extract_ashby_field_submissions(self):
        """Test converting Slack values to Ashby format."""
        from app.clients.slack_parsers import extract_field_submissions_for_ashby
        from tests.fixtures.sample_payloads import SLACK_MODAL_SUBMISSION

        state_values = SLACK_MODAL_SUBMISSION["view"]["state"]["values"]
        submissions = extract_field_submissions_for_ashby(state_values)

        # Should return list of field submissions
        assert isinstance(submissions, list)

        if len(submissions) > 0:
            submission = submissions[0]
            assert "path" in submission
            assert "value" in submission


class TestSlackFieldTypes:
    """Test that Slack field types match our builders."""

    def test_supported_slack_field_types(self):
        """Test that we handle all Slack input types."""
        supported_types = [
            "plain_text_input",
            "email_text_input",
            "number_input",
            "datepicker",
            "checkboxes",
            "static_select",
            "multi_static_select",
        ]

        # All types in sample payloads should be supported
        from tests.fixtures.sample_payloads import SLACK_MODAL_SUBMISSION

        state_values = SLACK_MODAL_SUBMISSION["view"]["state"]["values"]

        for block_id, actions in state_values.items():
            for action_id, action_data in actions.items():
                field_type = action_data["type"]
                assert field_type in supported_types

    def test_field_path_extraction(self):
        """Test that field paths follow expected pattern."""
        from tests.fixtures.sample_payloads import SLACK_MODAL_SUBMISSION

        state_values = SLACK_MODAL_SUBMISSION["view"]["state"]["values"]

        for block_id, actions in state_values.items():
            if block_id.startswith("field_"):
                # Block ID should be field_<path>
                field_path = block_id.replace("field_", "")
                assert len(field_path) > 0
