from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamps are used everywhere so SQLite and PostgreSQL behave the same."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
