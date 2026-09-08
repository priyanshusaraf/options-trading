"""Historical provider response publication through the canonical dataset store.

The trusted caller supplies existing owner, instrument, rights and policy facts.
Receiving candles alone never establishes those facts or monitoring freshness.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import replace
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.db.concurrency import caller_owned_savepoint
from app.market_data import dataset_authority as authority
from app.market_data import kite_historical_attribution as attribution
from app.market_data.kite_observations import map_historical_candles, MAX_HISTORICAL_ROWS
from app.market_data.observations import (
    RawObservationSegment, load_raw_segment,
)
from app.providers.connection_store import ConnectionNotFound, DataConnectionUnavailable
from research.data import provider_capture as capture

PURPOSE = "historical-data-capture:"
PRODUCER = "historical-kite-capture/1"
_PARAMETERS = {"capture_address", "connection_id", "captured_at", "mapping_authority",
               "requested_start", "requested_end"}


class HistoricalCaptureRefused(ValueError):
    def __init__(self, code="HISTORICAL_CAPTURE_UNAVAILABLE",
                 message="Historical data or its source authority is unavailable. Check the connection and requested coverage."):
        self.code = code
        super().__init__(message)


def _require(condition, code="HISTORICAL_CAPTURE_UNAVAILABLE", message=None):
    if not condition:
        if message is None:
            raise HistoricalCaptureRefused(code)
        raise HistoricalCaptureRefused(code, message)


def _document(raw):
    _require(type(raw) is bytes and 0 < len(raw) <= capture.MAX_BYTES)
    document = json.loads(raw, object_pairs_hook=capture._unique_object)
    rows = document["data"]["candles"]
    _require(type(rows) is list and 0 < len(rows) <= MAX_HISTORICAL_ROWS,
        "HISTORICAL_CAPTURE_ROW_COUNT", "No usable bounded history was returned. Choose a different or shorter date range.")
    _require(all(type(row) is list and len(row) == len(capture.FIELDS) + 1 for row in rows))
    return document


def _range(batch, requested_start, requested_end, timezone, calendar=None, as_of=None):
    first, last = batch.observations[0], batch.observations[-1]
    _require(requested_start <= first.event_time <= last.event_time <= requested_end,
        "HISTORICAL_CAPTURE_OUTSIDE_REQUEST", "The provider returned bars outside the requested range. Fetch the range again.")
    rows = batch.observations[::len(capture.FIELDS)]
    _require(all(row.event_time.microsecond == row.completed_at.microsecond == 0 for row in rows),
        "HISTORICAL_CAPTURE_BAR_PRECISION",
        "Candle timestamps must use whole seconds. Check the provider interval before importing this range.")
    if calendar is not None:
        from app.market_truth.dated_sessions import expected_bars
        expected = expected_bars(calendar, requested_start=requested_start,
            requested_end=requested_end, resolution_seconds=first.resolution_seconds, cutoff_at=as_of)
        _require(tuple((row.event_time, row.completed_at) for row in rows) == expected,
            "HISTORICAL_CAPTURE_SESSION_GAPS", "The returned candles do not cover the declared completed sessions.")
    elif first.resolution_seconds == 86400:
        _require(all(row.event_time.astimezone(ZoneInfo(timezone)).time() == dt.time.min for row in rows),
            "HISTORICAL_CAPTURE_DAILY_LABEL",
            "Daily candle labels do not match the data timezone. Check the provider mapping before importing this range.")
    else:
        _require(all(previous.completed_at == following.event_time for previous, following in zip(rows, rows[1:])),
            "HISTORICAL_CAPTURE_SESSION_GAPS",
            "This range crosses missing bars or session breaks. Session-calendar alignment is required before this intraday backtest can run.")
    return first, last, len(rows)


def _grant_clock(session, context, first, *, connection_id, raw_response, captured_at,
                 recorded_at, requested_start, requested_end, clock_binding=None):
    if context.mapping_authority != attribution.MAPPING_AUTHORITY:
        return first.event_time
    return attribution.validate_historical_capture_attribution(
        session, context, connection_id=connection_id, raw_response=raw_response,
        captured_at=captured_at, recorded_at=recorded_at, requested_start=requested_start,
        requested_end=requested_end, resolution_seconds=first.resolution_seconds,
        clock_binding=clock_binding)


def _coverage_session(context, alignment, calendar=None):
    if calendar is not None:
        return "INSTRUMENT_CALENDAR"
    if context.mapping_authority != attribution.MAPPING_AUTHORITY:
        return "INSTRUMENT_CALENDAR"
    _require((alignment.calendar, alignment.session, alignment.timezone, alignment.resolution_seconds)
             == ("PROVIDER_DAILY_DATE_LABEL", "ALL_RECORDED", "Asia/Kolkata", 86400),
        "HISTORICAL_CAPTURE_DAILY_POLICY_REQUIRED",
        "This historical source supports recorded daily labels only. Use daily data without claiming a complete exchange calendar.")
    return "ALL_RECORDED"


def _raw_capture(owner_id, context, raw_response, recorded_at):
    schema = (attribution.RESPONSE_SCHEMA if context.mapping_authority == attribution.MAPPING_AUTHORITY
              else "kite-historical-candle/3")
    return RawObservationSegment(owner_id, context.provider_product_address, context.provider_contract_address,
        "application/json", schema, raw_response, recorded_at)


def _historical_source_identity(observation):
    # A receipt can change without changing the provider's reported candle.
    # Preserve the complete raw-row digest and every source/market identity.
    receipt_fields = {"available_at", "recorded_at", "raw_segment_address", "raw_byte_offset",
        "correction_id", "supersedes_address"}
    return {key: value for key, value in observation.fact().items() if key not in receipt_fields}


def _unrevised_historical_sources(session, context, batch, as_of):
    from sqlalchemy import select, tuple_
    from app.db.models import AuthorityProviderObservation
    from app.market_data.observations import load_provider_observation
    expected = {(item.event_time.replace(tzinfo=None), item.field, item.resolution_seconds):
        _historical_source_identity(item) for item in batch.observations}
    rows = session.scalars(select(AuthorityProviderObservation).where(
        AuthorityProviderObservation.owner_id == context.owner_id,
        AuthorityProviderObservation.product_address == context.provider_product_address,
        AuthorityProviderObservation.available_at <= as_of.replace(tzinfo=None),
        tuple_(AuthorityProviderObservation.event_time, AuthorityProviderObservation.field,
            AuthorityProviderObservation.resolution_seconds).in_(expected))).all()
    for row in rows:
        prior = load_provider_observation(session, row.address)
        if prior.provider_token != context.mapping.provider_token or prior.recorded_at > as_of:
            continue
        key = (prior.event_time.replace(tzinfo=None), prior.field, prior.resolution_seconds)
        _require(_historical_source_identity(prior) == expected[key],
            "HISTORICAL_CAPTURE_REVISION_REQUIRES_LINEAGE",
            "Previously captured history changed. A source correction requires explicit lineage.")


def _source_anchor(session, observation):
    from sqlalchemy import select
    from app.db.models import AuthorityProviderObservation
    from app.market_data.observations import load_provider_observation
    row = session.scalar(select(AuthorityProviderObservation).where(
        AuthorityProviderObservation.owner_id == observation.owner_id,
        AuthorityProviderObservation.product_address == observation.provider_product_address,
        AuthorityProviderObservation.correction_id == observation.correction_id))
    if row is None:
        return observation
    anchor = load_provider_observation(session, row.address)
    _require(_historical_source_identity(anchor) == _historical_source_identity(observation),
        "HISTORICAL_CAPTURE_REVISION_REQUIRES_LINEAGE",
        "Previously captured history changed. A source correction requires explicit lineage.")
    return anchor


def _source_receipt(item, anchor):
    from app.ir.hashing import content_address
    return replace(item, correction_id=content_address({
        "schema": "historical-source-receipt/1", "event_identity": item.correction_id,
        "anchor_address": anchor.address,
        "raw_segment_address": item.raw_segment_address, "available_at": item.available_at.isoformat(),
        "recorded_at": item.recorded_at.isoformat()}), supersedes_address=anchor.address)


def _source_receipts(session, batch):
    # Link unchanged reobservations to the unique original event record.
    return replace(batch, observations=tuple(
        _source_receipt(item, _source_anchor(session, item)) for item in batch.observations))


def _persist_source_anchors(session, batch):
    from app.market_data.kite_observations import _correction_id
    from app.market_data.observations import persist_raw_segment, persist_provider_observation
    for raw in batch.raw_segments:
        persist_raw_segment(session, raw)
    for receipt in batch.observations:
        candidate = replace(receipt, supersedes_address=None,
            correction_id=_correction_id(receipt.sequence_id, receipt.resolution_seconds))
        anchor = _source_anchor(session, candidate)
        _require(anchor.address == receipt.supersedes_address, "HISTORICAL_CAPTURE_SOURCE_CHANGED",
            "The saved source changed during capture. Fetch the history again.")
        # The original unique event key also fences concurrent first captures.
        persist_provider_observation(session, anchor)


def _facts(session, *, owner_id, connection_id, raw_response, context,
           capability_profile_address, policy_addresses, captured_at, recorded_at,
           as_of, requested_start, requested_end, bundle_maximum_age=None, source_receipts=False):
    captured_at, recorded_at, as_of = map(capture._capture_time,
        (captured_at, recorded_at, as_of))
    requested_start, requested_end = map(capture._time, (requested_start, requested_end))
    context, contract = capture._context(session, owner_id, context)
    policies = capture._policies(session, owner_id, policy_addresses, as_of, historical=True)
    profile = capture._profile(session, owner_id, capability_profile_address, context, as_of)
    from research.data.dated_session_binding import load_dated_session_binding
    binding = load_dated_session_binding(session, owner_id=owner_id, alignment=policies[0],
        instrument=context.canonical_instrument, product_address=context.provider_product_address,
        contract_address=context.provider_contract_address, as_of=as_of)
    calendar = binding.calendar if binding is not None else None
    document = _document(raw_response)
    batch = map_historical_candles(document, context=context, resolution_seconds=policies[0].resolution_seconds,
        available_at=captured_at, recorded_at=recorded_at, as_of=as_of, dated_sessions=calendar)
    first, last, count = _range(batch, requested_start, requested_end, policies[0].timezone, calendar, captured_at)
    acquired_at = _grant_clock(session, context, first, connection_id=connection_id,
        raw_response=raw_response, captured_at=captured_at, recorded_at=recorded_at,
        requested_start=requested_start, requested_end=requested_end, clock_binding=binding)
    _require(contract.effective_from <= acquired_at
             and (context.mapping.effective_to is None or last.completed_at <= context.mapping.effective_to))
    session_policy = _coverage_session(context, policies[0], calendar)
    maximum_age = math.ceil((captured_at - first.completed_at).total_seconds())
    if bundle_maximum_age is not None:
        _require(type(bundle_maximum_age) is int and bundle_maximum_age >= maximum_age)
        maximum_age = bundle_maximum_age
    _require(all(capture._covered(profile, field, first, maximum_age, first.resolution_seconds,
        minimum_bars=count, last=last, session_policy=session_policy) for field in capture.FIELDS),
        "HISTORICAL_CAPTURE_COVERAGE_UNAVAILABLE",
        "Verified provider coverage does not cover the returned history. Check the instrument, interval and allowed range.")
    truth = capture._truth(session, context, policies, first, as_of)
    capture._truth(session, context, policies, last, as_of)
    if source_receipts:
        _unrevised_historical_sources(session, context, batch, as_of)
        batch = _source_receipts(session, batch)
    else:
        capture._unrevised_sources(session, context, batch)
    raw = _raw_capture(owner_id, context, raw_response, recorded_at)
    return context, policies, profile, truth, document, batch, raw


def _normalization(context, raw, connection_id, captured_at, requested_start, requested_end, observation_schema):
    parameters = {"capture_address": raw.address, "connection_id": str(connection_id),
        "captured_at": captured_at.isoformat(), "mapping_authority": context.mapping_authority,
        "requested_start": requested_start.isoformat(), "requested_end": requested_end.isoformat()}
    parameters["source_receipts"] = "historical-source-receipt/1"
    from app.market_data import kite_observations, dated_session_clock
    from app.market_truth import dated_sessions
    from research.data import dated_session_binding
    source = "".join(Path(module.__file__).read_text() for module in (
        capture, kite_observations, dated_sessions, dated_session_binding, dated_session_clock)) + Path(__file__).read_text()
    return capture._normalization_facts(context.owner_id, context, raw, parameters, PRODUCER, source,
        observation_schema=observation_schema)


def _publish(execution_session, research_session, facts, project_id, connection_id,
             captured_at, requested_start, requested_end, as_of):
    context, policies, profile, truth, document, batch, raw = facts
    algorithm, schema, transform = _normalization(context, raw, connection_id, captured_at, requested_start, requested_end,
        batch.observations[0].raw_schema)
    algorithms = capture._algorithms(execution_session, context.owner_id, policies, algorithm, as_of)
    normalized = capture._normalized(context, policies, truth, document, batch, algorithm, transform)
    creation = authority.DatasetCreationEvidence(context.owner_id, PRODUCER,
        tuple(sorted(item.address for item in (*batch.observations, *normalized))),
        (raw.address,), algorithm.address, raw.recorded_at)
    manifest, segments = capture._dataset(context, project_id, policies, profile, truth, batch,
        normalized, schema, transform, algorithms, creation, purpose=PURPOSE)
    with caller_owned_savepoint(execution_session, scope="historical-data-capture"):
        connection = capture._connection(execution_session, context.owner_id, project_id, connection_id, lock=True)
        capture._connection_clock(connection, captured_at, as_of)
        _persist_source_anchors(execution_session, batch)
        return capture._persist_capture(execution_session, research_session, raw, batch, normalized,
            algorithm, schema, transform, creation, manifest, segments, as_of)


def publish_historical_kite_capture(execution_session, research_session, *, owner_id, project_id,
        connection_id, raw_response, context, capability_profile_address, alignment_policy_address,
        missing_data_policy_address, adjustment_policy_address, roll_policy_address,
        captured_at, recorded_at, as_of, requested_start, requested_end):
    """Publish retained history, without fetching, committing or granting live freshness."""
    try:
        connection = capture._connection(execution_session, owner_id, project_id, connection_id)
        capture._connection_clock(connection, capture._capture_time(captured_at), capture._capture_time(as_of))
        facts = _facts(execution_session, owner_id=owner_id, connection_id=connection_id,
            raw_response=raw_response, context=context,
            capability_profile_address=capability_profile_address,
            policy_addresses=(alignment_policy_address, missing_data_policy_address, adjustment_policy_address, roll_policy_address),
            captured_at=captured_at, recorded_at=recorded_at, as_of=as_of,
            requested_start=requested_start, requested_end=requested_end, source_receipts=True)
        return _publish(execution_session, research_session, facts, project_id, connection_id,
            captured_at, requested_start, requested_end, as_of)
    except HistoricalCaptureRefused:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError,
            ConnectionNotFound, DataConnectionUnavailable, IntegrityError):
        raise HistoricalCaptureRefused() from None


def load_historical_capture_binding(session, manifest, deps, candles, as_of):
    """Reconstruct retained bytes and source clocks before retrospective projection."""
    if not manifest.purpose.startswith(PURPOSE):
        return None
    _require(len(manifest.normalization_transform_addresses) == len(manifest.raw_schema_addresses) == 1)
    transform = deps[manifest.normalization_transform_addresses[0]]
    parameters = dict(transform.parameters)
    from research.data.provider_history_bundle import PRODUCERS as BUNDLE_PRODUCERS, load_historical_bundle_binding
    if parameters.get("kind") in BUNDLE_PRODUCERS:
        return load_historical_bundle_binding(session, manifest, deps, candles, as_of)
    receipt_mode = parameters.get("source_receipts")
    _require(receipt_mode in {None, "historical-source-receipt/1"})
    expected_parameters = _PARAMETERS if receipt_mode is None else _PARAMETERS | {"source_receipts"}
    _require(set(parameters) == expected_parameters and transform.output_schema == "strategy-bar/1"
             and transform.input_raw_schema_addresses == manifest.raw_schema_addresses)
    raw = load_raw_segment(session, parameters["capture_address"])
    context = capture._capture_identity(session, manifest, parameters)
    captured_at, requested_start, requested_end = (dt.datetime.fromisoformat(parameters[name])
        for name in ("captured_at", "requested_start", "requested_end"))
    # Saved historical evidence survives a later login or connection revocation.
    # Publication checks the active connection; replay checks the retained facts.
    facts = _facts(session, owner_id=manifest.owner_id, connection_id=int(parameters["connection_id"]),
        raw_response=raw.payload, context=context,
        capability_profile_address=manifest.capability_profile_address,
        policy_addresses=(manifest.alignment_policy_address, manifest.missing_data_policy_address,
            manifest.adjustment_policy_address, manifest.roll_policy_address), captured_at=captured_at,
        recorded_at=raw.recorded_at, as_of=as_of, requested_start=requested_start, requested_end=requested_end,
        source_receipts=receipt_mode is not None)
    _matches(manifest, deps, candles, facts)
    return {"connection_id": int(parameters["connection_id"]), "raw_capture_address": raw.address,
        "captured_at": captured_at.isoformat(), "requested_start": requested_start.isoformat(),
        "requested_end": requested_end.isoformat(), "returned_start": candles[0].ts.isoformat(),
        "returned_end": candles[-1].ts.isoformat(), "bar_count": len(candles),
        "calendar_coverage": "NOT_ASSERTED", "historical_source_availability": "NOT_SUPPLIED"}


def _matches(manifest, deps, candles, facts):
    _, _, _, _, document, batch, raw = facts
    rows = document["data"]["candles"]
    _require(len(candles) == len(rows))
    for candle, row, source in zip(candles, rows, batch.observations[::len(capture.FIELDS)], strict=True):
        _require(candle.ts == source.event_time
                 and tuple(getattr(candle, field.lower()) for field in capture.FIELDS) == capture._numeric_values(row))
    _require(manifest.provider_observation_addresses == tuple(sorted(item.address for item in batch.observations))
             and manifest.recorded_at == raw.recorded_at.isoformat())
    schema = deps[manifest.raw_schema_addresses[0]]
    creation = deps[manifest.creation_evidence_addresses[0]]
    _require(schema.evidence_address == raw.address and creation.producer == PRODUCER
             and creation.artifact_addresses == (raw.address,))
