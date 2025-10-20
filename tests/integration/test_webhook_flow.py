"""Integration tests for webhook flow (webhook → schedule processing → DB)."""

from uuid import UUID, uuid4

import pytest

from app.services.interviews import process_schedule_update


class TestWebhookFlow:
    """Integration tests for complete webhook processing flow."""

    @pytest.mark.asyncio
    async def test_scheduled_webhook_creates_schedule(
        self, clean_db, sample_interview, sample_slack_user
    ):
        """Test that Scheduled webhook creates schedule in database."""
        schedule_id = uuid4()
        event_id = uuid4()
        application_id = uuid4()
        stage_id = uuid4()
        interviewer_id = uuid4()

        # Build webhook payload with real UUIDs
        schedule = {
            "id": str(schedule_id),
            "status": "Scheduled",
            "applicationId": str(application_id),
            "candidateId": "candidate_test",
            "interviewStageId": str(stage_id),
            "interviewEvents": [
                {
                    "id": str(event_id),
                    "interviewId": sample_interview["interview_id"],
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
                            "id": str(interviewer_id),
                            "firstName": "Test",
                            "lastName": "User",
                            "email": "test@example.com",
                            "globalRole": "Interviewer",
                            "trainingRole": "Trained",
                            "isEnabled": True,
                            "updatedAt": "2024-10-19T10:00:00.000Z",
                            "interviewerPool": {
                                "id": str(uuid4()),
                                "title": "Test Pool",
                                "isArchived": False,
                                "trainingPath": {},
                            },
                        }
                    ],
                }
            ],
        }

        # Process the schedule update
        await process_schedule_update(schedule)

        # Verify schedule was created
        async with clean_db.acquire() as conn:
            schedule_row = await conn.fetchrow(
                "SELECT * FROM interview_schedules WHERE schedule_id = $1",
                schedule_id,
            )

            assert schedule_row is not None
            assert schedule_row["status"] == "Scheduled"
            assert schedule_row["application_id"] == application_id

            # Verify event was created
            event_row = await conn.fetchrow(
                "SELECT * FROM interview_events WHERE event_id = $1",
                event_id,
            )

            assert event_row is not None
            assert event_row["schedule_id"] == schedule_id
            assert event_row["interview_id"] == UUID(sample_interview["interview_id"])

            # Verify interviewer assignment was created
            assignment_row = await conn.fetchrow(
                "SELECT * FROM interview_assignments WHERE event_id = $1",
                event_id,
            )

            assert assignment_row is not None
            assert assignment_row["interviewer_id"] == interviewer_id
            assert assignment_row["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_cancelled_webhook_deletes_schedule(self, clean_db, sample_interview):
        """Test that Cancelled webhook removes schedule from database."""
        # First create a schedule
        schedule_id = uuid4()

        async with clean_db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO interview_schedules
                (schedule_id, application_id, interview_stage_id, status, candidate_id, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                schedule_id,
                uuid4(),
                uuid4(),
                "Scheduled",
                "candidate_123",
            )

        # Now cancel it
        schedule = {
            "id": str(schedule_id),
            "status": "Cancelled",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_123",
            "interviewStageId": str(uuid4()),
            "interviewEvents": [],
        }

        await process_schedule_update(schedule)

        # Verify schedule was deleted
        async with clean_db.acquire() as conn:
            schedule_row = await conn.fetchrow(
                "SELECT * FROM interview_schedules WHERE schedule_id = $1", schedule_id
            )

            assert schedule_row is None

    @pytest.mark.asyncio
    async def test_duplicate_webhook_is_idempotent(self, clean_db, sample_interview):
        """
        EDGE CASE: Ashby can send duplicate webhooks (network retries, race conditions).
        Test that processing same webhook twice results in same DB state.
        """
        schedule_id = uuid4()
        event_id = uuid4()

        schedule = {
            "id": str(schedule_id),
            "status": "Scheduled",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_test",
            "interviewStageId": str(uuid4()),
            "interviewEvents": [
                {
                    "id": str(event_id),
                    "interviewId": sample_interview["interview_id"],
                    "startTime": "2024-10-20T14:00:00.000Z",
                    "endTime": "2024-10-20T15:00:00.000Z",
                    "feedbackLink": "https://ashby.com/feedback",
                    "location": "Zoom",
                    "meetingLink": "https://zoom.us/test",
                    "hasSubmittedFeedback": False,
                    "createdAt": "2024-10-19T10:00:00.000Z",
                    "updatedAt": "2024-10-19T10:00:00.000Z",
                    "extraData": {},
                    "interviewers": [],
                }
            ],
        }

        # Process twice
        await process_schedule_update(schedule)
        await process_schedule_update(schedule)

        # Verify only one schedule exists
        async with clean_db.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM interview_schedules WHERE schedule_id = $1",
                schedule_id,
            )

            assert count == 1

            # Verify only one event exists
            event_count = await conn.fetchval(
                "SELECT COUNT(*) FROM interview_events WHERE schedule_id = $1",
                schedule_id,
            )

            assert event_count == 1

    @pytest.mark.asyncio
    async def test_invalid_status_ignored(self, clean_db):
        """
        EDGE CASE: Ashby adds new status types we don't handle yet.
        Test that unknown statuses are logged but don't crash.
        """
        schedule_id = uuid4()

        schedule = {
            "id": str(schedule_id),
            "status": "InvalidStatus",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_invalid",
            "interviewStageId": str(uuid4()),
            "interviewEvents": [],
        }

        # Should not raise error
        await process_schedule_update(schedule)

        # Verify nothing was created
        async with clean_db.acquire() as conn:
            schedule_row = await conn.fetchrow(
                "SELECT * FROM interview_schedules WHERE schedule_id = $1", schedule_id
            )

            assert schedule_row is None

    @pytest.mark.asyncio
    async def test_webhook_with_multiple_interviewers(self, clean_db, sample_interview):
        """
        EDGE CASE: Panel interviews have multiple interviewers.
        Test that all interviewer assignments are created.
        """
        schedule_id = uuid4()
        event_id = uuid4()
        interviewer_1_id = uuid4()
        interviewer_2_id = uuid4()

        schedule = {
            "id": str(schedule_id),
            "status": "Scheduled",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_panel",
            "interviewStageId": str(uuid4()),
            "interviewEvents": [
                {
                    "id": str(event_id),
                    "interviewId": sample_interview["interview_id"],
                    "startTime": "2024-10-20T14:00:00.000Z",
                    "endTime": "2024-10-20T15:00:00.000Z",
                    "feedbackLink": "https://ashby.com/feedback",
                    "location": "Conference Room A",
                    "meetingLink": None,  # In-person interview
                    "hasSubmittedFeedback": False,
                    "createdAt": "2024-10-19T10:00:00.000Z",
                    "updatedAt": "2024-10-19T10:00:00.000Z",
                    "extraData": {},
                    "interviewers": [
                        {
                            "id": str(interviewer_1_id),
                            "firstName": "Alice",
                            "lastName": "Smith",
                            "email": "alice@company.com",
                            "globalRole": "Interviewer",
                            "trainingRole": "Trained",
                            "isEnabled": True,
                            "updatedAt": "2024-10-19T10:00:00.000Z",
                            "interviewerPool": {
                                "id": str(uuid4()),
                                "title": "Engineering Pool",
                                "isArchived": False,
                                "trainingPath": {},
                            },
                        },
                        {
                            "id": str(interviewer_2_id),
                            "firstName": "Bob",
                            "lastName": "Johnson",
                            "email": "bob@company.com",
                            "globalRole": "Interviewer",
                            "trainingRole": "Shadow",  # Different training level
                            "isEnabled": True,
                            "updatedAt": "2024-10-19T10:00:00.000Z",
                            "interviewerPool": {
                                "id": str(uuid4()),
                                "title": "Engineering Pool",
                                "isArchived": False,
                                "trainingPath": {},
                            },
                        },
                    ],
                }
            ],
        }

        await process_schedule_update(schedule)

        # Verify both interviewers were assigned
        async with clean_db.acquire() as conn:
            assignments = await conn.fetch(
                "SELECT * FROM interview_assignments WHERE event_id = $1 ORDER BY email",
                event_id,
            )

            assert len(assignments) == 2
            assert assignments[0]["email"] == "alice@company.com"
            assert assignments[0]["training_role"] == "Trained"
            assert assignments[1]["email"] == "bob@company.com"
            assert assignments[1]["training_role"] == "Shadow"

    @pytest.mark.asyncio
    async def test_webhook_update_replaces_events(self, clean_db, sample_interview):
        """
        EDGE CASE: Ashby sends update when interview is rescheduled.
        Test that old event is replaced with new event (full replace strategy).
        """
        schedule_id = uuid4()
        event_v1_id = uuid4()
        event_v2_id = uuid4()

        # Create initial schedule with event v1
        schedule_v1 = {
            "id": str(schedule_id),
            "status": "Scheduled",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_reschedule",
            "interviewStageId": str(uuid4()),
            "interviewEvents": [
                {
                    "id": str(event_v1_id),
                    "interviewId": sample_interview["interview_id"],
                    "startTime": "2024-10-20T14:00:00.000Z",
                    "endTime": "2024-10-20T15:00:00.000Z",
                    "feedbackLink": "https://ashby.com/feedback",
                    "location": "Zoom",
                    "meetingLink": "https://zoom.us/meeting1",
                    "hasSubmittedFeedback": False,
                    "createdAt": "2024-10-19T10:00:00.000Z",
                    "updatedAt": "2024-10-19T10:00:00.000Z",
                    "extraData": {},
                    "interviewers": [],
                }
            ],
        }

        await process_schedule_update(schedule_v1)

        # Update with rescheduled event v2 (different time, different Zoom link)
        schedule_v2 = {
            "id": str(schedule_id),
            "status": "Scheduled",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_reschedule",
            "interviewStageId": str(uuid4()),
            "interviewEvents": [
                {
                    "id": str(event_v2_id),  # New event ID
                    "interviewId": sample_interview["interview_id"],
                    "startTime": "2024-10-21T10:00:00.000Z",  # Different time
                    "endTime": "2024-10-21T11:00:00.000Z",
                    "feedbackLink": "https://ashby.com/feedback",
                    "location": "Zoom",
                    "meetingLink": "https://zoom.us/meeting2",  # Different link
                    "hasSubmittedFeedback": False,
                    "createdAt": "2024-10-20T08:00:00.000Z",
                    "updatedAt": "2024-10-20T08:00:00.000Z",
                    "extraData": {},
                    "interviewers": [],
                }
            ],
        }

        await process_schedule_update(schedule_v2)

        # Verify old event was replaced
        async with clean_db.acquire() as conn:
            # Old event should be deleted (CASCADE from schedule upsert)
            event_v1 = await conn.fetchrow(
                "SELECT * FROM interview_events WHERE event_id = $1", event_v1_id
            )
            assert event_v1 is None

            # New event should exist
            event_v2 = await conn.fetchrow(
                "SELECT * FROM interview_events WHERE event_id = $1", event_v2_id
            )
            assert event_v2 is not None
            assert event_v2["meeting_link"] == "https://zoom.us/meeting2"

    @pytest.mark.asyncio
    async def test_webhook_with_missing_optional_fields(
        self, clean_db, sample_interview
    ):
        """
        EDGE CASE: Some fields from Ashby are optional (meetingLink, location, etc).
        Test that webhook processes correctly with minimal data.
        """
        schedule_id = uuid4()
        event_id = uuid4()

        schedule = {
            "id": str(schedule_id),
            "status": "Scheduled",
            "applicationId": str(uuid4()),
            "candidateId": "candidate_minimal",
            "interviewStageId": None,  # Optional
            "interviewEvents": [
                {
                    "id": str(event_id),
                    "interviewId": sample_interview["interview_id"],
                    "startTime": "2024-10-20T14:00:00.000Z",
                    "endTime": "2024-10-20T15:00:00.000Z",
                    "feedbackLink": "https://ashby.com/feedback",
                    "location": None,  # No location specified
                    "meetingLink": None,  # No meeting link
                    "hasSubmittedFeedback": False,
                    "createdAt": "2024-10-19T10:00:00.000Z",
                    "updatedAt": "2024-10-19T10:00:00.000Z",
                    "extraData": {},
                    "interviewers": [],
                }
            ],
        }

        await process_schedule_update(schedule)

        # Verify schedule and event were created despite missing fields
        async with clean_db.acquire() as conn:
            schedule_row = await conn.fetchrow(
                "SELECT * FROM interview_schedules WHERE schedule_id = $1",
                schedule_id,
            )
            assert schedule_row is not None
            assert schedule_row["interview_stage_id"] is None

            event_row = await conn.fetchrow(
                "SELECT * FROM interview_events WHERE event_id = $1",
                event_id,
            )
            assert event_row is not None
            assert event_row["location"] is None
            assert event_row["meeting_link"] is None
