"""Bind retained dated-session declarations to the existing alignment authority.

The declaration supplies calendar coverage; provider omissions never do. Its
provenance remains visible and is not promoted to observed exchange truth.
"""
from __future__ import annotations

from app.market_data.observations import load_raw_segment
from app.market_data.dated_session_clock import SCHEMA, COMPLETION_SCHEMA, prepare_session_clock
from app.market_truth.authority import load_market_truth_snapshot
from app.market_truth.identity import load_provider_identity

CALENDAR = "DATED_SESSIONS_CLIP_CLOSE_V1"


def _require(condition):
    if not condition:
        raise ValueError("DATED_SESSION_BINDING_UNAVAILABLE")


def _source(session, truth, owner_id, product_address, contract_address, as_of, schema=SCHEMA):
    candidates = []
    for address in truth.source_evidence:
        raw = load_raw_segment(session, address)
        if raw.raw_schema == schema:
            _require(raw.owner_id == owner_id and raw.product_address == product_address
                     and raw.contract_address == contract_address
                     and raw.media_type == "application/json" and raw.recorded_at <= as_of)
            candidates.append(raw)
    _require(len(candidates) == 1)
    return candidates[0]


def load_dated_session_binding(session, *, owner_id, alignment, instrument,
        product_address, contract_address, as_of):
    """Reload calendar and completion evidence for isolated synthetic history."""
    if alignment.calendar != CALENDAR:
        return None
    _require(alignment.owner_id == owner_id and alignment.resolution_seconds in {900, 1800, 3600})
    entity, product, contract = load_provider_identity(session, contract_address)
    _require(product.address == product_address)
    truth = load_market_truth_snapshot(session, alignment.truth_snapshot_address)
    _require(truth.recorded_at <= as_of and truth.knowledge_cutoff <= as_of
             and instrument.address in truth.instrument_addresses)
    raw = _source(session, truth, owner_id, product_address, contract_address, as_of)
    completion = _source(session, truth, owner_id, product_address, contract_address,
                         as_of, COMPLETION_SCHEMA)
    result = prepare_session_clock(owner_id=owner_id, entity=entity, product=product, contract=contract,
        instrument=instrument, resolution_seconds=alignment.resolution_seconds,
        calendar_source=raw, completion_source=completion, as_of=as_of)
    _require(result.calendar.timezone == alignment.timezone)
    _require(max(raw.recorded_at, completion.recorded_at) <= truth.recorded_at)
    return result
