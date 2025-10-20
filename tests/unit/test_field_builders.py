"""Unit tests for Slack field builders."""

import pytest

from app.clients.slack_field_builders import (
    FIELD_BUILDERS,
    build_boolean_field,
    build_date_field,
    build_email_field,
    build_input_block_from_field,
    build_multiselect_field,
    build_number_field,
    build_richtext_field,
    build_score_field,
    build_select_field,
    build_text_field,
)


class TestBuildInputBlockFromField:
    """Tests for build_input_block_from_field dispatcher."""

    def test_dispatcher_calls_correct_builder(self):
        """Test that dispatcher routes to correct builder function."""
        field = {"type": "String", "path": "test_field", "title": "Test"}
        config = {"isRequired": True}

        result = build_input_block_from_field(field, config)

        assert result is not None
        assert result["type"] == "input"
        assert result["block_id"] == "field_test_field"

    def test_unsupported_field_type_returns_none(self):
        """Test that unsupported field types return None."""
        field = {"type": "UnsupportedType", "path": "test", "title": "Test"}
        config = {}

        result = build_input_block_from_field(field, config)

        assert result is None

    def test_all_supported_types_have_builders(self):
        """Test that all types in FIELD_BUILDERS are supported."""
        expected_types = [
            "String",
            "Phone",
            "Email",
            "RichText",
            "Number",
            "Date",
            "Boolean",
            "Score",
            "ValueSelect",
            "MultiValueSelect",
        ]

        for field_type in expected_types:
            assert field_type in FIELD_BUILDERS


class TestBuildTextField:
    """Tests for build_text_field function."""

    def test_basic_text_field(self):
        """Test building basic text field."""
        field = {"path": "name", "title": "Full Name"}
        config = {"isRequired": True}

        result = build_text_field(field, config)

        assert result["type"] == "input"
        assert result["block_id"] == "field_name"
        assert result["label"]["text"] == "Full Name"
        assert result["optional"] is False
        assert result["element"]["type"] == "plain_text_input"
        assert result["element"]["action_id"] == "name"

    def test_text_field_with_draft_value(self):
        """Test text field with pre-populated draft value."""
        field = {"path": "name", "title": "Name"}
        config = {"isRequired": False}

        result = build_text_field(field, config, draft_value="John Doe")

        assert result["element"]["initial_value"] == "John Doe"

    def test_optional_text_field(self):
        """Test optional text field."""
        field = {"path": "notes", "title": "Notes"}
        config = {"isRequired": False}

        result = build_text_field(field, config)

        assert result["optional"] is True


class TestBuildScoreField:
    """Tests for build_score_field function."""

    def test_score_field_structure(self):
        """Test that score field has correct structure."""
        field = {"path": "score", "title": "Interview Score"}
        config = {"isRequired": True}

        result = build_score_field(field, config)

        assert result["element"]["type"] == "static_select"
        assert len(result["element"]["options"]) == 4

        # Verify score options
        options = result["element"]["options"]
        assert options[0]["value"] == "1"
        assert "Strong No Hire" in options[0]["text"]["text"]
        assert options[3]["value"] == "4"
        assert "Strong Hire" in options[3]["text"]["text"]

    def test_score_field_with_draft_value(self):
        """Test score field with pre-selected value."""
        field = {"path": "score", "title": "Score"}
        config = {}

        result = build_score_field(field, config, draft_value={"score": 3})

        assert "initial_option" in result["element"]
        assert result["element"]["initial_option"]["value"] == "3"


class TestBuildSelectField:
    """Tests for build_select_field function."""

    def test_select_field_with_options(self):
        """Test building select field with options."""
        field = {
            "path": "department",
            "title": "Department",
            "selectableValues": [
                {"label": "Engineering", "value": "eng"},
                {"label": "Product", "value": "product"},
            ],
        }
        config = {"isRequired": True}

        result = build_select_field(field, config)

        assert result["element"]["type"] == "static_select"
        assert len(result["element"]["options"]) == 2
        assert result["element"]["options"][0]["text"]["text"] == "Engineering"
        assert result["element"]["options"][0]["value"] == "eng"

    def test_select_field_with_draft_value(self):
        """Test select field with pre-selected value."""
        field = {
            "path": "level",
            "title": "Level",
            "selectableValues": [
                {"label": "Junior", "value": "junior"},
                {"label": "Senior", "value": "senior"},
            ],
        }
        config = {}

        result = build_select_field(field, config, draft_value="senior")

        assert "initial_option" in result["element"]
        assert result["element"]["initial_option"]["value"] == "senior"


class TestBuildMultiselectField:
    """Tests for build_multiselect_field function."""

    def test_multiselect_field_structure(self):
        """Test building multi-select field."""
        field = {
            "path": "skills",
            "title": "Skills",
            "selectableValues": [
                {"label": "Python", "value": "python"},
                {"label": "JavaScript", "value": "js"},
            ],
        }
        config = {}

        result = build_multiselect_field(field, config)

        assert result["element"]["type"] == "multi_static_select"
        assert len(result["element"]["options"]) == 2

    def test_multiselect_with_draft_values(self):
        """Test multi-select with pre-selected values."""
        field = {
            "path": "skills",
            "title": "Skills",
            "selectableValues": [
                {"label": "Python", "value": "python"},
                {"label": "JavaScript", "value": "js"},
                {"label": "Go", "value": "go"},
            ],
        }
        config = {}

        result = build_multiselect_field(field, config, draft_value=["python", "go"])

        assert "initial_options" in result["element"]
        assert len(result["element"]["initial_options"]) == 2
        values = [opt["value"] for opt in result["element"]["initial_options"]]
        assert "python" in values
        assert "go" in values


class TestBuildRichTextField:
    """Tests for build_richtext_field function."""

    def test_richtext_field_has_dispatch_config(self):
        """Test that richtext field includes dispatch_action_config for auto-save on Enter."""
        field = {"path": "notes", "title": "Interview Notes"}
        config = {"isRequired": True}

        result = build_richtext_field(field, config)

        assert result["element"]["type"] == "plain_text_input"
        assert result["element"]["multiline"] is True
        assert result["element"]["dispatch_action"] is True
        assert "dispatch_action_config" in result["element"]
        assert result["element"]["dispatch_action_config"]["trigger_actions_on"] == [
            "on_enter_pressed"
        ]

    def test_richtext_field_with_draft_value(self):
        """Test richtext field with pre-populated draft value."""
        field = {"path": "feedback", "title": "Feedback"}
        config = {"isRequired": False}

        result = build_richtext_field(field, config, draft_value="Great candidate")

        assert result["element"]["initial_value"] == "Great candidate"
