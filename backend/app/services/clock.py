from datetime import UTC, datetime


def as_aware(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime.

    SQLite has no timezone type, so values written as aware come back naive.
    Anything that compares a stored datetime in Python must pass it through here
    first, or the comparison raises on the naive/aware mismatch.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)
