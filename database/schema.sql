-- ============================================
-- Ashby Slack Feedback - Database Schema
-- Version: 1.0
-- Description: Complete schema for webhook ingestion
--              and feedback reminder system
-- ============================================
-- Setup: psql $DATABASE_URL -f database/schema.sql
-- ============================================

BEGIN;

-- ============================================
-- Core Webhook Ingestion Tables
-- ============================================

-- Interview Schedules
CREATE TABLE IF NOT EXISTS interview_schedules (
    schedule_id UUID PRIMARY KEY,
    application_id UUID NOT NULL,
    interview_stage_id UUID,
    status TEXT NOT NULL,
    candidate_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_interview_schedules_application_id
ON interview_schedules(application_id);

-- Interview Definitions (Reference Table)
CREATE TABLE IF NOT EXISTS interviews (
    interview_id UUID PRIMARY KEY,
    title TEXT,
    external_title TEXT,
    is_archived BOOLEAN,
    is_debrief BOOLEAN,
    instructions_html TEXT,
    instructions_plain TEXT,
    job_id UUID,
    feedback_form_definition_id UUID,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interview Events
CREATE TABLE IF NOT EXISTS interview_events (
    event_id UUID PRIMARY KEY,
    schedule_id UUID NOT NULL REFERENCES interview_schedules(schedule_id) ON DELETE CASCADE,
    interview_id UUID NOT NULL REFERENCES interviews(interview_id),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    feedback_link TEXT,
    location TEXT,
    meeting_link TEXT,
    has_submitted_feedback BOOLEAN,
    extra_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_interview_events_schedule_id
ON interview_events(schedule_id);

CREATE INDEX IF NOT EXISTS idx_interview_events_interview_id
ON interview_events(interview_id);

CREATE INDEX IF NOT EXISTS idx_interview_events_start_time
ON interview_events(start_time);

-- Interview Assignments (Interviewers)
CREATE TABLE IF NOT EXISTS interview_assignments (
    event_id UUID NOT NULL REFERENCES interview_events(event_id) ON DELETE CASCADE,
    interviewer_id UUID NOT NULL,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    global_role TEXT,
    training_role TEXT,
    is_enabled BOOLEAN,
    manager_id UUID,
    interviewer_pool_id UUID,
    interviewer_pool_title TEXT,
    interviewer_pool_is_archived BOOLEAN,
    training_path JSONB,
    interviewer_updated_at TIMESTAMPTZ,
    PRIMARY KEY (event_id, interviewer_id)
);

CREATE INDEX IF NOT EXISTS idx_interview_assignments_email
ON interview_assignments(email);

-- Webhook Audit Log
CREATE TABLE IF NOT EXISTS ashby_webhook_payloads (
    id BIGSERIAL PRIMARY KEY,
    schedule_id UUID,
    received_at TIMESTAMPTZ DEFAULT NOW(),
    action TEXT,
    payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_ashby_webhook_payloads_received_at
ON ashby_webhook_payloads(received_at DESC);

CREATE INDEX IF NOT EXISTS idx_ashby_webhook_payloads_schedule_id
ON ashby_webhook_payloads(schedule_id);

-- ============================================
-- Feedback Application Tables
-- ============================================

-- Feedback Form Definitions
CREATE TABLE IF NOT EXISTS feedback_form_definitions (
    form_definition_id UUID PRIMARY KEY,
    title TEXT,
    definition JSONB NOT NULL,
    is_archived BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_forms_active
ON feedback_form_definitions(form_definition_id)
WHERE NOT is_archived;

-- Slack Users Directory
CREATE TABLE IF NOT EXISTS slack_users (
    slack_user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    real_name TEXT,
    display_name TEXT,
    is_bot BOOLEAN DEFAULT false,
    deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_slack_users_email
ON slack_users(email);

-- Feedback Reminders Tracking
CREATE TABLE IF NOT EXISTS feedback_reminders_sent (
    event_id UUID NOT NULL REFERENCES interview_events(event_id) ON DELETE CASCADE,
    interviewer_id UUID NOT NULL,
    slack_user_id TEXT NOT NULL REFERENCES slack_users(slack_user_id),
    slack_channel_id TEXT NOT NULL,
    slack_message_ts TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    opened_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    PRIMARY KEY (event_id, interviewer_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_reminders_sent_at
ON feedback_reminders_sent(sent_at);

CREATE INDEX IF NOT EXISTS idx_feedback_reminders_pending
ON feedback_reminders_sent(event_id)
WHERE submitted_at IS NULL;

-- Feedback Drafts
CREATE TABLE IF NOT EXISTS feedback_drafts (
    event_id UUID NOT NULL REFERENCES interview_events(event_id) ON DELETE CASCADE,
    interviewer_id UUID NOT NULL,
    form_values JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id, interviewer_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_drafts_updated
ON feedback_drafts(updated_at DESC);

-- ============================================
-- Migration Tracking
-- ============================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

-- Record initial schema
INSERT INTO schema_migrations (version, name, description)
VALUES (1, 'initial_schema', 'Core webhook tables + feedback app tables')
ON CONFLICT (version) DO NOTHING;

COMMIT;

