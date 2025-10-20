# API Reference

## Base URL

```
http://localhost:8000  # Development
https://your-domain.com  # Production
```

## Authentication

### Ashby Webhooks

All Ashby webhook requests include an HMAC-SHA256 signature for verification:

```
x-ashby-signature: sha256=<hex_digest>
```

The signature is computed using:
- Secret: `ASHBY_WEBHOOK_SECRET` environment variable
- Body: Raw request body (bytes)
- Algorithm: HMAC-SHA256

### Slack Interactions

Slack requests are verified using the Slack SDK with the `SLACK_SIGNING_SECRET` environment variable.

### Admin Endpoints

**Note**: Currently no authentication. Should be protected behind firewall or add API key authentication in production.

---

## Endpoints

### Health Check

**`GET /health`**

Check application health and database connectivity.

#### Response

**200 OK** - Application is healthy

```json
{
  "status": "healthy",
  "database": "connected",
  "pool": {
    "size": 10,
    "free": 8,
    "in_use": 2
  }
}
```

**503 Service Unavailable** - Database unavailable

```json
{
  "detail": "Database unavailable"
}
```

---

### Root

**`GET /`**

Root endpoint returning application name.

#### Response

**200 OK**

```json
{
  "message": "Ashby Slack Feedback Application"
}
```

---

## Ashby Webhooks

### Handle Webhook

**`POST /webhooks/ashby`**

Receive and process Ashby webhook events.

**Rate Limit**: 100 requests/minute per IP

#### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `x-ashby-signature` | Yes* | HMAC-SHA256 signature (`sha256=<hex>`) |
| `Content-Type` | Yes | `application/json` |

*Not required for ping/test webhooks

#### Request Body

**Ping Webhook** (setup verification):

```json
{
  "action": "ping",
  "type": "ping"
}
```

**Interview Schedule Update**:

```json
{
  "action": "interviewSchedule.updated",
  "webhookEvent": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  },
  "interviewSchedule": {
    "id": "schedule-uuid",
    "applicationId": "app-uuid",
    "interviewStageId": "stage-uuid",
    "status": "Scheduled",
    "candidateId": "candidate-id",
    "updatedAt": "2024-10-19T14:30:00.000Z",
    "interviewEvents": [
      {
        "id": "event-uuid",
        "interviewId": "interview-uuid",
        "startTime": "2024-10-19T15:00:00.000Z",
        "endTime": "2024-10-19T15:30:00.000Z",
        "feedbackLink": "https://ashbyhq.com/feedback/...",
        "meetingLink": "https://zoom.us/j/...",
        "location": "Zoom",
        "hasSubmittedFeedback": false,
        "createdAt": "2024-10-19T14:00:00.000Z",
        "updatedAt": "2024-10-19T14:30:00.000Z",
        "interviewers": [
          {
            "id": "interviewer-uuid",
            "firstName": "Jane",
            "lastName": "Doe",
            "email": "jane@company.com",
            "globalRole": "Interviewer",
            "isEnabled": true
          }
        ]
      }
    ]
  }
}
```

#### Responses

**200 OK** - Ping webhook acknowledged

```json
{
  "status": "ok",
  "message": "pong"
}
```

**204 No Content** - Webhook processed successfully

**400 Bad Request** - Invalid JSON or malformed payload

```json
{
  "detail": "Invalid JSON"
}
```

**401 Unauthorized** - Invalid or missing signature

```json
{
  "detail": "Invalid webhook signature"
}
```

**429 Too Many Requests** - Rate limit exceeded

```json
{
  "error": "Rate limit exceeded: 100 per 1 minute"
}
```

---

## Slack Interactions

### Handle Interaction

**`POST /slack/interactions`**

Handle Slack interactive component events (modal submissions, button clicks, view closures).

#### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `x-slack-signature` | Yes | Slack request signature |
| `x-slack-request-timestamp` | Yes | Request timestamp (prevents replays) |
| `Content-Type` | Yes | `application/x-www-form-urlencoded` |

#### Request Body

Slack sends form-encoded payload with a `payload` field containing JSON.

**Modal Submission**:

```json
{
  "type": "view_submission",
  "user": {
    "id": "U123ABC456",
    "name": "jane.doe"
  },
  "view": {
    "id": "V123ABC456",
    "type": "modal",
    "private_metadata": "{\"event_id\":\"event-uuid\",\"interviewer_id\":\"interviewer-uuid\",\"form_definition_id\":\"form-uuid\"}",
    "state": {
      "values": {
        "block-id": {
          "action-id": {
            "type": "plain_text_input",
            "value": "User's response"
          }
        }
      }
    }
  }
}
```

**View Closed** (user dismisses modal):

> **Note**: view_closed events do NOT include state.values, so drafts cannot be
> saved on modal close. Instead, we use dispatch_action_config on text inputs
> to save drafts when users press Enter.

```json
{
  "type": "view_closed",
  "user": {
    "id": "U123ABC456"
  },
  "view": {
    "private_metadata": "{\"event_id\":\"event-uuid\",\"interviewer_id\":\"interviewer-uuid\"}"
    // Note: state.values is NOT included in view_closed events
  }
}
```

**Dispatch Action** (Enter key pressed in text field):

```json
{
  "type": "block_actions",
  "view": {
    "private_metadata": "{\"event_id\":\"event-uuid\",\"interviewer_id\":\"interviewer-uuid\"}",
    "state": {
      "values": { /* Current form state - this IS included! */ }
    }
  },
  "actions": [{
    "action_id": "field_overall_notes",
    "type": "plain_text_input",
    "value": "User's current text"
  }]
}
```

**Open Feedback Modal** (block action):

```json
{
  "type": "block_actions",
  "user": {
    "id": "U123ABC456"
  },
  "actions": [
    {
      "action_id": "open_feedback_modal",
      "block_id": "actions_block",
      "value": "event-uuid"
    }
  ]
}
```

#### Responses

**200 OK** - Interaction processed

For modal submissions, returns acknowledgment or validation errors:

```json
{
  "response_action": "errors",
  "errors": {
    "block-id": "This field is required"
  }
}
```

For button clicks, returns empty body to prevent timeout.

---

## Admin Endpoints

### Sync Feedback Forms

**`POST /admin/sync-forms`**

Manually trigger feedback form synchronization from Ashby.

Useful after creating or updating feedback forms in Ashby.

#### Response

**200 OK**

```json
{
  "status": "completed",
  "message": "Feedback forms synced"
}
```

---

### Sync Slack Users

**`POST /admin/sync-slack-users`**

Manually trigger Slack user synchronization.

Useful after new employees join or email addresses change.

#### Response

**200 OK**

```json
{
  "status": "completed",
  "message": "Slack users synced"
}
```

---

### Get Statistics

**`GET /admin/stats`**

Retrieve application statistics.

#### Response

**200 OK**

```json
{
  "interviews": {
    "scheduled": 42,
    "upcoming_24h": 8,
    "completed_7d": 156
  },
  "reminders": {
    "sent_today": 23,
    "pending": 5,
    "submission_rate_7d": 0.89
  },
  "forms": {
    "total": 3,
    "active": 2
  },
  "slack_users": {
    "total": 45,
    "active": 43
  }
}
```

---

## Error Handling

### Standard Error Format

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Request succeeded |
| 204 | No Content | Webhook processed successfully |
| 400 | Bad Request | Invalid JSON, malformed payload |
| 401 | Unauthorized | Invalid signature |
| 403 | Forbidden | Missing permissions |
| 404 | Not Found | Endpoint doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected application error |
| 503 | Service Unavailable | Database unavailable |

---

## Webhook Setup

### Ashby Configuration

1. Go to **Settings → Webhooks** in Ashby
2. Click **Create Webhook**
3. Set URL: `https://your-domain.com/webhooks/ashby`
4. Select event: **Interview Schedule Updated**
5. Set secret: Use your `ASHBY_WEBHOOK_SECRET` value
6. Click **Test Webhook** (should return 200 OK with "pong")
7. Save

### Slack App Configuration

1. Go to **api.slack.com/apps**
2. Create new app or select existing
3. Under **Interactivity & Shortcuts**:
   - Enable Interactivity
   - Request URL: `https://your-domain.com/slack/interactions`
4. Under **OAuth & Permissions**:
   - Add scopes: `chat:write`, `users:read`, `users:read.email`, `files.remote:write`
   - Install to workspace
   - Copy **Bot User OAuth Token** to `SLACK_BOT_TOKEN`
5. Under **Basic Information**:
   - Copy **Signing Secret** to `SLACK_SIGNING_SECRET`

---

## Rate Limiting

### Current Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/webhooks/ashby` | 100 requests | 1 minute |
| All other endpoints | No limit | - |

### Rate Limit Response

**429 Too Many Requests**

```json
{
  "error": "Rate limit exceeded: 100 per 1 minute"
}
```

**Headers**:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets
- `Retry-After`: Seconds to wait before retrying

---

## Testing

### Interactive Documentation

FastAPI provides auto-generated interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Example: Test Webhook Locally

```bash
# Compute signature
SECRET="your_webhook_secret"
BODY='{"action":"ping"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

# Send request
curl -X POST http://localhost:8000/webhooks/ashby \
  -H "Content-Type: application/json" \
  -H "x-ashby-signature: sha256=$SIGNATURE" \
  -d "$BODY"
```

### Example: Simulate Interview Webhook

See `tests/fixtures/sample_payloads.py` for complete webhook payload examples.

```python
import httpx
import hmac
import hashlib

secret = "your_webhook_secret"
payload = {
    "action": "interviewSchedule.updated",
    "interviewSchedule": { /* ... */ }
}

body = json.dumps(payload).encode()
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

response = httpx.post(
    "http://localhost:8000/webhooks/ashby",
    content=body,
    headers={
        "Content-Type": "application/json",
        "x-ashby-signature": f"sha256={signature}"
    }
)
```

---

## Versioning

Current version: **1.0.0**

The API currently does not use versioning. Breaking changes will be communicated via:
- GitHub releases
- CHANGELOG.md updates
- Migration guides in documentation

Future versions may use URL versioning (`/v2/webhooks/ashby`) or header versioning.

