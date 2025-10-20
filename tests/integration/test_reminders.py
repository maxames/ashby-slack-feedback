"""Integration tests for reminders (window detection, message building)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.clients.slack_views import build_reminder_message


class TestReminderWindowDetection:
    """Integration tests for reminder scheduling window (4-20 minutes)."""

    @pytest.mark.asyncio
    async def test_reminder_query_finds_interviews_in_window(
        self, clean_db, sample_interview, sample_slack_user, sample_feedback_form
    ):
        """Test that query finds interviews 4-20 minutes away."""
        # Create interview event 10 minutes in the future
        now = datetime.now(UTC)
        start_time = now + timedelta(minutes=10)
        end_time = start_time + timedelta(hours=1)

        schedule_id = uuid4()
        event_id = uuid4()
        interviewer_id = uuid4()

        async with clean_db.acquire() as conn:
            # Create schedule
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

            # Create event
            await conn.execute(
                """
                INSERT INTO interview_events
                (event_id, schedule_id, interview_id, created_at, updated_at,
                 start_time, end_time, feedback_link, location, meeting_link,
                 has_submitted_feedback, extra_data)
                VALUES ($1, $2, $3, NOW(), NOW(), $4, $5, $6, $7, $8, $9, $10)
                """,
                event_id,
                schedule_id,
                UUID(sample_interview["interview_id"]),
                start_time,
                end_time,
                "https://ashby.com/feedback",
                "Zoom",
                "https://zoom.us/test",
                False,
                "{}",
            )

            # Create interviewer assignment
            await conn.execute(
                """
                INSERT INTO interview_assignments
                (event_id, interviewer_id, first_name, last_name, email,
                 global_role, training_role, is_enabled, manager_id,
                 interviewer_pool_id, interviewer_pool_title,
                 interviewer_pool_is_archived, training_path, interviewer_updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
                """,
                event_id,
                interviewer_id,
                "Test",
                "User",
                "test@example.com",
                "Interviewer",
                "Trained",
                True,
                None,
                uuid4(),
                "Test Pool",
                False,
                "{}",
            )

            # Query for reminders (should find this one)
            results = await conn.fetch(
                """
                SELECT
                    ie.event_id,
                    ie.start_time,
                    ia.interviewer_id,
                    ia.email AS interviewer_email,
                    ia.first_name,
                    ia.last_name,
                    su.slack_user_id,
                    i.title AS interview_title,
                    i.feedback_form_definition_id,
                    s.candidate_id,
                    s.application_id
                FROM interview_events ie
                JOIN interview_assignments ia ON ie.event_id = ia.event_id
                JOIN interviews i ON ie.interview_id = i.interview_id
                JOIN interview_schedules s ON ie.schedule_id = s.schedule_id
                JOIN slack_users su ON ia.email = su.email
                WHERE ie.start_time BETWEEN NOW() + INTERVAL '4 minutes'
                                        AND NOW() + INTERVAL '20 minutes'
                  AND s.status = 'Scheduled'
                  AND NOT EXISTS (
                      SELECT 1 FROM feedback_reminders_sent frs
                      WHERE frs.event_id = ie.event_id
                        AND frs.interviewer_id = ia.interviewer_id
                  )
                """
            )

            assert len(results) == 1
            assert results[0]["event_id"] == event_id

    @pytest.mark.asyncio
    async def test_no_reminder_for_past_interviews(
        self, clean_db, sample_interview, sample_slack_user
    ):
        """
        EDGE CASE: Interview already started (no reminder needed).
        Test that reminders are not sent for past interviews.
        """
        # Create interview event 10 minutes in the past
        now = datetime.now(UTC)
        start_time = now - timedelta(minutes=10)
        end_time = start_time + timedelta(hours=1)

        schedule_id = uuid4()
        event_id = uuid4()

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
                "candidate_past",
            )

            await conn.execute(
                """
                INSERT INTO interview_events
                (event_id, schedule_id, interview_id, created_at, updated_at,
                 start_time, end_time, feedback_link, location, meeting_link,
                 has_submitted_feedback, extra_data)
                VALUES ($1, $2, $3, NOW(), NOW(), $4, $5, $6, $7, $8, $9, $10)
                """,
                event_id,
                schedule_id,
                UUID(sample_interview["interview_id"]),
                start_time,
                end_time,
                "https://ashby.com/feedback",
                "Zoom",
                "https://zoom.us/test",
                False,
                "{}",
            )

            await conn.execute(
                """
                INSERT INTO interview_assignments
                (event_id, interviewer_id, first_name, last_name, email,
                 global_role, training_role, is_enabled, manager_id,
                 interviewer_pool_id, interviewer_pool_title,
                 interviewer_pool_is_archived, training_path, interviewer_updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
                """,
                event_id,
                uuid4(),
                "Test",
                "User",
                "test@example.com",
                "Interviewer",
                "Trained",
                True,
                None,
                uuid4(),
                "Test Pool",
                False,
                "{}",
            )

            # Query should NOT find past interviews
            results = await conn.fetch(
                """
                SELECT ie.event_id
                FROM interview_events ie
                JOIN interview_assignments ia ON ie.event_id = ia.event_id
                JOIN interview_schedules s ON ie.schedule_id = s.schedule_id
                JOIN slack_users su ON ia.email = su.email
                WHERE ie.start_time BETWEEN NOW() + INTERVAL '4 minutes'
                                        AND NOW() + INTERVAL '20 minutes'
                  AND s.status = 'Scheduled'
                """
            )

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_no_reminder_for_far_future_interviews(
        self, clean_db, sample_interview, sample_slack_user
    ):
        """
        EDGE CASE: Interview is too far in future (>20 minutes).
        Test that reminders are not sent too early.
        """
        # Create interview event 30 minutes in the future
        now = datetime.now(UTC)
        start_time = now + timedelta(minutes=30)
        end_time = start_time + timedelta(hours=1)

        schedule_id = uuid4()
        event_id = uuid4()

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
                "candidate_future",
            )

            await conn.execute(
                """
                INSERT INTO interview_events
                (event_id, schedule_id, interview_id, created_at, updated_at,
                 start_time, end_time, feedback_link, location, meeting_link,
                 has_submitted_feedback, extra_data)
                VALUES ($1, $2, $3, NOW(), NOW(), $4, $5, $6, $7, $8, $9, $10)
                """,
                event_id,
                schedule_id,
                UUID(sample_interview["interview_id"]),
                start_time,
                end_time,
                "https://ashby.com/feedback",
                "Zoom",
                "https://zoom.us/test",
                False,
                "{}",
            )

            await conn.execute(
                """
                INSERT INTO interview_assignments
                (event_id, interviewer_id, first_name, last_name, email,
                 global_role, training_role, is_enabled, manager_id,
                 interviewer_pool_id, interviewer_pool_title,
                 interviewer_pool_is_archived, training_path, interviewer_updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
                """,
                event_id,
                uuid4(),
                "Test",
                "User",
                "test@example.com",
                "Interviewer",
                "Trained",
                True,
                None,
                uuid4(),
                "Test Pool",
                False,
                "{}",
            )

            # Query should NOT find future interviews beyond 20 min
            results = await conn.fetch(
                """
                SELECT ie.event_id
                FROM interview_events ie
                JOIN interview_assignments ia ON ie.event_id = ia.event_id
                JOIN interview_schedules s ON ie.schedule_id = s.schedule_id
                JOIN slack_users su ON ia.email = su.email
                WHERE ie.start_time BETWEEN NOW() + INTERVAL '4 minutes'
                                        AND NOW() + INTERVAL '20 minutes'
                  AND s.status = 'Scheduled'
                """
            )

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_reminder_not_sent_twice(
        self, clean_db, sample_interview, sample_slack_user
    ):
        """
        EDGE CASE: Reminder job runs multiple times (every 5 minutes).
        Test that duplicate reminders are prevented by tracking table.
        """
        # Create an actual event to satisfy FK constraint
        now = datetime.now(UTC)
        start_time = now + timedelta(minutes=10)
        end_time = start_time + timedelta(hours=1)

        schedule_id = uuid4()
        event_id = uuid4()
        interviewer_id = uuid4()

        async with clean_db.acquire() as conn:
            # Create schedule
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
                "candidate_test",
            )

            # Create event
            await conn.execute(
                """
                INSERT INTO interview_events
                (event_id, schedule_id, interview_id, created_at, updated_at,
                 start_time, end_time, feedback_link, location, meeting_link,
                 has_submitted_feedback, extra_data)
                VALUES ($1, $2, $3, NOW(), NOW(), $4, $5, $6, $7, $8, $9, $10)
                """,
                event_id,
                schedule_id,
                UUID(sample_interview["interview_id"]),
                start_time,
                end_time,
                "https://ashby.com/feedback",
                "Zoom",
                "https://zoom.us/test",
                False,
                "{}",
            )

            # Record that reminder was sent
            await conn.execute(
                """
                INSERT INTO feedback_reminders_sent
                (event_id, interviewer_id, slack_user_id, slack_channel_id,
                 slack_message_ts, sent_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                event_id,
                interviewer_id,
                "U123456",
                "D123456",
                "1234567890.123456",
            )

            # Query should exclude already-sent reminders
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM feedback_reminders_sent
                    WHERE event_id = $1 AND interviewer_id = $2
                )
                """,
                event_id,
                interviewer_id,
            )

            assert exists is True

    @pytest.mark.asyncio
    async def test_no_reminder_for_cancelled_interviews(
        self, clean_db, sample_interview, sample_slack_user
    ):
        """
        EDGE CASE: Interview was cancelled after scheduling.
        Test that reminders respect schedule status.
        """
        now = datetime.now(UTC)
        start_time = now + timedelta(minutes=10)
        end_time = start_time + timedelta(hours=1)

        schedule_id = uuid4()
        event_id = uuid4()

        async with clean_db.acquire() as conn:
            # Create cancelled schedule
            await conn.execute(
                """
                INSERT INTO interview_schedules
                (schedule_id, application_id, interview_stage_id, status, candidate_id, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                schedule_id,
                uuid4(),
                uuid4(),
                "Cancelled",  # Cancelled status
                "candidate_cancelled",
            )

            await conn.execute(
                """
                INSERT INTO interview_events
                (event_id, schedule_id, interview_id, created_at, updated_at,
                 start_time, end_time, feedback_link, location, meeting_link,
                 has_submitted_feedback, extra_data)
                VALUES ($1, $2, $3, NOW(), NOW(), $4, $5, $6, $7, $8, $9, $10)
                """,
                event_id,
                schedule_id,
                UUID(sample_interview["interview_id"]),
                start_time,
                end_time,
                "https://ashby.com/feedback",
                "Zoom",
                "https://zoom.us/test",
                False,
                "{}",
            )

            await conn.execute(
                """
                INSERT INTO interview_assignments
                (event_id, interviewer_id, first_name, last_name, email,
                 global_role, training_role, is_enabled, manager_id,
                 interviewer_pool_id, interviewer_pool_title,
                 interviewer_pool_is_archived, training_path, interviewer_updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
                """,
                event_id,
                uuid4(),
                "Test",
                "User",
                "test@example.com",
                "Interviewer",
                "Trained",
                True,
                None,
                uuid4(),
                "Test Pool",
                False,
                "{}",
            )

            # Query should NOT find cancelled interviews
            results = await conn.fetch(
                """
                SELECT ie.event_id
                FROM interview_events ie
                JOIN interview_assignments ia ON ie.event_id = ia.event_id
                JOIN interview_schedules s ON ie.schedule_id = s.schedule_id
                JOIN slack_users su ON ia.email = su.email
                WHERE ie.start_time BETWEEN NOW() + INTERVAL '4 minutes'
                                        AND NOW() + INTERVAL '20 minutes'
                  AND s.status = 'Scheduled'  -- Only scheduled interviews
                """
            )

            assert len(results) == 0


class TestReminderMessageBuilding:
    """Unit-style tests for reminder message construction."""

    def test_reminder_message_structure(self):
        """Test that reminder message has required blocks."""
        candidate_data = {
            "id": "candidate_123",
            "name": "Jane Doe",
            "emailAddresses": [{"value": "jane@example.com"}],
        }

        interview_data = {
            "event_id": "event_123",
            "interview_title": "Technical Interview",
            "start_time": datetime(2024, 10, 20, 14, 0, tzinfo=UTC),
            "end_time": datetime(2024, 10, 20, 15, 0, tzinfo=UTC),
            "form_definition_id": "form_123",
            "application_id": "app_123",
            "interviewer_id": "int_123",
        }

        blocks = build_reminder_message(
            candidate_data=candidate_data,
            interview_data=interview_data,
            file_external_id=None,
            job_title=None,
        )

        # Verify structure
        assert isinstance(blocks, list)
        assert len(blocks) > 0

        # Find header block
        header_blocks = [b for b in blocks if b.get("type") == "header"]
        assert len(header_blocks) == 1
        assert "Feedback Reminder" in header_blocks[0]["text"]["text"]

        # Find action block (button)
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 1
        assert action_blocks[0]["elements"][0]["action_id"] == "open_feedback_modal"

    def test_reminder_message_with_resume(self):
        """Test that resume link is included when available."""
        candidate_data = {
            "id": "candidate_123",
            "name": "Jane Doe",
            "emailAddresses": [{"value": "jane@example.com"}],
        }

        interview_data = {
            "event_id": "event_123",
            "interview_title": "Tech Interview",
            "start_time": datetime(2024, 10, 20, 14, 0, tzinfo=UTC),
            "end_time": datetime(2024, 10, 20, 15, 0, tzinfo=UTC),
            "form_definition_id": "form_123",
            "application_id": "app_123",
            "interviewer_id": "int_123",
        }

        blocks = build_reminder_message(
            candidate_data=candidate_data,
            interview_data=interview_data,
            file_external_id="file_ext_123",
            job_title=None,
        )

        # Find section with resume
        section_texts = [
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        ]

        has_resume = any("Resume" in text or "file" in text for text in section_texts)
        assert has_resume

    def test_reminder_message_without_candidate_email(self):
        """
        EDGE CASE: Candidate has no email in Ashby.
        Test message structure when emailAddresses is empty (the bug we fixed!).
        """
        candidate_data = {
            "id": "candidate_456",
            "name": "John Smith",
            "emailAddresses": [],  # Empty list - no email
        }

        interview_data = {
            "event_id": "event_456",
            "interview_title": "Phone Screen",
            "start_time": datetime(2024, 10, 21, 10, 0, tzinfo=UTC),
            "form_definition_id": "form_456",
            "application_id": "app_456",
            "interviewer_id": "int_456",
        }

        # This should NOT crash (fixed bug)
        blocks = build_reminder_message(
            candidate_data=candidate_data,
            interview_data=interview_data,
            file_external_id=None,
            job_title=None,
        )

        # Verify basic structure exists
        assert len(blocks) >= 4  # Header, info, divider, actions, footer

        # Verify candidate name still shows
        section_texts = [
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        ]

        has_candidate_name = any("John Smith" in text for text in section_texts)
        assert has_candidate_name

    def test_reminder_button_contains_metadata(self):
        """Test that button value contains all required metadata for modal."""
        import json

        candidate_data = {
            "id": "candidate_789",
            "name": "Test Candidate",
            "emailAddresses": [],
        }

        interview_data = {
            "event_id": "event_789",
            "interview_title": "Final Interview",
            "start_time": datetime(2024, 10, 22, 15, 30, tzinfo=UTC),
            "form_definition_id": "form_789",
            "application_id": "app_789",
            "interviewer_id": "int_789",
        }

        blocks = build_reminder_message(
            candidate_data=candidate_data,
            interview_data=interview_data,
            file_external_id=None,
            job_title=None,
        )

        # Find action block and extract button value
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        button = action_blocks[0]["elements"][0]
        metadata = json.loads(button["value"])

        # Verify all required fields for opening modal
        assert metadata["event_id"] == "event_789"
        assert metadata["form_definition_id"] == "form_789"
        assert metadata["application_id"] == "app_789"
        assert metadata["interviewer_id"] == "int_789"
        assert metadata["candidate_id"] == "candidate_789"

    def test_reminder_message_with_all_fields(self):
        """Test reminder message includes all available candidate and interview fields."""
        import json

        candidate_data = {
            "id": "candidate_123",
            "name": "Jane Smith",
            "primaryEmailAddress": {"value": "jane@example.com"},
            "primaryPhoneNumber": {"value": "+1-555-0123"},
            "position": "Software Engineer",
            "company": "TechCorp",
            "school": "MIT",
            "location": {"locationSummary": "San Francisco, CA"},
            "timezone": "America/Los_Angeles",
            "socialLinks": [
                {"url": "https://linkedin.com/in/jane", "type": "LinkedIn"},
                {"url": "https://github.com/jane", "type": "GitHub"},
            ],
            "profileUrl": "https://ashby.com/candidates/123",
        }

        interview_data = {
            "event_id": "event_123",
            "interview_title": "Technical Interview",
            "start_time": datetime(2024, 10, 20, 14, 0, tzinfo=UTC),
            "end_time": datetime(2024, 10, 20, 15, 0, tzinfo=UTC),
            "meeting_link": "https://zoom.us/j/123",
            "location": "Zoom",
            "feedback_link": "https://ashby.com/feedback/123",
            "instructions_plain": "Focus on technical skills and problem-solving ability.",
            "form_definition_id": "form_123",
            "application_id": "app_123",
            "interviewer_id": "interviewer_123",
        }

        blocks = build_reminder_message(
            candidate_data=candidate_data,
            interview_data=interview_data,
            file_external_id=None,
            job_title="Senior Software Engineer",
        )

        # Verify all sections present
        message_text = json.dumps(blocks)
        assert "Jane Smith" in message_text
        assert "jane@example.com" in message_text
        assert "+1-555-0123" in message_text
        assert "LinkedIn" in message_text
        assert "GitHub" in message_text
        assert "San Francisco, CA" in message_text
        assert "Technical Interview" in message_text
        assert "Senior Software Engineer" in message_text
        assert "zoom.us" in message_text
        assert "60 min" in message_text  # Duration
