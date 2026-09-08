"""Immutable point-in-time rulebook and market-truth snapshot contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, ClassVar

from app.ir.hashing import canonical_json
from app.market_truth.identity import (CanonicalFact, MarketTruthError, Quality,
    Reconstruction, _address, _closed_text, _frozen_pairs, _instant, _interval,
    canonical_fact_address, canonical_fact_bytes)


_MAX_RECORDS = 10_000


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class RulebookRecord:
    """One revisioned fact whose natural key has one value at an instant."""

    record_kind: str
    natural_key: tuple[tuple[str, str], ...]
    terms: tuple[tuple[str, str], ...]
    effective_from: datetime
    effective_to: datetime | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.record_kind, str) or not self.record_kind:
            raise MarketTruthError("record_kind is required")
        object.__setattr__(self, "natural_key", _frozen_pairs(self.natural_key, "natural_key"))
        object.__setattr__(self, "terms", _frozen_pairs(self.terms, "terms"))
        _interval(self.effective_from, self.effective_to)
        _instant(self.recorded_at, "recorded_at")
        object.__setattr__(self, "effective_from", _utc(self.effective_from))
        if self.effective_to is not None:
            object.__setattr__(self, "effective_to", _utc(self.effective_to))
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at))

    def payload(self) -> dict[str, Any]:
        return {"record_kind": self.record_kind, "natural_key": self.natural_key, "terms": self.terms, "effective_from": self.effective_from.isoformat(), "effective_to": self.effective_to.isoformat() if self.effective_to else None, "recorded_at": self.recorded_at.isoformat()}


def _contains(record: RulebookRecord, at: datetime) -> bool:
    return record.effective_from <= at and (record.effective_to is None or at < record.effective_to)


def _validate_records(records: tuple[RulebookRecord, ...]) -> None:
    for index, record in enumerate(records):
        if not isinstance(record, RulebookRecord):
            raise MarketTruthError("snapshot records must be rulebook records")
        for other in records[index + 1:]:
            if record.record_kind != other.record_kind or record.natural_key != other.natural_key:
                continue
            if (other.effective_to is None or record.effective_from < other.effective_to) and (record.effective_to is None or other.effective_from < record.effective_to):
                if record.recorded_at == other.recorded_at:
                    raise MarketTruthError("rulebook records overlap ambiguously on their natural key")


@dataclass(frozen=True)
class MarketTruthSnapshot(CanonicalFact):
    """An immutable manifest. Current state cannot substitute for this revision."""

    records: tuple[RulebookRecord, ...]
    effective_from: datetime
    effective_to: datetime | None
    recorded_at: datetime
    quality: Quality
    reconstruction: Reconstruction | None = None
    authority_scope: str = "LEGACY"
    knowledge_cutoff: datetime | None = None
    instrument_addresses: tuple[str, ...] = ()
    source_evidence: tuple[str, ...] = ()
    _canonical_schema: str = field(
        default="market-truth-snapshot/3", init=False, repr=False, compare=True)

    LEGACY_SCHEMA: ClassVar[str] = "market-truth-snapshot/2"
    SCHEMA: ClassVar[str] = "market-truth-snapshot/3"
    SUPPORTED_SCHEMAS: ClassVar[frozenset[str]] = frozenset({LEGACY_SCHEMA, SCHEMA})

    def __post_init__(self) -> None:
        _interval(self.effective_from, self.effective_to)
        _instant(self.recorded_at, "recorded_at")
        if not isinstance(self.quality, Quality):
            raise MarketTruthError("market truth quality is closed")
        if self.quality is Quality.RECONSTRUCTED and self.reconstruction is None:
            raise MarketTruthError("reconstructed truth requires algorithm/version/gaps")
        if self.quality is not Quality.RECONSTRUCTED and self.reconstruction is not None:
            raise MarketTruthError("only reconstructed truth has reconstruction metadata")
        records = tuple(self.records)
        if len(records) > _MAX_RECORDS:
            raise MarketTruthError("market truth record bound exceeded")
        _validate_records(records)
        object.__setattr__(self, "effective_from", _utc(self.effective_from))
        if self.effective_to is not None:
            object.__setattr__(self, "effective_to", _utc(self.effective_to))
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at))
        cutoff = self.knowledge_cutoff or self.recorded_at
        _instant(cutoff, "knowledge_cutoff")
        cutoff = _utc(cutoff)
        object.__setattr__(self, "knowledge_cutoff", cutoff)
        _closed_text(self.authority_scope, "authority_scope", maximum=128)
        instruments = tuple(self.instrument_addresses)
        evidence = tuple(self.source_evidence)
        if len(instruments) > _MAX_RECORDS or len(evidence) > _MAX_RECORDS:
            raise MarketTruthError("market truth dependency bound exceeded")
        for value in instruments:
            _address(value, "instrument address")
        for value in evidence:
            _address(value, "source evidence address")
        if tuple(sorted(set(instruments))) != instruments or tuple(sorted(set(evidence))) != evidence:
            raise MarketTruthError("market truth dependencies must be sorted and unique")
        if any(record.recorded_at > cutoff for record in records):
            raise MarketTruthError("snapshot cannot contain a record learned after its knowledge_cutoff")
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "instrument_addresses", instruments)
        object.__setattr__(self, "source_evidence", evidence)

    @property
    def digest(self) -> str:
        return self.address

    @property
    def schema(self) -> str:
        """The exact schema that supplied this immutable snapshot."""
        return self._canonical_schema

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_fact_bytes(self.schema, self.fact())

    @property
    def address(self) -> str:
        return canonical_fact_address(self.schema, self.fact())

    def fact(self) -> dict[str, Any]:
        reconstruction = None if self.reconstruction is None else {
            "algorithm": self.reconstruction.algorithm,
            "version": self.reconstruction.version,
            "unresolved_gaps": list(self.reconstruction.unresolved_gaps),
        }
        fact = {
            "authority_scope": self.authority_scope,
            "knowledge_cutoff": self.knowledge_cutoff.isoformat(),
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "quality": self.quality.value,
            "instrument_addresses": list(self.instrument_addresses),
            "records": [record.payload() for record in self.records],
            "source_evidence": list(self.source_evidence),
            "reconstruction": reconstruction,
        }
        if self.schema == self.SCHEMA:
            fact["recorded_at"] = self.recorded_at.isoformat()
        elif self.schema != self.LEGACY_SCHEMA:  # pragma: no cover - frozen internal guard
            raise MarketTruthError("market truth snapshot schema is unsupported")
        return fact

    def require_authority_complete(self) -> None:
        if self.schema != self.SCHEMA:
            raise MarketTruthError("legacy market truth is reconstruction-only")
        self.require_loadable_authority()

    def require_loadable_authority(self) -> None:
        """Verify common content for current writes or frozen historical reads."""
        if self.authority_scope == "LEGACY":
            raise MarketTruthError("legacy market truth has no typed authority")
        if self.quality is Quality.OBSERVED and not self.source_evidence:
            raise MarketTruthError("observed truth requires immutable source evidence")
        if self.quality is Quality.UNKNOWN and (self.records or self.instrument_addresses):
            raise MarketTruthError("unknown truth cannot carry authoritative records")

    @classmethod
    def from_bytes(cls, value: bytes) -> "MarketTruthSnapshot":
        document = cls._canonical_document(value)
        if document["schema"] == cls.LEGACY_SCHEMA:
            return cls.from_legacy_v2_bytes(value)
        if document["schema"] != cls.SCHEMA:
            raise MarketTruthError("market truth snapshot schema is unsupported")
        return cls._from_document(value, document, schema=cls.SCHEMA)

    @classmethod
    def from_legacy_v2_bytes(cls, value: bytes) -> "MarketTruthSnapshot":
        """Reconstruct actual historical v2 bytes without inventing a new identity."""
        document = cls._canonical_document(value)
        if document["schema"] != cls.LEGACY_SCHEMA:
            raise MarketTruthError("market truth bytes are not an explicit legacy v2 snapshot")
        return cls._from_document(value, document, schema=cls.LEGACY_SCHEMA)

    @classmethod
    def _canonical_document(cls, value: bytes) -> dict[str, Any]:
        if not isinstance(value, bytes) or len(value) > 256 * 1024:
            raise MarketTruthError("market truth bytes are absent or oversized")
        try:
            document = json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketTruthError("market truth bytes are malformed") from exc
        if (canonical_json(document).encode("utf-8") != value
                or not isinstance(document, dict)
                or set(document) != {"schema", "fact"}):
            raise MarketTruthError("market truth envelope is not closed and canonical")
        return document

    @classmethod
    def _from_document(cls, value: bytes, document: dict[str, Any], *, schema: str) -> "MarketTruthSnapshot":
        fact = document["fact"]
        keys = {"authority_scope", "knowledge_cutoff", "effective_from", "effective_to",
            "quality", "instrument_addresses", "records", "source_evidence", "reconstruction"}
        if schema == cls.SCHEMA:
            keys.add("recorded_at")
        if not isinstance(fact, dict) or set(fact) != keys:
            raise MarketTruthError("market truth document is not closed")
        try:
            reconstruction = fact["reconstruction"]
            reconstructed = None if reconstruction is None else Reconstruction(
                reconstruction["algorithm"], reconstruction["version"],
                tuple(reconstruction["unresolved_gaps"]))
            records = tuple(RulebookRecord(
                row["record_kind"], tuple(tuple(item) for item in row["natural_key"]),
                tuple(tuple(item) for item in row["terms"]),
                datetime.fromisoformat(row["effective_from"]),
                datetime.fromisoformat(row["effective_to"]) if row["effective_to"] else None,
                datetime.fromisoformat(row["recorded_at"])) for row in fact["records"])
            recorded_at = datetime.fromisoformat(
                fact["recorded_at"] if schema == cls.SCHEMA else fact["knowledge_cutoff"])
            result = cls(records, datetime.fromisoformat(fact["effective_from"]),
                datetime.fromisoformat(fact["effective_to"]) if fact["effective_to"] else None,
                recorded_at, Quality(fact["quality"]),
                reconstructed, fact["authority_scope"], datetime.fromisoformat(fact["knowledge_cutoff"]),
                tuple(fact["instrument_addresses"]), tuple(fact["source_evidence"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketTruthError("market truth document is malformed") from exc
        object.__setattr__(result, "_canonical_schema", schema)
        if result.canonical_bytes != value:
            raise MarketTruthError("market truth bytes do not reconstruct exactly")
        return result

    def require_observed_ground_truth(self) -> None:
        if self.quality is not Quality.OBSERVED:
            raise MarketTruthError("only OBSERVED truth supports a ground-truth claim")

    def record_at(self, record_kind: str, natural_key: tuple[tuple[str, str], ...], at: datetime) -> RulebookRecord:
        return resolve_record(
            self.records, record_kind, natural_key, at,
            recorded_at_cutoff=self.knowledge_cutoff,
        )


def resolve_record(records: tuple[RulebookRecord, ...], record_kind: str, natural_key: tuple[tuple[str, str], ...], at: datetime, *, recorded_at_cutoff: datetime | None = None) -> RulebookRecord:
    """Resolve exactly one historical fact; gaps never forward-fill current rules."""
    _instant(at, "at")
    if recorded_at_cutoff is not None:
        _instant(recorded_at_cutoff, "recorded_at_cutoff")
    key = _frozen_pairs(natural_key, "natural_key")
    matches = [record for record in records if record.record_kind == record_kind and record.natural_key == key and _contains(record, at) and (recorded_at_cutoff is None or record.recorded_at <= recorded_at_cutoff)]
    if not matches:
        raise MarketTruthError("point-in-time rule is unavailable or ambiguous; current substitution is forbidden")
    latest = max(record.recorded_at for record in matches)
    resolved = [record for record in matches if record.recorded_at == latest]
    if len(resolved) != 1:
        raise MarketTruthError("point-in-time rule is unavailable or ambiguous; current substitution is forbidden")
    return resolved[0]
