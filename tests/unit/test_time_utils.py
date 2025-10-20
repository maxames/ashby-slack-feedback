"""Unit tests for time utilities."""

from datetime import UTC, datetime, timedelta

import pytest

from app.utils.time import (
    ensure_utc,
    format_slack_timestamp,
    is_stale,
    parse_ashby_timestamp,
)


class TestParseAshbyTimestamp:
    """Tests for parse_ashby_timestamp function."""

    def test_parse_valid_timestamp_with_z(self):
        """Test parsing ISO 8601 timestamp with Z suffix."""
        ts_string = "2024-10-19T14:30:00.000Z"
        result = parse_ashby_timestamp(ts_string)

        assert result is not None
        assert result == datetime(2024, 10, 19, 14, 30, tzinfo=UTC)
        assert result.tzinfo is not None

    def test_parse_valid_timestamp_with_offset(self):
        """Test parsing ISO 8601 timestamp with +00:00 offset."""
        ts_string = "2024-10-19T14:30:00.000+00:00"
        result = parse_ashby_timestamp(ts_string)

        assert result is not None
        assert result == datetime(2024, 10, 19, 14, 30, tzinfo=UTC)

    def test_parse_none_returns_none(self):
        """Test that None input returns None."""
        assert parse_ashby_timestamp(None) is None

    def test_parse_empty_string_returns_none(self):
        """Test that empty string returns None."""
        assert parse_ashby_timestamp("") is None

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_ashby_timestamp("not a timestamp")


class TestEnsureUtc:
    """Tests for ensure_utc function."""

    def test_naive_datetime_gets_utc(self):
        """Test that naive datetime gets UTC timezone."""
        naive_dt = datetime(2024, 10, 19, 14, 30)
        result = ensure_utc(naive_dt)

        assert result.tzinfo is not None
        assert result.tzinfo == UTC
        assert result == datetime(2024, 10, 19, 14, 30, tzinfo=UTC)

    def test_aware_datetime_converted_to_utc(self):
        """Test that timezone-aware datetime is converted to UTC."""
        # Create datetime in different timezone (e.g., EST = UTC-5)
        from datetime import timezone

        est = timezone(timedelta(hours=-5))
        est_dt = datetime(2024, 10, 19, 9, 30, tzinfo=est)

        result = ensure_utc(est_dt)

        assert result.tzinfo == UTC
        assert result == datetime(2024, 10, 19, 14, 30, tzinfo=UTC)

    def test_utc_datetime_unchanged(self):
        """Test that datetime already in UTC is unchanged."""
        utc_dt = datetime(2024, 10, 19, 14, 30, tzinfo=UTC)
        result = ensure_utc(utc_dt)

        assert result == utc_dt
        assert result.tzinfo == UTC


class TestFormatSlackTimestamp:
    """Tests for format_slack_timestamp function."""

    def test_format_utc_datetime(self):
        """Test formatting UTC datetime for Slack."""
        dt = datetime(2024, 10, 19, 14, 30, tzinfo=UTC)
        result = format_slack_timestamp(dt)

        # Should return <!date^{unix_timestamp}^{time}|{fallback}>
        assert result.startswith("<!date^")
        assert "^{time}|" in result
        assert result.endswith(">")

        # Extract unix timestamp
        unix_ts = int(result.split("^")[1])
        expected_unix = int(dt.timestamp())
        assert unix_ts == expected_unix

    def test_format_naive_datetime_assumes_utc(self):
        """Test that naive datetime is assumed to be UTC."""
        naive_dt = datetime(2024, 10, 19, 14, 30)
        result = format_slack_timestamp(naive_dt)

        # Should still work (treated as UTC)
        assert result.startswith("<!date^")
        assert "^{time}|" in result


class TestIsStale:
    """Tests for is_stale function."""

    def test_old_datetime_is_stale(self):
        """Test that datetime older than threshold is stale."""
        old_dt = datetime.now(UTC) - timedelta(hours=25)
        assert is_stale(old_dt, hours=24) is True

    def test_recent_datetime_is_not_stale(self):
        """Test that datetime within threshold is not stale."""
        recent_dt = datetime.now(UTC) - timedelta(hours=23)
        assert is_stale(recent_dt, hours=24) is False

    def test_exact_threshold_is_stale(self):
        """Test that datetime exactly at threshold is considered stale."""
        exact_dt = datetime.now(UTC) - timedelta(hours=24)
        # Due to processing time, this might be slightly past 24 hours
        assert is_stale(exact_dt, hours=24) is True

    def test_custom_threshold(self):
        """Test using custom hour threshold."""
        dt_10_hours_ago = datetime.now(UTC) - timedelta(hours=10)

        assert is_stale(dt_10_hours_ago, hours=8) is True
        assert is_stale(dt_10_hours_ago, hours=12) is False

    def test_naive_datetime_handled(self):
        """Test that naive datetime is handled (assumed UTC)."""
        naive_old = datetime.now() - timedelta(hours=25)
        # Should not raise error, assumes UTC
        result = is_stale(naive_old, hours=24)
        assert isinstance(result, bool)
