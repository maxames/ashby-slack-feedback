# Deployment Guide

This guide covers deploying Ashby Slack Feedback to various platforms.

## Prerequisites

Before deploying, ensure you have:

- PostgreSQL 15+ database
- Ashby ATS account with API access
- Slack workspace with admin permissions
- Domain name or public URL for webhooks

## Quick Deploy Options

### Option 1: Render.com (Recommended)

Render provides a simple one-click deployment with automatic database setup.

#### Steps

1. Fork/Clone Repository
   ```bash
   git clone https://github.com/maxames/ashby-slack-feedback.git
   cd ashby-slack-feedback
   ```

2. Create Render Account
   - Sign up at [render.com](https://render.com)
   - Connect your GitHub account

3. Deploy Using render.yaml
   - In Render dashboard, click **New → Blueprint**
   - Connect your repository
   - Render will automatically detect `render.yaml`
   - Click **Apply**

4. Configure Environment Variables

   Render will prompt for these required variables:

   | Variable | Description | Where to Find |
   |----------|-------------|---------------|
   | `ASHBY_API_KEY` | Ashby API key | Ashby → Settings → API Keys |
   | `ASHBY_WEBHOOK_SECRET` | Webhook secret | Create your own (32+ characters) |
   | `SLACK_BOT_TOKEN` | Bot token (`xoxb-...`) | See Slack App Setup below |
   | `SLACK_SIGNING_SECRET` | Signing secret | Slack → Basic Information → Signing Secret |

5. Wait for Deployment
   - Render will build and deploy your app
   - Database will be automatically created (empty)
   - Note your public URL: `https://your-app-name.onrender.com`

6. Apply Database Schema - Required Manual Step

   Render does not support automatic schema initialization for PostgreSQL. After first deployment:

   ```bash
   # Get DATABASE_URL from Render dashboard (Environment tab)
   psql <DATABASE_URL> -f database/schema.sql
   ```

   Verify schema applied:
   ```bash
   psql <DATABASE_URL> -c "\dt"
   # Should show: interview_schedules, interview_events, etc.
   ```

7. Configure Webhooks
   - See "Webhook Configuration" section below

#### render.yaml Configuration

The included `render.yaml` configures:
- Web service (Python runtime, auto-scaling)
- PostgreSQL database (Starter plan)
- Environment variables (secrets required, defaults set)
- Health check monitoring
- Schema must be applied manually (see step 6 above)

---

### Option 2: Railway

Railway offers simple deployment with automatic HTTPS and database provisioning.

#### Steps

1. Install Railway CLI
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. Initialize Project
   ```bash
   cd ashby-slack-feedback
   railway init
   ```

3. Provision Database
   ```bash
   railway add --plugin postgresql
   ```

4. Set Environment Variables
   ```bash
   railway variables set ASHBY_API_KEY="your_key"
   railway variables set ASHBY_WEBHOOK_SECRET="your_secret"
   railway variables set SLACK_BOT_TOKEN="xoxb-..."
   railway variables set SLACK_SIGNING_SECRET="your_secret"
   railway variables set LOG_LEVEL="INFO"
   ```

5. Deploy
   ```bash
   railway up
   ```

6. Apply Database Schema
   ```bash
   # Get database URL
   railway variables get DATABASE_URL

   # Apply schema
   psql <DATABASE_URL> -f database/schema.sql
   ```

7. Get Public URL
   ```bash
   railway domain
   ```

---

### Option 3: Fly.io

Fly.io provides edge deployment with automatic global distribution.

#### Steps

1. Install flyctl
   ```bash
   # macOS
   brew install flyctl

   # Or use install script
   curl -L https://fly.io/install.sh | sh
   ```

2. Login and Launch
   ```bash
   flyctl auth login
   cd ashby-slack-feedback
   flyctl launch
   ```

3. Configure Database
   ```bash
   # Create Postgres database
   flyctl postgres create

   # Attach to app
   flyctl postgres attach <db-name>
   ```

4. Set Secrets
   ```bash
   flyctl secrets set ASHBY_API_KEY="your_key"
   flyctl secrets set ASHBY_WEBHOOK_SECRET="your_secret"
   flyctl secrets set SLACK_BOT_TOKEN="xoxb-..."
   flyctl secrets set SLACK_SIGNING_SECRET="your_secret"
   ```

5. Apply Schema
   ```bash
   # Connect to Postgres
   flyctl postgres connect -a <db-name>

   # In psql prompt, paste contents of database/schema.sql
   ```

6. Deploy
   ```bash
   flyctl deploy
   ```

---

### Option 4: Docker Compose (Self-Hosted)

Run locally or on your own server using Docker.

#### Steps

1. Install Docker
   - [Get Docker Desktop](https://www.docker.com/products/docker-desktop)

2. Clone Repository
   ```bash
   git clone https://github.com/maxames/ashby-slack-feedback.git
   cd ashby-slack-feedback
   ```

3. Configure Environment
   ```bash
   cp .env.example .env
   nano .env  # Edit with your values
   ```

4. Start Services
   ```bash
   docker-compose up -d
   ```

5. View Logs
   ```bash
   docker-compose logs -f app
   ```

6. Expose to Internet

   For local development, use [ngrok](https://ngrok.com):
   ```bash
   ngrok http 8000
   ```

   For production, use a reverse proxy (nginx, Caddy) with your domain.

---

### Option 5: Manual Deployment

Deploy to any Linux server with Python 3.12+.

#### Steps

1. Provision Server
   - Ubuntu 22.04+ recommended
   - At least 512MB RAM, 10GB disk

2. Install Dependencies
   ```bash
   sudo apt update
   sudo apt install -y python3.12 python3.12-venv postgresql-15 nginx
   ```

3. Set Up PostgreSQL
   ```bash
   # Create database and user
   sudo -u postgres psql
   CREATE DATABASE ashby_feedback;
   CREATE USER feedback_app WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE ashby_feedback TO feedback_app;
   \q

   # Apply schema
   psql postgresql://feedback_app:secure_password@localhost/ashby_feedback -f database/schema.sql
   ```

4. Clone and Configure
   ```bash
   cd /opt
   git clone https://github.com/maxames/ashby-slack-feedback.git
   cd ashby-slack-feedback

   python3.12 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   cp .env.example .env
   nano .env  # Configure environment variables
   ```

5. Create Systemd Service
   ```bash
   sudo nano /etc/systemd/system/ashby-feedback.service
   ```

   ```ini
   [Unit]
   Description=Ashby Slack Feedback
   After=network.target postgresql.service

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/opt/ashby-slack-feedback
   Environment="PATH=/opt/ashby-slack-feedback/venv/bin"
   EnvironmentFile=/opt/ashby-slack-feedback/.env
   ExecStart=/opt/ashby-slack-feedback/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

6. Start Service
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ashby-feedback
   sudo systemctl start ashby-feedback
   sudo systemctl status ashby-feedback
   ```

7. Configure Nginx Reverse Proxy
   ```bash
   sudo nano /etc/nginx/sites-available/ashby-feedback
   ```

   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/ashby-feedback /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

8. Set Up SSL with Let's Encrypt
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

---

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Ashby API
ASHBY_API_KEY=your_ashby_api_key_here
ASHBY_WEBHOOK_SECRET=your_webhook_secret_here

# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your_signing_secret

# Application
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Generating Secrets

For `ASHBY_WEBHOOK_SECRET`, generate a strong random string:

```bash
# Using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Using OpenSSL
openssl rand -base64 32
```

Use this same secret in both your `.env` file and Ashby webhook configuration.

---

## Slack App Setup

### 1. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From an app manifest**
4. Select your workspace
5. Paste the contents of `slack-manifest.yml` (see below)
6. Click **Create**

### 2. Install to Workspace

1. Go to **OAuth & Permissions**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy **Bot User OAuth Token** (starts with `xoxb-`)
5. Save to `SLACK_BOT_TOKEN` environment variable

### 3. Get Signing Secret

1. Go to **Basic Information**
2. Under **App Credentials**, find **Signing Secret**
3. Click **Show** and copy the value
4. Save to `SLACK_SIGNING_SECRET` environment variable

### 4. Configure Interactivity

1. Go to **Interactivity & Shortcuts**
2. Enable **Interactivity**
3. Set **Request URL** to: `https://your-domain.com/slack/interactions`
4. Click **Save Changes**

### 5. Verify Scopes

Ensure your app has these scopes under **OAuth & Permissions**:

- `chat:write` - Send messages to users
- `users:read` - Read user information
- `users:read.email` - Read user email addresses
- `files.remote:write` - Register remote files (for resume links)

---

## Ashby Webhook Configuration

### 1. Create Webhook

1. Log in to Ashby
2. Go to **Settings → Developer → Webhooks**
3. Click **Create Webhook**

### 2. Configure Webhook

| Field | Value |
|-------|-------|
| **Name** | Interview Feedback Reminder |
| **URL** | `https://your-domain.com/webhooks/ashby` |
| **Events** | Select `interviewSchedule.updated` |
| **Secret** | Use your `ASHBY_WEBHOOK_SECRET` value |

### 3. Test Webhook

1. Click **Test Webhook** button
2. Should return `200 OK` with `{"status":"ok","message":"pong"}`
3. Check your application logs for `webhook_ping_received`

### 4. Save and Activate

1. Click **Save**
2. Ensure webhook is **Active** (toggle on)

---

## Post-Deployment Verification

### 1. Check Health Endpoint

```bash
curl https://your-domain.com/health
```

Should return:
```json
{
  "status": "healthy",
  "database": "connected",
  "pool": { "size": 10, "free": 8, "in_use": 2 }
}
```

### 2. Verify Logs

Check application logs for successful startup:
```
application_starting
database_connected
scheduler_setup
running_initial_syncs
sync_feedback_forms_complete
sync_interviews_complete
sync_slack_users_complete
application_ready
```

### 3. Check Database

Connect to database and verify tables exist:
```bash
psql $DATABASE_URL

\dt  -- List tables
SELECT COUNT(*) FROM slack_users;  -- Should show Slack users
SELECT COUNT(*) FROM feedback_form_definitions;  -- Should show forms
```

### 4. Test Webhook

Send a test webhook from Ashby (see above) and verify:
- Returns 200 OK
- Logs show `webhook_ping_received`
- No errors in logs

### 5. Monitor Scheduler

Watch logs for scheduled jobs (every 5 minutes):
```
reminder_check_started
reminders_checked (count=X)
```

---

## Monitoring and Maintenance

### Logs

**Render/Railway/Fly.io**: Use platform dashboard to view logs

**Docker Compose**:
```bash
docker-compose logs -f app
```

**Manual Deployment**:
```bash
sudo journalctl -u ashby-feedback -f
```

### Health Checks

Set up uptime monitoring with:
- [UptimeRobot](https://uptimerobot.com) (free)
- [Pingdom](https://www.pingdom.com)
- [StatusCake](https://www.statuscake.com)

Monitor: `GET https://your-domain.com/health` every 5 minutes

### Database Backups

**Render**: Automatic daily backups on paid plans

**Railway**: Manual backups:
```bash
railway run pg_dump $DATABASE_URL > backup.sql
```

**Fly.io**: Automatic snapshots on Postgres clusters

**Manual**:
```bash
# Daily backup cron job
0 2 * * * pg_dump $DATABASE_URL | gzip > /backups/ashby-$(date +\%Y\%m\%d).sql.gz
```

### Updates

**Pull Latest Code**:
```bash
git pull origin main
pip install -r requirements.txt
```

**Restart Application**:
- Render/Railway/Fly.io: Automatic on git push
- Docker: `docker-compose restart app`
- Manual: `sudo systemctl restart ashby-feedback`

### Database Migrations

**Current approach**: Manual SQL changes + tracking table.

When you need to change the schema:

1. Apply the change:
   ```bash
   psql $DATABASE_URL -c "ALTER TABLE interviews ADD COLUMN archived_at TIMESTAMPTZ;"
   ```

2. Record it:
   ```bash
   psql $DATABASE_URL -c "INSERT INTO schema_migrations (version, name, description)
   VALUES (2, 'add_archived_at', 'Track archived interviews');"
   ```

3. Update `database/schema.sql` so fresh installs include it

4. Commit to git with clear migration notes

See `database/README.md` for full migration workflow.

**Future**: Add Alembic if the project gets multiple contributors or frequent schema changes.

---

## Troubleshooting

### Application Won't Start

**Check logs for**:
- Database connection errors → Verify `DATABASE_URL`
- Import errors → Ensure all dependencies installed
- Config errors → Verify all required env vars are set

**Solution**:
```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1"

# Test Python imports
python -c "from app.main import app; print('OK')"

# Verify environment variables
env | grep -E 'DATABASE_URL|ASHBY|SLACK'
```

### Webhooks Not Receiving

**Symptoms**: Ashby webhook shows errors or timeouts

**Check**:
1. DNS Resolution: `nslookup your-domain.com`
2. Port Open: `curl https://your-domain.com/health`
3. Firewall Rules: Ensure port 80/443 open
4. Rate Limiting: Check if IP is blocked

**Ashby Requirements**:
- Must respond within 10 seconds
- Must return 2xx status code
- Must be HTTPS in production

### Reminders Not Sending

**Symptoms**: Logs show no reminders being sent

**Check**:
1. Scheduler Running: Look for `reminder_check_started` in logs every 5 min
2. Slack Users Synced: `SELECT COUNT(*) FROM slack_users`
3. Interviews Exist: `SELECT COUNT(*) FROM interview_events WHERE start_time > NOW()`
4. Time Window: Reminders only send 4-20 minutes before interview

**Manual Trigger**:
```bash
curl -X POST https://your-domain.com/admin/sync-slack-users
```

### Database Connection Pool Exhausted

**Symptoms**: `asyncpg.exceptions.TooManyConnectionsError`

**Solutions**:
1. Check for connection leaks: Look for long-running queries
2. Restart application: Clears stuck connections

### High Memory Usage

**Symptoms**: Application crashes or restarts frequently

**Solutions**:
1. Increase instance size: Render/Railway/Fly.io dashboard
2. Check for leaks: Look for unbounded data growth in logs

---

## Security Best Practices

### Environment Variables

- Never commit `.env` files to git
- Use your platform's secret management (Render secrets, Railway variables, etc.)
- Rotate secrets if you think they've been compromised

### Database

- Use strong passwords (let your platform generate them)
- Enable SSL connections (most platforms do this by default)
- Set up automated backups (daily for production)

### Application

- Keep dependencies updated: `pip list --outdated`
- Use HTTPS only (Render/Railway/Fly.io handle this automatically)
- Set `LOG_LEVEL=INFO` in production (not DEBUG)

### Slack & Ashby

- Regenerate tokens if compromised
- Limit bot permissions to only required scopes
- Don't log or display API keys

---

## Performance Tuning

### Database Indexes

The schema includes optimized indexes. If you experience slow queries:

```sql
-- Check query performance
EXPLAIN ANALYZE SELECT * FROM interview_events WHERE start_time > NOW();

-- Add custom indexes if needed
CREATE INDEX IF NOT EXISTS idx_custom ON table(column);
```

### Connection Pool

Adjust based on your traffic:

```python
# core/database.py
await asyncpg.create_pool(
    min_size=2,      # Increase for high traffic
    max_size=10,     # Increase if pool exhaustion occurs
    max_queries=50000,
    max_inactive_connection_lifetime=300
)
```

### Scheduler Frequency

Adjust job intervals in `services/scheduler.py`:

```python
# Reminders: Every 5 minutes (default)
scheduler.add_job(send_due_reminders, 'interval', minutes=5)

# For busier systems, consider 3 minutes
# scheduler.add_job(send_due_reminders, 'interval', minutes=3)
```

---

## Scaling Considerations

### Do You Need to Scale?

Probably not. A single instance can comfortably handle:
- 100 webhooks/minute (rate limited)
- 1000+ interviews/day
- Hundreds of concurrent Slack messages
- 50+ interviewers

**When to consider scaling**: If you're regularly hitting rate limits or your instance is OOMing (which would be impressive).

### If You Actually Need to Scale

The API is stateless, but **APScheduler runs in-process**. This creates a problem for horizontal scaling.

**If you need multiple instances:**

1. Option 1 - Split Services (simplest)
   - One "worker" instance with scheduler enabled
   - Multiple "web" instances with scheduler disabled
   - Route all traffic to web instances

2. Option 2 - Distributed Lock
   - Add Redis + distributed lock library
   - All instances run scheduler, but lock prevents duplicates
   - More complex, only worth it at very high scale

3. Option 3 - External Cron
   - Remove APScheduler entirely
   - Run reminder checks via cron job calling admin endpoints
   - Most production-ready approach

**For 99% of companies using Ashby**, one instance is plenty.

### Database Performance

For typical usage (< 1000 interviews/day):
- Default connection pool (10 connections) is fine
- Indexes are already optimized
- No read replicas needed
- No partitioning needed

If you're storing 100k+ interviews, consider:
- Archiving old data (> 6 months)
- Adding `VACUUM ANALYZE` to cron
- Bumping instance size before adding complexity

---

## Support and Resources

- **Documentation**: [docs/](docs/)
- **GitHub Issues**: [github.com/maxames/ashby-slack-feedback/issues](https://github.com/maxames/ashby-slack-feedback/issues)
- **Ashby API Docs**: [developers.ashbyhq.com](https://developers.ashbyhq.com)
- **Slack API Docs**: [api.slack.com](https://api.slack.com)

For deployment-specific support:
- **Render**: [render.com/docs](https://render.com/docs)
- **Railway**: [docs.railway.app](https://docs.railway.app)
- **Fly.io**: [fly.io/docs](https://fly.io/docs)

