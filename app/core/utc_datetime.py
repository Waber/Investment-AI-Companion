"""Timezone-aware UTC values for ``DateTime(timezone=True)`` columns.

SQLite stores a datetime as text and keeps the wall clock, not the
instant. ``2025-12-31T02:00:00+02:00`` and ``2025-12-31T00:00:00Z`` are
the same moment, but SQLite would save ``02:00`` and ``00:00``. This
type converts to UTC before the database sees the value, then attaches
UTC when the value is read back.

PostgreSQL ``timestamptz`` already stores the instant. The bind value
stays timezone-aware so the driver does not treat it as session-local
time. That is the "no behavior change" path for PostgreSQL.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as an aware UTC datetime.

    A naive value is interpreted as UTC. The API already accepts
    offset-less strings such as ``2024-12-31T00:00:00``. An aware value
    keeps the same instant; only the clock changes to UTC.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Normalize a timezone-aware datetime column to UTC.

    ``cache_ok`` must be True. Otherwise SQLAlchemy warns that it cannot
    cache statements that use this type.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        utc_value = as_utc(value)
        # SQLite's datetime binder uses the wall-clock fields and ignores
        # tzinfo. Hand it the UTC clock with the zone removed so 02:00+02
        # and 00:00Z are stored as the same text.
        if dialect.name == "sqlite":
            return utc_value.replace(tzinfo=None)
        return utc_value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # SQLite returns a naive clock. We stored UTC, so the zone is UTC.
        # An aware value (PostgreSQL) is converted without moving the instant.
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
