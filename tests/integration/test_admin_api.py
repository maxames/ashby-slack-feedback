"""Integration tests for admin API endpoints."""

import pytest


class TestAdminEndpoints:
    """Test admin API endpoints."""

    @pytest.mark.asyncio
    async def test_admin_sync_forms_triggers_sync(self, mock_ashby_client, clean_db):
        """Test that sync-forms endpoint triggers form synchronization."""
        from uuid import uuid4

        from app.api.admin import admin_sync_forms
        from app.core.database import db
        from tests.fixtures.mock_clients import create_ashby_paginated_response

        # Setup mock responses with valid UUIDs
        form_id_1 = str(uuid4())
        form_id_2 = str(uuid4())
        mock_ashby_client.add_response(
            "feedbackFormDefinition.list",
            create_ashby_paginated_response(
                [
                    {
                        "id": form_id_1,
                        "title": "Form 1",
                        "formDefinition": {"sections": []},
                        "isArchived": False,
                    },
                    {
                        "id": form_id_2,
                        "title": "Form 2",
                        "formDefinition": {"sections": []},
                        "isArchived": False,
                    },
                ]
            ),
        )

        # Call endpoint
        response = await admin_sync_forms()

        # Verify response
        assert response["status"] == "completed"

        # Verify forms were synced to database
        forms_count = await db.fetchval(
            "SELECT COUNT(*) FROM feedback_form_definitions"
        )
        assert forms_count >= 2

    @pytest.mark.asyncio
    async def test_admin_sync_slack_users_triggers_sync(
        self, mock_slack_client, clean_db
    ):
        """Test that sync-slack-users endpoint triggers user synchronization."""
        from unittest.mock import AsyncMock

        from app.api.admin import admin_sync_slack_users
        from app.core.database import db

        # Setup mock Slack response - override the default
        mock_slack_client.client.users_list = AsyncMock(
            return_value={
                "ok": True,
                "members": [
                    {
                        "id": "USYNC1",
                        "profile": {
                            "email": "usersync1@example.com",
                            "display_name": "User Sync 1",
                        },
                        "real_name": "User Sync One",
                        "is_bot": False,
                        "deleted": False,
                    },
                    {
                        "id": "USYNC2",
                        "profile": {
                            "email": "usersync2@example.com",
                            "display_name": "User Sync 2",
                        },
                        "real_name": "User Sync Two",
                        "is_bot": False,
                        "deleted": False,
                    },
                ],
            }
        )

        # Call endpoint
        response = await admin_sync_slack_users()

        # Verify response
        assert response["status"] == "completed"

        # Verify users were synced to database
        users_count = await db.fetchval(
            "SELECT COUNT(*) FROM slack_users WHERE NOT deleted"
        )
        assert users_count >= 2

    @pytest.mark.asyncio
    async def test_admin_stats_returns_correct_counts(
        self, clean_db, sample_interview_event
    ):
        """Test that stats endpoint returns accurate counts."""
        from app.api.admin import admin_stats
        from app.core.database import db

        # Insert test data using existing event
        event_id = sample_interview_event["event_id"]
        interviewer_id = sample_interview_event["interviewer_id"]

        # First insert slack_user (FK requirement)
        await db.execute(
            """
            INSERT INTO slack_users (slack_user_id, real_name, email)
            VALUES ($1, $2, $3)
            ON CONFLICT (slack_user_id) DO NOTHING
            """,
            "U123",
            "Test User",
            "testuser123@example.com",
        )

        await db.execute(
            """
            INSERT INTO feedback_reminders_sent
            (event_id, interviewer_id, slack_user_id, slack_channel_id, slack_message_ts, sent_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
            event_id,
            interviewer_id,
            "U123",
            "D123",
            "123456.789",
        )

        # Call endpoint
        stats = await admin_stats()

        # Verify stats structure
        assert "reminders_sent" in stats
        assert "pending_feedback" in stats
        assert "active_drafts" in stats
        assert "feedback_forms" in stats
        assert "slack_users" in stats

        # Verify counts are numbers
        assert isinstance(stats["reminders_sent"], int)
        assert stats["reminders_sent"] >= 1

    @pytest.mark.asyncio
    async def test_admin_stats_counts_reminders_sent(
        self, clean_db, sample_interview_event
    ):
        """Test that reminders_sent count is accurate."""
        from uuid import uuid4

        from app.api.admin import admin_stats
        from app.core.database import db

        # Insert multiple reminders using existing event
        event_id = sample_interview_event["event_id"]

        # First insert slack_users (FK requirement)
        for i in range(3):
            await db.execute(
                """
                INSERT INTO slack_users (slack_user_id, real_name, email)
                VALUES ($1, $2, $3)
                ON CONFLICT (slack_user_id) DO NOTHING
                """,
                f"UREMD{i}",
                f"User {i}",
                f"userremd{i}@example.com",
            )

        # Insert 3 reminders with different interviewer_ids to avoid PK collision
        for i in range(3):
            await db.execute(
                """
                INSERT INTO feedback_reminders_sent
                (event_id, interviewer_id, slack_user_id, slack_channel_id, slack_message_ts, sent_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                event_id,
                str(uuid4()),  # Different interviewer_id for each
                f"UREMD{i}",
                f"D{i}",
                f"{i}.123",
            )

        stats = await admin_stats()
        assert stats["reminders_sent"] >= 3

    @pytest.mark.asyncio
    async def test_admin_stats_counts_pending_feedback(
        self, clean_db, sample_interview_event
    ):
        """Test that pending_feedback count is accurate."""
        from app.api.admin import admin_stats
        from app.core.database import db

        # Insert slack_user first (FK requirement)
        event_id = sample_interview_event["event_id"]
        await db.execute(
            """
            INSERT INTO slack_users (slack_user_id, real_name, email)
            VALUES ($1, $2, $3)
            ON CONFLICT (slack_user_id) DO NOTHING
            """,
            "U999",
            "Test User Pending",
            "testpending999@example.com",
        )

        # Insert reminder without submission using existing event
        await db.execute(
            """
            INSERT INTO feedback_reminders_sent
            (event_id, interviewer_id, slack_user_id, slack_channel_id, slack_message_ts, sent_at, submitted_at)
            VALUES ($1, $2, $3, $4, $5, NOW(), NULL)
            """,
            event_id,
            sample_interview_event["interviewer_id"],
            "U999",
            "D123",
            "123.456",
        )

        stats = await admin_stats()
        assert stats["pending_feedback"] >= 1

    @pytest.mark.asyncio
    async def test_admin_stats_counts_active_drafts(
        self, clean_db, sample_interview_event
    ):
        """Test that active_drafts count is accurate."""
        from uuid import uuid4

        from app.api.admin import admin_stats
        from app.services.feedback import save_draft

        # Save some drafts using existing event_id
        event_id = sample_interview_event["event_id"]
        for i in range(2):
            await save_draft(
                event_id,
                str(uuid4()),
                {"field": f"value{i}"},
            )

        stats = await admin_stats()
        assert stats["active_drafts"] >= 2

    @pytest.mark.asyncio
    async def test_admin_stats_counts_feedback_forms(
        self, clean_db, sample_feedback_form
    ):
        """Test that feedback_forms count is accurate."""
        from app.api.admin import admin_stats

        stats = await admin_stats()

        # At least one form from sample_feedback_form fixture
        assert stats["feedback_forms"] >= 1

    @pytest.mark.asyncio
    async def test_admin_stats_counts_slack_users(self, clean_db, sample_slack_user):
        """Test that slack_users count is accurate."""
        from app.api.admin import admin_stats

        stats = await admin_stats()

        # At least one user from sample_slack_user fixture
        assert stats["slack_users"] >= 1


from unittest.mock import AsyncMock
