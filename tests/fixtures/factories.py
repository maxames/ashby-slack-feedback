"""Test fixtures and factories."""

from datetime import UTC, datetime, timedelta


def create_interview_event(
    event_id: str = "event_test",
    schedule_id: str = "schedule_test",
    interview_id: str = "interview_test",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    interviewer_email: str = "test@example.com",
) -> dict:
    """Create test interview event data."""
    if start_time is None:
        start_time = datetime.now(UTC) + timedelta(minutes=10)
    if end_time is None:
        end_time = start_time + timedelta(hours=1)

    return {
        "event_id": event_id,
        "schedule_id": schedule_id,
        "interview_id": interview_id,
        "start_time": start_time,
        "end_time": end_time,
        "interviewer_email": interviewer_email,
        "slack_user_id": "U123456",
        "interview_title": "Technical Interview",
        "feedback_form_definition_id": "form_def_123",
        "candidate_id": "candidate_789",
        "application_id": "app_456",
        "interviewer_id": "interviewer_111",
    }


def create_feedback_draft(
    event_id: str = "event_test",
    interviewer_id: str = "interviewer_test",
    form_values: dict | None = None,
) -> dict:
    """Create test feedback draft data."""
    if form_values is None:
        form_values = {"overall_score": "3", "notes": "Test feedback notes"}

    return {
        "event_id": event_id,
        "interviewer_id": interviewer_id,
        "form_values": form_values,
    }


def create_ashby_webhook_payload(
    schedule_id: str | None = None,
    status: str = "Scheduled",
    event_id: str | None = None,
) -> dict:
    """Create test Ashby webhook payload."""
    import uuid

    if schedule_id is None:
        schedule_id = str(uuid.uuid4())
    if event_id is None:
        event_id = str(uuid.uuid4())

    return {
        "action": "interviewScheduleUpdate",
        "data": {
            "interviewSchedule": {
                "id": schedule_id,
                "status": status,
                "applicationId": str(uuid.uuid4()),
                "candidateId": str(uuid.uuid4()),
                "interviewStageId": str(uuid.uuid4()),
                "interviewEvents": [
                    {
                        "id": event_id,
                        "interviewId": str(uuid.uuid4()),
                        "startTime": "2024-10-20T14:00:00.000Z",
                        "endTime": "2024-10-20T15:00:00.000Z",
                        "feedbackLink": "https://ashby.com/feedback",
                        "location": "Zoom",
                        "meetingLink": "https://zoom.us/test",
                        "hasSubmittedFeedback": False,
                        "createdAt": "2024-10-19T10:00:00.000Z",
                        "updatedAt": "2024-10-19T10:00:00.000Z",
                        "extraData": {},
                        "interviewers": [
                            {
                                "id": str(uuid.uuid4()),
                                "firstName": "Test",
                                "lastName": "User",
                                "email": "test@example.com",
                                "globalRole": "Interviewer",
                                "trainingRole": "Trained",
                                "isEnabled": True,
                                "updatedAt": "2024-10-19T10:00:00.000Z",
                                "interviewerPool": {
                                    "id": str(uuid.uuid4()),
                                    "title": "Test Pool",
                                    "isArchived": False,
                                    "trainingPath": {},
                                },
                            }
                        ],
                    }
                ],
            }
        },
    }


def create_slack_modal_state(field_values: dict[str, any] | None = None) -> dict:
    """
    Create Slack modal state.values structure.

    Args:
        field_values: Dict of field_path → value mappings

    Returns:
        Slack state.values dict
    """
    if field_values is None:
        field_values = {
            "overall_score": "3",
            "notes": "Strong technical skills",
        }

    state_values = {}

    for field_path, value in field_values.items():
        block_id = f"field_{field_path}"

        # Determine action type based on value type
        if isinstance(value, bool):
            state_values[block_id] = {
                field_path: {
                    "type": "checkboxes",
                    "selected_options": [{"value": "true"}] if value else [],
                }
            }
        elif isinstance(value, list):
            state_values[block_id] = {
                field_path: {
                    "type": "multi_static_select",
                    "selected_options": [{"value": v} for v in value],
                }
            }
        elif isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            state_values[block_id] = {
                field_path: {
                    "type": "static_select",
                    "selected_option": {"value": str(value)},
                }
            }
        else:
            state_values[block_id] = {
                field_path: {
                    "type": "plain_text_input",
                    "value": str(value),
                }
            }

    return state_values


def create_slack_interaction_payload(
    interaction_type: str = "block_actions",
    action_id: str = "open_feedback_modal",
    button_value: dict | None = None,
    state_values: dict | None = None,
    private_metadata: dict | None = None,
) -> dict:
    """
    Create Slack interaction payload.

    Args:
        interaction_type: Type of interaction (block_actions, view_submission, view_closed)
        action_id: Action identifier
        button_value: Button value dict for block_actions
        state_values: Modal state values for view_submission
        private_metadata: Private metadata dict

    Returns:
        Slack interaction payload
    """
    import json

    base_payload = {
        "type": interaction_type,
        "user": {"id": "U123456", "name": "test.user"},
        "trigger_id": "trigger_test_123",
    }

    if interaction_type == "block_actions":
        if button_value is None:
            button_value = {
                "event_id": "event_test",
                "form_definition_id": "form_def_test",
                "application_id": "app_test",
                "interviewer_id": "interviewer_test",
                "candidate_id": "candidate_test",
            }

        base_payload["actions"] = [
            {
                "action_id": action_id,
                "block_id": "actions_block",
                "value": json.dumps(button_value),
            }
        ]

        # Add view for dispatch actions
        if action_id.startswith("field_"):
            if private_metadata is None:
                private_metadata = button_value
            if state_values is None:
                state_values = create_slack_modal_state()

            base_payload["view"] = {
                "id": "view_test",
                "private_metadata": json.dumps(private_metadata),
                "state": {"values": state_values},
            }

    elif interaction_type == "view_submission":
        if private_metadata is None:
            private_metadata = {
                "event_id": "event_test",
                "form_definition_id": "form_def_test",
                "application_id": "app_test",
                "interviewer_id": "interviewer_test",
                "candidate_id": "candidate_test",
            }
        if state_values is None:
            state_values = create_slack_modal_state()

        base_payload["view"] = {
            "id": "view_test",
            "callback_id": "submit_feedback",
            "private_metadata": json.dumps(private_metadata),
            "state": {"values": state_values},
        }

    elif interaction_type == "view_closed":
        base_payload["view"] = {
            "id": "view_test",
            "callback_id": "submit_feedback",
        }

    return base_payload


def create_ashby_api_response(
    endpoint: str, data: dict | list | None = None, success: bool = True
) -> dict:
    """
    Create Ashby API response structure.

    Args:
        endpoint: API endpoint name (for endpoint-specific structure)
        data: Response data
        success: Whether response is successful

    Returns:
        Ashby API response dict
    """
    if not success:
        return {
            "success": False,
            "error": "API error occurred",
        }

    if data is None:
        # Default data based on endpoint
        if endpoint == "candidate.info":
            data = {
                "id": "candidate_test",
                "name": "Test Candidate",
                "emailAddresses": [{"value": "test@example.com"}],
            }
        elif endpoint == "feedbackFormDefinition.info":
            data = {
                "id": "form_def_test",
                "title": "Test Form",
                "formDefinition": {
                    "sections": [
                        {
                            "title": "Assessment",
                            "fields": [
                                {
                                    "field": {
                                        "path": "overall_score",
                                        "type": "Score",
                                        "title": "Overall Score",
                                    },
                                    "isRequired": True,
                                }
                            ],
                        }
                    ]
                },
            }
        elif endpoint == "interview.info":
            data = {
                "id": "interview_test",
                "title": "Technical Interview",
                "feedbackFormDefinitionId": "form_def_test",
            }
        elif endpoint == "job.info":
            data = {
                "id": "job_test",
                "title": "Software Engineer",
            }
        else:
            data = {}

    return {
        "success": True,
        "results": data,
    }
