# Database Setup and Migration Guide

This directory contains the database schema for the Ashby Slack Feedback application.

## Overview

The database consists of 9 tables split into two logical groups:

**Core Webhook Ingestion (5 tables):**
- `interview_schedules` - Interview schedule metadata
- `interview_events` - Individual interview events within schedules
- `interviews` - Interview definitions (reference table)
- `interview_assignments` - Interviewer assignments to events
- `ashby_webhook_payloads` - Audit log of raw webhook payloads

**Feedback Application (4 tables):**
- `feedback_form_definitions` - Ashby feedback form schemas
- `slack_users` - Slack workspace user directory
- `feedback_reminders_sent` - Tracking table for sent reminders
- `feedback_drafts` - Partial form submissions (auto-saved)

## Initial Setup

### Local Development

```bash
# 1. Create database
createdb ashby_feedback

# 2. Set environment variable
export DATABASE_URL="postgresql://localhost:5432/ashby_feedback"

# 3. Run schema
psql $DATABASE_URL -f database/schema.sql

# 4. Verify tables created
psql $DATABASE_URL -c "\dt"

# 5. Check schema version
psql $DATABASE_URL -c "SELECT * FROM schema_migrations;"
```

Expected output:
```
 version |      name       |              description               |         applied_at
---------+-----------------+----------------------------------------+----------------------------
       1 | initial_schema  | Core webhook tables + feedback app...  | 2024-01-15 10:23:45.123-08
```

### Production (Render PostgreSQL)

```bash
# 1. Get DATABASE_URL from Render dashboard
# Format: postgresql://user:password@host:5432/dbname

# 2. Run schema
psql $DATABASE_URL -f database/schema.sql

# 3. Verify
psql $DATABASE_URL -c "SELECT version, name FROM schema_migrations;"
```

### Test Environment

For running tests locally:

```bash
# 1. Create test database
createdb ashby_feedback_test
# Or with full path if needed: /opt/homebrew/opt/postgresql@15/bin/createdb ashby_feedback_test

# 2. Apply schema
psql ashby_feedback_test -f database/schema.sql

# 3. Copy test environment config
cp .env.test.example .env.test
# Edit .env.test with your username (run `whoami` to check)

# 4. Run tests
pytest
```

## Schema Migrations

This project uses manual migrations with version tracking. No migration framework (Alembic, etc.) is required.

### Why Manual?

For a 9-table, solo-developer project:
- Simpler than Alembic
- Full control over changes
- Easy to understand and debug
- No additional dependencies
- Change history via `schema_migrations` table

### Making Schema Changes

#### Step 1: Apply the Change

Development:
```bash
# Make the change
psql $DATABASE_URL -c "ALTER TABLE interviews ADD COLUMN archived_at TIMESTAMPTZ;"

# Or run from file
psql $DATABASE_URL -f changes/002_add_archived_at.sql
```

Production (with transaction):
```bash
psql $DATABASE_URL <<EOF
BEGIN;

-- Your change here
ALTER TABLE interviews ADD COLUMN archived_at TIMESTAMPTZ;

-- Record it
INSERT INTO schema_migrations (version, name, description)
VALUES (2, 'add_archived_at', 'Track when interviews are archived');

COMMIT;
EOF
```

#### Step 2: Update schema.sql

Update the `CREATE TABLE interviews` statement in `database/schema.sql` to include the new column:

```sql
CREATE TABLE interviews (
    interview_id UUID PRIMARY KEY,
    title TEXT,
    -- ... existing columns ...
    archived_at TIMESTAMPTZ,  -- NEW
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

This ensures fresh database setups include the change.

#### Step 3: Record Migration

Insert into `schema_migrations` table (if not done in Step 1):

```bash
psql $DATABASE_URL -c "
INSERT INTO schema_migrations (version, name, description)
VALUES (2, 'add_archived_at', 'Track when interviews are archived');
"
```

#### Step 4: Document in Git

```bash
git add database/schema.sql
git commit -m "Add archived_at column to interviews table

Schema change:
- ALTER TABLE interviews ADD COLUMN archived_at TIMESTAMPTZ
- Recorded as migration version 2
- Updated schema.sql for fresh installs

Rationale: Track when interview definitions are archived to
support soft-delete functionality and historical reporting."
```

### Checking Migration Status

View all applied migrations:
```bash
psql $DATABASE_URL -c "SELECT * FROM schema_migrations ORDER BY version;"
```

Get current version:
```bash
psql $DATABASE_URL -c "SELECT MAX(version) as current_version FROM schema_migrations;"
```

View with formatted output:
```bash
psql $DATABASE_URL <<EOF
SELECT
    version,
    name,
    description,
    applied_at AT TIME ZONE 'America/Los_Angeles' as applied_at_pst
FROM schema_migrations
ORDER BY version DESC;
EOF
```

## Common Operations

### Reset Database (Destructive)

Development only:
```bash
# Drop and recreate
dropdb ashby_feedback && createdb ashby_feedback

# Run schema
psql $DATABASE_URL -f database/schema.sql
```

### Backup Database

Before any schema change:
```bash
# Full backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Schema only
pg_dump $DATABASE_URL --schema-only > schema_backup.sql

# Data only
pg_dump $DATABASE_URL --data-only > data_backup.sql
```

### Restore Database

```bash
# From full backup
psql $DATABASE_URL < backup_20240115_102345.sql

# Drop and restore (clean slate)
dropdb ashby_feedback
createdb ashby_feedback
psql $DATABASE_URL < backup_20240115_102345.sql
```

### Inspect Schema

```bash
# List all tables
psql $DATABASE_URL -c "\dt"

# Describe specific table
psql $DATABASE_URL -c "\d interview_schedules"

# Show table sizes
psql $DATABASE_URL -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Show all indexes
psql $DATABASE_URL -c "\di"

# Show foreign keys
psql $DATABASE_URL -c "
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;
"
```

## Schema Migrations Table

The `schema_migrations` table tracks all schema changes:

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Fields:**
- `version` - Sequential integer (1, 2, 3, ...)
- `name` - Short kebab-case identifier (e.g., `add-archived-at`)
- `description` - Human-readable explanation
- `applied_at` - Timestamp of when migration was applied

**Example entries:**
```
 version |      name       |              description               |         applied_at
---------+-----------------+----------------------------------------+----------------------------
       1 | initial_schema  | Core webhook tables + feedback app...  | 2024-01-15 10:23:45-08
       2 | add_archived_at | Track when interviews are archived     | 2024-01-20 14:15:22-08
       3 | add_slack_index | Index on slack_users.email for perf   | 2024-01-25 09:45:11-08
```

## Troubleshooting

### "Table already exists" error

This means the database is already initialized. Check current state:
```bash
psql $DATABASE_URL -c "\dt"
psql $DATABASE_URL -c "SELECT * FROM schema_migrations;"
```

To start fresh:
```bash
dropdb ashby_feedback && createdb ashby_feedback
psql $DATABASE_URL -f database/schema.sql
```

### Foreign key constraint violation

Check the order of operations. Parent tables must exist before child tables:

Correct order:
1. `interview_events` (parent)
2. `feedback_reminders_sent` (child, FK to interview_events)

If you get FK errors:
```bash
# Check if parent table exists
psql $DATABASE_URL -c "\d interview_events"

# Check if data exists in parent
psql $DATABASE_URL -c "SELECT COUNT(*) FROM interview_events;"
```

### Connection refused

Check DATABASE_URL:
```bash
echo $DATABASE_URL

# Should look like:
# postgresql://user:password@host:5432/dbname
```

Test connection:
```bash
psql $DATABASE_URL -c "SELECT version();"
```

### Permission denied

Ensure your database user has necessary privileges:
```sql
-- Run as superuser
GRANT ALL PRIVILEGES ON DATABASE ashby_feedback TO your_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO your_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO your_user;
```

## When to Add a Migration Framework

Consider adding Alembic or a similar tool if:
- Multiple developers making concurrent schema changes
- Need automatic rollback capabilities
- Schema changes become frequent (>1 per week)
- Project scales beyond 20+ tables
- Team grows beyond 2-3 developers

For the current scope (9 tables, solo developer), manual migrations are sufficient.

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Architecture Documentation](../docs/ARCHITECTURE.md)
- [psql Quick Reference](https://www.postgresql.org/docs/current/app-psql.html)

## Support

For questions or issues:
1. Check this README
2. Review ARCHITECTURE.md for system design
3. Check schema_migrations table for current state
4. Review git history for recent changes

