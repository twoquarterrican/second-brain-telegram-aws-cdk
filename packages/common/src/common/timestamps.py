"""Timestamp formatting utilities for event sourcing."""

from datetime import datetime, timezone


def format_iso8601_zulu(dt: datetime | None = None) -> str:
    """
    Format a datetime as ISO8601 with Zulu (UTC) timezone, without offset.

    Args:
        dt: datetime to format. If None, uses current UTC time.

    Returns:
        ISO8601 formatted string in Zulu format, e.g. "2025-01-18T13:45:30Z"
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to UTC if needed
    dt_utc = dt.astimezone(timezone.utc)

    # Format using strftime for future-proof compatibility
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
