"""Reload retained provider history as an exact completed-bar monitoring prefix.

No acquisition, execution authority or retrospective freshness is inferred here.
The worker must use ``bar_identity`` for refetch deduplication, while retaining
the manifest and terminal observation addresses as evaluation evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

from app.ir.hashing import content_address
from app.ir.first_party.monitoring_intent_v2 import MAX_PREFIX_EVENTS
from app.market_data.observations import load_normalized_observation
from research.data import canonical_dataset as canonical


class MonitoringInputRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise MonitoringInputRefused(code)


@dataclass(frozen=True, slots=True)
class MonitoringInputPrefix:
    projection: object
    manifest_address: str
    observation_address: str
    bar_identity: str
    event_at: dt.datetime
    completed_at: dt.datetime
    available_at: dt.datetime
    recorded_at: dt.datetime
    cutoff_at: dt.datetime
    bar_count: int
    instrument: object
    candles: tuple


def _request(cutoff_at, timeframe_seconds, minimum_bars, maximum_age_seconds, now):
    _require(type(cutoff_at) is dt.datetime and cutoff_at.tzinfo is dt.timezone.utc,
             "MONITORING_INPUT_CLOCK_INVALID")
    _require(type(now) is dt.datetime and now.tzinfo is dt.timezone.utc and cutoff_at <= now,
             "MONITORING_INPUT_FUTURE_CUTOFF")
    _require(type(timeframe_seconds) is int and timeframe_seconds in {900, 1800, 3600, 86400},
             "MONITORING_INPUT_TIMEFRAME_INVALID")
    _require(type(minimum_bars) is int and 1 <= minimum_bars <= MAX_PREFIX_EVENTS,
             "MONITORING_INPUT_WARMUP_INVALID")
    _require(minimum_bars <= canonical.MAX_ROWS, "MONITORING_INPUT_WARMUP_UNSUPPORTED")
    _require(type(maximum_age_seconds) is int and 0 < maximum_age_seconds <= 86400,
             "MONITORING_INPUT_FRESHNESS_INVALID")


def _dataset_source(research_session, execution_session, owner_id, manifest_address, cutoff_at):
    # Reuse the canonical authority loader, with the exact monitoring cutoff.
    # The public research batch API deliberately accepts whole-second cutoffs.
    research, execution = canonical._authority_batch_plan(
        research_session, execution_session, owner_id, [manifest_address])
    instrument, data = canonical._load_one(research, execution, owner_id, manifest_address, cutoff_at)
    _require("historical_capture" in data.binding and "current_capture" not in data.binding,
             "MONITORING_INPUT_PROVIDER_HISTORY_REQUIRED")
    return instrument, data


def _dataset(research_session, execution_session, owner_id, manifest_address, cutoff_at):
    return _dataset_source(research_session, execution_session, owner_id, manifest_address, cutoff_at)[1]


def _terminal(execution_session, data):
    authority = data._verified_authority
    pairs = zip(authority.segments, authority.object_bytes, strict=True)
    segment, payload = max(pairs, key=lambda pair: pair[0].row_start)
    index = canonical.decode_observation_index(payload)
    observations = tuple(load_normalized_observation(execution_session, address)
                         for address in index["rows"][-1])
    _require(bool(observations), "MONITORING_INPUT_TERMINAL_MISSING")
    return observations


def _terminal_clock(observations, data, instrument_address, timeframe_seconds, cutoff_at, maximum_age_seconds):
    opened = data.candles[-1].ts
    completed = opened + dt.timedelta(seconds=timeframe_seconds)
    if data._dated_session_binding is not None:
        from app.market_truth.dated_sessions import completion_for
        completed = completion_for(data._dated_session_binding.calendar, opened, timeframe_seconds)
    _require(all((item.canonical_instrument_address, item.resolution_seconds,
                  item.event_time, item.completed_at) ==
                 (instrument_address, timeframe_seconds, opened, completed)
                 for item in observations), "MONITORING_INPUT_TERMINAL_MISMATCH")
    _require(all(completed <= item.available_at <= item.recorded_at <= cutoff_at
                 for item in observations), "MONITORING_INPUT_UNAVAILABLE")
    _require(dt.timedelta(0) <= cutoff_at - completed <= dt.timedelta(seconds=maximum_age_seconds),
             "MONITORING_INPUT_STALE")
    return opened, completed


def load_monitoring_input_prefix(research_session, execution_session, *, owner_id,
        manifest_address, instrument_address, timeframe_seconds, minimum_bars,
        maximum_age_seconds, cutoff_at, graph_input_fields, now=None):
    """Verify history and bind its requested age; ``now`` is a trusted worker clock."""
    current = dt.datetime.now(dt.timezone.utc) if now is None else now
    _request(cutoff_at, timeframe_seconds, minimum_bars, maximum_age_seconds, current)
    try:
        instrument, data = _dataset_source(research_session, execution_session, owner_id, manifest_address, cutoff_at)
        _require(data.binding["instrument_address"] == instrument_address
                 and data._alignment_fact.resolution_seconds == timeframe_seconds,
                 "MONITORING_INPUT_SCOPE_MISMATCH")
        _require(minimum_bars <= data.bar_count <= MAX_PREFIX_EVENTS, "MONITORING_INPUT_WARMUP_REQUIRED")
        observations = _terminal(execution_session, data)
        opened, completed = _terminal_clock(observations, data, instrument_address,
            timeframe_seconds, cutoff_at, maximum_age_seconds)
        projection = canonical.project_verified_research_inputs(
            data, owner_id=owner_id, graph_input_fields=graph_input_fields,
            evaluation_freshness_seconds=maximum_age_seconds)
        _require(projection.availability_index[-1].to_pydatetime() == completed
                 and projection.bar_open_index[-1].to_pydatetime() == opened,
                 "MONITORING_INPUT_PROJECTION_CLOCK_MISMATCH")
        bar_identity = content_address({"schema": "monitoring-completed-bar/1",
            "owner_id": owner_id, "instrument_address": instrument_address,
            "timeframe_seconds": timeframe_seconds, "event_at": opened.isoformat()})
        return MonitoringInputPrefix(projection, manifest_address,
            content_address({"schema": "monitoring-terminal-observations/1",
                             "addresses": sorted(item.address for item in observations)}),
            bar_identity, opened, completed, max(item.available_at for item in observations),
            max(item.recorded_at for item in observations), cutoff_at, data.bar_count, instrument, data.candles)
    except MonitoringInputRefused:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        raise MonitoringInputRefused("MONITORING_INPUT_AUTHORITY_INVALID") from None
