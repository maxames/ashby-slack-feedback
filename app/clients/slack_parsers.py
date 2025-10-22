"""Slack Block Kit parsers for extracting form values from modal submissions."""

from __future__ import annotations

from typing import Any

from app.types.ashby import FeedbackFormTD, FieldSubmissionTD
from app.types.slack import FormValuesDictTD


def build_field_type_map(form_definition: FeedbackFormTD) -> dict[str, str]:
    """
    Build a map of field_path → field_type from form definition.

    Args:
        form_definition: Ashby form definition

    Returns:
        Dict mapping field paths to their types (e.g., {"feedback": "RichText"})
    """
    field_type_map = {}
    form_def = form_definition.get("formDefinition", form_definition)

    for section in form_def.get("sections", []):
        for field_config in section.get("fields", []):
            field = field_config["field"]
            field_type_map[field["path"]] = field["type"]

    return field_type_map


def extract_form_values(state_values: dict[str, Any]) -> FormValuesDictTD:
    """
    Extract all form values from Slack modal state for draft saving.

    Returns simple dict: {"field_path": value, ...}

    Args:
        state_values: Slack modal state values dict

    Returns:
        Dict of field_path → value mappings
    """
    form_values: FormValuesDictTD = {}

    for block_id, actions in state_values.items():
        if not block_id.startswith("field_"):
            continue

        field_path = block_id.replace("field_", "")
        _, action_data = next(iter(actions.items()))
        action_type = action_data["type"]

        # Extract value based on type
        if action_type == "plain_text_input":
            form_values[field_path] = action_data.get("value")

        elif action_type == "email_text_input":
            form_values[field_path] = action_data.get("value")

        elif action_type == "number_input":
            form_values[field_path] = action_data.get("value")

        elif action_type == "datepicker":
            form_values[field_path] = action_data.get("selected_date")

        elif action_type == "checkboxes":
            selected = action_data.get("selected_options", [])
            form_values[field_path] = len(selected) > 0

        elif action_type == "static_select":
            selected = action_data.get("selected_option")
            if selected:
                form_values[field_path] = selected["value"]

        elif action_type == "multi_static_select":
            selected_options = action_data.get("selected_options", [])
            form_values[field_path] = [opt["value"] for opt in selected_options]

    return form_values


def extract_field_submissions_for_ashby(
    state_values: dict[str, Any],
    form_definition: FeedbackFormTD,
) -> list[FieldSubmissionTD]:
    """
    Extract form values and convert to Ashby API format.

    Returns list of {"path": "...", "value": ...} objects.

    Args:
        state_values: Slack modal state values dict
        form_definition: Ashby form definition for field type mapping

    Returns:
        List of field submissions for Ashby API
    """
    field_submissions: list[FieldSubmissionTD] = []

    # Build field type lookup map
    field_type_map = build_field_type_map(form_definition)

    for block_id, actions in state_values.items():
        if not block_id.startswith("field_"):
            continue

        field_path = block_id.replace("field_", "")
        field_type = field_type_map.get(field_path)  # Get actual type

        _, action_data = next(iter(actions.items()))
        action_type = action_data["type"]

        value = None

        if action_type == "plain_text_input":
            value = action_data.get("value")
            # Use actual field type instead of guessing
            if value and field_type == "RichText":
                value = {"type": "PlainText", "value": value}

        elif action_type == "email_text_input":
            value = action_data.get("value")

        elif action_type == "number_input":
            raw_value = action_data.get("value")
            value = int(raw_value) if raw_value else None

        elif action_type == "datepicker":
            value = action_data.get("selected_date")  # YYYY-MM-DD format

        elif action_type == "checkboxes":
            selected = action_data.get("selected_options", [])
            value = len(selected) > 0  # Boolean

        elif action_type == "static_select":
            selected = action_data.get("selected_option")
            if selected:
                # Use actual field type instead of guessing
                if field_type == "Score":
                    value = {"score": int(selected["value"])}
                else:
                    value = selected["value"]

        elif action_type == "multi_static_select":
            selected_options = action_data.get("selected_options", [])
            value = [opt["value"] for opt in selected_options]

        # Only add if value is not None
        if value is not None:
            field_submissions.append({"path": field_path, "value": value})

    return field_submissions
