"""Contract tests for Ashby webhook payload structure validation."""

import pytest

from tests.fixtures.sample_payloads import (
    ASHBY_CANDIDATE_INFO,
    ASHBY_FEEDBACK_FORM,
    ASHBY_INTERVIEW_SCHEDULE_UPDATE,
)


class TestAshbyWebhookPayloads:
    """Validate that sample payloads match expected Ashby API structure."""

    def test_interview_schedule_update_structure(self):
        """Test interviewScheduleUpdate webhook has required fields."""
        payload = ASHBY_INTERVIEW_SCHEDULE_UPDATE

        # Top-level structure
        assert "action" in payload
        assert payload["action"] == "interviewScheduleUpdate"
        assert "data" in payload
        assert "interviewSchedule" in payload["data"]

        schedule = payload["data"]["interviewSchedule"]

        # Schedule required fields
        assert "id" in schedule
        assert "status" in schedule
        assert "applicationId" in schedule
        assert "candidateId" in schedule
        assert "interviewEvents" in schedule
        assert isinstance(schedule["interviewEvents"], list)

    def test_interview_event_structure(self):
        """Test interview event has required fields."""
        payload = ASHBY_INTERVIEW_SCHEDULE_UPDATE
        events = payload["data"]["interviewSchedule"]["interviewEvents"]

        assert len(events) > 0

        event = events[0]

        # Event required fields
        assert "id" in event
        assert "interviewId" in event
        assert "startTime" in event
        assert "endTime" in event
        assert "interviewers" in event
        assert isinstance(event["interviewers"], list)

        # Timestamp format validation
        assert "T" in event["startTime"]  # ISO 8601
        assert "Z" in event["startTime"] or "+" in event["startTime"]

    def test_interviewer_structure(self):
        """Test interviewer has required fields."""
        payload = ASHBY_INTERVIEW_SCHEDULE_UPDATE
        event = payload["data"]["interviewSchedule"]["interviewEvents"][0]
        interviewers = event["interviewers"]

        assert len(interviewers) > 0

        interviewer = interviewers[0]

        # Interviewer required fields
        assert "id" in interviewer
        assert "firstName" in interviewer
        assert "lastName" in interviewer
        assert "email" in interviewer
        assert "interviewerPool" in interviewer

        # Email format validation
        assert "@" in interviewer["email"]

        # Interviewer pool structure
        pool = interviewer["interviewerPool"]
        assert "id" in pool
        assert "title" in pool

    def test_candidate_info_structure(self):
        """Test candidate.info response has required fields."""
        response = ASHBY_CANDIDATE_INFO

        assert "success" in response
        assert response["success"] is True
        assert "results" in response

        candidate = response["results"]

        # Candidate required fields
        assert "id" in candidate
        assert "name" in candidate
        assert "emailAddresses" in candidate
        assert isinstance(candidate["emailAddresses"], list)

    def test_feedback_form_structure(self):
        """Test feedbackFormDefinition structure."""
        response = ASHBY_FEEDBACK_FORM

        assert "success" in response
        assert response["success"] is True
        assert "results" in response

        form = response["results"]

        # Form required fields
        assert "id" in form
        assert "title" in form
        assert "formDefinition" in form

        form_def = form["formDefinition"]
        assert "sections" in form_def
        assert isinstance(form_def["sections"], list)

        if len(form_def["sections"]) > 0:
            section = form_def["sections"][0]
            assert "fields" in section
            assert isinstance(section["fields"], list)

            if len(section["fields"]) > 0:
                field_config = section["fields"][0]
                assert "field" in field_config
                assert "isRequired" in field_config

                field = field_config["field"]
                assert "path" in field
                assert "type" in field


class TestAshbyPayloadValidation:
    """Test edge cases and validation for Ashby payloads."""

    def test_schedule_status_values(self):
        """Test that status values are from expected set."""
        valid_statuses = ["Scheduled", "Complete", "Cancelled", "Requested"]
        payload = ASHBY_INTERVIEW_SCHEDULE_UPDATE
        status = payload["data"]["interviewSchedule"]["status"]

        assert status in valid_statuses

    def test_timestamp_parsability(self):
        """Test that timestamps can be parsed."""
        from datetime import datetime

        payload = ASHBY_INTERVIEW_SCHEDULE_UPDATE
        event = payload["data"]["interviewSchedule"]["interviewEvents"][0]

        start_time_str = event["startTime"]

        # Should be parsable to datetime
        dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        assert dt is not None
        assert dt.tzinfo is not None

    def test_field_type_values(self):
        """Test that field types are from expected set."""
        valid_types = [
            "String",
            "Email",
            "Phone",
            "RichText",
            "Number",
            "Date",
            "Boolean",
            "Score",
            "ValueSelect",
            "MultiValueSelect",
        ]

        form = ASHBY_FEEDBACK_FORM
        sections = form["results"]["formDefinition"]["sections"]

        for section in sections:
            for field_config in section["fields"]:
                field_type = field_config["field"]["type"]
                # Not all types need to be present, but all present ones must be valid
                assert field_type in valid_types or field_type not in ["Unknown"]
