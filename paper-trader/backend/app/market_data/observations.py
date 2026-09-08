"""Immutable, causal market-data observations and explicit alignment."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Any, ClassVar, Iterable, Mapping

from app.ir.hashing import canonical_json
from app.ir.validity import NumericValue, ValidityState
from app.market_data.numeric import NumericIngressError, market_float
from app.market_truth.identity import (CanonicalFact, MarketTruthError, _address,
                                       _closed_text, _parse_envelope, _utc)
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive


_MAX_RAW_SEGMENT_BYTES = 4 * 1024 * 1024
_MAX_OBSERVATION_INPUTS = 64


_observation_pass = ContextVar("observation_pass", default=None)


def _observation_pass_memo(session):
    state = _observation_pass.get()
    return state[1] if state is not None and state[0] is session else None


@contextmanager
def _observation_dependency_rows(session):
    """Retain verified immutable evidence only inside this session validation pass."""
    token = _observation_pass.set((session, {}))
    try:
        with _pinned_observation_rows(session):
            yield
    finally:
        _observation_pass.reset(token)


@contextmanager
def _pinned_observation_rows(session):
    """Keep shared immutable ORM rows alive only while one pass uses them."""
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.db.models import (
        AuthorityCanonicalInstrument, AuthorityProviderAlias, AuthorityProviderContract,
        AuthorityProviderEntity, AuthorityProviderProduct, AuthorityRawSegment,
    )
    # Canonical batch facades already pin their rows and are not event targets.
    if not isinstance(session, Session):
        yield
        return
    shared = (AuthorityCanonicalInstrument, AuthorityProviderAlias, AuthorityProviderContract,
              AuthorityProviderEntity, AuthorityProviderProduct, AuthorityRawSegment)
    retained = {row for row in session.identity_map.values() if isinstance(row, shared)}

    def retain(_session, row):
        if isinstance(row, shared):
            retained.add(row)

    transitions = ("loaded_as_persistent", "pending_to_persistent")
    for transition in transitions:
        event.listen(session, transition, retain)
    try:
        yield
    finally:
        for transition in transitions:
            event.remove(session, transition, retain)
        retained.clear()


def retain_observation_dependencies(run):
    """Scope shared row and verified response lifetimes to one validation pass."""
    @wraps(run)
    def retained(execution_session, *args, **kwargs):
        with _observation_dependency_rows(execution_session):
            return run(execution_session, *args, **kwargs)
    return retained


class StaleNumericIdentityError(ValueError):
    """Stored observation bytes predate the canonical market-zero rule."""


def _aware_ordered(event: dt.datetime, completed: dt.datetime,
                   available: dt.datetime, recorded: dt.datetime) -> tuple[dt.datetime, ...]:
    values = tuple(_utc(value, name) for value, name in (
        (event, "event_time"), (completed, "completed_at"),
        (available, "available_at"), (recorded, "recorded_at")))
    if values[1] < values[0] or values[2] < values[0] or values[3] < values[2]:
        raise ValueError("observation timestamps are not causal")
    return values


def _positive_int(value: object, name: str, *, allow_zero: bool = False) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError(f"{name} must be a bounded integer")
    return value


def _numeric_fact(value: NumericValue) -> dict[str, Any]:
    if not isinstance(value, NumericValue):
        raise ValueError("normalized observation requires NumericValue")
    raw = value.value
    if isinstance(raw, tuple):
        raw = list(raw)
    return {"state": value.state.value, "value": raw,
            "causes": [item.value for item in value.causes]}


def _canonical_market_numeric(value: NumericValue) -> NumericValue:
    """Apply the one raw-market scalar rule before observation identity."""
    if not isinstance(value, NumericValue):
        raise ValueError("normalized observation requires NumericValue")
    if value.state is not ValidityState.VALID:
        return value
    try:
        normalized = market_float(value.value, field="normalized observation numeric")
    except NumericIngressError as exc:
        raise ValueError("normalized observation requires one finite market scalar") from exc
    # Preserve every nonzero finite representation.  Only zero has one new
    # canonical representation, regardless of an integer or signed-float input.
    canonical = 0.0 if normalized == 0.0 else value.value
    return NumericValue(ValidityState.VALID, canonical)


def _numeric_from_fact(value: object) -> NumericValue:
    if type(value) is not dict or set(value) != {"state", "value", "causes"}:
        raise ValueError("numeric fact is not closed")
    try:
        raw = tuple(value["value"]) if isinstance(value["value"], list) else value["value"]
        return NumericValue(ValidityState(value["state"]), raw,
                            tuple(ValidityState(item) for item in value["causes"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("numeric fact is malformed") from exc


@dataclass(frozen=True)
class RawObservationSegment(CanonicalFact):
    """Immutable raw bytes. Location is deliberately not part of byte identity."""

    SCHEMA: ClassVar[str] = "provider-raw-segment/1"
    owner_id: str
    product_address: str
    contract_address: str
    media_type: str
    raw_schema: str
    payload: bytes
    recorded_at: dt.datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _closed_text(self.owner_id, "owner_id", maximum=64))
        _address(self.product_address, "product_address")
        _address(self.contract_address, "contract_address")
        object.__setattr__(self, "media_type", _closed_text(self.media_type, "media_type"))
        object.__setattr__(self, "raw_schema", _closed_text(self.raw_schema, "raw_schema"))
        if (not isinstance(self.payload, bytes) or not self.payload
                or len(self.payload) > _MAX_RAW_SEGMENT_BYTES):
            raise ValueError("raw segment bytes are absent or oversized")
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at, "recorded_at"))

    @property
    def byte_digest(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def fact(self) -> dict[str, Any]:
        return {"owner_id": self.owner_id, "product_address": self.product_address,
                "contract_address": self.contract_address, "media_type": self.media_type,
                "raw_schema": self.raw_schema, "byte_digest": self.byte_digest,
                "byte_length": len(self.payload), "recorded_at": self.recorded_at.isoformat()}


@dataclass(frozen=True)
class ProviderObservation(CanonicalFact):
    """Closed record of the exact bytes supplied by one permitted product."""

    SCHEMA: ClassVar[str] = "provider-observation/1"
    owner_id: str
    provider_entity_address: str
    provider_product_address: str
    provider_contract_address: str
    mapping_address: str
    provider_token: str
    raw_schema: str
    field: str
    resolution_seconds: int
    event_time: dt.datetime
    completed_at: dt.datetime
    available_at: dt.datetime
    recorded_at: dt.datetime
    sequence_id: str
    correction_id: str
    raw_segment_address: str
    raw_byte_offset: int
    raw_byte_length: int
    raw_byte_digest: str
    validity: ValidityState
    supersedes_address: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _closed_text(self.owner_id, "owner_id", maximum=64))
        for name in ("provider_entity_address", "provider_product_address",
                     "provider_contract_address", "mapping_address", "raw_segment_address"):
            _address(getattr(self, name), name)
        if self.supersedes_address is not None:
            _address(self.supersedes_address, "supersedes_address")
        for name in ("provider_token", "raw_schema", "field", "sequence_id", "correction_id"):
            object.__setattr__(self, name, _closed_text(getattr(self, name), name))
        _positive_int(self.resolution_seconds, "resolution_seconds")
        _positive_int(self.raw_byte_offset, "raw_byte_offset", allow_zero=True)
        _positive_int(self.raw_byte_length, "raw_byte_length")
        if (not isinstance(self.raw_byte_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", self.raw_byte_digest) is None):
            raise ValueError("raw_byte_digest is malformed")
        if not isinstance(self.validity, ValidityState):
            raise ValueError("provider observation validity is not closed")
        event, completed, available, recorded = _aware_ordered(
            self.event_time, self.completed_at, self.available_at, self.recorded_at)
        for name, value in zip(("event_time", "completed_at", "available_at", "recorded_at"),
                               (event, completed, available, recorded), strict=True):
            object.__setattr__(self, name, value)

    def verify_segment(self, segment: RawObservationSegment) -> None:
        if (not isinstance(segment, RawObservationSegment)
                or segment.address != self.raw_segment_address
                or segment.owner_id != self.owner_id
                or segment.product_address != self.provider_product_address
                or segment.contract_address != self.provider_contract_address):
            raise ValueError("raw segment dependency does not match observation")
        end = self.raw_byte_offset + self.raw_byte_length
        if end > len(segment.payload):
            raise ValueError("raw observation byte range exceeds its segment")
        digest = hashlib.sha256(segment.payload[self.raw_byte_offset:end]).hexdigest()
        if digest != self.raw_byte_digest:
            raise ValueError("raw observation byte digest does not match its segment")

    def fact(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id, "provider_entity_address": self.provider_entity_address,
            "provider_product_address": self.provider_product_address,
            "provider_contract_address": self.provider_contract_address,
            "mapping_address": self.mapping_address, "provider_token": self.provider_token,
            "raw_schema": self.raw_schema, "field": self.field,
            "resolution_seconds": self.resolution_seconds,
            "event_time": self.event_time.isoformat(), "completed_at": self.completed_at.isoformat(),
            "available_at": self.available_at.isoformat(), "recorded_at": self.recorded_at.isoformat(),
            "sequence_id": self.sequence_id, "correction_id": self.correction_id,
            "raw_segment_address": self.raw_segment_address,
            "raw_byte_offset": self.raw_byte_offset, "raw_byte_length": self.raw_byte_length,
            "raw_byte_digest": self.raw_byte_digest, "validity": self.validity.value,
            "supersedes_address": self.supersedes_address,
        }

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ProviderObservation":
        keys = {"owner_id", "provider_entity_address", "provider_product_address",
                "provider_contract_address", "mapping_address", "provider_token", "raw_schema",
                "field", "resolution_seconds", "event_time", "completed_at", "available_at",
                "recorded_at", "sequence_id", "correction_id", "raw_segment_address",
                "raw_byte_offset", "raw_byte_length", "raw_byte_digest", "validity",
                "supersedes_address"}
        fact = _parse_envelope(payload, cls.SCHEMA, keys)["fact"]
        try:
            return cls(**{**fact, "validity": ValidityState(fact["validity"]),
                **{name: dt.datetime.fromisoformat(fact[name]) for name in (
                    "event_time", "completed_at", "available_at", "recorded_at")}})
        except (TypeError, ValueError) as exc:
            raise ValueError("provider observation bytes are malformed") from exc


@dataclass(frozen=True)
class NormalizedMarketObservation(CanonicalFact):
    """Typed normalized fact, never interchangeable with a provider observation."""

    SCHEMA: ClassVar[str] = "normalized-market-observation/1"
    canonical_instrument_address: str
    provider_observation_addresses: tuple[str, ...]
    transform_address: str
    transform_version: str
    policy_address: str
    algorithm_address: str
    algorithm_version: str
    market_truth_address: str
    normalized_schema: str
    field: str
    resolution_seconds: int
    event_time: dt.datetime
    completed_at: dt.datetime
    available_at: dt.datetime
    recorded_at: dt.datetime
    numeric: NumericValue
    correction_lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("canonical_instrument_address", "transform_address", "policy_address",
                     "algorithm_address", "market_truth_address"):
            _address(getattr(self, name), name)
        if (not isinstance(self.provider_observation_addresses, tuple)
                or not self.provider_observation_addresses
                or len(self.provider_observation_addresses) > _MAX_OBSERVATION_INPUTS
                or len(set(self.provider_observation_addresses)) != len(self.provider_observation_addresses)):
            raise ValueError("normalized raw inputs must be bounded, ordered, and unique")
        for item in self.provider_observation_addresses:
            _address(item, "provider_observation_address")
        if (not isinstance(self.correction_lineage, tuple)
                or len(self.correction_lineage) > _MAX_OBSERVATION_INPUTS):
            raise ValueError("correction lineage exceeds its bound")
        for item in self.correction_lineage:
            _address(item, "correction_lineage address")
        for name in ("transform_version", "algorithm_version", "normalized_schema", "field"):
            object.__setattr__(self, name, _closed_text(getattr(self, name), name))
        _positive_int(self.resolution_seconds, "resolution_seconds")
        object.__setattr__(self, "numeric", _canonical_market_numeric(self.numeric))
        event, completed, available, recorded = _aware_ordered(
            self.event_time, self.completed_at, self.available_at, self.recorded_at)
        for name, value in zip(("event_time", "completed_at", "available_at", "recorded_at"),
                               (event, completed, available, recorded), strict=True):
            object.__setattr__(self, name, value)

    def fact(self) -> dict[str, Any]:
        return {"canonical_instrument_address": self.canonical_instrument_address,
                "provider_observation_addresses": list(self.provider_observation_addresses),
                "transform_address": self.transform_address, "transform_version": self.transform_version,
                "policy_address": self.policy_address, "algorithm_address": self.algorithm_address,
                "algorithm_version": self.algorithm_version,
                "market_truth_address": self.market_truth_address,
                "normalized_schema": self.normalized_schema, "field": self.field,
                "resolution_seconds": self.resolution_seconds,
                "event_time": self.event_time.isoformat(), "completed_at": self.completed_at.isoformat(),
                "available_at": self.available_at.isoformat(), "recorded_at": self.recorded_at.isoformat(),
                "numeric": _numeric_fact(self.numeric),
                "correction_lineage": list(self.correction_lineage)}

    @classmethod
    def from_bytes(cls, payload: bytes) -> "NormalizedMarketObservation":
        keys = {"canonical_instrument_address", "provider_observation_addresses",
                "transform_address", "transform_version", "policy_address", "algorithm_address",
                "algorithm_version", "market_truth_address", "normalized_schema", "field",
                "resolution_seconds", "event_time", "completed_at", "available_at", "recorded_at",
                "numeric", "correction_lineage"}
        fact = _parse_envelope(payload, cls.SCHEMA, keys)["fact"]
        try:
            observation = cls(**{**fact,
                "provider_observation_addresses": tuple(fact["provider_observation_addresses"]),
                "correction_lineage": tuple(fact["correction_lineage"]),
                "numeric": _numeric_from_fact(fact["numeric"]),
                **{name: dt.datetime.fromisoformat(fact[name]) for name in (
                    "event_time", "completed_at", "available_at", "recorded_at")}})
        except (TypeError, ValueError, MarketTruthError) as exc:
            raise ValueError("normalized observation bytes are malformed") from exc
        if observation.canonical_bytes != payload:
            raw_numeric = fact["numeric"].get("value")
            if (isinstance(raw_numeric, float) and raw_numeric == 0.0
                    and math.copysign(1.0, raw_numeric) < 0):
                raise StaleNumericIdentityError(
                    "stored observation has stale signed-zero numeric identity")
            raise StaleNumericIdentityError(
                "stored observation has stale canonical numeric identity")
        return observation


@dataclass(frozen=True)
class DataObservation:
    instrument: str
    field: str
    timeframe_seconds: int
    event_time: dt.datetime
    available_at: dt.datetime
    completed_at: dt.datetime
    source_address: str
    market_truth_address: str
    numeric: NumericValue

    def __post_init__(self) -> None:
        if (not isinstance(self.instrument, str) or not self.instrument.strip()
                or not isinstance(self.field, str) or not self.field.strip()
                or isinstance(self.timeframe_seconds, bool)
                or not isinstance(self.timeframe_seconds, int) or self.timeframe_seconds <= 0):
            raise ValueError("observation identity is incomplete")
        if not isinstance(self.numeric, NumericValue):
            raise ValueError("observation requires NumericValue")
        times = (self.event_time, self.completed_at, self.available_at)
        if any(not isinstance(value, dt.datetime) or value.tzinfo is None
               or value.utcoffset() is None for value in times):
            raise ValueError("observation timestamps must be aware")
        if not (self.available_at >= self.event_time
                and self.completed_at >= self.event_time):
            raise ValueError("observation timestamps are not causal")
        if not all(isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value)
                   for value in (self.source_address, self.market_truth_address)):
            raise ValueError("observation provenance address is malformed")

    @property
    def validity(self) -> ValidityState:
        return self.numeric.state

    @property
    def value(self):
        return self.numeric.value


@dataclass(frozen=True)
class AlignmentPolicy:
    maximum_age_seconds: int
    maximum_skew_seconds: int
    session: str = "CONTINUOUS"
    resampling: str = "ASOF_BACKWARD"
    invalid_input: str = "REFUSE"
    timezone: str = "UTC"
    completed_bar_rule: str = "COMPLETED_ONLY"

    def __post_init__(self) -> None:
        if (isinstance(self.maximum_age_seconds, bool) or isinstance(self.maximum_skew_seconds, bool)
                or not isinstance(self.maximum_age_seconds, int)
                or not isinstance(self.maximum_skew_seconds, int)
                or self.maximum_age_seconds < 0 or self.maximum_skew_seconds < 0):
            raise ValueError("alignment bounds must be non-negative")
        # Calendar evaluation needs the accepted market-truth session resolver;
        # it is not silently approximated by this consumer seam.
        if self.session != "CONTINUOUS":
            raise ValueError("unknown session policy")
        if self.resampling not in {"EXACT", "ASOF_BACKWARD"}:
            raise ValueError("unknown resampling policy")
        if self.invalid_input != "REFUSE":
            raise ValueError("implicit fill or fallback is not permitted")
        if self.timezone != "UTC":
            raise ValueError("unknown alignment timezone")
        if self.completed_bar_rule != "COMPLETED_ONLY":
            raise ValueError("unknown completed-bar rule")


def align_observation(observations: Iterable[DataObservation], *, at: dt.datetime,
                      policy: AlignmentPolicy) -> DataObservation | None:
    """Choose the latest completed, available, valid fact at ``at``.

    This deliberately returns no value for forming, future, stale, invalid, or
    skewed data.  Forward filling/interpolation needs a separate, provenance-
    bearing policy and is not represented by this Phase 4 seam.
    """
    if (not isinstance(at, dt.datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("alignment time must be aware")
    if not isinstance(policy, AlignmentPolicy):
        raise ValueError("alignment requires AlignmentPolicy")
    rows = tuple(observations)
    if any(not isinstance(row, DataObservation) for row in rows):
        raise ValueError("alignment requires DataObservation rows")
    eligible = [row for row in rows if row.available_at <= at
                and row.completed_at <= at and row.event_time <= at
                and row.validity is ValidityState.VALID]
    if not eligible:
        return None
    top_key = max((row.event_time, row.completed_at) for row in eligible)
    top_rows = {row for row in eligible
                if (row.event_time, row.completed_at) == top_key}
    if len(top_rows) != 1:
        return None
    chosen = top_rows.pop()
    age = (at - chosen.event_time).total_seconds()
    if age > policy.maximum_age_seconds:
        return None
    if policy.resampling == "EXACT" and chosen.event_time != at:
        return None
    return chosen


def align_required_series(series: Mapping[str, Iterable[DataObservation]], *, at: dt.datetime,
                          policy: AlignmentPolicy) -> dict[str, DataObservation] | None:
    """Align required legs and reject cross-series event-time skew explicitly."""
    if not series:
        return None
    aligned = {name: align_observation(rows, at=at, policy=policy)
               for name, rows in series.items()}
    if any(row is None for row in aligned.values()):
        return None
    timestamps = [row.event_time for row in aligned.values() if row is not None]
    if (max(timestamps) - min(timestamps)).total_seconds() > policy.maximum_skew_seconds:
        return None
    return {name: row for name, row in aligned.items() if row is not None}


def _row_fact_bytes(row: object) -> bytes:
    value = getattr(row, "canonical_json", None)
    if not isinstance(value, str):
        raise MarketTruthError("authority row has no canonical bytes")
    return value.encode("utf-8")


def persist_raw_segment(session, segment: RawObservationSegment) -> None:
    from app.db.models import AuthorityRawSegment
    from app.market_truth.identity import load_provider_identity

    if not isinstance(segment, RawObservationSegment):
        raise MarketTruthError("only provider-raw-segment/1 can enter authority storage")
    entity, product, contract = load_provider_identity(session, segment.contract_address)
    if (product.address != segment.product_address or contract.owner_id != segment.owner_id):
        raise MarketTruthError("raw segment provider identity does not match")
    existing = session.get(AuthorityRawSegment, segment.address)
    if existing is not None:
        loaded = load_raw_segment(session, segment.address)
        if loaded.canonical_bytes != segment.canonical_bytes or loaded.payload != segment.payload:
            raise MarketTruthError("raw segment address collision")
        return
    session.add(AuthorityRawSegment(
        address=segment.address, schema=segment.SCHEMA,
        canonical_json=segment.canonical_bytes.decode("utf-8"),
        owner_id=segment.owner_id, product_address=segment.product_address,
        contract_address=segment.contract_address, raw_bytes=segment.payload,
        byte_digest=segment.byte_digest, byte_length=len(segment.payload),
        authority_state="VERIFIED_V2"))
    session.flush()


def load_raw_segment(session, address: str) -> RawObservationSegment:
    from app.db.models import AuthorityRawSegment
    from app.market_truth.identity import load_provider_identity

    _address(address, "raw segment address")
    row = session.get(AuthorityRawSegment, address)
    if row is None or row.authority_state != "VERIFIED_V2" or row.schema != RawObservationSegment.SCHEMA:
        raise MarketTruthError("raw segment authority is absent")
    fact = _parse_envelope(_row_fact_bytes(row), RawObservationSegment.SCHEMA, {
        "owner_id", "product_address", "contract_address", "media_type", "raw_schema",
        "byte_digest", "byte_length", "recorded_at"})["fact"]
    try:
        segment = RawObservationSegment(
            owner_id=fact["owner_id"], product_address=fact["product_address"],
            contract_address=fact["contract_address"], media_type=fact["media_type"],
            raw_schema=fact["raw_schema"], payload=bytes(row.raw_bytes),
            recorded_at=dt.datetime.fromisoformat(fact["recorded_at"]))
    except (TypeError, ValueError) as exc:
        raise MarketTruthError("raw segment row is malformed") from exc
    if (segment.address != row.address or segment.owner_id != row.owner_id
            or segment.product_address != row.product_address
            or segment.contract_address != row.contract_address
            or segment.byte_digest != row.byte_digest or len(segment.payload) != row.byte_length
            or fact["byte_digest"] != row.byte_digest or fact["byte_length"] != row.byte_length):
        raise MarketTruthError("raw segment copied columns do not match bytes")
    _, product, contract = load_provider_identity(session, segment.contract_address)
    if product.address != segment.product_address or contract.owner_id != segment.owner_id:
        raise MarketTruthError("raw segment provider dependency does not match")
    return segment


def _provider_dependency_identity(observation, entity, product, contract, alias, segment):
    if (entity.address != observation.provider_entity_address
            or product.address != observation.provider_product_address
            or contract.owner_id != observation.owner_id
            or alias.product_address != product.address
            or getattr(alias, "provider_contract_address", contract.address) != contract.address
            or alias.provider_token != observation.provider_token
            or segment.raw_schema != observation.raw_schema):
        raise MarketTruthError("provider observation identity chain does not match")


def _provider_dependency_intervals(observation, contract, alias, grant_time):
    if (not (contract.effective_from <= grant_time
             and (contract.effective_to is None or grant_time < contract.effective_to))
            or not (alias.effective_from <= observation.event_time
                    and (alias.effective_to is None or observation.event_time < alias.effective_to))):
        raise MarketTruthError("provider observation dependency interval does not match")


def _verify_provider_dependencies(session, observation, entity, product, contract, alias, segment):
    from app.market_data.kite_historical_attribution import observation_grant_time
    _provider_dependency_identity(observation, entity, product, contract, alias, segment)
    grant_time = observation_grant_time(session, observation, alias, segment)
    _provider_dependency_intervals(observation, contract, alias, grant_time)


def persist_provider_observation(session, observation: ProviderObservation) -> None:
    from app.db.models import AuthorityProviderObservation
    from app.market_truth.identity import load_provider_alias, load_provider_identity

    if not isinstance(observation, ProviderObservation):
        raise MarketTruthError("only provider-observation/1 can enter authority storage")
    entity, product, contract = load_provider_identity(session, observation.provider_contract_address)
    alias = load_provider_alias(session, observation.mapping_address)
    segment = load_raw_segment(session, observation.raw_segment_address)
    _verify_provider_dependencies(session, observation, entity, product, contract, alias, segment)
    observation.verify_segment(segment)
    if observation.supersedes_address is not None:
        prior = load_provider_observation(session, observation.supersedes_address)
        if (prior.owner_id, prior.provider_product_address, prior.field, prior.event_time) != (
                observation.owner_id, observation.provider_product_address,
                observation.field, observation.event_time):
            raise MarketTruthError("provider correction lineage crosses an observation identity")
    existing = session.get(AuthorityProviderObservation, observation.address)
    if existing is not None:
        if _row_fact_bytes(existing) != observation.canonical_bytes:
            raise MarketTruthError("provider observation address collision")
        return
    session.add(AuthorityProviderObservation(
        address=observation.address, schema=observation.SCHEMA,
        canonical_json=observation.canonical_bytes.decode("utf-8"), owner_id=observation.owner_id,
        entity_address=observation.provider_entity_address,
        product_address=observation.provider_product_address,
        contract_address=observation.provider_contract_address,
        mapping_address=observation.mapping_address,
        raw_segment_address=observation.raw_segment_address, field=observation.field,
        resolution_seconds=observation.resolution_seconds,
        event_time=to_sql_utc_naive(observation.event_time, "event_time"),
        available_at=to_sql_utc_naive(observation.available_at, "available_at"),
        correction_id=observation.correction_id,
        supersedes_address=observation.supersedes_address, authority_state="VERIFIED_V2"))
    session.flush()


def _stored_provider_observation(session, address):
    from app.db.models import AuthorityProviderObservation
    row = session.get(AuthorityProviderObservation, address)
    if row is None or row.authority_state != "VERIFIED_V2" or row.schema != ProviderObservation.SCHEMA:
        raise MarketTruthError("provider observation authority is absent")
    observation = ProviderObservation.from_bytes(_row_fact_bytes(row))
    checks = (
        (observation.address, row.address), (observation.owner_id, row.owner_id),
        (observation.provider_entity_address, row.entity_address),
        (observation.provider_product_address, row.product_address),
        (observation.provider_contract_address, row.contract_address),
        (observation.mapping_address, row.mapping_address),
        (observation.raw_segment_address, row.raw_segment_address),
        (observation.field, row.field), (observation.resolution_seconds, row.resolution_seconds),
        (to_sql_utc_naive(observation.event_time, "event_time"),
         require_sql_utc_naive(row.event_time, "event_time")),
        (to_sql_utc_naive(observation.available_at, "available_at"),
         require_sql_utc_naive(row.available_at, "available_at")),
        (observation.correction_id, row.correction_id),
        (observation.supersedes_address, row.supersedes_address),
    )
    if any(left != right for left, right in checks):
        raise MarketTruthError("provider observation copied columns do not match bytes")
    return observation


def load_provider_observation(session, address: str, *, _seen: frozenset[str] = frozenset(),
                              _memo: dict[str, ProviderObservation] | None = None
                              ) -> ProviderObservation:
    from app.market_truth.identity import load_provider_alias, load_provider_identity

    _address(address, "provider observation address")
    if address in _seen:
        raise MarketTruthError("provider correction cycle detected")
    if _memo is not None and address in _memo:
        return _memo[address]
    observation = _stored_provider_observation(session, address)
    entity, product, contract = load_provider_identity(session, observation.provider_contract_address)
    alias = load_provider_alias(session, observation.mapping_address)
    segment = load_raw_segment(session, observation.raw_segment_address)
    observation.verify_segment(segment)
    _verify_provider_dependencies(session, observation, entity, product, contract, alias, segment)
    if observation.supersedes_address is not None:
        prior = load_provider_observation(
            session, observation.supersedes_address, _seen=_seen | {address}, _memo=_memo)
        if (prior.owner_id, prior.provider_product_address, prior.field, prior.event_time) != (
                observation.owner_id, observation.provider_product_address,
                observation.field, observation.event_time):
            raise MarketTruthError("provider correction lineage crosses an observation identity")
    if _memo is not None:
        _memo[address] = observation
    return observation


def persist_normalized_observation(session, observation: NormalizedMarketObservation) -> None:
    from app.db.models import AuthorityNormalizedObservation, AuthorityNormalizedObservationInput
    from app.market_truth.identity import load_canonical_instrument

    if not isinstance(observation, NormalizedMarketObservation):
        raise MarketTruthError("only normalized-market-observation/1 can enter authority storage")
    load_canonical_instrument(session, observation.canonical_instrument_address)
    from app.market_truth.identity import load_provider_alias
    for raw_address in observation.provider_observation_addresses:
        raw = load_provider_observation(session, raw_address)
        if load_provider_alias(session, raw.mapping_address).canonical_instrument_address \
                != observation.canonical_instrument_address:
            raise MarketTruthError("normalized observation input maps to another instrument")
    existing = session.get(AuthorityNormalizedObservation, observation.address)
    if existing is not None:
        if _row_fact_bytes(existing) != observation.canonical_bytes:
            raise MarketTruthError("normalized observation address collision")
        return
    session.add(AuthorityNormalizedObservation(
        address=observation.address, schema=observation.SCHEMA,
        canonical_json=observation.canonical_bytes.decode("utf-8"),
        instrument_address=observation.canonical_instrument_address,
        market_truth_address=observation.market_truth_address, field=observation.field,
        resolution_seconds=observation.resolution_seconds,
        event_time=to_sql_utc_naive(observation.event_time, "event_time"),
        available_at=to_sql_utc_naive(observation.available_at, "available_at"),
        authority_state="VERIFIED_V2"))
    session.flush()
    session.add_all([AuthorityNormalizedObservationInput(
        normalized_address=observation.address, ordinal=index,
        provider_observation_address=raw_address)
        for index, raw_address in enumerate(observation.provider_observation_addresses)])
    session.flush()


def load_normalized_observation(session, address: str, *,
                                _provider_memo: dict[str, ProviderObservation] | None = None
                                ) -> NormalizedMarketObservation:
    from sqlalchemy import select
    from app.db.models import AuthorityNormalizedObservation, AuthorityNormalizedObservationInput
    from app.market_truth.identity import load_canonical_instrument

    _address(address, "normalized observation address")
    row = session.get(AuthorityNormalizedObservation, address)
    if row is None or row.authority_state != "VERIFIED_V2" or row.schema != NormalizedMarketObservation.SCHEMA:
        raise MarketTruthError("normalized observation authority is absent")
    observation = NormalizedMarketObservation.from_bytes(_row_fact_bytes(row))
    inputs = session.execute(select(AuthorityNormalizedObservationInput).where(
        AuthorityNormalizedObservationInput.normalized_address == address).order_by(
            AuthorityNormalizedObservationInput.ordinal)).scalars().all()
    if ([item.ordinal for item in inputs] != list(range(len(inputs)))
            or tuple(item.provider_observation_address for item in inputs)
               != observation.provider_observation_addresses):
        raise MarketTruthError("normalized observation input order does not match bytes")
    checks = (
        (observation.address, row.address),
        (observation.canonical_instrument_address, row.instrument_address),
        (observation.market_truth_address, row.market_truth_address),
        (observation.field, row.field), (observation.resolution_seconds, row.resolution_seconds),
        (to_sql_utc_naive(observation.event_time, "event_time"),
         require_sql_utc_naive(row.event_time, "event_time")),
        (to_sql_utc_naive(observation.available_at, "available_at"),
         require_sql_utc_naive(row.available_at, "available_at")),
    )
    if any(left != right for left, right in checks):
        raise MarketTruthError("normalized observation copied columns do not match bytes")
    load_canonical_instrument(session, observation.canonical_instrument_address)
    from app.market_truth.identity import load_provider_alias
    for item in inputs:
        raw = load_provider_observation(
            session, item.provider_observation_address, _memo=_provider_memo)
        if load_provider_alias(session, raw.mapping_address).canonical_instrument_address \
                != observation.canonical_instrument_address:
            raise MarketTruthError("normalized observation input maps to another instrument")
    return observation


__all__ = [
    "AlignmentPolicy", "DataObservation", "NormalizedMarketObservation", "ProviderObservation",
    "RawObservationSegment", "StaleNumericIdentityError", "align_observation", "align_required_series",
    "load_normalized_observation", "load_provider_observation", "load_raw_segment",
    "persist_normalized_observation", "persist_provider_observation", "persist_raw_segment",
    "retain_observation_dependencies",
]
