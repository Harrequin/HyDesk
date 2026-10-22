"""Display formatting helpers shared across views."""

from __future__ import annotations

from datetime import datetime, timezone


def fmt_datetime(value: datetime | None) -> str:
    """Format a timestamp for display in local time.

    Stored timestamps are UTC (ISO-8601). Naive values are assumed UTC.
    """
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def fmt_text(value: str | None) -> str:
    """Display a nullable string, using an em dash when empty."""
    return value if value else "—"
