"""Database-neutral representation for copied authority timestamps.

Canonical authority documents retain timezone-aware UTC instants. The Phase 4
SQL schema uses timezone-naive ``DateTime`` columns for copied lookup values, so
writers store the corresponding UTC wall-clock value and loaders accept only
that exact naive representation.
"""
from __future__ import annotations

from datetime import datetime, timezone


class SQLTimestampError(ValueError):
    """A copied SQL timestamp is absent, ambiguous, or malformed."""


def to_sql_utc_naive(
    value: datetime | None,
    name: str,
    *,
    nullable: bool = False,
) -> datetime | None:
    """Convert one canonical aware instant to the copied SQL representation."""
    if value is None:
        if nullable:
            return None
        raise SQLTimestampError(f"{name} must be a timezone-aware datetime")
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SQLTimestampError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def require_sql_utc_naive(
    value: datetime | None,
    name: str,
    *,
    nullable: bool = False,
) -> datetime | None:
    """Validate a loaded copied value without reinterpreting its wall time."""
    if value is None:
        if nullable:
            return None
        raise SQLTimestampError(f"{name} must be a UTC-naive SQL datetime")
    if not isinstance(value, datetime) or value.tzinfo is not None or value.utcoffset() is not None:
        raise SQLTimestampError(f"{name} must be a UTC-naive SQL datetime")
    return value


__all__ = ["SQLTimestampError", "require_sql_utc_naive", "to_sql_utc_naive"]
