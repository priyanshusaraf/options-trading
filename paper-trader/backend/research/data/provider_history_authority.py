"""Compose bounded research facts from an admitted historical acquisition.

This producer creates neither an instrument identity nor a provider grant. It
uses the retained response and existing owner contract, records only measured
coverage, and makes no exchange-calendar or historical-publication claim.
The caller owns both transaction completion and project/connection admission.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from app.db.concurrency import caller_owned_savepoint
from app.ir.hashing import content_address
from app.market_data import dataset_authority as authority
from app.market_data.authority import persist_capability_profile, persist_provider_conformance
from app.market_data.capability import CapabilityProfile, ProviderConformance
from app.market_data.kite_historical_attribution import persist_historical_attribution
from app.market_data.kite_observations import map_historical_candles
from app.market_data.observations import retain_observation_dependencies
from app.market_truth.authority import persist_market_truth_snapshot
from app.market_truth.identity import Quality, Reconstruction
from app.market_truth.rulebook import MarketTruthSnapshot
from research.data import historical_capture as history
from research.data import provider_capture as capture


CALENDAR = "PROVIDER_DAILY_DATE_LABEL"
SESSION = "ALL_RECORDED"
TIMEZONE = "Asia/Kolkata"
RESOLUTION = 86400


def _intake(source):
    document = json.loads(source.receipt.payload)
    clock_binding = source.clock_binding
    history._require(document["request"]["interval"] == "day" or clock_binding is not None,
        "HISTORICAL_CAPTURE_DAILY_POLICY_REQUIRED",
        "Choose daily history. This research import does not support intraday intervals.")
    values = {
        "owner_id": source.context.owner_id,
        "connection_id": document["connection_id"],
        "context": source.context,
        "raw_response": source.historical_response.payload,
        "captured_at": dt.datetime.fromisoformat(document["historical_response"]["received_at"]),
        "recorded_at": source.historical_response.recorded_at,
        "as_of": dt.datetime.fromisoformat(document["as_of"]),
        "requested_start": dt.datetime.fromisoformat(document["request"]["from"]),
        "requested_end": dt.datetime.fromisoformat(document["request"]["to"]),
    }
    if clock_binding is not None:
        values.update(clock_binding=clock_binding, resolution_seconds=clock_binding.resolution_seconds)
    return values


def _clock_policy(values):
    clock_binding = values.get("clock_binding")
    if clock_binding is None:
        return CALENDAR, SESSION, TIMEZONE, RESOLUTION, None
    from research.data.dated_session_binding import CALENDAR as DATED_CALENDAR
    return (DATED_CALENDAR, "INSTRUMENT_CALENDAR", clock_binding.calendar.timezone,
            clock_binding.resolution_seconds, clock_binding.calendar)


def _measured_range(values):
    document = history._document(values["raw_response"])
    _, _, timezone, resolution, calendar = _clock_policy(values)
    batch = map_historical_candles(document, context=values["context"], resolution_seconds=resolution,
        available_at=values["captured_at"], recorded_at=values["recorded_at"], as_of=values["as_of"],
        dated_sessions=calendar)
    first, last, count = history._range(batch, values["requested_start"], values["requested_end"],
        timezone, calendar, values["captured_at"])
    lag = math.ceil((values["captured_at"] - first.completed_at).total_seconds())
    return first.event_time, last.completed_at, count, lag


def _coverage(field, start, end, count, lag, *, resolution=RESOLUTION, session=SESSION):
    return {
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": field, "resolution_seconds": resolution,
        "history": {"from": start, "to": end, "bars": count},
        "maximum_freshness_seconds": lag,
        "depth": {"kind": "NONE", "levels": None}, "session": session,
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False, "entitlement": "VERIFIED",
    }


def _offer(field, start, end, count, lag, *, resolution=RESOLUTION, session=SESSION):
    return {
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": field, "timeframes": [resolution], "maximum_history_bars": count,
        "available_from": start, "available_to": end, "maximum_freshness_seconds": lag,
        "depth": {"kind": "NONE", "levels": None}, "session": session,
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False, "entitled": True, "known": True,
    }


def _source_evidence(sources):
    evidence = {item.address for source in sources for item in (
        source.receipt, source.current_reference, source.historical_response)}
    for source in sources:
        if source.clock_binding is not None:
            evidence.update((source.clock_binding.source_address, source.clock_binding.completion_source_address))
    return tuple(sorted(evidence))


def _profile(source, values, bounds, *, sources=None, coverage_bounds=None):
    context = source.context
    sources = (source,) if sources is None else sources
    ranges = (bounds,) if coverage_bounds is None else coverage_bounds
    _, session_policy, _, resolution, calendar = _clock_policy(values)
    options = {"resolution": resolution, "session": session_policy}
    first_reference = min(dt.datetime.fromisoformat(json.loads(item.receipt.payload)
        ["current_reference"]["received_at"]) for item in sources)
    conformance = ProviderConformance(
        context.provider_product_address, capture.FIELDS, (resolution,),
        "retained-kite-dated-response-validation" if calendar is not None else "retained-kite-daily-response-validation", "1",
        first_reference, values["as_of"],
        _source_evidence(sources), "PASS",
        tuple(_coverage(field, *window, **options) for window in ranges for field in capture.FIELDS))
    profile = CapabilityProfile(
        context.owner_id, "RESEARCH", 1, values["as_of"], values["as_of"] + dt.timedelta(days=1),
        conformance.address, tuple(_offer(field, *window, **options) for window in ranges for field in capture.FIELDS),
        0, context.provider_entity_address, context.provider_product_address, context.provider_contract_address)
    return conformance, profile


def _policy_facts(source, values, bounds, *, sources=None, additional_evidence=()):
    owner, recorded = values["owner_id"], values["as_of"]
    instrument = source.context.canonical_instrument.address
    calendar, session_policy, timezone, resolution, dated = _clock_policy(values)
    algorithm = authority.DeterministicAlgorithm(owner,
        "kite-historical-dated-policy" if dated is not None else "kite-historical-daily-policy", "1",
        content_address({"source": Path(__file__).read_text()}),
        (content_address({"calendar": calendar, "session": session_policy, "timezone": timezone,
                          "resolution_seconds": resolution, "missing": "REFUSE",
                          "local_adjustment": "NONE", "roll": "NOT_APPLICABLE"}),), recorded)
    truth = MarketTruthSnapshot((), bounds[0], bounds[1], recorded, Quality.RECONSTRUCTED,
        Reconstruction("provider-response-at-acquisition", "1", (
            "historical source publication timestamps not supplied",
            "synthetic declared calendar and bar completion" if dated is not None
                else "exchange calendar and session coverage not asserted",
            "provider-supplied history may contain later price or volume adjustments",
            "current reference does not establish historical listing terms or universe membership",
        )), "RESEARCH", recorded, (instrument,),
        tuple(sorted(set(_source_evidence((source,) if sources is None else sources))
            | set(additional_evidence))))
    policies = (
        authority.AlignmentPolicy(owner, calendar, session_policy, timezone, resolution, truth.address, algorithm.address, recorded),
        authority.MissingDataPolicy(owner, "REFUSE", (), algorithm.address, recorded),
        authority.AdjustmentPolicy(owner, (instrument,), (truth.address,), "NONE", algorithm.address, recorded),
        authority.RollPolicy(owner, (instrument,), (truth.address,), "NONE", algorithm.address, recorded, "NOT_APPLICABLE"),
    )
    return algorithm, truth, policies


def _persist_policy_profile(session, conformance, profile, algorithm, truth, policies):
    authority.persist_deterministic_algorithm(session, algorithm)
    persist_market_truth_snapshot(session, truth)
    writers = (authority.persist_alignment_policy, authority.persist_missing_data_policy,
               authority.persist_adjustment_policy, authority.persist_roll_policy)
    for writer, policy in zip(writers, policies, strict=True):
        writer(session, policy)
    persist_provider_conformance(session, conformance)
    persist_capability_profile(session, profile)


@retain_observation_dependencies
def prepare_historical_authority(execution_session, source):
    """Persist source-derived facts and return existing publisher inputs; never commit."""
    with caller_owned_savepoint(execution_session, scope="historical-provider-authority"):
        persist_historical_attribution(execution_session, source)
        values = _intake(source)
        bounds = _measured_range(values)
        conformance, profile = _profile(source, values, bounds)
        algorithm, truth, policies = _policy_facts(source, values, bounds)
        _persist_policy_profile(execution_session, conformance, profile, algorithm, truth, policies)
    names = ("alignment_policy_address", "missing_data_policy_address", "adjustment_policy_address", "roll_policy_address")
    publication = {key: value for key, value in values.items() if key not in {"clock_binding", "resolution_seconds"}}
    return {**publication, **dict(zip(names, (policy.address for policy in policies), strict=True)),
            "capability_profile_address": profile.capability_profile_address}
