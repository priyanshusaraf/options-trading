"""Explicit dated session declarations and completed bar clocks.

SOURCE_DECLARED records a source declaration, never observed exchange truth.
These pure values confer no provider, execution, or shortened-bar grant.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address
from app.market_truth.identity import MarketTruthError

_FIELDS = {"schema", "instrument_address", "venue_code", "timezone", "provenance",
           "source_reference", "recorded_at", "rows"}
_ROW_FIELDS = {"date", "status", "opens_at", "closes_at"}
_UTC_CLOCK = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z")


@dataclass(frozen=True, slots=True)
class DatedSession:
    local_date: str
    opens_at: dt.datetime | None
    closes_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class DatedSessions:
    address: str
    provenance: str
    timezone: str
    dates: tuple[DatedSession, ...]
    instrument_address: str
    venue_code: str
    source_reference: str
    recorded_at: dt.datetime

    def __post_init__(self):
        dates = tuple(self.dates)
        _require(all(type(row) is DatedSession for row in dates), "invalid frozen dates")
        object.__setattr__(self, "dates", dates)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise MarketTruthError(f"DATED_SESSIONS_INVALID: {reason}")


def _closed(value, fields):
    _require(type(value) is dict and set(value) == fields, "closed document shape required")
    return value


def _unique_object(pairs):
    result = dict(pairs)
    _require(len(result) == len(pairs), "duplicate JSON keys")
    return result


def _reject_constant(value):
    raise MarketTruthError("DATED_SESSIONS_INVALID: non-finite JSON constant")


def _document(payload: bytes):
    _require(type(payload) is bytes and 0 < len(payload) <= 1_048_576, "payload must be 1..1048576 bytes")
    try:
        document = _closed(json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                                     parse_constant=_reject_constant), _FIELDS)
        canonical_json(document).encode("utf-8")
        return document
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise MarketTruthError("DATED_SESSIONS_INVALID: invalid JSON document") from exc


def _utc(value: dt.datetime) -> dt.datetime:
    _require(type(value) is dt.datetime and value.tzinfo is not None
             and value.utcoffset() == dt.timedelta(0), "exact UTC datetime required")
    return value.astimezone(dt.timezone.utc)


def _clock(value, *, whole=False):
    _require(type(value) is str and _UTC_CLOCK.fullmatch(value) is not None, "ISO UTC clock required")
    try:
        clock = _utc(dt.datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as exc:
        raise MarketTruthError("DATED_SESSIONS_INVALID: invalid UTC clock") from exc
    _require(not whole or clock.microsecond == 0, "whole-second session clocks required")
    return clock


def _zone(value):
    _require(type(value) is str and 0 < len(value) <= 128, "IANA timezone required")
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise MarketTruthError("DATED_SESSIONS_INVALID: unknown IANA timezone") from exc


def _date(value):
    _require(type(value) is str, "canonical local date required")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise MarketTruthError("DATED_SESSIONS_INVALID: invalid local date") from exc
    _require(parsed.isoformat() == value, "canonical local date required")
    return parsed


def _local(clock, zone):
    try:
        return clock.astimezone(zone)
    except OverflowError as exc:
        raise MarketTruthError("DATED_SESSIONS_INVALID: local clock outside supported dates") from exc


def _session(row, zone):
    _closed(row, _ROW_FIELDS)
    local_date = _date(row["date"])
    _require(row["status"] in ("OPEN", "CLOSED"), "OPEN or CLOSED status required")
    if row["status"] == "CLOSED":
        _require(row["opens_at"] is None and row["closes_at"] is None, "closed date must have null clocks")
        return DatedSession(row["date"], None, None)
    opens, closes = (_clock(row[key], whole=True) for key in ("opens_at", "closes_at"))
    _require(opens < closes, "session open must precede close")
    local_open, local_close = _local(opens, zone), _local(closes, zone)
    next_midnight = ((local_close.date() - local_date).days == 1
                     and local_close.time() == dt.time())
    _require(local_open.date() == local_date, "session open must belong to local date")
    _require(local_close.date() == local_date or next_midnight, "session close exceeds local date")
    return DatedSession(row["date"], opens, closes)


def _dates(rows, zone):
    _require(type(rows) is list and 1 <= len(rows) <= 366, "1..366 explicit dates required")
    result, previous_date, previous_close = [], None, None
    for row in rows:
        session = _session(row, zone)
        local_date = _date(session.local_date)
        if previous_date is not None:
            _require((local_date - previous_date).days == 1, "dates must be consecutive and ordered")
        if session.opens_at is not None:
            _require(previous_close is None or session.opens_at >= previous_close, "sessions overlap")
            previous_close = session.closes_at
        result.append(session)
        previous_date = local_date
    return tuple(result)


def _identity(document, instrument_address, venue_code, timezone):
    _require(document["schema"] == "dated-trading-sessions/1", "unsupported schema")
    _require(is_content_address(instrument_address), "canonical instrument address required")
    _require(type(venue_code) is str and re.fullmatch(r"[A-Z0-9]{4}", venue_code) is not None,
             "canonical venue code required")
    _require((document["instrument_address"], document["venue_code"], document["timezone"])
             == (instrument_address, venue_code, timezone), "foreign instrument, venue or timezone")


def _provenance(document, allow_synthetic):
    _require(type(allow_synthetic) is bool, "synthetic permission must be boolean")
    provenance = document["provenance"]
    _require(provenance in ("SOURCE_DECLARED", "SYNTHETIC"), "unsupported provenance")
    _require(provenance != "SYNTHETIC" or allow_synthetic, "synthetic sessions are not admitted")
    reference = document["source_reference"]
    _require(type(reference) is str and 0 < len(reference) <= 2048
             and reference == reference.strip() and "\x00" not in reference, "bounded source reference required")


def parse_dated_sessions(payload: bytes, *, instrument_address: str, venue_code: str,
                         timezone: str, as_of: dt.datetime,
                         allow_synthetic: bool = False) -> DatedSessions:
    """Validate a bounded declaration for one exact instrument and local timezone."""
    document = _document(payload)
    _identity(document, instrument_address, venue_code, timezone)
    zone = _zone(timezone)
    _provenance(document, allow_synthetic)
    recorded_at = _clock(document["recorded_at"])
    _require(recorded_at <= _utc(as_of), "future recorded_at")
    dates = _dates(document["rows"], zone)
    return DatedSessions(content_address(document), document["provenance"], timezone, dates,
                         instrument_address, venue_code, document["source_reference"], recorded_at)


def _resolution(value):
    _require(type(value) is int and value in (900, 1800, 3600), "unsupported resolution")
    return dt.timedelta(seconds=value)


def _covered_dates(calendar, start, end):
    _require(type(calendar) is DatedSessions, "parsed calendar required")
    zone = _zone(calendar.timezone)
    first, last = _local(start, zone).date(), _local(end, zone).date()
    rows = {row.local_date: row for row in calendar.dates}
    count = (last - first).days + 1
    _require(1 <= count <= 366, "request exceeds calendar date bound")
    dates = tuple((first + dt.timedelta(days=index)).isoformat() for index in range(count))
    if any(date not in rows for date in dates):
        raise MarketTruthError("DATED_SESSIONS_COVERAGE_MISSING: every requested local date must be explicit")
    return tuple(rows[date] for date in dates)


def _session_bars(session, start, end, interval, cutoff):
    if session.opens_at is None:
        return
    opens, closes = session.opens_at, session.closes_at
    if opens > end or start >= closes:
        return
    step = max(0, (start - opens) // interval)
    event = opens + step * interval
    if event < start:
        event += min(interval, closes - event)
    while event < closes and event <= end:
        completion = event + min(interval, closes - event)
        if completion <= cutoff:
            yield event, completion
        event = completion


def expected_bars(calendar: DatedSessions, *, requested_start: dt.datetime,
                  requested_end: dt.datetime, resolution_seconds: int,
                  cutoff_at: dt.datetime) -> tuple[tuple[dt.datetime, dt.datetime], ...]:
    """Return completed bars whose anchored opens lie in the inclusive request."""
    start, end, cutoff = (_utc(value) for value in (requested_start, requested_end, cutoff_at))
    _require(start <= end, "request start must not follow end")
    interval = _resolution(resolution_seconds)
    sessions = _covered_dates(calendar, start, end)
    result = []
    for session in sessions:
        for bar in _session_bars(session, start, end, interval, cutoff):
            _require(len(result) < 2000, "request exceeds 2000 completed bars")
            result.append(bar)
    return tuple(result)


def completion_for(calendar: DatedSessions, event: dt.datetime, resolution: int) -> dt.datetime:
    """Resolve an exact aligned bar open; never infer a session or provider grant."""
    event, interval = _utc(event), _resolution(resolution)
    session = _covered_dates(calendar, event, event)[0]
    _require(session.opens_at is not None, "bar open falls on an explicitly closed date")
    _require(session.opens_at <= event < session.closes_at, "bar open falls outside session")
    _require((event - session.opens_at) % interval == dt.timedelta(0), "bar open is not session aligned")
    return event + min(interval, session.closes_at - event)
