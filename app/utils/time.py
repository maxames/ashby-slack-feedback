"""Time utilities for timezone-aware timestamp handling."""

from datetime import UTC, datetime, timedelta


def parse_ashby_timestamp(ts_string: str | None) -> datetime | None:
    """
    Parse Ashby ISO 8601 timestamp to timezone-aware datetime.
    Returns None if string is None or invalid.

    Example input: "2024-10-19T14:30:00.000Z"
    Example output: datetime(2024, 10, 19, 14, 30, tzinfo=UTC)
    """
    if not ts_string:
        return None
    dt = datetime.fromisoformat(ts_string.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is timezone-aware in UTC.
    If naive, assume UTC. If aware, convert to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_slack_timestamp(dt: datetime) -> str:
    """
    Format datetime for Slack using Unix timestamp.
    Slack will automatically show time in user's local timezone.

    Example input: datetime(2024, 10, 19, 14, 30, tzinfo=UTC)
    Example output: "<!date^1729347000^{time}|2:30 PM UTC>"

    Format reference: https://api.slack.com/reference/surfaces/formatting#date-formatting
    """
    dt_utc = ensure_utc(dt)
    unix_ts = int(dt_utc.timestamp())
    fallback = dt_utc.strftime("%I:%M %p %Z")
    return f"<!date^{unix_ts}^{{time}}|{fallback}>"


def is_stale(dt: datetime, hours: int = 24) -> bool:
    """
    Check if datetime is older than specified hours.
    Always compares in UTC.
    """
    return ensure_utc(dt) < datetime.now(UTC) - timedelta(hours=hours)
