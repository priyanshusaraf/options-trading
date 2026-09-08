"""Internal single-bar capture publication through existing canonical authorities.

The bytes are injected by a trusted capture caller. This module neither calls
the DATA facade nor reads its credentials.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.backtest.dataset_store import DatasetManifest, DatasetSegment, dataset_byte_digest
from app.db.concurrency import caller_owned_savepoint
from app.db.models import BrokerConnection, Project
from app.ir.hashing import content_address
from app.ir.validity import valid
from app.market_data import dataset_authority as authority
from app.market_data.authority import load_capability_profile, load_provider_conformance
from app.market_data.capability import _offer_complete, _offer_matches
from app.market_data.kite_observations import KiteMappingContext, map_historical_candles
from app.market_data.numeric import market_float
from app.market_data.observations import (
    NormalizedMarketObservation, RawObservationSegment, load_raw_segment,
    persist_normalized_observation, persist_provider_observation, persist_raw_segment,
)
from app.market_truth.authority import load_market_truth_snapshot
from app.market_truth.identity import load_canonical_instrument, load_provider_alias, load_provider_identity
from app.providers.connection_store import ConnectionNotFound, DataConnectionUnavailable, OwnedConnectionStore
from research.domain.strategy_admissions import persist_verified_dataset_authority

PURPOSE = "current-data-capture:"
PRODUCER = "current-kite-capture/1"
FIELDS = ("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME")
MAX_BYTES = 1024 * 1024
UTC = dt.timezone.utc
_NORMALIZATION_VECTOR = (("2000-01-01T00:00:00Z", 100, 102, 99, 101, 1234),
                         (100.0, 102.0, 99.0, 101.0, 1234.0))


class CurrentCaptureRefused(ValueError):
    def __init__(self, code="CURRENT_CAPTURE_UNAVAILABLE", message="Current captured data or its authority is unavailable."):
        self.code = code
        super().__init__(message)


def _require(condition, code="CURRENT_CAPTURE_UNAVAILABLE", message="Current captured data or its authority is unavailable."):
    if not condition:
        raise CurrentCaptureRefused(code, message)


def _capture_time(value):
    _require(type(value) is dt.datetime and value.tzinfo is not None
             and value.utcoffset() == dt.timedelta(0))
    return value


def _time(value):
    value = _capture_time(value)
    _require(value.microsecond == 0)
    return value


def _connection(session, owner_id, project_id, connection_id, *, lock=False):
    _require(type(connection_id) is int and connection_id > 0)
    project = session.scalar(select(Project.project_id).where(
        Project.project_id == project_id, Project.owner_id == owner_id, Project.status == "active"))
    statement = select(BrokerConnection).where(
        BrokerConnection.id == connection_id, BrokerConnection.owner_id == owner_id)
    if lock:
        statement = statement.with_for_update()
    row = session.scalar(statement.execution_options(populate_existing=True))
    _require(project is not None and row is not None)
    store = OwnedConnectionStore.for_data_role(session, owner_id=owner_id,
        broker_account_id=row.broker_account_id)
    try:
        return store.require_data_connection(connection_id)
    except (ConnectionNotFound, DataConnectionUnavailable):
        raise CurrentCaptureRefused() from None


def _context(session, owner_id, context):
    _require(type(context) is KiteMappingContext and context.owner_id == owner_id)
    entity, product, contract = load_provider_identity(session, context.provider_contract_address)
    physical = load_canonical_instrument(session, context.canonical_instrument.address)
    alias = load_provider_alias(session, context.mapping.address)
    loaded = KiteMappingContext(owner_id, entity.address, product.address, contract.address,
        alias, physical, context.mapping_authority)
    _require(loaded == context and entity.entity_code == "kite" and contract.owner_id == owner_id
             and contract.mode == "RESEARCH" and "HISTORICAL" in contract.permitted_uses)
    _require((physical.contract_kind, physical.currency) == ("SPOT", "INR")
             and physical.asset_class in {"EQUITY", "INDEX"} and physical.venue_code in {"XNSE", "XBOM"})
    return loaded, contract


def _policies(session, owner_id, addresses, as_of, *, historical=False):
    loaders = (authority.load_alignment_policy, authority.load_missing_data_policy,
               authority.load_adjustment_policy, authority.load_roll_policy)
    values = tuple(loader(session, address) for loader, address in zip(loaders, addresses, strict=True))
    _require(all(value.owner_id == owner_id and _capture_time(value.recorded_at) <= as_of for value in values))
    alignment, missing, adjustment, roll = values
    resolutions = {900, 1800, 3600, 86400} if historical else {900, 1800, 3600}
    _require(alignment.resolution_seconds in resolutions
             and alignment.calendar != "USER_DECLARED_DATE_LABEL")
    _require(missing.handling == "REFUSE" and adjustment.method == roll.method == "NONE"
             and roll.selection_rule == "NOT_APPLICABLE")
    return values


def _profile(session, owner_id, address, context, as_of):
    profile = load_capability_profile(session, address, at_time=as_of)
    _require(profile.owner_id == owner_id and profile.mode == "RESEARCH"
             and profile.provider_product_address == context.provider_product_address
             and profile.provider_contract_address == context.provider_contract_address
             and profile.provider_entity_address == context.provider_entity_address)
    conformance = load_provider_conformance(session, profile.conformance_evidence_address)
    _require(conformance.observed_to <= as_of and profile.change_level in {0, 1})
    return profile


def _unique_object(pairs):
    result = dict(pairs)
    _require(len(result) == len(pairs))
    return result


def _payload(raw):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES)
    document = json.loads(raw, object_pairs_hook=_unique_object)
    rows = document["data"]["candles"]
    _require(type(rows) is list and len(rows) == 1 and type(rows[0]) is list and len(rows[0]) == 6,
             "CURRENT_CAPTURE_SINGLE_BAR_REQUIRED", "Supply exactly one completed OHLCV bar; historical warmup is separate.")
    return document


def _fresh(batch, maximum_age_seconds, resolution, as_of):
    _require(type(maximum_age_seconds) is int and 0 <= maximum_age_seconds <= resolution)
    first = batch.observations[0]
    _time(first.event_time); _time(first.completed_at)
    _require(0 <= (as_of - first.completed_at).total_seconds() <= maximum_age_seconds,
             "CURRENT_CAPTURE_STALE", "The captured bar exceeds the current-data age limit. Capture a new completed bar.")
    return first


def _covered(profile, field, first, maximum_age_seconds, resolution, *, minimum_bars=1, last=None,
             session_policy="INSTRUMENT_CALENDAR"):
    requirement = {"instrument": {"role": "primary", "type": "PHYSICAL"}, "field": field,
        "timeframe": resolution, "history": {"minimum_bars": minimum_bars, "warmup_bars": 0},
        "freshness": {"maximum_age_seconds": maximum_age_seconds}, "depth": {"kind": "NONE", "levels": None},
        "session": session_policy, "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False}
    return any(_offer_matches(offer, requirement) and _offer_complete(offer, requirement)
        and dt.datetime.fromisoformat(offer["available_from"]) <= first.event_time
        and dt.datetime.fromisoformat(offer["available_to"]) >= (last or first).completed_at for offer in profile.offers)


def _truth(session, context, policies, first, as_of):
    alignment, _, adjustment, roll = policies
    truth = load_market_truth_snapshot(session, alignment.truth_snapshot_address)
    _require(truth.authority_scope == "RESEARCH" and truth.recorded_at <= as_of
             and truth.knowledge_cutoff <= as_of and context.canonical_instrument.address in truth.instrument_addresses)
    _require(truth.effective_from <= first.event_time
             and (truth.effective_to is None or first.completed_at <= truth.effective_to))
    for policy in (adjustment, roll):
        _require(policy.instrument_addresses == (context.canonical_instrument.address,)
                 and policy.truth_snapshot_addresses == (truth.address,))
    return truth


def _connection_clock(connection, captured_at, as_of):
    _require(connection.last_authenticated_at is not None)
    authenticated = connection.last_authenticated_at.replace(tzinfo=UTC)
    created = connection.created_at.replace(tzinfo=UTC)
    updated = connection.updated_at.replace(tzinfo=UTC)
    _require(created <= authenticated <= captured_at and updated <= as_of)


def _unrevised_sources(session, context, batch):
    from app.db.models import AuthorityProviderObservation
    expected = {item.correction_id: item.address for item in batch.observations}
    rows = session.scalars(select(AuthorityProviderObservation).where(
        AuthorityProviderObservation.owner_id == context.owner_id,
        AuthorityProviderObservation.product_address == context.provider_product_address,
        AuthorityProviderObservation.correction_id.in_(expected))).all()
    _require(all(row.address == expected[row.correction_id] for row in rows),
        "CURRENT_CAPTURE_EVENT_ALREADY_RECORDED",
        "This completed bar already has a captured record. Use its saved dataset or capture a newer bar; revisions require explicit lineage.")


def _capture_facts(session, owner_id, project_id, connection_id, raw_response, context,
                   policy_addresses, capability_profile_address, captured_at, recorded_at, as_of, maximum_age_seconds):
    captured_at, recorded_at, as_of = map(_capture_time, (captured_at, recorded_at, as_of))
    connection = _connection(session, owner_id, project_id, connection_id)
    _connection_clock(connection, captured_at, as_of)
    context, contract = _context(session, owner_id, context)
    _require(context.mapping_authority in {"CURRENT_DUMP", "CAPTURED_POINT_IN_TIME"},
             "CURRENT_CAPTURE_HISTORICAL_CONTEXT",
             "Retrospective history cannot supply a current monitoring capture. Fetch a current completed bar with current source authority.")
    policies = _policies(session, owner_id, policy_addresses, as_of)
    profile = _profile(session, owner_id, capability_profile_address, context, as_of)
    document = _payload(raw_response)
    resolution = policies[0].resolution_seconds
    batch = map_historical_candles(document, context=context, resolution_seconds=resolution,
        available_at=captured_at, recorded_at=recorded_at, as_of=as_of)
    first = _fresh(batch, maximum_age_seconds, resolution, as_of)
    _unrevised_sources(session, context, batch)
    _require(contract.effective_from <= first.event_time
             and (context.mapping.effective_to is None or first.completed_at <= context.mapping.effective_to))
    _require(all(_covered(profile, field, first, maximum_age_seconds, resolution) for field in FIELDS),
             "CURRENT_CAPTURE_CAPABILITY_UNAVAILABLE", "Verified provider coverage for this completed bar is unavailable.")
    truth = _truth(session, context, policies, first, as_of)
    raw = RawObservationSegment(owner_id, context.provider_product_address, context.provider_contract_address,
        "application/json", "kite-historical-candle/3", raw_response, recorded_at)
    return context, policies, profile, truth, document, batch, raw


def _normalization_facts(owner_id, context, raw, parameters, producer, source, *, observation_schema=None):
    algorithm = authority.DeterministicAlgorithm(owner_id, producer, "1",
        content_address({"source": source}),
        (content_address({"input": _NORMALIZATION_VECTOR[0], "expected": _NORMALIZATION_VECTOR[1]}),), raw.recorded_at)
    schema = authority.RawSchema(owner_id, context.provider_product_address, context.provider_contract_address,
        raw.raw_schema if observation_schema is None else observation_schema,
        tuple(sorted((field.lower(), "number") for field in FIELDS)), raw.address, raw.recorded_at)
    transform = authority.NormalizationTransform(owner_id, (schema.address,), "strategy-bar/1",
        tuple(sorted(parameters.items())), algorithm.address, raw.recorded_at)
    return algorithm, schema, transform


def _normalization(owner_id, context, raw, connection_id, maximum_age_seconds, captured_at):
    parameters = {"capture_address": raw.address, "connection_id": str(connection_id),
        "maximum_age_seconds": str(maximum_age_seconds), "captured_at": captured_at.isoformat(),
        "mapping_authority": context.mapping_authority}
    return _normalization_facts(owner_id, context, raw, parameters, PRODUCER, Path(__file__).read_text())


def _numeric_values(row):
    return tuple(market_float(value, field=field) for field, value in zip(FIELDS, row[1:], strict=True))


def _normalized(context, policies, truth, document, batch, algorithm, transform):
    result = []
    numbers = (number for row in document["data"]["candles"] for number in _numeric_values(row))
    for source, number in zip(batch.observations, numbers, strict=True):
        result.append(NormalizedMarketObservation(context.canonical_instrument.address, (source.address,),
            transform.address, "1", policies[0].address, algorithm.address, "1", truth.address,
            transform.output_schema, source.field.upper(), source.resolution_seconds, source.event_time, source.completed_at,
            source.available_at, source.recorded_at, valid(number)))
    return tuple(result)


def _algorithms(session, owner_id, policies, algorithm, as_of):
    addresses = {policy.algorithm_address for policy in policies}
    for address in addresses:
        fact = authority.load_deterministic_algorithm(session, address)
        _require(fact.owner_id == owner_id and _capture_time(fact.recorded_at) <= as_of)
    return tuple(sorted(addresses | {algorithm.address}))


def _dataset(context, project_id, policies, profile, truth, batch, normalized, schema, transform, algorithms, creation,
             *, purpose=PURPOSE):
    from research.data.canonical_dataset import encode_observation_index
    first = batch.observations[0]
    row_count = len(normalized) // len(FIELDS)
    index = encode_observation_index(context.canonical_instrument.address, first.resolution_seconds,
        [[item.address for item in normalized[offset:offset + len(FIELDS)]]
         for offset in range(0, len(normalized), len(FIELDS))])
    source_addresses = tuple(sorted(item.address for item in batch.observations))
    normalized_addresses = tuple(sorted(item.address for item in normalized))
    segment = DatasetSegment(owner_id=context.owner_id, object_address=dataset_byte_digest(index),
        byte_digest=dataset_byte_digest(index), byte_length=len(index), media_type="application/json",
        raw_schema_address=schema.address, row_start=0, row_end=row_count,
        instrument_addresses=(context.canonical_instrument.address,), fields=tuple(sorted(FIELDS)),
        event_start=first.event_time.isoformat(), event_end=batch.observations[-1].completed_at.isoformat(),
        availability_start=first.available_at.isoformat(),
        availability_end=(first.available_at + dt.timedelta(seconds=1)).isoformat(),
        provider_product_addresses=(context.provider_product_address,), provider_contract_addresses=(context.provider_contract_address,),
        provider_observation_addresses=source_addresses, normalized_observation_addresses=normalized_addresses,
        normalization_transform_addresses=(transform.address,), algorithm_addresses=algorithms,
        correction_addresses=(), creation_evidence_address=creation.address)
    manifest = DatasetManifest(owner_id=context.owner_id, purpose=purpose + project_id, mode="RESEARCH",
        segment_addresses=(segment.segment_address,), aggregate_byte_digest=dataset_byte_digest(index),
        aggregate_byte_length=len(index), instrument_addresses=segment.instrument_addresses, fields=segment.fields,
        event_start=segment.event_start, event_end=segment.event_end, availability_start=segment.availability_start,
        availability_end=segment.availability_end, gaps=(), correction_addresses=(),
        provider_entity_addresses=(context.provider_entity_address,), provider_product_addresses=segment.provider_product_addresses,
        provider_contract_addresses=segment.provider_contract_addresses, provider_observation_addresses=source_addresses,
        normalized_observation_addresses=normalized_addresses, raw_schema_addresses=(schema.address,),
        normalization_transform_addresses=(transform.address,), truth_snapshot_addresses=(truth.address,),
        creation_evidence_addresses=(creation.address,), capability_profile_address=profile.capability_profile_address,
        alignment_policy_address=policies[0].address, missing_data_policy_address=policies[1].address,
        adjustment_policy_address=policies[2].address, roll_policy_address=policies[3].address,
        algorithm_addresses=algorithms, created_at=first.recorded_at.isoformat(), recorded_at=first.recorded_at.isoformat())
    return manifest, {segment.segment_address: (segment, index)}


def _publish(execution_session, research_session, facts, project_id, connection_id, maximum_age_seconds, captured_at, as_of):
    context, policies, profile, truth, document, batch, raw = facts
    algorithm, schema, transform = _normalization(context.owner_id, context, raw, connection_id, maximum_age_seconds, captured_at)
    algorithms = _algorithms(execution_session, context.owner_id, policies, algorithm, as_of)
    normalized = _normalized(context, policies, truth, document, batch, algorithm, transform)
    creation = authority.DatasetCreationEvidence(context.owner_id, PRODUCER,
        tuple(sorted([item.address for item in (*batch.observations, *normalized)])),
        (raw.address,), algorithm.address, raw.recorded_at)
    manifest, segments = _dataset(context, project_id, policies, profile, truth, batch,
        normalized, schema, transform, algorithms, creation)
    with caller_owned_savepoint(execution_session, scope="current-data-capture"):
        connection = _connection(execution_session, context.owner_id, project_id, connection_id, lock=True)
        _connection_clock(connection, captured_at, as_of)
        return _persist_capture(execution_session, research_session, raw, batch, normalized,
            algorithm, schema, transform, creation, manifest, segments, as_of)


def _persist_capture(execution_session, research_session, raw, batch, normalized,
                     algorithm, schema, transform, creation, manifest, segments, as_of):
    for segment in (raw, *batch.raw_segments):
        persist_raw_segment(execution_session, segment)
    authority.persist_deterministic_algorithm(execution_session, algorithm)
    authority.persist_raw_schema(execution_session, schema)
    authority.persist_normalization_transform(execution_session, transform)
    for observation in batch.observations:
        persist_provider_observation(execution_session, observation)
    for observation in normalized:
        persist_normalized_observation(execution_session, observation)
    authority.persist_dataset_creation_evidence(execution_session, creation)
    return persist_verified_dataset_authority(research_session, manifest=manifest, segments=segments,
        execution_session=execution_session, at_time=as_of)


def publish_current_kite_capture(execution_session, research_session, *, owner_id, project_id,
        connection_id, raw_response: bytes, context: KiteMappingContext, capability_profile_address,
        alignment_policy_address, missing_data_policy_address, adjustment_policy_address, roll_policy_address,
        captured_at: dt.datetime, recorded_at: dt.datetime, as_of: dt.datetime, maximum_age_seconds: int):
    """Publish one internal captured bar; never fetch data, commit, or infer entitlement."""
    try:
        facts = _capture_facts(execution_session, owner_id, project_id, connection_id, raw_response, context,
            (alignment_policy_address, missing_data_policy_address, adjustment_policy_address, roll_policy_address),
            capability_profile_address, captured_at, recorded_at, as_of, maximum_age_seconds)
        return _publish(execution_session, research_session, facts, project_id, connection_id,
            maximum_age_seconds, captured_at, as_of)
    except CurrentCaptureRefused:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError, ConnectionNotFound, DataConnectionUnavailable, IntegrityError):
        raise CurrentCaptureRefused() from None


def _capture_parameters(manifest, deps):
    _require(len(manifest.normalization_transform_addresses) == len(manifest.raw_schema_addresses) == 1)
    transform = deps[manifest.normalization_transform_addresses[0]]
    parameters = dict(transform.parameters)
    _require(set(parameters) == {"capture_address", "connection_id", "maximum_age_seconds", "captured_at", "mapping_authority"})
    _require(transform.output_schema == "strategy-bar/1"
             and transform.input_raw_schema_addresses == manifest.raw_schema_addresses)
    return parameters


def _capture_identity(session, manifest, parameters):
    from app.market_data.observations import load_provider_observation
    source = load_provider_observation(session, manifest.provider_observation_addresses[0])
    return KiteMappingContext(manifest.owner_id, source.provider_entity_address,
        source.provider_product_address, source.provider_contract_address,
        load_provider_alias(session, source.mapping_address),
        load_canonical_instrument(session, manifest.instrument_addresses[0]), parameters["mapping_authority"])


def _capture_manifest_matches(manifest, deps, candles, facts):
    _, _, _, _, document, batch, raw = facts
    first = batch.observations[0]
    _require(manifest.provider_observation_addresses == tuple(sorted(item.address for item in batch.observations)))
    _require(len(candles) == 1 and candles[0].ts == first.event_time)
    actual = tuple(getattr(candles[0], field.lower()) for field in FIELDS)
    expected = _numeric_values(document["data"]["candles"][0])
    _require(actual == expected)
    _require(manifest.availability_start == first.available_at.isoformat()
             and manifest.availability_end == (first.available_at + dt.timedelta(seconds=1)).isoformat()
             and manifest.recorded_at == raw.recorded_at.isoformat())
    schema = deps[manifest.raw_schema_addresses[0]]
    creation = deps[manifest.creation_evidence_addresses[0]]
    _require(schema.evidence_address == raw.address and creation.producer == PRODUCER
             and creation.artifact_addresses == (raw.address,))


def load_current_capture_binding(session, manifest, deps, candles, as_of):
    """Reconstruct capture bytes and recheck current authority before projecting."""
    if not manifest.purpose.startswith(PURPOSE):
        return None
    parameters = _capture_parameters(manifest, deps)
    raw = load_raw_segment(session, parameters["capture_address"])
    context = _capture_identity(session, manifest, parameters)
    captured_at = dt.datetime.fromisoformat(parameters["captured_at"])
    connection_id, maximum_age = int(parameters["connection_id"]), int(parameters["maximum_age_seconds"])
    facts = _capture_facts(session, manifest.owner_id, manifest.purpose[len(PURPOSE):],
        connection_id, raw.payload, context, (manifest.alignment_policy_address,
            manifest.missing_data_policy_address, manifest.adjustment_policy_address, manifest.roll_policy_address),
        manifest.capability_profile_address, captured_at, raw.recorded_at, as_of, maximum_age)
    _require(facts[-1].address == raw.address)
    _capture_manifest_matches(manifest, deps, candles, facts)
    return {"connection_id": connection_id, "raw_capture_address": raw.address,
        "captured_at": captured_at.isoformat(), "recorded_at": raw.recorded_at.isoformat(),
        "completed_at": facts[5].observations[0].completed_at.isoformat(),
        "maximum_age_seconds": maximum_age, "mapping_authority": context.mapping_authority}
