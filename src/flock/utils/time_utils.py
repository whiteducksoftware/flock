"""Time formatting utilities.

Provides human-readable time span formatting for date ranges.
"""

from __future__ import annotations

from datetime import datetime


def format_time_span(earliest: datetime | None, latest: datetime | None) -> str:
    """
    Format time span between two datetimes as human-readable string.

    Args:
        earliest: Start datetime
        latest: End datetime

    Returns:
        Human-readable span description:
        - "X days" for spans >= 2 days
        - "X.Y hours" for spans >= 1 hour
        - "X minutes" for spans > 0
        - "moments" for zero span
        - "empty" if no dates provided

    Examples:
        >>> from datetime import datetime, timedelta
        >>> now = datetime.now()
        >>> format_time_span(now, now + timedelta(days=3))
        "3 days"
        >>> format_time_span(now, now + timedelta(hours=2))
        "2.0 hours"
        >>> format_time_span(now, now + timedelta(minutes=45))
        "45 minutes"
    """
    if not earliest or not latest:
        return "empty"

    span = latest - earliest

    if span.days >= 2:
        return f"{span.days} days"

    if span.total_seconds() >= 3600:
        hours = span.total_seconds() / 3600
        return f"{hours:.1f} hours"

    if span.total_seconds() > 0:
        minutes = max(1, int(span.total_seconds() / 60))
        return f"{minutes} minutes"

    return "moments"
