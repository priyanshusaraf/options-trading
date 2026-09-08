"""Closed execution authority for DatasetManifest dependency roles.

Each public loader below owns one schema and one table.  Dataset consumers select
the loader from the manifest field being verified; callers never supply a fact
kind or an address dispatcher.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass, fields as dataclass_fields
from typing import Any, ClassVar

from app.ir.hashing import canonical_json
from app.market_truth.identity import CanonicalFact, canonical_fact_bytes
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive

_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_ITEMS = 1024


def _text(value: object, name: str, maximum: int = 256) -> str:
    if (not isinstance(value, str) or not value or len(value.encode()) > maximum
            or unicodedata.normalize("NFC", value) != value or "\x00" in value):
        raise ValueError(f"{name} must be bounded non-empty NFC text")
    return value


def _address(value: object, name: str) -> str:
    if not isinstance(value, str) or _ADDRESS.fullmatch(value) is None:
        raise ValueError(f"{name} must be a content address")
    return value


def _addresses(value: object, name: str, *, empty: bool = False, maximum: int = _MAX_ITEMS) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) > maximum or (not empty and not value):
        raise ValueError(f"{name} must be a bounded immutable address tuple")
    if value != tuple(sorted(set(value))):
        raise ValueError(f"{name} must be sorted and unique")
    for item in value:
        _address(item, name)
    return value


def _strings(value: object, name: str, *, empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) > _MAX_ITEMS or (not empty and not value):
        raise ValueError(f"{name} must be a bounded immutable string tuple")
    if value != tuple(sorted(set(value))):
        raise ValueError(f"{name} must be sorted and unique")
    for item in value:
        _text(item, name)
    return value


def _pairs(value: object, name: str, *, empty: bool = False) -> tuple[tuple[str, str], ...]:
    if (not isinstance(value, tuple) or len(value) > _MAX_ITEMS or (not empty and not value)
            or any(not isinstance(item, tuple) or len(item) != 2 for item in value)):
        raise ValueError(f"{name} must be bounded immutable pairs")
    if value != tuple(sorted(set(value))):
        raise ValueError(f"{name} must be sorted and unique")
    for key, item in value:
        _text(key, name)
        _text(item, name, 1024)
    return value


def _utc(value: dt.datetime, name: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(dt.timezone.utc)


def _common(owner_id: str, recorded_at: dt.datetime) -> tuple[str, dt.datetime]:
    return _text(owner_id, "owner_id", 64), _utc(recorded_at, "recorded_at")


def _fact_value(value: object) -> object:
    if isinstance(value, tuple):
        return [list(item) if isinstance(item, tuple) else item for item in value]
    if isinstance(value, dt.datetime):
        return value.isoformat()
    return value


class _ClosedDependency(CanonicalFact):
    SCHEMA: ClassVar[str]
    FIELDS: ClassVar[frozenset[str]]

    def fact(self) -> dict[str, Any]:
        return {field.name: _fact_value(getattr(self, field.name))
                for field in dataclass_fields(self)}

    @classmethod
    def _document(cls, payload: bytes) -> dict[str, Any]:
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f"{cls.SCHEMA} bytes are malformed") from exc
        if (not isinstance(document, dict) or set(document) != {"schema", "fact"}
                or document["schema"] != cls.SCHEMA or not isinstance(document["fact"], dict)
                or set(document["fact"]) != cls.FIELDS
                or canonical_json(document).encode() != payload):
            raise ValueError(f"{cls.SCHEMA} bytes are not closed canonical bytes")
        return document["fact"]

    @classmethod
    def _finish(cls, payload: bytes, values: dict[str, Any]):
        result = cls(**values)
        if result.canonical_bytes != payload:
            raise ValueError(f"{cls.SCHEMA} bytes do not reconstruct exactly")
        return result


@dataclass(frozen=True)
class RawSchema(_ClosedDependency):
    owner_id: str
    provider_product_address: str
    provider_contract_address: str
    schema_version: str
    fields: tuple[tuple[str, str], ...]
    evidence_address: str
    recorded_at: dt.datetime
    SCHEMA = "raw-schema/1"
    FIELDS = frozenset({"owner_id", "provider_product_address", "provider_contract_address",
        "schema_version", "fields", "evidence_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        _address(self.provider_product_address, "provider_product_address")
        _address(self.provider_contract_address, "provider_contract_address")
        _address(self.evidence_address, "evidence_address")
        _text(self.schema_version, "schema_version"); _pairs(self.fields, "fields")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "fields": tuple(tuple(x) for x in fact["fields"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class DeterministicAlgorithm(_ClosedDependency):
    owner_id: str
    name: str
    version: str
    implementation_address: str
    test_vector_addresses: tuple[str, ...]
    recorded_at: dt.datetime
    SCHEMA = "deterministic-algorithm/1"
    FIELDS = frozenset({"owner_id", "name", "version", "implementation_address",
        "test_vector_addresses", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        _text(self.name, "name"); _text(self.version, "version")
        _address(self.implementation_address, "implementation_address")
        _addresses(self.test_vector_addresses, "test_vector_addresses")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "test_vector_addresses": tuple(fact["test_vector_addresses"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class NormalizationTransform(_ClosedDependency):
    owner_id: str
    input_raw_schema_addresses: tuple[str, ...]
    output_schema: str
    parameters: tuple[tuple[str, str], ...]
    algorithm_address: str
    recorded_at: dt.datetime
    SCHEMA = "normalization-transform/1"
    FIELDS = frozenset({"owner_id", "input_raw_schema_addresses", "output_schema",
        "parameters", "algorithm_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        _addresses(self.input_raw_schema_addresses, "input_raw_schema_addresses")
        _text(self.output_schema, "output_schema"); _pairs(self.parameters, "parameters", empty=True)
        _address(self.algorithm_address, "algorithm_address")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact,
            "input_raw_schema_addresses": tuple(fact["input_raw_schema_addresses"]),
            "parameters": tuple(tuple(x) for x in fact["parameters"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class AlignmentPolicy(_ClosedDependency):
    owner_id: str
    calendar: str
    session: str
    timezone: str
    resolution_seconds: int
    truth_snapshot_address: str
    algorithm_address: str
    recorded_at: dt.datetime
    SCHEMA = "alignment-policy/1"
    FIELDS = frozenset({"owner_id", "calendar", "session", "timezone", "resolution_seconds",
        "truth_snapshot_address", "algorithm_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        for name in ("calendar", "session", "timezone"): _text(getattr(self, name), name)
        if isinstance(self.resolution_seconds, bool) or not isinstance(self.resolution_seconds, int) or self.resolution_seconds <= 0:
            raise ValueError("resolution_seconds must be positive")
        _address(self.truth_snapshot_address, "truth_snapshot_address")
        _address(self.algorithm_address, "algorithm_address")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class MissingDataPolicy(_ClosedDependency):
    owner_id: str
    handling: str
    explicit_gap_reasons: tuple[str, ...]
    algorithm_address: str
    recorded_at: dt.datetime
    SCHEMA = "missing-data-policy/1"
    FIELDS = frozenset({"owner_id", "handling", "explicit_gap_reasons", "algorithm_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        if self.handling not in {"REFUSE", "EXPLICIT_GAP"}: raise ValueError("missing-data handling is not closed")
        _strings(self.explicit_gap_reasons, "explicit_gap_reasons", empty=self.handling == "REFUSE")
        if self.handling == "REFUSE" and self.explicit_gap_reasons: raise ValueError("REFUSE cannot declare gap reasons")
        _address(self.algorithm_address, "algorithm_address")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "explicit_gap_reasons": tuple(fact["explicit_gap_reasons"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class AdjustmentPolicy(_ClosedDependency):
    owner_id: str
    instrument_addresses: tuple[str, ...]
    truth_snapshot_addresses: tuple[str, ...]
    method: str
    algorithm_address: str
    recorded_at: dt.datetime
    SCHEMA = "adjustment-policy/1"
    FIELDS = frozenset({"owner_id", "instrument_addresses", "truth_snapshot_addresses", "method",
        "algorithm_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        _addresses(self.instrument_addresses, "instrument_addresses")
        _addresses(self.truth_snapshot_addresses, "truth_snapshot_addresses")
        _text(self.method, "method"); _address(self.algorithm_address, "algorithm_address")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "instrument_addresses": tuple(fact["instrument_addresses"]),
            "truth_snapshot_addresses": tuple(fact["truth_snapshot_addresses"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class RollPolicy(AdjustmentPolicy):
    selection_rule: str
    SCHEMA = "roll-policy/1"
    FIELDS = frozenset({"owner_id", "instrument_addresses", "truth_snapshot_addresses", "method",
        "algorithm_address", "recorded_at", "selection_rule"})

    def __post_init__(self):
        super().__post_init__(); _text(self.selection_rule, "selection_rule")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "instrument_addresses": tuple(fact["instrument_addresses"]),
            "truth_snapshot_addresses": tuple(fact["truth_snapshot_addresses"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class DatasetCreationEvidence(_ClosedDependency):
    owner_id: str
    producer: str
    source_addresses: tuple[str, ...]
    artifact_addresses: tuple[str, ...]
    algorithm_address: str
    recorded_at: dt.datetime
    SCHEMA = "dataset-creation-evidence/1"
    # 2,000 daily OHLCV rows, with one provider and one normalized fact per field.
    MAX_SOURCE_ADDRESSES: ClassVar[int] = 20_000
    MAX_CANONICAL_BYTES: ClassVar[int] = 2 * 1024 * 1024
    FIELDS = frozenset({"owner_id", "producer", "source_addresses", "artifact_addresses",
        "algorithm_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        _text(self.producer, "producer")
        _addresses(self.source_addresses, "source_addresses", maximum=self.MAX_SOURCE_ADDRESSES)
        _addresses(self.artifact_addresses, "artifact_addresses")
        _address(self.algorithm_address, "algorithm_address")

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_fact_bytes(self.SCHEMA, self.fact(), maximum_bytes=self.MAX_CANONICAL_BYTES)

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "source_addresses": tuple(fact["source_addresses"]),
            "artifact_addresses": tuple(fact["artifact_addresses"]),
            "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


@dataclass(frozen=True)
class DatasetCorrection(_ClosedDependency):
    owner_id: str
    provider_product_address: str
    provider_contract_address: str
    sequence: int
    supersedes_address: str | None
    reason: str
    creation_evidence_address: str
    algorithm_address: str
    recorded_at: dt.datetime
    SCHEMA = "dataset-correction/1"
    FIELDS = frozenset({"owner_id", "provider_product_address", "provider_contract_address",
        "sequence", "supersedes_address", "reason", "creation_evidence_address",
        "algorithm_address", "recorded_at"})

    def __post_init__(self):
        owner, recorded = _common(self.owner_id, self.recorded_at)
        object.__setattr__(self, "owner_id", owner); object.__setattr__(self, "recorded_at", recorded)
        _address(self.provider_product_address, "provider_product_address")
        _address(self.provider_contract_address, "provider_contract_address")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0: raise ValueError("correction sequence is invalid")
        if self.supersedes_address is not None: _address(self.supersedes_address, "supersedes_address")
        if (self.sequence == 0) != (self.supersedes_address is None): raise ValueError("correction predecessor and sequence disagree")
        _text(self.reason, "reason"); _address(self.creation_evidence_address, "creation_evidence_address")
        _address(self.algorithm_address, "algorithm_address")

    @classmethod
    def from_bytes(cls, payload: bytes):
        fact = cls._document(payload)
        return cls._finish(payload, {**fact, "recorded_at": dt.datetime.fromisoformat(fact["recorded_at"])})


def _row_values(fact: _ClosedDependency, *, product: str | None = None,
                contract: str | None = None, role_value: str = "") -> dict[str, Any]:
    dependencies: set[str] = set()
    for name, value in fact.fact().items():
        if name.endswith("_address") and isinstance(value, str) and _ADDRESS.fullmatch(value):
            dependencies.add(value)
        elif name.endswith("_addresses") and isinstance(value, list):
            dependencies.update(item for item in value
                                if isinstance(item, str) and _ADDRESS.fullmatch(item))
    return {"address": fact.address, "schema": fact.SCHEMA,
        "canonical_json": fact.canonical_bytes.decode(), "owner_id": fact.owner_id,
        "product_address": product, "contract_address": contract,
        "dependency_addresses_json": canonical_json(sorted(dependencies)), "role_value": role_value,
        "recorded_at": to_sql_utc_naive(fact.recorded_at, "recorded_at"),
        "authority_state": "VERIFIED_V2"}


def _role_value(fact: _ClosedDependency) -> str:
    for name in ("schema_version", "version", "output_schema", "handling", "method",
                 "producer"):
        value = getattr(fact, name, None)
        if isinstance(value, str):
            return value
    if isinstance(fact, DatasetCorrection):
        return str(fact.sequence)
    return ""


def _persist(session, model, fact, values, loader):
    existing = session.get(model, fact.address)
    if existing is not None:
        if loader(session, fact.address).canonical_bytes != fact.canonical_bytes:
            raise ValueError(f"{fact.SCHEMA} address collision")
        return
    session.add(model(**values)); session.flush()


def _load_row(session, model, cls, address):
    row = session.get(model, address)
    if row is None or row.authority_state != "VERIFIED_V2" or row.schema != cls.SCHEMA:
        raise ValueError(f"{cls.SCHEMA} authority is absent")
    fact = cls.from_bytes(row.canonical_json.encode())
    expected = _row_values(fact, product=getattr(fact, "provider_product_address", None),
        contract=getattr(fact, "provider_contract_address", None),
        role_value=_role_value(fact))
    for name in ("address", "schema", "canonical_json", "owner_id", "product_address",
                 "contract_address", "dependency_addresses_json", "role_value",
                 "authority_state"):
        if getattr(row, name) != expected[name]:
            raise ValueError(f"{cls.SCHEMA} copied columns do not match bytes")
    if (require_sql_utc_naive(row.recorded_at, "recorded_at")
            != expected["recorded_at"]):
        raise ValueError(f"{cls.SCHEMA} copied columns do not match bytes")
    return fact


def persist_deterministic_algorithm(session, fact: DeterministicAlgorithm) -> None:
    from app.db.models import AuthorityDeterministicAlgorithm
    _persist(session, AuthorityDeterministicAlgorithm, fact,
        _row_values(fact, role_value=fact.version), load_deterministic_algorithm)


def load_deterministic_algorithm(session, address: str) -> DeterministicAlgorithm:
    from app.db.models import AuthorityDeterministicAlgorithm
    return _load_row(session, AuthorityDeterministicAlgorithm, DeterministicAlgorithm, address)


def persist_raw_schema(session, fact: RawSchema) -> None:
    from app.db.models import AuthorityRawSchema
    from app.market_truth.identity import load_provider_identity
    _, product, contract = load_provider_identity(session, fact.provider_contract_address)
    if product.address != fact.provider_product_address or contract.owner_id != fact.owner_id:
        raise ValueError("raw schema provider contract does not match")
    _persist(session, AuthorityRawSchema, fact, _row_values(fact,
        product=fact.provider_product_address, contract=fact.provider_contract_address,
        role_value=fact.schema_version), load_raw_schema)


def load_raw_schema(session, address: str) -> RawSchema:
    from app.db.models import AuthorityRawSchema
    from app.market_truth.identity import load_provider_identity
    fact = _load_row(session, AuthorityRawSchema, RawSchema, address)
    _, product, contract = load_provider_identity(session, fact.provider_contract_address)
    if product.address != fact.provider_product_address or contract.owner_id != fact.owner_id:
        raise ValueError("raw schema provider contract does not match")
    return fact


def persist_normalization_transform(session, fact: NormalizationTransform) -> None:
    from app.db.models import AuthorityNormalizationTransform
    for address in fact.input_raw_schema_addresses:
        if load_raw_schema(session, address).owner_id != fact.owner_id: raise ValueError("transform owner mismatch")
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("transform algorithm owner mismatch")
    _persist(session, AuthorityNormalizationTransform, fact,
        _row_values(fact, role_value=fact.output_schema), load_normalization_transform)


def load_normalization_transform(session, address: str) -> NormalizationTransform:
    from app.db.models import AuthorityNormalizationTransform
    fact = _load_row(session, AuthorityNormalizationTransform, NormalizationTransform, address)
    for dependency in fact.input_raw_schema_addresses:
        if load_raw_schema(session, dependency).owner_id != fact.owner_id: raise ValueError("transform owner mismatch")
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("transform algorithm owner mismatch")
    return fact


def _persist_policy(session, model, fact, loader):
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("policy algorithm owner mismatch")
    _persist(session, model, fact, _row_values(fact, role_value=getattr(fact, "handling", getattr(fact, "method", ""))), loader)


def persist_alignment_policy(session, fact: AlignmentPolicy) -> None:
    from app.db.models import AuthorityAlignmentPolicy
    from app.market_truth.authority import load_market_truth_snapshot
    load_market_truth_snapshot(session, fact.truth_snapshot_address)
    _persist_policy(session, AuthorityAlignmentPolicy, fact, load_alignment_policy)


def load_alignment_policy(session, address: str) -> AlignmentPolicy:
    from app.db.models import AuthorityAlignmentPolicy
    from app.market_truth.authority import load_market_truth_snapshot
    fact = _load_row(session, AuthorityAlignmentPolicy, AlignmentPolicy, address)
    load_market_truth_snapshot(session, fact.truth_snapshot_address)
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("policy algorithm owner mismatch")
    return fact


def persist_missing_data_policy(session, fact: MissingDataPolicy) -> None:
    from app.db.models import AuthorityMissingDataPolicy
    _persist_policy(session, AuthorityMissingDataPolicy, fact, load_missing_data_policy)


def load_missing_data_policy(session, address: str) -> MissingDataPolicy:
    from app.db.models import AuthorityMissingDataPolicy
    fact = _load_row(session, AuthorityMissingDataPolicy, MissingDataPolicy, address)
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("policy algorithm owner mismatch")
    return fact


def _verify_instrument_truth_policy(session, fact):
    from app.market_truth.identity import load_canonical_instrument
    from app.market_truth.authority import load_market_truth_snapshot
    for address in fact.instrument_addresses: load_canonical_instrument(session, address)
    for address in fact.truth_snapshot_addresses: load_market_truth_snapshot(session, address)
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("policy algorithm owner mismatch")


def persist_adjustment_policy(session, fact: AdjustmentPolicy) -> None:
    from app.db.models import AuthorityAdjustmentPolicy
    _verify_instrument_truth_policy(session, fact)
    _persist(session, AuthorityAdjustmentPolicy, fact, _row_values(fact, role_value=fact.method), load_adjustment_policy)


def load_adjustment_policy(session, address: str) -> AdjustmentPolicy:
    from app.db.models import AuthorityAdjustmentPolicy
    fact = _load_row(session, AuthorityAdjustmentPolicy, AdjustmentPolicy, address)
    _verify_instrument_truth_policy(session, fact); return fact


def persist_roll_policy(session, fact: RollPolicy) -> None:
    from app.db.models import AuthorityRollPolicy
    _verify_instrument_truth_policy(session, fact)
    _persist(session, AuthorityRollPolicy, fact, _row_values(fact, role_value=fact.method), load_roll_policy)


def load_roll_policy(session, address: str) -> RollPolicy:
    from app.db.models import AuthorityRollPolicy
    fact = _load_row(session, AuthorityRollPolicy, RollPolicy, address)
    _verify_instrument_truth_policy(session, fact); return fact


def persist_dataset_creation_evidence(session, fact: DatasetCreationEvidence) -> None:
    from app.db.models import AuthorityDatasetCreationEvidence
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("creation algorithm owner mismatch")
    _persist(session, AuthorityDatasetCreationEvidence, fact, _row_values(fact, role_value=fact.producer), load_dataset_creation_evidence)


def load_dataset_creation_evidence(session, address: str) -> DatasetCreationEvidence:
    from app.db.models import AuthorityDatasetCreationEvidence
    fact = _load_row(session, AuthorityDatasetCreationEvidence, DatasetCreationEvidence, address)
    if load_deterministic_algorithm(session, fact.algorithm_address).owner_id != fact.owner_id: raise ValueError("creation algorithm owner mismatch")
    return fact


def persist_dataset_correction(session, fact: DatasetCorrection) -> None:
    from app.db.models import AuthorityDatasetCorrection
    from app.market_truth.identity import load_provider_identity
    existing = session.get(AuthorityDatasetCorrection, fact.address)
    if existing is not None:
        if load_dataset_correction(session, fact.address).canonical_bytes != fact.canonical_bytes:
            raise ValueError("dataset-correction/1 address collision")
        return
    creation = load_dataset_creation_evidence(session, fact.creation_evidence_address)
    algorithm = load_deterministic_algorithm(session, fact.algorithm_address)
    _, product, contract = load_provider_identity(session, fact.provider_contract_address)
    if (creation.owner_id != fact.owner_id or algorithm.owner_id != fact.owner_id
            or product.address != fact.provider_product_address
            or contract.owner_id != fact.owner_id):
        raise ValueError("correction dependencies cross authority")
    if fact.supersedes_address is not None:
        prior = load_dataset_correction(session, fact.supersedes_address)
        if (prior.owner_id, prior.provider_product_address, prior.provider_contract_address, prior.sequence + 1) != (
                fact.owner_id, fact.provider_product_address, fact.provider_contract_address, fact.sequence):
            raise ValueError("correction chain crosses authority or skips sequence")
    from sqlalchemy import select
    sequence_row = session.execute(select(AuthorityDatasetCorrection.address).where(
            AuthorityDatasetCorrection.owner_id == fact.owner_id,
            AuthorityDatasetCorrection.product_address == fact.provider_product_address,
            AuthorityDatasetCorrection.contract_address == fact.provider_contract_address,
            AuthorityDatasetCorrection.role_value == str(fact.sequence))).first()
    if sequence_row is not None:
        raise ValueError("correction chain fork is forbidden")
    _persist(session, AuthorityDatasetCorrection, fact, _row_values(fact,
        product=fact.provider_product_address, contract=fact.provider_contract_address,
        role_value=str(fact.sequence)), load_dataset_correction)


def load_dataset_correction(session, address: str, *, _seen: frozenset[str] = frozenset()) -> DatasetCorrection:
    from app.db.models import AuthorityDatasetCorrection
    from app.market_truth.identity import load_provider_identity
    if address in _seen: raise ValueError("correction cycle is forbidden")
    fact = _load_row(session, AuthorityDatasetCorrection, DatasetCorrection, address)
    creation = load_dataset_creation_evidence(session, fact.creation_evidence_address)
    algorithm = load_deterministic_algorithm(session, fact.algorithm_address)
    _, product, contract = load_provider_identity(session, fact.provider_contract_address)
    if (creation.owner_id != fact.owner_id or algorithm.owner_id != fact.owner_id
            or product.address != fact.provider_product_address
            or contract.owner_id != fact.owner_id):
        raise ValueError("correction dependencies cross authority")
    if fact.supersedes_address is not None:
        prior = load_dataset_correction(session, fact.supersedes_address, _seen=_seen | {address})
        if (prior.owner_id, prior.provider_product_address, prior.provider_contract_address, prior.sequence + 1) != (
                fact.owner_id, fact.provider_product_address, fact.provider_contract_address, fact.sequence):
            raise ValueError("correction chain crosses authority or skips sequence")
    return fact


__all__ = ["AdjustmentPolicy", "AlignmentPolicy", "DatasetCorrection", "DatasetCreationEvidence",
    "DeterministicAlgorithm", "MissingDataPolicy", "NormalizationTransform", "RawSchema", "RollPolicy",
    "load_adjustment_policy", "load_alignment_policy", "load_dataset_correction",
    "load_dataset_creation_evidence", "load_deterministic_algorithm", "load_missing_data_policy",
    "load_normalization_transform", "load_raw_schema", "load_roll_policy", "persist_adjustment_policy",
    "persist_alignment_policy", "persist_dataset_correction", "persist_dataset_creation_evidence",
    "persist_deterministic_algorithm", "persist_missing_data_policy", "persist_normalization_transform",
    "persist_raw_schema", "persist_roll_policy"]
