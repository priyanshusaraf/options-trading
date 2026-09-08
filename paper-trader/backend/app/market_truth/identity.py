"""Canonical physical-instrument, selector, and provider-mapping values.

Provider identifiers intentionally live only in ``ProviderInstrumentMapping``.
They cannot participate in an instrument's content identity or a strategy's
economic selector.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, ClassVar
import json
import re
import unicodedata

from app.ir.hashing import canonical_json, content_address
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive


class MarketTruthError(ValueError):
    """Point-in-time market truth is absent, ambiguous, or malformed."""


class Quality(str, Enum):
    OBSERVED = "OBSERVED"
    RECONSTRUCTED = "RECONSTRUCTED"
    UNKNOWN = "UNKNOWN"


_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_FACT_BYTES = 256 * 1024
_MAX_UNDERLIER_DEPTH = 64


def _closed_text(value: object, name: str, *, maximum: int = 256) -> str:
    if (not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum
            or unicodedata.normalize("NFC", value) != value or "\x00" in value):
        raise MarketTruthError(f"{name} must be bounded non-empty NFC text")
    return value


def _address(value: object, name: str) -> str:
    if not isinstance(value, str) or _ADDRESS.fullmatch(value) is None:
        raise MarketTruthError(f"{name} must be a canonical content address")
    return value


def _utc(value: datetime, name: str) -> datetime:
    _instant(value, name)
    return value.astimezone(timezone.utc)


def canonical_fact_bytes(schema: str, fact: dict[str, Any], *, maximum_bytes: int = _MAX_FACT_BYTES) -> bytes:
    """Return the sole domain-separated byte representation of an authority fact."""
    _closed_text(schema, "schema", maximum=64)
    if not isinstance(fact, dict) or not fact:
        raise MarketTruthError("fact must be a non-empty closed object")
    encoded = canonical_json({"schema": schema, "fact": fact}).encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise MarketTruthError("canonical fact exceeds the persistence bound")
    return encoded


def canonical_fact_address(schema: str, fact: dict[str, Any]) -> str:
    return content_address({"schema": schema, "fact": fact})


class CanonicalFact:
    """Mixin for immutable, domain-separated authority documents."""

    SCHEMA: ClassVar[str]

    def fact(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_fact_bytes(self.SCHEMA, self.fact())

    @property
    def address(self) -> str:
        return canonical_fact_address(self.SCHEMA, self.fact())


def canonical_decimal(value: str) -> str:
    """Accept one non-floating decimal spelling and return its canonical form."""
    if not isinstance(value, str) or not value:
        raise MarketTruthError("decimal identity must be a non-empty canonical string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise MarketTruthError("decimal identity is invalid") from exc
    if not parsed.is_finite():
        raise MarketTruthError("decimal identity must be finite")
    normalized = format(parsed.normalize(), "f")
    if normalized == "-0":
        normalized = "0"
    if value != normalized:
        raise MarketTruthError("decimal identity is not canonical")
    return normalized


def _instant(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MarketTruthError(f"{name} must be timezone-aware")


def _interval(start: datetime, end: datetime | None) -> None:
    _instant(start, "effective_from")
    if end is not None:
        _instant(end, "effective_to")
        if end <= start:
            raise MarketTruthError("effective interval must be half-open and non-empty")


def _frozen_pairs(value: tuple[tuple[str, str], ...], name: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(item, tuple) or len(item) != 2 or not all(isinstance(part, str) and part for part in item)
        for item in value
    ):
        raise MarketTruthError(f"{name} must be immutable non-empty string pairs")
    if tuple(sorted(value)) != value or len(set(value)) != len(value):
        raise MarketTruthError(f"{name} must be sorted and unique")
    return value


@dataclass(frozen=True)
class CanonicalInstrumentId:
    """An exact physical instrument under Strategy OS authority."""

    venue: str
    asset_class: str
    economic_underlying: str
    contract_kind: str
    currency: str
    expiry: datetime | None = None
    strike: str | None = None
    option_right: str | None = None
    multiplier: str | None = None
    series_terms: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("venue", "asset_class", "economic_underlying", "contract_kind", "currency"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise MarketTruthError(f"{name} is required")
        if self.expiry is not None:
            _instant(self.expiry, "expiry")
        if self.strike is not None:
            object.__setattr__(self, "strike", canonical_decimal(self.strike))
        if self.multiplier is not None:
            object.__setattr__(self, "multiplier", canonical_decimal(self.multiplier))
        if self.option_right not in {None, "CALL", "PUT"}:
            raise MarketTruthError("option_right must be CALL or PUT")
        if (self.strike is None) != (self.option_right is None):
            raise MarketTruthError("option strike and right must be specified together")
        object.__setattr__(self, "series_terms", _frozen_pairs(self.series_terms, "series_terms"))
        allowed = {
            ("EQUITY", "SPOT"),
            ("INDEX", "SPOT"),
            ("FUTURE", "FUTURE"),
            ("OPTION", "WEEKLY_OPTION"),
            ("OPTION", "MONTHLY_OPTION"),
        }
        pair = (self.asset_class, self.contract_kind)
        if pair not in allowed:
            raise MarketTruthError("asset_class and contract_kind combination is not supported")
        if self.series_terms:
            raise MarketTruthError("series_terms have no admitted contract schema")
        if pair in {("EQUITY", "SPOT"), ("INDEX", "SPOT")}:
            if any(value is not None for value in (
                    self.expiry, self.strike, self.option_right, self.multiplier)):
                raise MarketTruthError("spot identity cannot contain derivative terms")
        elif pair == ("FUTURE", "FUTURE"):
            if self.expiry is None or self.multiplier is None \
                    or self.strike is not None or self.option_right is not None:
                raise MarketTruthError("future identity requires only expiry and multiplier")
        elif (self.expiry is None or self.strike is None
              or self.option_right is None or self.multiplier is None):
            raise MarketTruthError("listed option identity requires expiry, strike, right, and multiplier")

    @property
    def address(self) -> str:
        return content_address({"canonical_instrument": self.identity_payload()})

    def identity_payload(self) -> dict[str, Any]:
        return {
            "venue": self.venue, "asset_class": self.asset_class,
            "economic_underlying": self.economic_underlying, "contract_kind": self.contract_kind,
            "currency": self.currency, "expiry": self.expiry.isoformat() if self.expiry else None,
            "strike": self.strike, "option_right": self.option_right, "multiplier": self.multiplier,
            "series_terms": self.series_terms,
        }


@dataclass(frozen=True)
class CanonicalPhysicalInstrument(CanonicalFact):
    """Identity-complete ``canonical-instrument/1`` authority fact.

    Legacy ``CanonicalInstrumentId`` remains readable for older non-authority
    callers. Only this closed value can enter the new authority tables.
    """

    SCHEMA: ClassVar[str] = "canonical-instrument/1"
    authority_namespace: str
    authority_version: str
    venue_code: str
    asset_class: str
    contract_kind: str
    currency: str
    economic_underlier_address: str | None
    expiry: datetime | None = None
    strike: str | None = None
    option_right: str | None = None
    multiplier: str | None = None
    series_terms: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("authority_namespace", "authority_version", "venue_code",
                     "asset_class", "contract_kind", "currency"):
            object.__setattr__(self, name, _closed_text(getattr(self, name), name))
        derivative = self.contract_kind in {"FUTURE", "WEEKLY_OPTION", "MONTHLY_OPTION"}
        if derivative:
            _address(self.economic_underlier_address, "economic_underlier_address")
        elif self.economic_underlier_address is not None:
            raise MarketTruthError("a non-derivative root has a typed null underlier")
        if self.expiry is not None:
            object.__setattr__(self, "expiry", _utc(self.expiry, "expiry"))
        if self.strike is not None:
            object.__setattr__(self, "strike", canonical_decimal(self.strike))
        if self.multiplier is not None:
            object.__setattr__(self, "multiplier", canonical_decimal(self.multiplier))
        if self.option_right not in {None, "CALL", "PUT"}:
            raise MarketTruthError("option_right must be CALL or PUT")
        object.__setattr__(self, "series_terms", _frozen_pairs(self.series_terms, "series_terms"))
        admitted = {
            ("EQUITY", "SPOT"), ("INDEX", "SPOT"), ("FUTURE", "FUTURE"),
            ("OPTION", "WEEKLY_OPTION"), ("OPTION", "MONTHLY_OPTION"),
        }
        pair = (self.asset_class, self.contract_kind)
        if pair not in admitted or self.series_terms:
            raise MarketTruthError("instrument contract schema is not admitted")
        if self.contract_kind == "SPOT":
            if any(value is not None for value in (
                    self.expiry, self.strike, self.option_right, self.multiplier)):
                raise MarketTruthError("spot identity cannot contain derivative terms")
        elif self.contract_kind == "FUTURE":
            if (self.expiry is None or self.multiplier is None or self.strike is not None
                    or self.option_right is not None):
                raise MarketTruthError("future identity requires expiry and multiplier only")
        elif any(value is None for value in (
                self.expiry, self.strike, self.option_right, self.multiplier)):
            raise MarketTruthError("option identity requires all defining terms")

    def fact(self) -> dict[str, Any]:
        return {
            "authority_namespace": self.authority_namespace,
            "authority_version": self.authority_version,
            "venue_code": self.venue_code,
            "asset_class": self.asset_class,
            "contract_kind": self.contract_kind,
            "currency": self.currency,
            "economic_underlier_address": self.economic_underlier_address,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "strike": self.strike,
            "option_right": self.option_right,
            "multiplier": self.multiplier,
            "series_terms": [list(item) for item in self.series_terms],
        }

    @classmethod
    def from_bytes(cls, payload: bytes) -> "CanonicalPhysicalInstrument":
        envelope = _parse_envelope(payload, cls.SCHEMA, {
            "authority_namespace", "authority_version", "venue_code", "asset_class",
            "contract_kind", "currency", "economic_underlier_address", "expiry",
            "strike", "option_right", "multiplier", "series_terms",
        })
        fact = envelope["fact"]
        try:
            return cls(
                authority_namespace=fact["authority_namespace"],
                authority_version=fact["authority_version"], venue_code=fact["venue_code"],
                asset_class=fact["asset_class"], contract_kind=fact["contract_kind"],
                currency=fact["currency"],
                economic_underlier_address=fact["economic_underlier_address"],
                expiry=datetime.fromisoformat(fact["expiry"]) if fact["expiry"] else None,
                strike=fact["strike"], option_right=fact["option_right"],
                multiplier=fact["multiplier"],
                series_terms=tuple(tuple(item) for item in fact["series_terms"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketTruthError("canonical instrument bytes are malformed") from exc


def _parse_envelope(payload: bytes, schema: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(payload, bytes) or not payload or len(payload) > _MAX_FACT_BYTES:
        raise MarketTruthError("canonical bytes are absent or oversized")
    try:
        text = payload.decode("utf-8", errors="strict")
        envelope = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketTruthError("canonical bytes are malformed") from exc
    if (type(envelope) is not dict or set(envelope) != {"schema", "fact"}
            or envelope["schema"] != schema or type(envelope["fact"]) is not dict
            or set(envelope["fact"]) != keys or canonical_json(envelope) != text):
        raise MarketTruthError("canonical envelope is not closed or canonical")
    return envelope


@dataclass(frozen=True)
class ProviderEntity(CanonicalFact):
    SCHEMA: ClassVar[str] = "provider-entity/1"
    authority_namespace: str
    entity_code: str
    legal_name: str

    def __post_init__(self) -> None:
        for name in ("authority_namespace", "entity_code", "legal_name"):
            object.__setattr__(self, name, _closed_text(getattr(self, name), name))

    def fact(self) -> dict[str, Any]:
        return {"authority_namespace": self.authority_namespace,
                "entity_code": self.entity_code, "legal_name": self.legal_name}

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ProviderEntity":
        fact = _parse_envelope(payload, cls.SCHEMA, {
            "authority_namespace", "entity_code", "legal_name"})["fact"]
        return cls(**fact)


@dataclass(frozen=True)
class ProviderProduct(CanonicalFact):
    SCHEMA: ClassVar[str] = "provider-product/1"
    entity_address: str
    product_code: str
    observation_namespace: str
    product_version: str

    def __post_init__(self) -> None:
        _address(self.entity_address, "entity_address")
        for name in ("product_code", "observation_namespace", "product_version"):
            object.__setattr__(self, name, _closed_text(getattr(self, name), name))

    def fact(self) -> dict[str, Any]:
        return {"entity_address": self.entity_address, "product_code": self.product_code,
                "observation_namespace": self.observation_namespace,
                "product_version": self.product_version}

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ProviderProduct":
        fact = _parse_envelope(payload, cls.SCHEMA, {
            "entity_address", "product_code", "observation_namespace", "product_version"})["fact"]
        return cls(**fact)


@dataclass(frozen=True)
class ProviderContract(CanonicalFact):
    SCHEMA: ClassVar[str] = "provider-contract/1"
    owner_id: str
    product_address: str
    mode: str
    permitted_uses: tuple[str, ...]
    effective_from: datetime
    effective_to: datetime | None
    evidence_address: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _closed_text(self.owner_id, "owner_id", maximum=64))
        _address(self.product_address, "product_address")
        object.__setattr__(self, "mode", _closed_text(self.mode, "mode", maximum=32))
        if (not isinstance(self.permitted_uses, tuple) or not self.permitted_uses
                or tuple(sorted(set(self.permitted_uses))) != self.permitted_uses):
            raise MarketTruthError("permitted_uses must be a sorted non-empty tuple")
        for use in self.permitted_uses:
            _closed_text(use, "permitted use", maximum=64)
        object.__setattr__(self, "effective_from", _utc(self.effective_from, "effective_from"))
        if self.effective_to is not None:
            object.__setattr__(self, "effective_to", _utc(self.effective_to, "effective_to"))
        _interval(self.effective_from, self.effective_to)
        _address(self.evidence_address, "evidence_address")

    def fact(self) -> dict[str, Any]:
        return {"owner_id": self.owner_id, "product_address": self.product_address,
                "mode": self.mode, "permitted_uses": list(self.permitted_uses),
                "effective_from": self.effective_from.isoformat(),
                "effective_to": self.effective_to.isoformat() if self.effective_to else None,
                "evidence_address": self.evidence_address}

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ProviderContract":
        fact = _parse_envelope(payload, cls.SCHEMA, {
            "owner_id", "product_address", "mode", "permitted_uses", "effective_from",
            "effective_to", "evidence_address"})["fact"]
        try:
            return cls(owner_id=fact["owner_id"], product_address=fact["product_address"],
                       mode=fact["mode"], permitted_uses=tuple(fact["permitted_uses"]),
                       effective_from=datetime.fromisoformat(fact["effective_from"]),
                       effective_to=(datetime.fromisoformat(fact["effective_to"])
                                     if fact["effective_to"] else None),
                       evidence_address=fact["evidence_address"])
        except (TypeError, ValueError) as exc:
            raise MarketTruthError("provider contract bytes are malformed") from exc


@dataclass(frozen=True)
class ProviderInstrumentAlias(CanonicalFact):
    SCHEMA: ClassVar[str] = "provider-instrument-mapping/1"
    FACT_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "product_address", "provider_token", "provider_symbol", "canonical_instrument_address",
        "adapter_schema_version", "effective_from", "effective_to", "observation_namespace",
        "source_evidence_address"})
    product_address: str
    provider_token: str
    provider_symbol: str
    canonical_instrument_address: str
    adapter_schema_version: str
    effective_from: datetime
    effective_to: datetime | None
    observation_namespace: str
    source_evidence_address: str

    def __post_init__(self) -> None:
        for name in ("product_address", "canonical_instrument_address", "source_evidence_address"):
            _address(getattr(self, name), name)
        for name in ("provider_token", "provider_symbol", "adapter_schema_version",
                     "observation_namespace"):
            object.__setattr__(self, name, _closed_text(getattr(self, name), name))
        object.__setattr__(self, "effective_from", _utc(self.effective_from, "effective_from"))
        if self.effective_to is not None:
            object.__setattr__(self, "effective_to", _utc(self.effective_to, "effective_to"))
        _interval(self.effective_from, self.effective_to)

    def fact(self) -> dict[str, Any]:
        return {"product_address": self.product_address, "provider_token": self.provider_token,
                "provider_symbol": self.provider_symbol,
                "canonical_instrument_address": self.canonical_instrument_address,
                "adapter_schema_version": self.adapter_schema_version,
                "effective_from": self.effective_from.isoformat(),
                "effective_to": self.effective_to.isoformat() if self.effective_to else None,
                "observation_namespace": self.observation_namespace,
                "source_evidence_address": self.source_evidence_address}

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ProviderInstrumentAlias":
        fact = _parse_envelope(payload, cls.SCHEMA, cls.FACT_FIELDS)["fact"]
        try:
            return cls(**{**fact,
                "effective_from": datetime.fromisoformat(fact["effective_from"]),
                "effective_to": (datetime.fromisoformat(fact["effective_to"])
                                 if fact["effective_to"] else None)})
        except (TypeError, ValueError) as exc:
            raise MarketTruthError("provider mapping bytes are malformed") from exc


@dataclass(frozen=True)
class ProviderResponseInstrumentAlias(ProviderInstrumentAlias):
    """Attribution within one retained response, never historical token validity."""
    SCHEMA: ClassVar[str] = "provider-instrument-mapping/2"
    FACT_FIELDS: ClassVar[frozenset[str]] = ProviderInstrumentAlias.FACT_FIELDS | {
        "provider_contract_address"}
    provider_contract_address: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _address(self.provider_contract_address, "provider_contract_address")
        if self.effective_to is None:
            raise MarketTruthError("response alias requires a finite returned interval")

    def fact(self) -> dict[str, Any]:
        return {**super().fact(), "provider_contract_address": self.provider_contract_address}


def _response_alias_scope(alias):
    if isinstance(alias, ProviderResponseInstrumentAlias):
        return alias.provider_contract_address, alias.source_evidence_address
    return None


def _provider_alias_conflicts(left, right):
    left_scope, right_scope = _response_alias_scope(left), _response_alias_scope(right)
    if left_scope is not None or right_scope is not None:
        return left_scope == right_scope and left.address != right.address
    keys_match = any(getattr(left, field) == getattr(right, field) for field in (
        "provider_token", "provider_symbol", "canonical_instrument_address"))
    return (left.product_address == right.product_address
        and left.observation_namespace == right.observation_namespace
        and _provider_alias_intervals_overlap(left, right) and keys_match)


def _provider_alias_intervals_overlap(left, right):
    return ((right.effective_to is None or left.effective_from < right.effective_to)
            and (left.effective_to is None or right.effective_from < left.effective_to))


def validate_provider_aliases(aliases: tuple[ProviderInstrumentAlias, ...]) -> None:
    """Keep directory intervals global and each response attribution unambiguous."""
    if any(type(item) not in (ProviderInstrumentAlias, ProviderResponseInstrumentAlias) for item in aliases):
        raise MarketTruthError("provider aliases must be closed values")
    for index, left in enumerate(aliases):
        for right in aliases[index + 1:]:
            if _provider_alias_conflicts(left, right):
                raise MarketTruthError("provider alias interval overlaps or response attribution conflicts")


@dataclass(frozen=True)
class InstrumentSelector:
    """Durable economic intent, never a mutable provider or held-position key."""

    selector_kind: str
    parameters: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.selector_kind, str) or not self.selector_kind:
            raise MarketTruthError("selector_kind is required")
        object.__setattr__(self, "parameters", _frozen_pairs(self.parameters, "selector parameters"))
        schemas = {"nearest_eligible_weekly_call": ("delta_band",)}
        expected = schemas.get(self.selector_kind)
        if expected is None or tuple(key for key, _ in self.parameters) != expected:
            raise MarketTruthError("selector kind or economic parameter schema is not admitted")
        canonical_decimal(self.parameters[0][1])


@dataclass(frozen=True)
class ProviderInstrumentMapping:
    """A provider adapter's temporal alias for one canonical physical identity."""

    canonical_instrument: CanonicalInstrumentId
    provider: str
    provider_token: str
    adapter_version: str
    effective_from: datetime
    effective_to: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_instrument, CanonicalInstrumentId):
            raise MarketTruthError("mapping requires a canonical physical instrument")
        for name in ("provider", "provider_token", "adapter_version"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise MarketTruthError(f"{name} is required")
        _interval(self.effective_from, self.effective_to)


def _overlap(left: ProviderInstrumentMapping, right: ProviderInstrumentMapping) -> bool:
    left_end = left.effective_to
    right_end = right.effective_to
    return (right_end is None or left.effective_from < right_end) and (
        left_end is None or right.effective_from < left_end
    )


def validate_provider_mappings(mappings: tuple[ProviderInstrumentMapping, ...]) -> None:
    """Reject both remapped physical identities and overlapping provider-token reuse."""
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, ProviderInstrumentMapping):
            raise MarketTruthError("provider mappings must be closed values")
        for other in mappings[index + 1:]:
            if mapping.provider != other.provider or not _overlap(mapping, other):
                continue
            same_physical = mapping.canonical_instrument == other.canonical_instrument
            same_token = mapping.provider_token == other.provider_token
            if same_physical or same_token:
                raise MarketTruthError("provider mapping interval overlaps or token reuse is ambiguous")


def preserve_held_identity(held: CanonicalInstrumentId, selector: InstrumentSelector) -> CanonicalInstrumentId:
    """Bind a position to entry's physical contract; a selector cannot rewrite it."""
    if not isinstance(held, CanonicalInstrumentId) or not isinstance(selector, InstrumentSelector):
        raise MarketTruthError("held identity and selector must be canonical values")
    return held


@dataclass(frozen=True)
class Reconstruction:
    algorithm: str
    version: str
    unresolved_gaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.algorithm or not self.version:
            raise MarketTruthError("reconstruction requires algorithm and version")
        if any(not isinstance(gap, str) or not gap for gap in self.unresolved_gaps):
            raise MarketTruthError("reconstruction gaps must be explicit strings")


@dataclass(frozen=True)
class ContinuousFutureDefinition:
    """Explicit identity for a signal series and its independently tradable contracts."""

    signal_series: str
    roll_policy: str
    roll_policy_version: str
    adjustment_policy: str
    adjustment_policy_version: str
    tradable_contracts: tuple[CanonicalInstrumentId, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, name), str) or not getattr(self, name) for name in (
            "signal_series", "roll_policy", "roll_policy_version", "adjustment_policy", "adjustment_policy_version")):
            raise MarketTruthError("continuous future requires named versioned policies")
        if not self.tradable_contracts or any(not isinstance(item, CanonicalInstrumentId) for item in self.tradable_contracts):
            raise MarketTruthError("continuous future requires physical tradable contracts")
        if len(set(self.tradable_contracts)) != len(self.tradable_contracts):
            raise MarketTruthError("continuous future contracts must be distinct")

    @property
    def address(self) -> str:
        return content_address({"signal_series": self.signal_series, "roll": [self.roll_policy, self.roll_policy_version], "adjustment": [self.adjustment_policy, self.adjustment_policy_version], "contracts": [item.address for item in self.tradable_contracts]})


def _row_bytes(row: object) -> bytes:
    value = getattr(row, "canonical_json", None)
    if not isinstance(value, str):
        raise MarketTruthError("authority row has no canonical bytes")
    return value.encode("utf-8")


def persist_canonical_instrument(session, instrument: CanonicalPhysicalInstrument) -> None:
    from app.db.models import AuthorityCanonicalInstrument

    if not isinstance(instrument, CanonicalPhysicalInstrument):
        raise MarketTruthError("only canonical-instrument/1 can enter authority storage")
    if instrument.economic_underlier_address is not None:
        _, underlier_depth = _load_canonical_instrument_chain(
            session, instrument.economic_underlier_address)
        if underlier_depth >= _MAX_UNDERLIER_DEPTH:
            raise MarketTruthError("canonical underlier chain exceeds its bound")
    existing = session.get(AuthorityCanonicalInstrument, instrument.address)
    if existing is not None:
        loaded = load_canonical_instrument(session, instrument.address)
        if loaded.canonical_bytes != instrument.canonical_bytes:
            raise MarketTruthError("canonical instrument address collision")
        return
    session.add(AuthorityCanonicalInstrument(
        address=instrument.address, schema=instrument.SCHEMA,
        canonical_json=instrument.canonical_bytes.decode("utf-8"),
        venue_code=instrument.venue_code, asset_class=instrument.asset_class,
        contract_kind=instrument.contract_kind, currency=instrument.currency,
        economic_underlier_address=instrument.economic_underlier_address,
        authority_state="VERIFIED_V2"))
    session.flush()


def _load_canonical_instrument_chain(
        session, address: str, *, _seen: frozenset[str] = frozenset()
        ) -> tuple[CanonicalPhysicalInstrument, int]:
    from app.db.models import AuthorityCanonicalInstrument

    _address(address, "instrument address")
    seen = set(_seen)
    current_address = address
    requested: CanonicalPhysicalInstrument | None = None
    depth = 0
    while True:
        if current_address in seen:
            raise MarketTruthError("canonical underlier cycle detected")
        seen.add(current_address)
        row = session.get(AuthorityCanonicalInstrument, current_address)
        if (row is None or row.authority_state != "VERIFIED_V2"
                or row.schema != CanonicalPhysicalInstrument.SCHEMA):
            raise MarketTruthError("canonical instrument authority is absent")
        fact = CanonicalPhysicalInstrument.from_bytes(_row_bytes(row))
        if (fact.address != row.address or fact.venue_code != row.venue_code
                or fact.asset_class != row.asset_class or fact.contract_kind != row.contract_kind
                or fact.currency != row.currency
                or fact.economic_underlier_address != row.economic_underlier_address):
            raise MarketTruthError("canonical instrument copied columns do not match bytes")
        if requested is None:
            requested = fact
        if fact.economic_underlier_address is None:
            return requested, depth
        if depth >= _MAX_UNDERLIER_DEPTH:
            raise MarketTruthError("canonical underlier chain exceeds its bound")
        current_address = fact.economic_underlier_address
        depth += 1


def load_canonical_instrument(session, address: str, *, _seen: frozenset[str] = frozenset()
                              ) -> CanonicalPhysicalInstrument:
    fact, _depth = _load_canonical_instrument_chain(session, address, _seen=_seen)
    return fact


def persist_provider_identity(session, entity: ProviderEntity, product: ProviderProduct,
                              contract: ProviderContract) -> None:
    from app.db.models import (AuthorityProviderContract, AuthorityProviderEntity,
                               AuthorityProviderProduct)

    if (not isinstance(entity, ProviderEntity) or not isinstance(product, ProviderProduct)
            or not isinstance(contract, ProviderContract) or product.entity_address != entity.address
            or contract.product_address != product.address):
        raise MarketTruthError("provider entity/product/contract chain is inconsistent")
    for model, value, copied in (
        (AuthorityProviderEntity, entity, {"entity_code": entity.entity_code}),
        (AuthorityProviderProduct, product, {"entity_address": product.entity_address,
                                            "product_code": product.product_code,
                                            "observation_namespace": product.observation_namespace}),
        (AuthorityProviderContract, contract, {"owner_id": contract.owner_id,
                                               "product_address": contract.product_address,
                                               "mode": contract.mode,
                                               "effective_from": to_sql_utc_naive(
                                                   contract.effective_from, "effective_from"),
                                               "effective_to": to_sql_utc_naive(
                                                   contract.effective_to, "effective_to",
                                                   nullable=True)}),
    ):
        existing = session.get(model, value.address)
        if existing is not None:
            if _row_bytes(existing) != value.canonical_bytes:
                raise MarketTruthError("provider identity address collision")
            continue
        session.add(model(address=value.address, schema=value.SCHEMA,
                          canonical_json=value.canonical_bytes.decode("utf-8"),
                          authority_state="VERIFIED_V2", **copied))
        session.flush()


def load_provider_identity(session, contract_address: str
                           ) -> tuple[ProviderEntity, ProviderProduct, ProviderContract]:
    from app.db.models import (AuthorityProviderContract, AuthorityProviderEntity,
                               AuthorityProviderProduct)

    _address(contract_address, "provider contract address")
    contract_row = session.get(AuthorityProviderContract, contract_address)
    if (contract_row is None or contract_row.authority_state != "VERIFIED_V2"
            or contract_row.schema != ProviderContract.SCHEMA):
        raise MarketTruthError("provider contract authority is absent")
    contract = ProviderContract.from_bytes(_row_bytes(contract_row))
    product_row = session.get(AuthorityProviderProduct, contract.product_address)
    if (product_row is None or product_row.authority_state != "VERIFIED_V2"
            or product_row.schema != ProviderProduct.SCHEMA):
        raise MarketTruthError("provider product authority is absent")
    product = ProviderProduct.from_bytes(_row_bytes(product_row))
    entity_row = session.get(AuthorityProviderEntity, product.entity_address)
    if (entity_row is None or entity_row.authority_state != "VERIFIED_V2"
            or entity_row.schema != ProviderEntity.SCHEMA):
        raise MarketTruthError("provider entity authority is absent")
    entity = ProviderEntity.from_bytes(_row_bytes(entity_row))
    checks = (
        (contract.address, contract_row.address), (contract.product_address, contract_row.product_address),
        (contract.owner_id, contract_row.owner_id), (contract.mode, contract_row.mode),
        (to_sql_utc_naive(contract.effective_from, "effective_from"),
         require_sql_utc_naive(contract_row.effective_from, "effective_from")),
        (to_sql_utc_naive(contract.effective_to, "effective_to", nullable=True),
         require_sql_utc_naive(contract_row.effective_to, "effective_to", nullable=True)),
        (product.address, product_row.address), (product.entity_address, product_row.entity_address),
        (product.product_code, product_row.product_code),
        (product.observation_namespace, product_row.observation_namespace),
        (entity.address, entity_row.address), (entity.entity_code, entity_row.entity_code),
    )
    if any(left != right for left, right in checks):
        raise MarketTruthError("provider identity copied columns do not match bytes")
    return entity, product, contract


def _provider_alias_query_conditions(alias):
    from sqlalchemy import or_
    from app.db.models import AuthorityProviderAlias
    if isinstance(alias, ProviderResponseInstrumentAlias):
        return [
            AuthorityProviderAlias.provider_contract_address == alias.provider_contract_address,
            AuthorityProviderAlias.receipt_address == alias.source_evidence_address]
    conditions = [
        AuthorityProviderAlias.schema == ProviderInstrumentAlias.SCHEMA,
        AuthorityProviderAlias.product_address == alias.product_address,
        AuthorityProviderAlias.observation_namespace == alias.observation_namespace,
        or_(AuthorityProviderAlias.provider_token == alias.provider_token,
            AuthorityProviderAlias.provider_symbol == alias.provider_symbol,
            AuthorityProviderAlias.instrument_address == alias.canonical_instrument_address),
        or_(AuthorityProviderAlias.effective_to.is_(None),
            AuthorityProviderAlias.effective_to
            > to_sql_utc_naive(alias.effective_from, "effective_from")),
    ]
    if alias.effective_to is not None:
        conditions.append(
            AuthorityProviderAlias.effective_from
            < to_sql_utc_naive(alias.effective_to, "effective_to"))
    return conditions


def _validate_alias_product(session, alias):
    from app.db.models import AuthorityProviderProduct
    product = session.get(AuthorityProviderProduct, alias.product_address)
    if (product is None or product.authority_state != "VERIFIED_V2"
            or product.observation_namespace != alias.observation_namespace):
        raise MarketTruthError("provider alias product namespace does not match")


def persist_provider_alias(session, alias: ProviderInstrumentAlias) -> None:
    from sqlalchemy import select
    from app.db.models import AuthorityProviderAlias

    if type(alias) not in (ProviderInstrumentAlias, ProviderResponseInstrumentAlias):
        raise MarketTruthError("only closed provider instrument mappings can enter authority storage")
    _validate_response_alias_dependencies(session, alias)
    load_canonical_instrument(session, alias.canonical_instrument_address)
    _validate_alias_product(session, alias)
    conditions = _provider_alias_query_conditions(alias)
    overlap = session.execute(
        select(AuthorityProviderAlias).where(*conditions)).scalars().first()
    if overlap is not None and overlap.address != alias.address:
        raise MarketTruthError("provider alias interval overlaps in its product namespace")
    if overlap is not None:
        load_provider_alias(session, overlap.address)
        return
    session.add(AuthorityProviderAlias(
            address=alias.address, schema=alias.SCHEMA,
            canonical_json=alias.canonical_bytes.decode("utf-8"),
            product_address=alias.product_address,
            provider_contract_address=getattr(alias, "provider_contract_address", None),
            receipt_address=(alias.source_evidence_address
                             if isinstance(alias, ProviderResponseInstrumentAlias) else None),
            instrument_address=alias.canonical_instrument_address,
            provider_token=alias.provider_token, provider_symbol=alias.provider_symbol,
            observation_namespace=alias.observation_namespace,
            effective_from=to_sql_utc_naive(alias.effective_from, "effective_from"),
            effective_to=to_sql_utc_naive(alias.effective_to, "effective_to", nullable=True),
            authority_state="VERIFIED_V2"))
    session.flush()


def load_provider_alias(session, address: str) -> ProviderInstrumentAlias:
    from app.db.models import AuthorityProviderAlias
    _address(address, "provider alias address")
    row = session.get(AuthorityProviderAlias, address)
    if (row is None or row.authority_state != "VERIFIED_V2"
            or row.schema not in _PROVIDER_ALIAS_CODECS):
        raise MarketTruthError("provider alias authority is absent")
    alias = _PROVIDER_ALIAS_CODECS[row.schema].from_bytes(_row_bytes(row))
    _validate_response_alias_copies(row, alias)
    _validate_response_alias_dependencies(session, alias)
    checks = (
        (alias.address, row.address), (alias.product_address, row.product_address),
        (alias.canonical_instrument_address, row.instrument_address),
        (alias.provider_token, row.provider_token), (alias.provider_symbol, row.provider_symbol),
        (alias.observation_namespace, row.observation_namespace),
        (to_sql_utc_naive(alias.effective_from, "effective_from"),
         require_sql_utc_naive(row.effective_from, "effective_from")),
        (to_sql_utc_naive(alias.effective_to, "effective_to", nullable=True),
         require_sql_utc_naive(row.effective_to, "effective_to", nullable=True)),
    )
    if any(left != right for left, right in checks):
        raise MarketTruthError("provider alias copied columns do not match bytes")
    load_canonical_instrument(session, alias.canonical_instrument_address)
    _validate_alias_product(session, alias)
    return alias


_PROVIDER_ALIAS_CODECS = {
    ProviderInstrumentAlias.SCHEMA: ProviderInstrumentAlias,
    ProviderResponseInstrumentAlias.SCHEMA: ProviderResponseInstrumentAlias,
}


def _validate_response_alias_copies(row, alias):
    scope = _response_alias_scope(alias) or (None, None)
    if scope != (row.provider_contract_address, row.receipt_address):
        raise MarketTruthError("provider alias response scope differs from bytes")


def _validate_response_alias_dependencies(session, alias):
    if not isinstance(alias, ProviderResponseInstrumentAlias):
        return
    from app.market_data.observations import load_raw_segment
    _, product, contract = load_provider_identity(session, alias.provider_contract_address)
    receipt = load_raw_segment(session, alias.source_evidence_address)
    if (product.address != alias.product_address
            or receipt.contract_address != contract.address
            or receipt.product_address != product.address
            or receipt.owner_id != contract.owner_id):
        raise MarketTruthError("provider response alias contract or receipt does not match")
