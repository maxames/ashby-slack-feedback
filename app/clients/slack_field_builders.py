"""Slack Block Kit field builders for converting Ashby form fields to Slack inputs."""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from app.types.ashby import FormFieldConfigTD, FormFieldTD

logger = get_logger()


def build_text_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build plain text input for String/Phone fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    input_block["element"] = {
        "type": "plain_text_input",
        "action_id": field_path,
    }
    if draft_value:
        input_block["element"]["initial_value"] = str(draft_value)

    return input_block


def build_email_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build email input for Email fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    input_block["element"] = {
        "type": "email_text_input",
        "action_id": field_path,
    }
    if draft_value:
        input_block["element"]["initial_value"] = str(draft_value)

    return input_block


def build_richtext_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build multiline text input for RichText fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    input_block["element"] = {
        "type": "plain_text_input",
        "action_id": field_path,
        "multiline": True,
        "dispatch_action_config": {"trigger_actions_on": ["on_enter_pressed"]},
    }
    if draft_value:
        # Extract plain text from Ashby RichText format if needed
        text_value = (
            draft_value.get("value", draft_value)
            if isinstance(draft_value, dict)
            else draft_value
        )
        input_block["element"]["initial_value"] = str(text_value) if text_value else ""

    return input_block


def build_number_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build number input for Number fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    input_block["element"] = {
        "type": "number_input",
        "action_id": field_path,
        "is_decimal_allowed": False,
    }
    if draft_value:
        input_block["element"]["initial_value"] = str(draft_value)

    return input_block


def build_date_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build date picker for Date fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    input_block["element"] = {
        "type": "datepicker",
        "action_id": field_path,
    }
    if draft_value:
        input_block["element"]["initial_date"] = draft_value  # YYYY-MM-DD format

    return input_block


def build_boolean_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build checkbox for Boolean fields."""
    field_path = field["path"]
    label_text = field.get("title", field.get("humanReadablePath", "Field"))
    input_block = _create_input_block(field, field_config)

    input_block["element"] = {
        "type": "checkboxes",
        "action_id": field_path,
        "options": [
            {"text": {"type": "plain_text", "text": label_text}, "value": "true"}
        ],
    }
    if draft_value:
        input_block["element"]["initial_options"] = [
            {"text": {"type": "plain_text", "text": label_text}, "value": "true"}
        ]

    return input_block


def build_score_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build static select for Score fields (1-4 hire rating)."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    options = [
        {
            "text": {"type": "plain_text", "text": f"{i} - {label}"},
            "value": str(i),
        }
        for i, label in enumerate(
            ["Strong No Hire", "No Hire", "Hire", "Strong Hire"], start=1
        )
    ]

    input_block["element"] = {
        "type": "static_select",
        "action_id": field_path,
        "options": options,
    }

    if draft_value:
        score_value = (
            draft_value.get("score") if isinstance(draft_value, dict) else draft_value
        )
        if score_value:
            input_block["element"]["initial_option"] = next(
                (opt for opt in options if opt["value"] == str(score_value)), None
            )

    return input_block


def build_select_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build static select for ValueSelect fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    value_options = field.get("selectableValues", [])
    options = [
        {
            "text": {"type": "plain_text", "text": opt["label"]},
            "value": opt["value"],
        }
        for opt in value_options
    ]

    input_block["element"] = {
        "type": "static_select",
        "action_id": field_path,
        "options": options,
    }

    if draft_value and options:
        input_block["element"]["initial_option"] = next(
            (opt for opt in options if opt["value"] == draft_value), None
        )

    return input_block


def build_multiselect_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any]:
    """Build multi-static select for MultiValueSelect fields."""
    field_path = field["path"]
    input_block = _create_input_block(field, field_config)

    value_options = field.get("selectableValues", [])
    options = [
        {
            "text": {"type": "plain_text", "text": opt["label"]},
            "value": opt["value"],
        }
        for opt in value_options
    ]

    input_block["element"] = {
        "type": "multi_static_select",
        "action_id": field_path,
        "options": options,
    }

    if draft_value and isinstance(draft_value, list) and options:
        input_block["element"]["initial_options"] = [
            opt for opt in options if opt["value"] in draft_value
        ]

    return input_block


def _create_input_block(
    field: FormFieldTD, field_config: FormFieldConfigTD
) -> dict[str, Any]:
    """Create base input block structure with label and optional flag."""
    field_path = field["path"]
    label_text = field.get("title", field.get("humanReadablePath", "Field"))
    is_required = field_config.get("isRequired", False)

    return {
        "type": "input",
        "block_id": f"field_{field_path}",
        "label": {"type": "plain_text", "text": label_text},
        "optional": not is_required,
    }


# Field type dispatcher
FIELD_BUILDERS = {
    "String": build_text_field,
    "Phone": build_text_field,
    "Email": build_email_field,
    "RichText": build_richtext_field,
    "Number": build_number_field,
    "Date": build_date_field,
    "Boolean": build_boolean_field,
    "Score": build_score_field,
    "ValueSelect": build_select_field,
    "MultiValueSelect": build_multiselect_field,
}


def build_input_block_from_field(
    field: FormFieldTD, field_config: FormFieldConfigTD, draft_value: Any = None
) -> dict[str, Any] | None:
    """
    Convert Ashby field to Slack input block (dispatcher).

    Maps Ashby field types to appropriate Slack Block Kit inputs:
    - String/Phone → plain_text_input
    - Email → email_text_input
    - RichText → plain_text_input (multiline)
    - Number → number_input
    - Boolean → checkboxes
    - Date → datepicker
    - Score (1-4) → static_select
    - ValueSelect → static_select
    - MultiValueSelect → multi_static_select

    Args:
        field: Ashby field definition
        field_config: Field configuration (isRequired, etc.)
        draft_value: Pre-populated draft value (optional)

    Returns:
        Slack input block dict or None if unsupported field type
    """
    field_type = field["type"]
    builder = FIELD_BUILDERS.get(field_type)

    if not builder:
        logger.warning(
            "unsupported_field_type", field_type=field_type, path=field["path"]
        )
        return None

    return builder(field, field_config, draft_value)
