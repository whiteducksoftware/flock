"""Tests for time formatting utilities.

Validates human-readable time span formatting for various durations.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from flock.utils.time_utils import format_time_span


class TestFormatTimeSpan:
    """Test time span formatting with various durations."""

    def test_format_time_span_none_earliest(self):
        """Should return 'empty' when earliest is None."""
        result = format_time_span(None, datetime.now())
        assert result == "empty"

    def test_format_time_span_none_latest(self):
        """Should return 'empty' when latest is None."""
        result = format_time_span(datetime.now(), None)
        assert result == "empty"

    def test_format_time_span_both_none(self):
        """Should return 'empty' when both are None."""
        result = format_time_span(None, None)
        assert result == "empty"

    def test_format_time_span_days(self):
        """Should format spans >= 2 days as 'X days'."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(days=3, hours=5)
        result = format_time_span(now, later)
        assert result == "3 days"

    def test_format_time_span_exactly_two_days(self):
        """Should format exactly 2 days as '2 days'."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(days=2)
        result = format_time_span(now, later)
        assert result == "2 days"

    def test_format_time_span_hours(self):
        """Should format spans >= 1 hour as 'X.Y hours'."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(hours=2, minutes=30)
        result = format_time_span(now, later)
        assert result == "2.5 hours"

    def test_format_time_span_one_hour(self):
        """Should format exactly 1 hour as '1.0 hours'."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(hours=1)
        result = format_time_span(now, later)
        assert result == "1.0 hours"

    def test_format_time_span_minutes(self):
        """Should format spans < 1 hour as 'X minutes'."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(minutes=45)
        result = format_time_span(now, later)
        assert result == "45 minutes"

    def test_format_time_span_one_minute(self):
        """Should format very short spans as '1 minutes' (minimum)."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(seconds=30)
        result = format_time_span(now, later)
        assert result == "1 minutes"

    def test_format_time_span_zero(self):
        """Should return 'moments' for zero span."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        result = format_time_span(now, now)
        assert result == "moments"

    def test_format_time_span_large_days(self):
        """Should handle large day spans correctly."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(days=365)
        result = format_time_span(now, later)
        assert result == "365 days"

    def test_format_time_span_fractional_hours(self):
        """Should format fractional hours with one decimal place."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        later = now + timedelta(hours=3, minutes=20)
        result = format_time_span(now, later)
        # 3 hours + 20 minutes = 3.333... hours
        assert result.startswith("3.3")
        assert result.endswith("hours")
