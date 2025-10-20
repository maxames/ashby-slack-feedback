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
    schedule_id: str = "schedule_test",
    status: str = "Scheduled",
    event_id: str = "event_test",
) -> dict:
    """Create test Ashby webhook payload."""
    return {
        "action": "interviewScheduleUpdate",
        "data": {
            "interviewSchedule": {
                "id": schedule_id,
                "status": status,
                "applicationId": "app_test",
                "candidateId": "candidate_test",
                "interviewStageId": "stage_test",
                "interviewEvents": [
                    {
                        "id": event_id,
                        "interviewId": "interview_test",
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
                                "id": "interviewer_test",
                                "firstName": "Test",
                                "lastName": "User",
                                "email": "test@example.com",
                                "globalRole": "Interviewer",
                                "trainingRole": "Trained",
                                "isEnabled": True,
                                "updatedAt": "2024-10-19T10:00:00.000Z",
                                "interviewerPool": {
                                    "id": "pool_test",
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
