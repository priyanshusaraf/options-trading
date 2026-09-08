"""Explicit user-declared full-session metadata; never an exchange-hours guess."""
from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo


SCHEMA = "user-declared-daily-sessions/1"
FIELDS = ("SESSION_ID", "SESSION_OPEN_AT", "SESSION_CLOSE_AT")
MAX_BYTES = 1024 * 1024


class ImportedSessionsRefused(ValueError):
    code = "CSV_SESSION_METADATA_REFUSED"

    def __init__(self):
        super().__init__("Session metadata must identify every complete daily session and its source.")


def _require(condition):
    if not condition:
        raise ImportedSessionsRefused()


def _time(value):
    _require(isinstance(value, str))
    result = dt.datetime.fromisoformat(value)
    _require(result.tzinfo is not None and result.microsecond == 0)
    return result.astimezone(dt.timezone.utc)


def _row(row, label, previous_close):
    _require(type(row) is dict and set(row) == {
        "date_label", "session_id", "session_open_at", "session_close_at"})
    _require(row["date_label"] == label.date().isoformat())
    identifier = row["session_id"]
    _require(isinstance(identifier, str) and 0 < len(identifier) <= 128)
    opening, closing = _time(row["session_open_at"]), _time(row["session_close_at"])
    _require(opening < closing <= label + dt.timedelta(days=1))
    _require(label <= closing)
    _require(previous_close is None or opening > previous_close)
    return closing


def _document(payload, timezone):
    document = json.loads(payload)
    _require(type(document) is dict and set(document) == {
        "schema", "provenance", "source", "timezone", "complete_full_sessions", "rows"})
    _require(document["schema"] == SCHEMA and document["provenance"] == "USER_DECLARED"
             and document["complete_full_sessions"] is True and document["timezone"] == timezone)
    _require(isinstance(document["source"], str) and 0 < len(document["source"].strip()) <= 2048)
    return document


def validate_sessions(payload, *, labels, timezone):
    """Validate complete explicit rows against the original CSV date labels."""
    try:
        _require(isinstance(payload, bytes) and 0 < len(payload) <= MAX_BYTES)
        document = _document(payload, timezone)
        rows = document["rows"]
        _require(type(rows) is list and 0 < len(rows) == len(labels) <= 2000)
        zone, previous_close, identifiers = ZoneInfo(timezone), None, set()
        for row, label in zip(rows, labels, strict=True):
            local = label.astimezone(zone)
            _require(local.time() == dt.time.min)
            previous_close = _row(row, local, previous_close)
            _require(row["session_id"] not in identifiers)
            identifiers.add(row["session_id"])
        return document
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ImportedSessionsRefused() from None
