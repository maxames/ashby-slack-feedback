# Architecture Documentation

## Overview

Ashby Slack Feedback is built with clean architecture principles, emphasizing separation of concerns, testability, and maintainability. The application follows a layered architecture where each layer has a single, well-defined responsibility.

## System Architecture

```mermaid
graph LR
    A[Ashby ATS] -->|Webhook| B[API Layer]
    B --> C[Services Layer]
    C --> D[PostgreSQL Database]
    E[APScheduler] -->|Every 5min| C
    C -->|Send Reminders| F[Slack API]
    F -->|Interactions| B
    B --> C
    C -->|Submit Feedback| A
```

## Layer Responsibilities

### `/api/` - HTTP Handlers

Purpose: Receive HTTP requests, validate inputs, call services, return responses

Responsibilities:
- FastAPI route handlers
- Request validation (Pydantic models)
- Authentication/authorization checks
- HTTP-specific error handling
- Rate limiting

Files:
- `webhooks.py` - Ashby webhook endpoint with signature verification
- `slack_interactions.py` - Slack interactive component handlers (modals, actions)
- `admin.py` - Admin endpoints for manual sync triggers and stats

What it does NOT do:
- Business logic
- Direct database access
- External API calls
- View formatting

### `/clients/` - External API Wrappers

Purpose: Encapsulate all communication with external services

Responsibilities:
- HTTP client configuration
- API authentication setup
- Request/response marshalling
- View formatting (Slack Block Kit)
- Payload parsing

Files:
- `ashby.py` - Ashby ATS API client (fetch candidate info, submit feedback)
- `slack.py` - Slack SDK wrapper (send DMs, open modals, register files)
- `slack_views.py` - Slack UI formatters (feedback modal, reminder messages)
- `slack_field_builders.py` - Slack form field builders (text, select, date, etc.)
- `slack_parsers.py` - Slack payload extractors (form values, submissions)

What it does NOT do:
- Business logic
- Database access
- Calling other services

### `/services/` - Business Logic

Purpose: Orchestrate business operations, apply rules, manage state

Responsibilities:
- Business rule enforcement
- Data validation
- Database operations (direct SQL queries)
- Workflow orchestration
- Transaction management

Files:
- `interviews.py` - Interview schedule processing (webhook business logic)
- `feedback.py` - Feedback draft management and submission
- `reminders.py` - Reminder window detection and sending logic
- `sync.py` - Data synchronization (forms, interviews, users)
- `scheduler.py` - APScheduler configuration and job management

What it does NOT do:
- HTTP handling
- View formatting
- Direct external API calls (uses clients)

### `/core/` - Infrastructure

Purpose: Foundational infrastructure components

Responsibilities:
- Application configuration
- Database connection management
- Logging setup

Files:
- `config.py` - Environment variable configuration (Pydantic Settings)
- `database.py` - AsyncPG connection pool management
- `logging.py` - Structured logging setup (structlog)

What it does NOT do:
- Business logic
- HTTP handling
- External API calls

### `/models/` - Data Structures

Purpose: Define data shapes and validation rules for inbound requests

Responsibilities:
- Pydantic models for request validation
- Runtime validation logic
- API request/response contracts

Files:
- `webhooks.py` - Ashby webhook payload models

What it does NOT do:
- Business logic
- Database operations
- API calls

**See also**: `/types/` for static response structures (TypedDict)

### `/types/` - Static Type Definitions

Static type definitions for external API responses using TypedDict.

Files:
- `ashby.py` - Ashby API response types (CandidateTD, FileHandleTD, EmailAddressTD, etc.)
- `slack.py` - Slack payload types (SlackUserTD, SlackButtonMetadataTD, SlackModalMetadataTD, etc.)

What it does NOT do:
- Runtime validation (use Pydantic models in `/models/` for that)
- Business logic
- API calls

Distinction from `/models/`:
- `/models/` - Runtime validation with Pydantic for inbound requests
- `/types/` - Static type hints for external API responses (no validation)

### `/utils/` - Generic Helpers

Purpose: Reusable utility functions with no business logic

Responsibilities:
- Security utilities (HMAC verification)
- Time utilities (parsing, formatting, timezone handling)
- Generic helper functions

Files:
- `security.py` - Webhook signature verification
- `time.py` - Timezone-aware timestamp parsing and formatting

What it does NOT do:
- Business logic
- Database access
- API calls

## Data Flow

### 1. Webhook Ingestion Flow

```
Ashby ATS
  → POST /webhooks/ashby (api/webhooks.py)
    → Verify HMAC signature (utils/security.py)
    → Extract schedule data
    → Call services/interviews.process_schedule_update()
      → Validate status (Scheduled/Complete/Cancelled)
      → Apply business rules (cancellation → delete)
      → Execute full-replace upsert to database
      → Log webhook to audit table
  → Return 204 No Content
```

**Key decisions**:
- Signature verification happens in API layer (protocol-specific)
- Business rules (status validation) happen in service layer
- Full-replace strategy ensures idempotency

### 2. Reminder Scheduling Flow

```
APScheduler (every 5 minutes)
  → services/reminders.send_due_reminders()
    → Query database for interviews starting in 4-20 minutes
    → Filter out already-sent reminders
    → For each reminder:
      → Fetch candidate info (clients/ashby.fetch_candidate_info)
      → Build reminder message (clients/slack_views.build_reminder_message)
      → Send DM (clients/slack.send_dm)
      → Record in feedback_reminders_sent table
```

**Key decisions**:
- 4-20 minute window balances timeliness vs. spam
- Claim-before-send pattern prevents duplicate reminders
- View building happens in client layer

### 3. Feedback Submission Flow

```
Slack Modal Submission
  → POST /slack/interactions (api/slack_interactions.py)
    → Verify Slack signature (Slack SDK)
    → Parse private_metadata (event_id, interviewer_id, form_id)
    → Extract form values (clients/slack_parsers.extract_form_values)
    → Call services/feedback.submit_feedback()
      → Transform to Ashby format (clients/slack_parsers)
      → Submit to Ashby (clients/ashby.submit_feedback)
      → Delete draft from database
      → Update reminder tracking (submitted_at timestamp)
  → Return 200 OK
```

**Key decisions**:
- Draft auto-save on Enter key press (dispatch_action_config) for RichText fields
- Slack's view_closed event doesn't include state values, so we use dispatch actions
- Ashby submission happens before draft deletion (safety)
- Private metadata carries context without database lookup

## Database Schema

### Core Tables

**`interview_schedules`**
- Primary webhook ingestion table
- Stores schedule-level metadata
- Links to events via schedule_id

**`interview_events`**
- Individual interview events
- Contains timing, location, meeting links
- Links to interviewer assignments

**`interview_assignments`**
- Many-to-many: events ↔ interviewers
- Stores interviewer metadata
- Used for reminder targeting

**`feedback_reminders_sent`**
- Tracks reminder delivery
- Prevents duplicate sends
- Records open/submit timestamps

**`feedback_drafts`**
- Auto-saved form data
- Prevents data loss on modal dismiss
- Keyed by (event_id, interviewer_id)

### Reference Tables

**`interviews`**
- Interview type definitions
- Links to feedback form definitions
- Synced from Ashby API

**`feedback_form_definitions`**
- Ashby feedback form schemas
- Used to build Slack modals
- Cached for 24 hours

**`slack_users`**
- Email → Slack user ID mapping
- Synced hourly from Slack API
- Required for sending DMs

## Design Principles

### 1. Type Safety Strategy

External API responses are typed using `TypedDict` at client boundaries:

**Directory structure:**
- `app/types/ashby.py` - Ashby API response types
- `app/types/slack.py` - Slack payload types
- `app/models/` - Pydantic models for request validation

**Distinction:**
- `/models/` handles **runtime validation** (Pydantic for API requests)
- `/types/` handles **static structures** (TypedDict for API responses)

**Pattern:**
1. Define TypedDict for fields actually used
2. Cast once at the adapter boundary (in `clients/`)
3. Consume typed results everywhere else (no `dict[str, Any]` propagation)

This provides type safety without heavy model frameworks, while keeping the system pragmatic for working with dynamic external APIs.

**Enforcement:**
All architectural patterns must be reflected in this document before merge.

### Type Safety Implementation Details

**DateTime Handling:**
- `InterviewDataTD` uses `datetime` objects internally
- `slack_views.py` converts datetime → Slack format strings at the boundary using `format_slack_timestamp()`
- `utils/time.py` provides timezone-aware utilities for consistent formatting
- All timestamps from PostgreSQL TIMESTAMPTZ are timezone-aware by default
- Database stores all timestamps in UTC; Slack displays in user's local timezone

**Slack Block Kit:**
- Core block types (`SlackSectionTD`, `SlackDividerTD`, `SlackActionsTD`, `SlackContextTD`) defined in `/types/slack.py`
- Union type `SlackBlockTD` covers the block types actually used in the application
- Complex nested structures (button elements, modal internals) remain `dict[str, Any]` (pragmatic 80/20 trade-off)
- Block structure validated via contract tests rather than exhaustive typing
- Full typing would require 50+ nested TypedDicts with minimal benefit

**External SDK Stubs:**
- Type stubs created for `slack_sdk` in `/stubs/slack_sdk/web/async_client.pyi`
- Enables strict type checking without upstream type support
- Follows same pattern as existing stubs for `asyncpg`, `apscheduler`, `slowapi`
- Configured in `pyproject.toml` via `stubPath = "stubs"`

### 2. Separation of Concerns

Each layer has a single, well-defined purpose:
- API layer: HTTP protocol handling
- Services layer: Business logic
- Clients layer: External API communication

**Anti-pattern**: Business logic in API handlers
**Correct pattern**: API extracts data → Services apply logic → Clients communicate

### 2. Dependency Direction

```
api → services → clients
api → clients
  ↓      ↓         ↓
       core
```

Allowed:
- Services call clients
- API calls services
- API calls clients
- Everything can use core

Forbidden:
- Clients call services
- Core calls anything
- Circular dependencies

### 3. Idempotency

All operations must be safely repeatable:

Webhooks: Full-replace upsert strategy
- DELETE + INSERT instead of UPDATE
- Duplicate webhooks result in same final state

Reminders: Claim-before-send pattern
- INSERT INTO feedback_reminders_sent BEFORE sending
- Unique constraint prevents duplicates

Submissions: Ashby API handles idempotency
- Safe to retry on network failure

### 4. Timezone Awareness

All timestamps are UTC-aware:

Storage: PostgreSQL `TIMESTAMPTZ` (UTC)
Internal: Python `datetime` with `tzinfo=UTC`
External:
- Ashby API: ISO 8601 with 'Z' suffix
- Slack: Unix timestamps (auto-converted to user's timezone)

Utilities: `utils/time.py` provides:
- `parse_ashby_timestamp()` - ISO 8601 → datetime
- `format_slack_timestamp()` - datetime → Slack format
- `ensure_utc()` - Enforce timezone awareness
- `is_stale()` - Check data freshness

### 5. Structured Logging

All log events use structured logging with `structlog`:

```python
logger.info(
    "event_name",
    key1=value1,
    key2=value2,
    context="additional_info"
)
```

Benefits:
- Machine-parseable logs
- Easy filtering/aggregation
- Consistent format across application

## Security

### Webhook Verification

Ashby: HMAC-SHA256 signature verification
- Header: `x-ashby-signature: sha256=<hex_digest>`
- Prevents webhook spoofing
- Timing-safe comparison to prevent timing attacks

Slack: SDK handles signature verification
- Uses Slack signing secret
- Validates request timestamp (prevents replay attacks)

### Rate Limiting

**SlowAPI** integration:
- 100 requests/minute per IP for webhooks
- Prevents abuse and DoS
- Returns 429 Too Many Requests on limit exceed

### SQL Injection Prevention

**Parameterized queries** everywhere:
```python
await db.execute(
    "INSERT INTO table (col) VALUES ($1)",
    value  # Properly escaped by asyncpg
)
```

**Never** use f-strings for SQL construction

## Performance Considerations

### Connection Pooling

**AsyncPG connection pool**:
- Min size: 2 connections
- Max size: 10 connections
- Reuses connections across requests
- Automatic cleanup on shutdown

### Query Optimization

**Indexes** on:
- Foreign keys (schedule_id, event_id)
- Query filters (email, start_time)
- Sort columns (received_at DESC)

**Partial indexes** for common filters:
- Active feedback forms (WHERE NOT is_archived)
- Pending reminders (WHERE submitted_at IS NULL)

### Background Processing

**APScheduler**:
- Reminders: Every 5 minutes (low overhead)
- Form sync: Every 6 hours (API rate limit friendly)
- Interview sync: Every 15 minutes (balance freshness vs. load)
- Slack user sync: Every hour

## Testing Strategy

### Unit Tests

Focus: Pure functions and utilities
- `test_security.py` - HMAC verification, timing attacks
- `test_time_utils.py` - Timezone handling, parsing, formatting
- `test_field_builders.py` - Slack field type mappings

Characteristics:
- Fast (<1ms per test)
- No external dependencies
- High coverage of edge cases

### Integration Tests

Focus: Database operations and workflows
- `test_webhook_flow.py` - Webhook → DB with real database
- `test_feedback_flow.py` - Draft save/load/submit flow
- `test_reminders.py` - Reminder window detection and message building

Characteristics:
- Use real test database
- Test database transactions
- Cover realistic edge cases (cancellations, reschedules, missing data)

### Contract Tests

Focus: External payload validation
- `test_webhook_payloads.py` - Validate Ashby webhook structure
- `test_slack_payloads.py` - Validate Slack interaction structure

Characteristics:
- Verify payload shapes match expectations
- Catch breaking API changes early
- Document expected formats

## Deployment Considerations

### Environment Variables

All configuration via environment variables (12-factor app):
- No hardcoded secrets
- Easy to change per environment
- Validated at startup (Pydantic Settings)

### Database Migrations

Current: Schema in `database/schema.sql`
Future: Consider Alembic for version control

Migration tracking:
- `schema_migrations` table records applied migrations
- Supports rollback and audit trail

### Health Checks

**`GET /health`** endpoint provides:
- Database connectivity status
- Connection pool statistics (size, free, in_use)
- Used by orchestrators (Kubernetes, Render, Railway)

### Graceful Shutdown

Startup:
1. Connect to database
2. Setup and start scheduler
3. Run initial syncs (forms, interviews, users)

Shutdown:
1. Stop scheduler (completes running jobs)
2. Disconnect database (closes pool)
3. FastAPI handles request draining

## Future Enhancements

### Potential Improvements

1. **Repository Pattern**: Abstract database operations
   - Currently: Direct SQL in services
   - Future: `repositories/interviews.py`, `repositories/feedback.py`
   - Benefits: Easier to test, swap databases

2. **Event Sourcing**: Audit trail for all changes
   - Store all state transitions
   - Replay events for debugging
   - Support analytics

3. **Message Queue**: Decouple webhook processing
   - Use Redis/RabbitMQ for async processing
   - Improves webhook response time
   - Better failure handling

4. **Caching**: Reduce database load
   - Cache feedback form definitions (already implicit)
   - Cache Slack user lookups
   - Use Redis for distributed cache

5. **Metrics**: Observability improvements
   - Prometheus metrics (requests, durations, errors)
   - Grafana dashboards
   - Alerting on anomalies

### Scalability

**Current limitations**:
- Single-instance scheduler (no distributed lock)
- Reminder send is sequential (not parallelized)

**Scaling strategy**:
1. Horizontal scaling: Multiple API instances (stateless)
2. Scheduler: Use distributed lock (Redis/PostgreSQL advisory locks)
3. Reminders: Parallel processing with connection pool

## Conclusion

This architecture balances pragmatism with best practices:
- Clean separation of concerns enables easy maintenance
- Layered design supports testing at each level
- Idempotency and timezone handling prevent common bugs
- Structured logging aids debugging and monitoring

The codebase is designed for a team to understand quickly and extend confidently.

