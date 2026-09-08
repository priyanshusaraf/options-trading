"""Bounded observation-index adapter over existing persisted DatasetManifest/2.

No provider fetch, normalization, authority store, evaluator or alternative hash.
The schema role is provider provenance; the envelope describes index encoding.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import BindParameter

from app.core.instruments import Instrument
from app.ir.hashing import canonical_json, content_address
from app.ir.validity import ValidityState
from app.market_data import dataset_authority as authorities
from app.market_data.authority import load_capability_profile, load_provider_conformance
from app.market_data.candles import validate_candles
from app.market_data.numeric import market_float
from app.market_data.observations import (
    load_normalized_observation, load_provider_observation, load_raw_segment,
)
from app.market_truth.authority import load_market_truth_snapshot
from app.market_truth.identity import load_canonical_instrument, load_provider_alias
from research.domain.models import (
    ResearchDatasetManifestV2, ResearchDatasetManifestSegmentV2, ResearchDatasetSegmentV2,
)
from research.domain.strategy_admissions import load_verified_dataset_authority

CODEC = "strategy-os-observation-candle-index/1"
CODEC_V2 = "strategy-os-observation-candle-index/2"
FIELDS = ("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME")
PRICE_FIELDS = ("OPEN", "HIGH", "LOW", "CLOSE")
FIELD_SETS = {tuple(sorted(FIELDS)), tuple(sorted(PRICE_FIELDS))}
INTERVALS = {900: "15minute", 1800: "30minute", 3600: "60minute", 86_400: "day"}
MAX_MANIFESTS, MAX_ROWS, MAX_BYTES = 8, 2000, 8 * 1024 * 1024
PREFETCH_BATCH = MAX_ROWS * 5
UTC = dt.timezone.utc


class CanonicalDatasetRefused(ValueError):
    """Private stable refusal: never expose authority existence or stored values."""

    code = "EXPERIMENT_CANONICAL_DATASET_REFUSED"

    def __init__(self):
        super().__init__("canonical dataset selection is unavailable or unsupported")


def _require(condition):
    if not condition:
        raise CanonicalDatasetRefused()


def _observed_instant(value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    _require(isinstance(value, dt.datetime) and value.tzinfo is not None
             and value.utcoffset() == dt.timedelta(0))
    # The converter and engine operate in pandas nanosecond range.
    _require(pd.Timestamp.min.tz_localize("UTC") < value
             < pd.Timestamp.max.tz_localize("UTC"))
    return value


def _instant(value):
    value = _observed_instant(value)
    _require(value.microsecond == 0)
    return value


def _known(value, as_of):
    _require(_observed_instant(value) <= as_of)


def encode_observation_index(
    instrument_address, resolution_seconds, rows, *, fields=FIELDS, codec=CODEC,
):
    """Encode references only, with the same closed decoder used on reads."""
    fields = tuple(fields)
    document = {"schema": CODEC, "instrument_address": instrument_address,
        "resolution_seconds": resolution_seconds, "rows": [list(row) for row in rows]}
    if fields != FIELDS or codec == CODEC_V2:
        document.update(schema=CODEC_V2, fields=list(fields))
    payload = canonical_json(document).encode()
    decode_observation_index(payload)
    return payload


def _index_document(payload):
    obj = json.loads(payload.decode("utf-8"))
    _require(type(obj) is dict and obj.get("schema") in {CODEC, CODEC_V2})
    expected = {"schema", "instrument_address", "resolution_seconds", "rows"}
    if obj["schema"] == CODEC_V2:
        expected.add("fields")
    _require(set(obj) == expected and canonical_json(obj).encode() == payload)
    return obj


def _index_fields(obj):
    fields = FIELDS if obj["schema"] == CODEC else tuple(obj["fields"])
    _require(fields in {FIELDS, PRICE_FIELDS})
    return fields


def _index_rows(rows, fields):
    _require(type(rows) is list and 0 < len(rows) <= MAX_ROWS)
    for row in rows:
        _require(type(row) is list and len(row) == len(fields) and len(set(row)) == len(fields))
        for address in row:
            _address(address)


def decode_observation_index(payload):
    _require(isinstance(payload, bytes) and 0 < len(payload) <= MAX_BYTES)
    try:
        obj = _index_document(payload)
        _require(type(obj["resolution_seconds"]) is int
                 and obj["resolution_seconds"] in INTERVALS)
        _address(obj["instrument_address"])
        fields = _index_fields(obj)
        _index_rows(obj["rows"], fields)
        return {**obj, "fields": list(fields)}
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise CanonicalDatasetRefused() from None


def _address(value):
    _require(isinstance(value, str) and len(value) == 71 and value.startswith("sha256:")
             and all(c in "0123456789abcdef" for c in value[7:]))
    return value


def instrument_key(address):
    return "ci_" + base64.urlsafe_b64encode(bytes.fromhex(_address(address)[7:])).decode().rstrip("=")


def _simulation_projection(venue):
    from app.core.config import get_settings
    from app.backtest.engine import BACKTEST_EXIT_POLICY
    from app.engine.charges import CHARGE_SCHEDULE
    value = market_float(get_settings().backtest_slippage_pct, field="base slippage")
    _require(value >= 0)
    return {"segment":venue, "charge_segment":venue+"_EQ", "lot_size":1,
        "sizing":"floor(capital/price)", "has_options":False,
        "base_round_trip_slippage_pct":value,
        "request_slippage_bps_role":"additional_validation_stress_not_base_fill",
        "charge_schedule":dict(CHARGE_SCHEDULE[venue+"_EQ"]),
        "exit_policy":asdict(BACKTEST_EXIT_POLICY), "minimum_simulator_bars":57}


def _validated_row_clock(event, completed, available, expected_event, seconds, timezone,
                         retrospective, expected_bar=None):
    if expected_bar is not None:
        _require((event, completed) == expected_bar and completed <= available)
        return completed
    return _nominal_row_clock(event, completed, available, expected_event, seconds,
                              timezone, retrospective)


def _nominal_row_clock(event, completed, available, expected_event, seconds, timezone,
                       retrospective):
    contiguous = expected_event is None or event == expected_event
    daily_forward = (seconds == 86_400 and expected_event is not None
                     and event > expected_event - dt.timedelta(seconds=seconds))
    _require(completed == event + dt.timedelta(seconds=seconds)
             and (available >= completed if retrospective else available == completed)
             and (contiguous or daily_forward))
    if seconds == 86_400:
        _require(event.astimezone(ZoneInfo(timezone)).time() == dt.time.min)
    return completed


def _canonical_candle(event, numbers):
    op, hi, lo, cl = (numbers[field] for field in PRICE_FIELDS)
    volume = numbers.get("VOLUME")
    _require(min(op, hi, lo, cl) > 0
             and lo <= min(op, cl) <= max(op, cl) <= hi
             and (volume is None or volume >= 0))
    return CanonicalCandle(event, op, hi, lo, cl, volume)


def _availability_matches(start, end, observed, event_start, event_end, seconds,
                          retrospective):
    if retrospective:
        return start <= min(observed) and max(observed) < end
    return (start == event_start + dt.timedelta(seconds=seconds)
            and end == event_end + dt.timedelta(seconds=seconds))


def _time_interpretation(resolution, alignment, source_availability, event_end, capture=None, historical=None):
    imported = alignment.calendar == "USER_DECLARED_DATE_LABEL" or historical is not None
    # The whole prefix is available only after its last source receipt arrives.
    # Retained windows may have been acquired before the terminal bar existed.
    observed_at = max(source_availability)
    source_lag = math.ceil((observed_at - event_end).total_seconds())
    result = {
        "label": "bar_open", "resolution_seconds": resolution,
        "completed_at": "event_time+resolution",
        "evaluation_at": "event_time+resolution",
        "available_at": "actual_source_observed_at" if imported else "completed_at",
        "fill": "next_bar_open", "recorded_at": "separate_replay_cutoff",
        "date_timezone": alignment.timezone,
        "retrospective_evaluation": imported,
        "historical_source_availability": "NOT_SUPPLIED" if imported else "DECLARED",
        "actual_source_observed_at": observed_at.isoformat(),
        "actual_source_lag_seconds": source_lag if imported else 0,
    }
    if capture is not None:
        result.update(evaluation_at="actual_source_observed_at", available_at="actual_source_observed_at",
            actual_source_lag_seconds=source_lag, capture_kind="CURRENT_COMPLETED_BAR")
    if historical is not None:
        result["capture_kind"] = "HISTORICAL_RESEARCH"
    return result


def _research_projection(physical, venue):
    return _simulation_projection(venue) if physical.asset_class == "EQUITY" else None


def _research_session(alignment):
    return "ALL_RECORDED" if alignment.calendar in {"USER_DECLARED_DATE_LABEL", "PROVIDER_DAILY_DATE_LABEL"} \
        else "INSTRUMENT_CALENDAR"


def _research_freshness(dataset):
    capture = dataset.binding.get("current_capture")
    if capture is not None:
        return capture["maximum_age_seconds"]
    return dataset._provenance_binding["time_interpretation"].get(
        "actual_source_lag_seconds", 0)


def _projection_freshness(dataset, requested):
    if requested is None:
        return _research_freshness(dataset)
    _require(type(requested) is int and 0 < requested <= 86400)
    binding = dataset._provenance_binding
    _require("historical_capture" in binding and "current_capture" not in binding)
    cutoff = dt.datetime.fromisoformat(binding["as_of"])
    completed = _instant(dataset._verified_authority.manifest.event_end)
    _require(dt.timedelta(0) <= cutoff - completed <= dt.timedelta(seconds=requested))
    return requested


def _projection_codec(result, alignment):
    if alignment.calendar == "USER_DECLARED_DATE_LABEL":
        object.__setattr__(result, "source_codec", CODEC_V2)
    return result


@dataclass(frozen=True)
class CanonicalCandle:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class CanonicalDataset:
    instrument_key: str
    interval: str
    requested_days: int
    bar_count: int
    start_ts: int
    end_ts: int
    content_hash: str
    candles: tuple[CanonicalCandle, ...]
    binding_json: str
    _provenance_binding: dict = field(compare=False,repr=False)
    _verified_authority: object | None = field(default=None, compare=False, repr=False)
    _alignment_fact: object | None = field(default=None, compare=False, repr=False)
    _dated_session_binding: object | None = field(default=None, compare=False, repr=False)

    @property
    def binding(self):
        # Do not expose mutable internal lineage to a consumer.
        return json.loads(self.binding_json)


class _ScalarRows:
    """Minimal read result for typed-loader queries served from the batch."""

    def __init__(self, rows):
        self._rows = tuple(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        _require(len(self._rows) <= 1)
        return self._rows[0] if self._rows else None


class _BatchedTypedSession:
    """Request-scoped query plan; typed loaders remain the verifier."""

    def __init__(self, session, pinned_rows, result_maps):
        self._session = session
        self._pinned_rows = tuple(pinned_rows)  # keep the identity map strong
        self._result_maps = result_maps
        self._verified = set()
        self._fact_cache = {}

    def execute(self, statement, *args, **kwargs):
        descriptions = getattr(statement, "column_descriptions", ())
        entity = descriptions[0].get("entity") if len(descriptions) == 1 else None
        mapping = self._result_maps.get(entity)
        if mapping is not None:
            values = [node.value for node in visitors.iterate(statement)
                      if isinstance(node, BindParameter)]
            key = next((value for value in values
                        if isinstance(value, str) and value in mapping), None)
            if key is not None:
                rows = mapping[key]
                return _ScalarRows(rows if isinstance(rows, (tuple, list)) else (rows,))
        return self._session.execute(statement, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._session, name)

    def mark_verified(self, manifest):
        from app.db import models as m
        provider = set(manifest.provider_observation_addresses)
        normalized = set(manifest.normalized_observation_addresses)
        provider_rows = self._result_maps["rows_by_model"].get(m.AuthorityProviderObservation,{})
        pending=list(provider)
        while pending:
            row=provider_rows.get(pending.pop())
            if row is not None and row.supersedes_address and row.supersedes_address not in provider:
                provider.add(row.supersedes_address);pending.append(row.supersedes_address)
        raw = {provider_rows[address].raw_segment_address for address in provider if address in provider_rows}
        aliases = {provider_rows[address].mapping_address for address in provider if address in provider_rows}
        self._verified.update(normalized | provider | raw | aliases)

    def _row(self, model, address):
        _require(address in self._verified)
        row = self._result_maps["rows_by_model"].get(model,{}).get(address)
        _require(row is not None)
        return row

    def _document(self,model,address):
        key=("document",model,address)
        if key not in self._fact_cache:
            self._fact_cache[key]=json.loads(self._row(model,address).canonical_json)["fact"]
        return self._fact_cache[key]

    def normalized_fact(self,address):
        from app.db.models import AuthorityNormalizedObservation
        from app.market_data.observations import _numeric_from_fact
        from types import SimpleNamespace
        key=("projection",AuthorityNormalizedObservation,address)
        if key not in self._fact_cache:
            fact=self._document(AuthorityNormalizedObservation,address)
            self._fact_cache[key]=SimpleNamespace(**{**fact,
                "provider_observation_addresses":tuple(fact["provider_observation_addresses"]),
                "correction_lineage":tuple(fact["correction_lineage"]),
                "event_time":dt.datetime.fromisoformat(fact["event_time"]),
                "completed_at":dt.datetime.fromisoformat(fact["completed_at"]),
                "available_at":dt.datetime.fromisoformat(fact["available_at"]),
                "recorded_at":dt.datetime.fromisoformat(fact["recorded_at"]),
                "numeric":_numeric_from_fact(fact["numeric"])})
        return self._fact_cache[key]

    def provider_fact(self,address):
        from app.db.models import AuthorityProviderObservation
        from types import SimpleNamespace
        key=("projection",AuthorityProviderObservation,address)
        if key not in self._fact_cache:
            fact=self._document(AuthorityProviderObservation,address)
            self._fact_cache[key]=SimpleNamespace(**{**fact,
                "event_time":dt.datetime.fromisoformat(fact["event_time"]),
                "completed_at":dt.datetime.fromisoformat(fact["completed_at"]),
                "available_at":dt.datetime.fromisoformat(fact["available_at"]),
                "recorded_at":dt.datetime.fromisoformat(fact["recorded_at"]),
                "validity":ValidityState(fact["validity"])})
        return self._fact_cache[key]

    def alias_fact(self,address):
        from app.db.models import AuthorityProviderAlias
        from types import SimpleNamespace
        key=("projection",AuthorityProviderAlias,address)
        if key not in self._fact_cache:
            fact=self._document(AuthorityProviderAlias,address)
            self._fact_cache[key]=SimpleNamespace(**fact)
        return self._fact_cache[key]

    def raw_fact(self,address):
        from app.db.models import AuthorityRawSegment
        from types import SimpleNamespace
        key=("projection",AuthorityRawSegment,address)
        if key not in self._fact_cache:
            fact=self._document(AuthorityRawSegment,address)
            self._fact_cache[key]=SimpleNamespace(**{**fact,
                "recorded_at":dt.datetime.fromisoformat(fact["recorded_at"])})
        return self._fact_cache[key]


def _chunks(values):
    values = tuple(values)
    for offset in range(0, len(values), PREFETCH_BATCH):
        yield values[offset:offset + PREFETCH_BATCH]


def _batch_rows(session, model, addresses, pinned):
    addresses = tuple(sorted(set(addresses)))
    for batch in _chunks(addresses):
        if batch:
            pinned.extend(session.scalars(select(model).where(model.address.in_(batch))).all())


def _authority_batch_plan(research_session, execution_session, owner_id, addresses):
    """Bound size, bytes and owner before typed loaders traverse the same rows."""
    from app.db import models as m
    manifest_rows = research_session.scalars(select(ResearchDatasetManifestV2).where(
        ResearchDatasetManifestV2.owner_id == owner_id,
        ResearchDatasetManifestV2.manifest_address.in_(addresses))).all()
    _require(len(manifest_rows) == len(addresses))
    manifest_facts = {row.manifest_address: json.loads(bytes(row.canonical_bytes))["fact"]
                      for row in manifest_rows}
    _require(sum(len(bytes(row.canonical_bytes)) for row in manifest_rows) <= MAX_BYTES)

    segment_rows = research_session.execute(select(ResearchDatasetSegmentV2).join(
        ResearchDatasetManifestSegmentV2,
        (ResearchDatasetManifestSegmentV2.owner_id == ResearchDatasetSegmentV2.owner_id)
        & (ResearchDatasetManifestSegmentV2.segment_address == ResearchDatasetSegmentV2.segment_address)
    ).where(ResearchDatasetManifestSegmentV2.owner_id == owner_id,
            ResearchDatasetManifestSegmentV2.manifest_address.in_(addresses))).scalars().all()
    links = research_session.scalars(select(ResearchDatasetManifestSegmentV2).where(
        ResearchDatasetManifestSegmentV2.owner_id == owner_id,
        ResearchDatasetManifestSegmentV2.manifest_address.in_(addresses))).all()
    _require(0 < len(segment_rows) <= MAX_ROWS and len(links) == len(segment_rows))
    segment_facts = {row.segment_address: json.loads(bytes(row.canonical_bytes))["fact"]
                     for row in segment_rows}

    total_rows = sum(fact["row_end"] - fact["row_start"] for fact in segment_facts.values())
    total_index = sum(row.byte_length for row in segment_rows)
    _require(type(total_rows) is int and 0 < total_rows <= MAX_ROWS
             and total_index == sum(row.aggregate_byte_length for row in manifest_rows)
             and total_index <= MAX_BYTES
             and sum(len(bytes(row.canonical_bytes)) for row in segment_rows) <= MAX_BYTES)
    _require(all(row.byte_length == len(bytes(row.object_bytes)) for row in segment_rows))

    def union(name, documents):
        return {value for document in documents for value in document.get(name, ())}

    mfacts = tuple(manifest_facts.values())
    sfacts = tuple(segment_facts.values())
    normalized = union("normalized_observation_addresses", sfacts)
    provider = union("provider_observation_addresses", sfacts)
    _require(0 < len(normalized) <= MAX_ROWS * 5 and 0 < len(provider) <= MAX_ROWS * 5 * 64)

    normalized_input_rows = []
    for batch in _chunks(normalized):
        normalized_input_rows.extend(execution_session.scalars(select(
            m.AuthorityNormalizedObservationInput).where(
                m.AuthorityNormalizedObservationInput.normalized_address.in_(batch))).all())
    normalized_inputs = {}
    for row in normalized_input_rows:
        normalized_inputs.setdefault(row.normalized_address, []).append(row)
        provider.add(row.provider_observation_address)
    for rows in normalized_inputs.values():
        rows.sort(key=lambda row: row.ordinal)
    _require(len(provider) <= MAX_ROWS * 5 * 64)

    source_rows = []
    pending = set(provider)
    seen = set()
    while pending:
        batch = tuple(sorted(pending - seen))[:PREFETCH_BATCH]
        if not batch:
            break
        seen.update(batch)
        rows = execution_session.scalars(select(m.AuthorityProviderObservation).where(
            m.AuthorityProviderObservation.address.in_(batch))).all()
        source_rows.extend(rows)
        pending.update(row.supersedes_address for row in rows if row.supersedes_address)
        _require(len(pending | seen) <= MAX_ROWS * 5 * 64)
    _require(all(row.owner_id == owner_id for row in source_rows))

    raw_addresses = {row.raw_segment_address for row in source_rows}
    raw_rows = []
    for batch in _chunks(raw_addresses):
        raw_rows.extend(execution_session.scalars(select(m.AuthorityRawSegment).where(
            m.AuthorityRawSegment.address.in_(batch))).all())
    _require(all(row.owner_id == owner_id for row in raw_rows)
             and sum(row.byte_length for row in raw_rows) + total_index <= MAX_BYTES
             and all(row.byte_length == len(bytes(row.raw_bytes)) for row in raw_rows))

    pinned = [*normalized_input_rows, *source_rows, *raw_rows]
    aliases = {row.mapping_address for row in source_rows}
    contracts = union("provider_contract_addresses", mfacts) | {row.contract_address for row in source_rows}
    products = union("provider_product_addresses", mfacts) | {row.product_address for row in source_rows}
    entities = union("provider_entity_addresses", mfacts) | {row.entity_address for row in source_rows}
    instruments = union("instrument_addresses", mfacts)
    model_addresses = (
        (m.AuthorityNormalizedObservation, normalized),
        (m.AuthorityProviderAlias, aliases),
        (m.AuthorityProviderContract, contracts),
        (m.AuthorityProviderProduct, products),
        (m.AuthorityProviderEntity, entities),
        (m.AuthorityCanonicalInstrument, instruments),
        (m.AuthorityRawSchema, union("raw_schema_addresses", mfacts)),
        (m.AuthorityNormalizationTransform, union("normalization_transform_addresses", mfacts)),
        (m.AuthorityMarketTruthSnapshot, union("truth_snapshot_addresses", mfacts)),
        (m.AuthorityDatasetCreationEvidence, union("creation_evidence_addresses", mfacts)),
        (m.AuthorityDatasetCorrection, union("correction_addresses", mfacts)),
        (m.AuthorityDeterministicAlgorithm, union("algorithm_addresses", mfacts)),
        (m.AuthorityCapabilityProfile, {d["capability_profile_address"] for d in mfacts}),
        (m.AuthorityAlignmentPolicy, {d["alignment_policy_address"] for d in mfacts}),
        (m.AuthorityMissingDataPolicy, {d["missing_data_policy_address"] for d in mfacts}),
        (m.AuthorityAdjustmentPolicy, {d["adjustment_policy_address"] for d in mfacts}),
        (m.AuthorityRollPolicy, {d["roll_policy_address"] for d in mfacts}),
    )
    for model, model_addresses_set in model_addresses:
        _batch_rows(execution_session, model, model_addresses_set, pinned)
    profiles = [row for row in pinned if isinstance(row, m.AuthorityCapabilityProfile)]
    conformance = {json.loads(row.canonical_json)["fact"]["conformance_evidence_address"]
                   for row in profiles}
    _batch_rows(execution_session, m.AuthorityProviderConformance, conformance, pinned)

    links_by_manifest = {}
    for link in links:
        links_by_manifest.setdefault(link.manifest_address, []).append(link)
    for values in links_by_manifest.values():
        values.sort(key=lambda row: row.ordinal)
    research_maps = {
        ResearchDatasetManifestV2: {row.manifest_address: row for row in manifest_rows},
        ResearchDatasetManifestSegmentV2: links_by_manifest,
        ResearchDatasetSegmentV2: {row.segment_address: row for row in segment_rows},
    }
    rows_by_model={}
    for row in pinned:
        rows_by_model.setdefault(type(row),{})[getattr(row,"address",None)]=row
    execution_maps = {m.AuthorityNormalizedObservationInput: normalized_inputs,
                      "rows_by_model":rows_by_model}
    return (_BatchedTypedSession(research_session, [*manifest_rows, *links, *segment_rows], research_maps),
            _BatchedTypedSession(execution_session, pinned, execution_maps))

def _dependencies(execution_session, manifest, as_of):
    """Typed dependency cutoff verification in addition to existing role closure."""
    loaded = {}
    groups = (
        (manifest.raw_schema_addresses, authorities.load_raw_schema),
        (manifest.normalization_transform_addresses, authorities.load_normalization_transform),
        (manifest.algorithm_addresses, authorities.load_deterministic_algorithm),
        (manifest.creation_evidence_addresses, authorities.load_dataset_creation_evidence),
        (manifest.correction_addresses, authorities.load_dataset_correction),
        (manifest.truth_snapshot_addresses, load_market_truth_snapshot),
        ((manifest.alignment_policy_address,), authorities.load_alignment_policy),
        ((manifest.missing_data_policy_address,), authorities.load_missing_data_policy),
        ((manifest.adjustment_policy_address,), authorities.load_adjustment_policy),
        ((manifest.roll_policy_address,), authorities.load_roll_policy),
    )
    for addresses, loader in groups:
        for address in addresses:
            value = loader(execution_session, address)
            _known(value.recorded_at, as_of)
            loaded[address] = value
    _require(loaded[manifest.adjustment_policy_address].method == "NONE"
             and loaded[manifest.roll_policy_address].method == "NONE"
             and loaded[manifest.roll_policy_address].selection_rule == "NOT_APPLICABLE"
             and loaded[manifest.missing_data_policy_address].handling == "REFUSE")
    for address in manifest.truth_snapshot_addresses:
        truth = loaded[address]
        _known(truth.knowledge_cutoff, as_of)
        _require(truth.authority_scope == "RESEARCH")
        for record in truth.records:
            _known(record.recorded_at, as_of)
    profile = load_capability_profile(execution_session, manifest.capability_profile_address, at_time=as_of)
    conformance = load_provider_conformance(execution_session, profile.conformance_evidence_address)
    _known(profile.observed_at, as_of)
    _known(conformance.observed_to, as_of)
    return loaded


def _normalized_fact(session, reference):
    return (session.normalized_fact(reference) if isinstance(session, _BatchedTypedSession)
            else load_normalized_observation(session, reference))


def _source_facts(session, reference):
    if isinstance(session, _BatchedTypedSession):
        source = session.provider_fact(reference)
        return source, session.raw_fact(source.raw_segment_address), \
            session.alias_fact(source.mapping_address)
    source = load_provider_observation(session, reference)
    return source, load_raw_segment(session, source.raw_segment_address), \
        load_provider_alias(session, source.mapping_address)


def _verify_prior_chain(session, source, as_of):
    prior = source
    while prior.supersedes_address is not None:
        prior, raw, _alias = _source_facts(session, prior.supersedes_address)
        _known(prior.recorded_at, as_of)
        _known(prior.available_at, as_of)
        _known(raw.recorded_at, as_of)


def _verify_source_identity(source, raw, alias, owner_id, schema, schema_fields,
                            physical, field):
    _require(source.owner_id == owner_id
             and source.provider_product_address == schema.provider_product_address
             and source.provider_contract_address == schema.provider_contract_address
             and source.raw_schema == schema.schema_version
             and raw.raw_schema == schema.schema_version
             and source.field in schema_fields and source.field.upper() == field
             and alias.canonical_instrument_address == physical.address)


def _verified_sources(session, observation, *, owner_id, schema, schema_fields,
                      physical, field, seconds, event, completed, available, as_of):
    seen = set()
    for reference in observation.provider_observation_addresses:
        source, raw, alias = _source_facts(session, reference)
        _verify_source_identity(source, raw, alias, owner_id, schema, schema_fields,
                                physical, field)
        _require(source.resolution_seconds == seconds
                 and source.validity is ValidityState.VALID
                 and source.event_time == event and source.completed_at == completed
                 and source.available_at == available)
        _known(source.recorded_at, as_of)
        _known(raw.recorded_at, as_of)
        _known(source.available_at, as_of)
        _verify_prior_chain(session, source, as_of)
        seen.add(reference)
    return seen


def _verify_normalization_lineage(observation, deps, schema, physical, event, completed):
    transform = deps[observation.transform_address]
    algorithm = deps[observation.algorithm_address]
    truth = deps[observation.market_truth_address]
    _require(transform.input_raw_schema_addresses == (schema.address,)
             and transform.output_schema == observation.normalized_schema
             and transform.algorithm_address == observation.algorithm_address
             and observation.algorithm_version == algorithm.version
             and observation.transform_version == "1"
             and physical.address in truth.instrument_addresses
             and truth.effective_from <= event
             and (truth.effective_to is None or completed <= truth.effective_to))


def _normalized_value(session, reference, observation, *, seen, deps, manifest,
                      schema, schema_fields, physical, field, seconds, event,
                      completed, available, owner_id, as_of):
    _require(reference not in seen["normalized"]
             and observation.canonical_instrument_address == physical.address
             and observation.field == field and observation.resolution_seconds == seconds
             and (observation.event_time, observation.completed_at, observation.available_at)
             == (event, completed, available)
             and observation.numeric.state is ValidityState.VALID
             and observation.policy_address == manifest.alignment_policy_address
             and not observation.correction_lineage)
    _known(observation.recorded_at, as_of)
    _known(observation.available_at, as_of)
    _verify_normalization_lineage(observation, deps, schema, physical, event, completed)
    seen["sources"].update(_verified_sources(
        session, observation, owner_id=owner_id, schema=schema,
        schema_fields=schema_fields, physical=physical, field=field, seconds=seconds,
        event=event, completed=completed, available=available, as_of=as_of))
    seen["normalized"].add(reference)
    seen["transforms"].add(observation.transform_address)
    seen["algorithms"].add(observation.algorithm_address)
    seen["truth"].add(observation.market_truth_address)
    return market_float(observation.numeric.value, field=field)


def _load_index_row(session, references, row_fields, *, seen, deps, manifest,
                    schema, physical, seconds, expected_event, imported, owner_id, as_of,
                    expected_bar=None):
    observations = [_normalized_fact(session, reference) for reference in references]
    first = observations[0]
    event, completed = (_instant(getattr(first, name))
        for name in ("event_time", "completed_at"))
    available = _observed_instant(first.available_at)
    expected_event = _validated_row_clock(
        event, completed, available, expected_event, seconds,
        deps[manifest.alignment_policy_address].timezone, imported, expected_bar)
    schema_fields = dict(schema.fields)
    numbers = {field: _normalized_value(
        session, reference, observation, seen=seen, deps=deps, manifest=manifest,
        schema=schema, schema_fields=schema_fields, physical=physical, field=field,
        seconds=seconds, event=event, completed=completed, available=available,
        owner_id=owner_id, as_of=as_of)
        for field, reference, observation in zip(
            row_fields, references, observations, strict=True)}
    return _canonical_candle(event, numbers), expected_event, available


def _segment_index(segment, payload, *, physical, manifest, row_start, resolution):
    _require(segment.media_type == "application/json")
    index = decode_observation_index(payload)
    seconds = index["resolution_seconds"]
    fields = tuple(index["fields"])
    resolution = seconds if resolution is None else resolution
    _require((seconds, index["instrument_address"], segment.instrument_addresses)
             == (resolution, physical.address, (physical.address,))
             and tuple(sorted(fields)) == segment.fields == manifest.fields
             and segment.row_start == row_start
             and segment.row_end - segment.row_start == len(index["rows"]))
    references = [reference for row in index["rows"] for reference in row]
    _require(len(references) == len(set(references))
             and set(references) == set(segment.normalized_observation_addresses))
    return index, seconds, fields, resolution


def _verify_segment_dependencies(segment, manifest, deps, seen):
    seen["algorithms"].update(deps[reference].algorithm_address for reference in (
        manifest.alignment_policy_address, manifest.missing_data_policy_address,
        manifest.adjustment_policy_address, manifest.roll_policy_address,
        segment.creation_evidence_address, *segment.correction_addresses))
    _require(seen["normalized"] == set(segment.normalized_observation_addresses)
             and seen["sources"] == set(segment.provider_observation_addresses)
             and seen["transforms"] == set(segment.normalization_transform_addresses)
             and seen["algorithms"] == set(segment.algorithm_addresses)
             and seen["truth"].issubset(manifest.truth_snapshot_addresses))


def _finish_segment(segment, *, manifest, deps, seen, candles, first, seconds,
                    source_availability, imported, completed_end=None):
    creation = deps[segment.creation_evidence_address]
    _verify_segment_dependencies(segment, manifest, deps, seen)
    start = candles[first].ts
    end = completed_end if completed_end is not None else candles[-1].ts + dt.timedelta(seconds=seconds)
    available = source_availability[first:]
    _require(_instant(segment.event_start) == start and _instant(segment.event_end) == end
             and _availability_matches(
                 _observed_instant(segment.availability_start), _observed_instant(segment.availability_end),
                 available, start, end, seconds, imported)
             and set(creation.source_addresses) == seen["sources"] | seen["normalized"])
    return {"segment_address": segment.segment_address, "object_address": segment.object_address,
        "byte_digest": segment.byte_digest, "byte_length": segment.byte_length,
        "raw_schema_address": segment.raw_schema_address, "row_start": segment.row_start,
        "row_end": segment.row_end}


def _ordered_segments(authority):
    by_start = {}
    for segment, payload in zip(authority.segments, authority.object_bytes, strict=True):
        _require(segment.row_start not in by_start)
        by_start[segment.row_start] = (segment, payload)
    return by_start


def _canonical_asset_requirements(physical, observed_availability):
    _require((physical.asset_class == "EQUITY"
              or (observed_availability and physical.asset_class == "INDEX"))
             and (physical.contract_kind, physical.currency) == ("SPOT", "INR")
             and physical.venue_code in {"XNSE", "XBOM"})


def _dataset_dependencies(execution_session, m, as_of):
    _require(m.mode == "RESEARCH" and len(m.instrument_addresses) == 1
             and m.fields in FIELD_SETS and not m.gaps)
    _known(m.created_at, as_of)
    _known(m.recorded_at, as_of)
    from research.data.provider_capture import PURPOSE
    from research.data.historical_capture import PURPOSE as HISTORICAL_PURPOSE
    current = m.purpose.startswith(PURPOSE)
    historical = m.purpose.startswith(HISTORICAL_PURPOSE)
    # The one-second exclusive availability bound is not a future observation.
    _known(m.availability_start if current or historical else m.availability_end, as_of)
    deps = _dependencies(execution_session, m, as_of)
    physical = load_canonical_instrument(execution_session, m.instrument_addresses[0])
    imported = m.purpose.startswith("user-supplied-personal-research:") or current or historical
    _canonical_asset_requirements(physical, imported)
    return deps, physical, imported


def _verify_loaded_candles(m, candles, expected_event, source_availability, resolution, imported):
    _require(candles and _instant(m.event_start) == candles[0].ts
             and _instant(m.event_end) == expected_event
             and _availability_matches(
                 _observed_instant(m.availability_start), _observed_instant(m.availability_end),
                 source_availability, candles[0].ts, expected_event, resolution, imported))
    _, report = validate_candles(candles)
    _require(report.clean and report.kept == len(candles))


def _imported_session_binding(session, manifest, deps, candles, alignment, as_of):
    if alignment.calendar != "USER_DECLARED_DATE_LABEL":
        return None
    from research.data.imported_sessions import SCHEMA, validate_sessions
    sources = []
    for truth_address in manifest.truth_snapshot_addresses:
        for address in deps[truth_address].source_evidence:
            raw = load_raw_segment(session, address)
            _require(raw.owner_id == manifest.owner_id
                     and raw.product_address in manifest.provider_product_addresses
                     and raw.contract_address in manifest.provider_contract_addresses)
            _known(raw.recorded_at, as_of)
            if raw.raw_schema == SCHEMA:
                _require(raw.media_type == "application/json")
                document = validate_sessions(raw.payload,
                    labels=[candle.ts for candle in candles], timezone=alignment.timezone)
                sources.append({"source_address": raw.address, "document": document})
    _require(len(sources) <= 1)
    return sources[0] if sources else None


def _dated_calendar_rows(execution_session, manifest, deps, physical, as_of):
    from research.data.dated_session_binding import CALENDAR, load_dated_session_binding
    from app.market_truth.dated_sessions import expected_bars
    alignment = deps[manifest.alignment_policy_address]
    if alignment.calendar != CALENDAR:
        return None, None
    _require(len(manifest.provider_product_addresses) == len(manifest.provider_contract_addresses) == 1)
    binding = load_dated_session_binding(execution_session, owner_id=manifest.owner_id,
        alignment=alignment, instrument=physical, product_address=manifest.provider_product_addresses[0],
        contract_address=manifest.provider_contract_addresses[0], as_of=as_of)
    if binding is None:
        return None, None
    rows = expected_bars(binding.calendar, requested_start=_instant(manifest.event_start),
        requested_end=_instant(manifest.event_end) - dt.timedelta(seconds=1),
        resolution_seconds=alignment.resolution_seconds, cutoff_at=as_of)
    _require(bool(rows))
    return binding, rows


def _expected_dated_bar(rows, position):
    if rows is None:
        return None
    _require(position < len(rows))
    return rows[position]


def _bind_dated_provenance(binding, dated_binding):
    if dated_binding is not None:
        binding["dated_sessions"] = dated_binding.metadata()
        binding["time_interpretation"].update(
            completed_at="declared_session_bar_completion",
            evaluation_at="declared_session_bar_completion")


def _load_one(session, execution_session, owner_id, address, as_of):
    authority = load_verified_dataset_authority(session, owner_id=owner_id,
        manifest_address=address, execution_session=execution_session, at_time=as_of)
    m = authority.manifest
    if isinstance(execution_session,_BatchedTypedSession):
        execution_session.mark_verified(m)
    deps, physical, imported = _dataset_dependencies(execution_session, m, as_of)
    dated_binding, dated_rows = _dated_calendar_rows(execution_session, m, deps, physical, as_of)
    venue = {"XNSE": "NSE", "XBOM": "BSE"}[physical.venue_code]
    key = instrument_key(physical.address)
    instrument = Instrument(key, physical.address, venue, "", "", "", 1, 0.0, 0,
                            0.0, 0.0, has_options=False, source="canonical_dataset")
    candles, bindings = [], []
    expected_event = None
    resolution = None
    source_availability = []
    by_start = _ordered_segments(authority)
    while by_start:
        _require(len(candles) in by_start)
        segment, payload = by_start.pop(len(candles))
        index, seconds, row_fields, resolution = _segment_index(
            segment, payload, physical=physical, manifest=m,
            row_start=len(candles), resolution=resolution)
        alignment = deps[m.alignment_policy_address]
        _require(alignment.resolution_seconds == seconds)
        schema = deps[segment.raw_schema_address]
        _require(segment.provider_product_addresses == (schema.provider_product_address,)
                 and segment.provider_contract_addresses == (schema.provider_contract_address,))
        seen = {name: set() for name in (
            "normalized", "sources", "transforms", "algorithms", "truth")}
        first = len(candles)
        for references in index["rows"]:
            candle, expected_event, available = _load_index_row(
                execution_session, references, row_fields, seen=seen, deps=deps,
                manifest=m, schema=schema, physical=physical, seconds=seconds,
                expected_event=expected_event, imported=imported,
                owner_id=owner_id, as_of=as_of,
                expected_bar=_expected_dated_bar(dated_rows, len(candles)))
            source_availability.append(available)
            candles.append(candle)
        bindings.append(_finish_segment(
            segment, manifest=m, deps=deps, seen=seen, candles=candles, first=first,
            seconds=seconds, source_availability=source_availability, imported=imported,
            completed_end=expected_event))
    _require(dated_rows is None or len(candles) == len(dated_rows))
    _verify_loaded_candles(m, candles, expected_event, source_availability, resolution, imported)
    from research.data.provider_capture import load_current_capture_binding
    capture = load_current_capture_binding(execution_session, m, deps, candles, as_of)
    from research.data.historical_capture import load_historical_capture_binding
    historical = load_historical_capture_binding(execution_session, m, deps, candles, as_of)
    binding = {"manifest_address": address, "instrument_address": physical.address,
        "instrument": physical.fact(), "as_of": as_of.isoformat(), "segments": bindings,
        "authority_manifest": m.fact(),
        "time_interpretation": _time_interpretation(
            resolution, alignment, source_availability, expected_event, capture, historical),
        "projection": _research_projection(physical, venue),
        "session_metadata": _imported_session_binding(
            execution_session, m, deps, candles, alignment, as_of)}
    if capture is not None:
        binding["current_capture"] = capture
    if historical is not None:
        binding["historical_capture"] = historical
    _bind_dated_provenance(binding, dated_binding)
    return instrument, CanonicalDataset(key, INTERVALS[resolution], 0, len(candles),
        int(candles[0].ts.timestamp()), int(candles[-1].ts.timestamp()), address,
        tuple(candles), canonical_json(binding), binding, authority, alignment, dated_binding)


def load_canonical_datasets(session, *, execution_session, owner_id, selections, now=None):
    """Reload only owner-scoped manifests; no client-supplied provenance accepted."""
    try:
        _require(0 < len(selections) <= MAX_MANIFESTS)
        addresses = [_address(item.manifest_address) for item in selections]
        _require(len(set(addresses)) == len(addresses))
        times = {_instant(item.as_of) for item in selections}
        _require(len(times) == 1)
        as_of = times.pop()
        _require(as_of <= (now or dt.datetime.now(UTC)))
        typed_research, typed_execution = _authority_batch_plan(
            session, execution_session, owner_id, addresses)
        datasets = [_load_one(typed_research,typed_execution,owner_id,address,as_of)
                    for address in addresses]
        _require(len({data.instrument_key for _, data in datasets}) == len(datasets)
                 and len({data.interval for _, data in datasets}) == 1)
        return datasets
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        raise CanonicalDatasetRefused() from None


def _projection_input_count(dataset, fields):
    return isinstance(fields, dict) and (len(fields) == 1 or (
        len(fields) == 2 and "session" in fields and dataset.binding.get("session_metadata")))


def _projection_authority(dataset, owner_id, graph_input_fields):
    _require(isinstance(dataset, CanonicalDataset)
             and dataset._verified_authority is not None
             and dataset._alignment_fact is not None)
    authority = dataset._verified_authority
    manifest = authority.manifest
    _require(manifest.owner_id == owner_id and manifest.mode == "RESEARCH"
             and manifest.manifest_address == dataset.content_hash
             and len(manifest.instrument_addresses) == 1
             and _projection_input_count(dataset, graph_input_fields))
    return authority, manifest, dataset._alignment_fact


def _projection_indexes(dataset, resolution):
    capture = dataset.binding.get("current_capture")
    times = ([dt.datetime.fromisoformat(capture["captured_at"])] if capture is not None else
             [candle.ts + dt.timedelta(seconds=resolution) for candle in dataset.candles])
    if dataset._dated_session_binding is not None:
        from app.market_truth.dated_sessions import completion_for
        times = [completion_for(dataset._dated_session_binding.calendar, candle.ts, resolution)
                 for candle in dataset.candles]
    available = pd.DatetimeIndex(times)
    opened = pd.DatetimeIndex([candle.ts for candle in dataset.candles])
    _require(available.tz is not None and available.is_unique
             and available.is_monotonic_increasing and len(available) == dataset.bar_count)
    return available, opened


def _selected_projection_fields(requested, allowed):
    fields = tuple(sorted(set(requested)))
    _require(len(fields) == len(requested)
             and all(isinstance(field, str) and field in allowed for field in fields))
    return fields


def _projection_fields(manifest, requested_fields, session_metadata=None):
    normalized = {}
    for input_name, requested in sorted(requested_fields.items()):
        _require(isinstance(input_name, str) and input_name
                 and isinstance(requested, (tuple, list)) and requested)
        from research.data.imported_sessions import FIELDS as SESSION_FIELDS
        allowed = SESSION_FIELDS if input_name == "session" and session_metadata else manifest.fields
        normalized[input_name] = _selected_projection_fields(requested, allowed)
    return normalized


def _projection_contexts(dataset, manifest, alignment, available, opened, evaluation_freshness_seconds=None):
    dataset_context = content_address({
        "schema": "verified-observation-dataset-context/1",
        "dataset_manifest_address": manifest.manifest_address,
        "availability_index": [item.isoformat() for item in available],
        "bar_open_position_map": [item.isoformat() for item in opened],
        "session_metadata": dataset.binding.get("session_metadata"),
        **({"dated_sessions": dataset.binding["dated_sessions"]} if dataset.binding.get("dated_sessions") else {}),
        **({"current_capture": dataset.binding["current_capture"]} if dataset.binding.get("current_capture") else {}),
        "retrospective_evaluation": dataset._provenance_binding[
            "time_interpretation"].get("retrospective_evaluation", False),
        "actual_source_observed_at": dataset._provenance_binding[
            "time_interpretation"].get("actual_source_observed_at"),
    })
    evaluation_context = content_address({
        "schema": "verified-observation-evaluation-context/1",
        "alignment_policy_address": manifest.alignment_policy_address,
        "missing_data_policy_address": manifest.missing_data_policy_address,
        "adjustment_policy_address": manifest.adjustment_policy_address,
        "session": alignment.session, "calendar": alignment.calendar,
        "timezone": alignment.timezone, "resolution_seconds": alignment.resolution_seconds,
        **({"evaluation_freshness_seconds": evaluation_freshness_seconds}
            if evaluation_freshness_seconds is not None else {}),
        "resampling": "NONE",
    })
    return dataset_context, evaluation_context


def _projected_series(selected, values, session_metadata, derived, available):
    source = ({field: [row[field.lower()] for row in session_metadata["document"]["rows"]]
               for field in selected} if derived else values)
    return {field.lower(): pd.Series(source[field], index=available,
        dtype=object if derived else float) for field in selected}


def _projection_payloads(dataset, owner_id, manifest, alignment, fields, available,
                         dataset_context, evaluation_context, freshness_seconds):
    values = {field: [getattr(candle, field.lower()) for candle in dataset.candles]
              for field in FIELDS}
    inputs, facts = {}, {}
    session_metadata = dataset.binding.get("session_metadata")
    for input_name, selected in fields.items():
        derived = input_name == "session" and session_metadata is not None
        inputs[input_name] = _projected_series(selected, values, session_metadata, derived, available)
        facts[input_name] = {
            "schema": "canonical-input-binding/1", "owner_id": owner_id,
            "dataset_context_address": dataset_context,
            "evaluation_context_address": evaluation_context,
            "dataset_manifest_address": manifest.manifest_address,
            "market_truth_address": manifest.truth_snapshot_addresses[0],
            "provider_product_address": manifest.provider_product_addresses[0],
            "provider_contract_address": manifest.provider_contract_addresses[0],
            "canonical_instrument_address": manifest.instrument_addresses[0],
            "instrument": {"role": "primary" if input_name == "frame" else input_name,
                           "type": "PHYSICAL"},
            "timeframe": alignment.resolution_seconds, "fields": list(selected),
            "freshness": {"maximum_age_seconds": freshness_seconds},
            "depth": {"kind": "NONE", "levels": None},
            "session": "INSTRUMENT_CALENDAR" if session_metadata else _research_session(alignment),
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
            "derived_local": derived,
        }
    return inputs, facts


def _verified_projection(authority, manifest, alignment, owner_id, inputs, facts,
                         available, opened, dataset_context, evaluation_context):
    _require(len(manifest.truth_snapshot_addresses) == 1
             and len(manifest.provider_product_addresses) == 1
             and len(manifest.provider_contract_addresses) == 1)
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    bindings = canonical_input_bindings(
        owner_id=owner_id, dataset_context_address=dataset_context,
        evaluation_context_address=evaluation_context, bindings=facts,
        expected_source_addresses={name: content_address(fact) for name, fact in facts.items()})
    from research.evaluation.phase5_runtime import _verify_canonical_observation_projection
    segments = {segment.segment_address: (segment, payload)
        for segment, payload in zip(authority.segments, authority.object_bytes, strict=True)}
    result = _verify_canonical_observation_projection(
        manifest, segments, inputs, bindings,
        availability_index=available, bar_open_index=opened,
        session_policy_address=content_address({
            "schema": "canonical-session-policy/1", "calendar": alignment.calendar,
            "session": alignment.session, "timezone": alignment.timezone}),
        resampling_policy_address=content_address({
            "schema": "canonical-resampling-policy/1", "method": "NONE",
            "resolution_seconds": alignment.resolution_seconds}))
    return _projection_codec(result, alignment)


def project_verified_research_inputs(
    dataset: CanonicalDataset, *, owner_id: str,
    graph_input_fields: dict[str, tuple[str, ...] | list[str]],
    evaluation_freshness_seconds: int | None = None,
):
    """Bind verified rows and an optional explicit completed-bar evaluation age.

    The age is a consumer limit, not acquisition latency or provider authority.
    It enters the canonical evaluation context; source receipts stay unchanged.
    """
    try:
        authority, manifest, alignment = _projection_authority(
            dataset, owner_id, graph_input_fields)
        freshness = _projection_freshness(dataset, evaluation_freshness_seconds)
        available, opened = _projection_indexes(dataset, alignment.resolution_seconds)
        fields = _projection_fields(manifest, graph_input_fields, dataset.binding.get("session_metadata"))
        dataset_context, evaluation_context = _projection_contexts(
            dataset, manifest, alignment, available, opened, evaluation_freshness_seconds)
        inputs, facts = _projection_payloads(
            dataset, owner_id, manifest, alignment, fields, available,
            dataset_context, evaluation_context, freshness)
        result = _verified_projection(
            authority, manifest, alignment, owner_id, inputs, facts, available, opened,
            dataset_context, evaluation_context)
        object.__setattr__(result, "source_provenance_json", dataset.binding_json)
        object.__setattr__(result, "source_provenance_address", content_address(dataset.binding))
        return result
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        raise CanonicalDatasetRefused() from None


def project_verified_research_input_set(
    datasets: dict[str, CanonicalDataset], *, owner_id: str, primary_input: str,
    graph_input_fields: dict[str, tuple[str, ...] | list[str]],
):
    """Bind separately verified instruments on an exact completed-bar clock."""
    try:
        _require(isinstance(datasets, dict) and 2 <= len(datasets) <= MAX_MANIFESTS)
        _require(isinstance(graph_input_fields, dict)
                 and set(datasets) == set(graph_input_fields) and primary_input in datasets)
        times = {_instant(data.binding["as_of"]) for data in datasets.values()}
        _require(len(times) == 1)
        sources = {name: project_verified_research_inputs(
            data, owner_id=owner_id, graph_input_fields={"frame": graph_input_fields[name]})
            for name, data in sorted(datasets.items())}
        from research.evaluation.phase5_runtime import _verify_observation_input_set
        return _verify_observation_input_set(
            sources, owner_id=owner_id, primary_input=primary_input,
            as_of=times.pop().isoformat())
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        raise CanonicalDatasetRefused() from None


def _canonical_dataset_requirements(strategy, instrument, data):
    available_fields = set(data._verified_authority.manifest.fields)
    _require(data.bar_count >= max(57, strategy.declared_warmup + 1)
             and instrument.key == data.instrument_key
             and {field.upper() for field in strategy.required_inputs}.issubset(available_fields))
    binding = data._provenance_binding
    _require(binding["projection"] is not None
             and binding["projection"] == _simulation_projection(instrument.segment))
    return binding


def _canonical_node_requirements(strategy, binding):
    seconds = binding["time_interpretation"]["resolution_seconds"]
    timeframe = "day" if seconds == 86_400 else f"{seconds//60}m"
    for node in strategy.resolved.nodes:
        _require(node.causal is not None and not node.causal.context_inputs
                 and node.causal.input_bar == "completed" and node.purity == "pure")
        domain = node.domain or {}
        _require(domain.get("instrument", "*") in {"*", binding["instrument_address"]}
                 and domain.get("timeframe", "*") in {"*", timeframe})


def canonical_provenance(strategy, datasets):
    """Refuse unsupported resolved runtime requirements before graph evaluation."""
    _require(strategy.resolved.format_version == 1
             and set(strategy.required_inputs).issubset(f.lower() for f in FIELDS)
             and not hasattr(strategy, "composition"))
    for instrument, data in datasets:
        # Existing simulate() uses its legacy 50+5+2 entry gate even for an IR
        # strategy. Refuse insufficient data before it can become silent zeros.
        binding = _canonical_dataset_requirements(strategy, instrument, data)
        _canonical_node_requirements(strategy, binding)
    codecs = {CODEC_V2 if data.binding["time_interpretation"]["retrospective_evaluation"]
              else CODEC for _, data in datasets}
    _require(len(codecs) == 1)
    return {"schema": "canonical-dataset-bindings/1", "codec": codecs.pop(),
        "adapter_contract": "q03-provider-provenance-index-encoding/1",
        "adapter_source_address": content_address({"source": Path(__file__).read_text()}),
        "bindings": {data.instrument_key: data.binding for _, data in datasets}}
