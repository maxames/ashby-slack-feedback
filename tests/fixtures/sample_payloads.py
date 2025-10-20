"""Sample payloads for testing."""

from typing import Any

# Sample Ashby webhook payload for interviewScheduleUpdate
ASHBY_INTERVIEW_SCHEDULE_UPDATE: dict[str, Any] = {
    "action": "interviewScheduleUpdate",
    "data": {
        "interviewSchedule": {
            "id": "schedule_123",
            "status": "Scheduled",
            "applicationId": "app_456",
            "candidateId": "candidate_789",
            "interviewStageId": "stage_abc",
            "interviewEvents": [
                {
                    "id": "event_001",
                    "interviewId": "interview_xyz",
                    "startTime": "2024-10-20T14:00:00.000Z",
                    "endTime": "2024-10-20T15:00:00.000Z",
                    "feedbackLink": "https://ashby.com/feedback/event_001",
                    "location": "Zoom",
                    "meetingLink": "https://zoom.us/j/123456789",
                    "hasSubmittedFeedback": False,
                    "createdAt": "2024-10-19T10:00:00.000Z",
                    "updatedAt": "2024-10-19T10:00:00.000Z",
                    "extraData": {},
                    "interviewers": [
                        {
                            "id": "interviewer_111",
                            "firstName": "John",
                            "lastName": "Doe",
                            "email": "john.doe@company.com",
                            "globalRole": "Interviewer",
                            "trainingRole": "Trained",
                            "isEnabled": True,
                            "updatedAt": "2024-10-19T10:00:00.000Z",
                            "interviewerPool": {
                                "id": "pool_aaa",
                                "title": "Engineering Interviewers",
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

# Sample Ashby candidate info response
ASHBY_CANDIDATE_INFO: dict[str, Any] = {
    "success": True,
    "results": {
        "id": "candidate_789",
        "name": "Jane Smith",
        "emailAddresses": [{"value": "jane.smith@example.com", "type": "Personal"}],
        "resumeFileHandle": {
            "handle": "file_handle_xyz",
            "name": "Jane_Smith_Resume.pdf",
        },
    },
}

# Sample Slack interaction payload (button click)
SLACK_BUTTON_CLICK: dict[str, Any] = {
    "type": "block_actions",
    "user": {"id": "U123456", "name": "john.doe"},
    "trigger_id": "trigger_abc123",
    "actions": [
        {
            "action_id": "open_feedback_modal",
            "block_id": "actions_block",
            "value": '{"event_id": "event_001", "form_definition_id": "form_def_123", '
            '"application_id": "app_456", "interviewer_id": "interviewer_111", '
            '"candidate_id": "candidate_789"}',
        }
    ],
}

# Sample Slack modal submission payload
SLACK_MODAL_SUBMISSION: dict[str, Any] = {
    "type": "view_submission",
    "user": {"id": "U123456", "name": "john.doe"},
    "view": {
        "id": "view_123",
        "callback_id": "submit_feedback",
        "private_metadata": '{"event_id": "event_001", "form_definition_id": "form_def_123", '
        '"application_id": "app_456", "interviewer_id": "interviewer_111", '
        '"candidate_id": "candidate_789"}',
        "state": {
            "values": {
                "field_overall_score": {
                    "overall_score": {
                        "type": "static_select",
                        "selected_option": {"value": "3"},
                    }
                },
                "field_notes": {
                    "notes": {
                        "type": "plain_text_input",
                        "value": "Candidate showed strong technical skills.",
                    }
                },
            }
        },
    },
}

# Sample Ashby feedback form definition
ASHBY_FEEDBACK_FORM: dict[str, Any] = {
    "success": True,
    "results": {
        "id": "form_def_123",
        "title": "Technical Interview Feedback",
        "isArchived": False,
        "formDefinition": {
            "sections": [
                {
                    "title": "Interview Assessment",
                    "fields": [
                        {
                            "field": {
                                "path": "overall_score",
                                "type": "Score",
                                "title": "Overall Score",
                            },
                            "isRequired": True,
                        },
                        {
                            "field": {
                                "path": "notes",
                                "type": "RichText",
                                "title": "Interview Notes",
                            },
                            "isRequired": False,
                        },
                    ],
                }
            ]
        },
    },
}
