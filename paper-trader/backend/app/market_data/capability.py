"""Closed, immutable Phase 4 data-capability assessment facts.

Profiles describe declared data capability only; they neither choose nor connect a
provider and contain no execution authority or credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, TYPE_CHECKING

from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address
from app.market_data.requirements import DataRequirementPlan
from app.market_truth.identity import (
    ProviderContract,
    canonical_fact_address,
    canonical_fact_bytes,
)


if TYPE_CHECKING:
    from app.backtest.dataset_store import DatasetManifest
    from app.ir.first_party.analytical_v2.contracts import ContractInputBindings


class CapabilityRefusal(ValueError):
    """A capability fact is incomplete, stale, or semantically unsafe."""


_MODES = frozenset({"RESEARCH", "PAPER", "LIVE"})
_RESULTS = frozenset({"SATISFIED", "UNAVAILABLE", "INSUFFICIENT_RANGE", "INSUFFICIENT_RESOLUTION", "INSUFFICIENT_FRESHNESS", "UNKNOWN"})
_REASONS = {"SATISFIED": frozenset({"one declared offer covers the complete requirement"}), "UNKNOWN": frozenset({"complete capability is unknown"}), "UNAVAILABLE": frozenset({"entitlement is not verified", "no single offer covers the complete requirement"}), "INSUFFICIENT_RANGE": frozenset({"no complete offer has required history"}), "INSUFFICIENT_RESOLUTION": frozenset({"no complete offer has required resolution"}), "INSUFFICIENT_FRESHNESS": frozenset({"no complete offer has required freshness"})}
_FIELDS = frozenset({"OPEN", "HIGH", "LOW", "CLOSE", "LAST", "BID", "ASK", "BID_SIZE", "ASK_SIZE", "TRADE", "VOLUME", "OPEN_INTEREST", "IMPLIED_VOLATILITY", "DELTA", "GAMMA", "VEGA", "THETA"})
_INSTRUMENT_TYPES = frozenset({"PHYSICAL", "ECONOMIC_SELECTOR", "CONTINUOUS_FUTURE"})
_SESSIONS = frozenset({"INSTRUMENT_CALENDAR", "CONTINUOUS", "ALL_RECORDED"})
_ALIGNMENTS = frozenset({"EXACT", "ASOF_BACKWARD", "COMPLETED_RESAMPLE"})
_ENTITLEMENT_STATES = frozenset({"VERIFIED", "UNVERIFIED", "DENIED"})
_MAX_OFFERS = 10_000
CAPABILITY_ASSESSMENT_SCHEMA = "capability-assessment/2"
CAPABILITY_ASSESSMENT_ALGORITHM = "closed-capability-evaluation"
CAPABILITY_ASSESSMENT_ALGORITHM_VERSION = "2"
_ASSESSMENT_FACT_KEYS = frozenset({
    "owner_id", "mode", "plan_address", "registry_snapshot_address",
    "capability_profile_address", "dataset_manifest_address",
    "market_truth_snapshot_address", "evaluation_policy_address",
    "assessment_evidence_address", "assessed_at", "requirement_results",
    "assessment_algorithm", "assessment_algorithm_version",
})
_ASSESSMENT_ADDRESS_KEYS = _ASSESSMENT_FACT_KEYS - {
    "owner_id", "mode", "assessed_at", "requirement_results",
    "assessment_algorithm", "assessment_algorithm_version",
}


def _address(value: str, label: str) -> str:
    if not isinstance(value, str) or not is_content_address(value):
        raise CapabilityRefusal(f"{label} must be a content address")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise CapabilityRefusal("capability facts must be closed JSON")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _time_text(value: int | datetime) -> str | int:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CapabilityRefusal("capability time must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, bool) or not isinstance(value, int):
        raise CapabilityRefusal("capability time is invalid")
    return value


def _aware_datetime(value: Any, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CapabilityRefusal(f"{label} is invalid") from exc
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        raise CapabilityRefusal(f"{label} is invalid")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProviderConformance:
    product_address: str
    tested_fields: tuple[str, ...]
    tested_resolutions: tuple[int, ...]
    test_method: str
    test_version: str
    observed_from: datetime
    observed_to: datetime
    evidence_artifacts: tuple[str, ...]
    result: str
    coverage: tuple[Mapping[str, Any], ...] = ()

    SCHEMA = "provider-conformance/1"
    V2_SCHEMA = "provider-conformance/2"
    SUPPORTED_SCHEMAS = frozenset({SCHEMA, V2_SCHEMA})

    def __post_init__(self) -> None:
        _address(self.product_address, "product")
        if (not self.test_method or not self.test_version or self.result not in {"PASS", "FAIL"}
                or self.observed_from.tzinfo is None or self.observed_to.tzinfo is None
                or self.observed_to <= self.observed_from):
            raise CapabilityRefusal("provider conformance metadata is invalid")
        fields = tuple(sorted(set(self.tested_fields)))
        resolutions = tuple(sorted(set(self.tested_resolutions)))
        artifacts = tuple(sorted(set(self.evidence_artifacts)))
        if not fields or any(item not in _FIELDS for item in fields):
            raise CapabilityRefusal("provider conformance fields are invalid")
        if not resolutions or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in resolutions):
            raise CapabilityRefusal("provider conformance resolutions are invalid")
        if not artifacts:
            raise CapabilityRefusal("provider conformance requires evidence artifacts")
        for item in artifacts:
            _address(item, "conformance artifact")
        object.__setattr__(self, "tested_fields", fields)
        object.__setattr__(self, "tested_resolutions", resolutions)
        object.__setattr__(self, "evidence_artifacts", artifacts)
        object.__setattr__(self, "observed_from", self.observed_from.astimezone(timezone.utc))
        object.__setattr__(self, "observed_to", self.observed_to.astimezone(timezone.utc))
        normalized_coverage: list[Mapping[str, Any]] = []
        for row in self.coverage:
            if not isinstance(row, Mapping) or set(row) != {
                "instrument", "field", "resolution_seconds", "history",
                "maximum_freshness_seconds", "depth", "session", "alignment",
                "derived_local", "entitlement",
            }:
                raise CapabilityRefusal("provider conformance coverage is not closed")
            instrument = row["instrument"]
            history = row["history"]
            depth = row["depth"]
            alignment = row["alignment"]
            if (not isinstance(instrument, Mapping)
                    or set(instrument) != {"role", "type"}
                    or not isinstance(instrument["role"], str)
                    or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", instrument["role"]) is None
                    or instrument["type"] not in _INSTRUMENT_TYPES):
                raise CapabilityRefusal("provider conformance instrument is invalid")
            if (row["field"] not in fields
                    or isinstance(row["resolution_seconds"], bool)
                    or not isinstance(row["resolution_seconds"], int)
                    or row["resolution_seconds"] not in resolutions):
                raise CapabilityRefusal("provider conformance field or resolution is invalid")
            if not isinstance(history, Mapping) or set(history) != {"from", "to", "bars"}:
                raise CapabilityRefusal("provider conformance history is invalid")
            history_from = _aware_datetime(history["from"], "provider conformance history")
            history_to = _aware_datetime(history["to"], "provider conformance history")
            if (history_to <= history_from or isinstance(history["bars"], bool)
                    or not isinstance(history["bars"], int)
                    or history["bars"] < 0):
                raise CapabilityRefusal("provider conformance history is invalid")
            if (isinstance(row["maximum_freshness_seconds"], bool)
                    or not isinstance(row["maximum_freshness_seconds"], int)
                    or row["maximum_freshness_seconds"] < 0):
                raise CapabilityRefusal("provider conformance freshness is invalid")
            if (not isinstance(depth, Mapping)
                    or set(depth) != {"kind", "levels"}
                    or depth["kind"] not in {"NONE", "TOP_OF_BOOK", "BOOK"}
                    or (depth["kind"] in {"NONE", "TOP_OF_BOOK"}
                        and depth["levels"] is not None)
                    or (depth["kind"] == "BOOK" and (
                        isinstance(depth["levels"], bool)
                        or not isinstance(depth["levels"], int)
                        or depth["levels"] < 1))):
                raise CapabilityRefusal("provider conformance depth is invalid")
            if (row["session"] not in _SESSIONS
                    or not isinstance(alignment, Mapping)
                    or set(alignment) != {"kind", "maximum_skew_seconds"}
                    or alignment["kind"] not in _ALIGNMENTS
                    or isinstance(alignment["maximum_skew_seconds"], bool)
                    or not isinstance(alignment["maximum_skew_seconds"], int)
                    or alignment["maximum_skew_seconds"] < 0
                    or not isinstance(row["derived_local"], bool)
                    or row["entitlement"] not in _ENTITLEMENT_STATES):
                raise CapabilityRefusal("provider conformance semantics are invalid")
            normalized_coverage.append(_freeze({
                **row,
                "history": {
                    "from": history_from.isoformat(),
                    "to": history_to.isoformat(),
                    "bars": history["bars"],
                },
            }))
        normalized_coverage.sort(key=lambda item: canonical_json(_plain(item)))
        if len({canonical_json(_plain(item)) for item in normalized_coverage}) \
                != len(normalized_coverage):
            raise CapabilityRefusal("provider conformance coverage is duplicated")
        object.__setattr__(self, "coverage", tuple(normalized_coverage))

    @property
    def schema(self) -> str:
        return self.V2_SCHEMA if self.coverage else self.SCHEMA

    def fact(self) -> dict[str, Any]:
        result = {"product_address": self.product_address, "tested_fields": list(self.tested_fields),
            "tested_resolutions": list(self.tested_resolutions), "test_method": self.test_method,
            "test_version": self.test_version, "observed_from": self.observed_from.isoformat(),
            "observed_to": self.observed_to.isoformat(), "evidence_artifacts": list(self.evidence_artifacts),
            "result": self.result}
        if self.coverage:
            result["coverage"] = _plain(self.coverage)
        return result

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_fact_bytes(self.schema, self.fact())

    @property
    def address(self) -> str:
        return canonical_fact_address(self.schema, self.fact())

    @classmethod
    def from_bytes(cls, value: bytes) -> "ProviderConformance":
        try:
            document = json.loads(value.decode("utf-8"))
            if (canonical_json(document).encode() != value
                    or set(document) != {"schema", "fact"}
                    or document["schema"] not in cls.SUPPORTED_SCHEMAS):
                raise ValueError
            fact = document["fact"]
            legacy_keys = {"product_address", "tested_fields", "tested_resolutions",
                "test_method", "test_version", "observed_from", "observed_to",
                "evidence_artifacts", "result"}
            expected = legacy_keys | ({"coverage"} if document["schema"] == cls.V2_SCHEMA else set())
            if set(fact) != expected:
                raise ValueError
            coverage = []
            for row in fact.get("coverage", []):
                item = dict(row)
                item["history"] = {
                    **item["history"],
                    "from": datetime.fromisoformat(item["history"]["from"]),
                    "to": datetime.fromisoformat(item["history"]["to"]),
                }
                coverage.append(item)
            result = cls(fact["product_address"], tuple(fact["tested_fields"]),
                tuple(fact["tested_resolutions"]), fact["test_method"], fact["test_version"],
                datetime.fromisoformat(fact["observed_from"]), datetime.fromisoformat(fact["observed_to"]),
                tuple(fact["evidence_artifacts"]), fact["result"], tuple(coverage))
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise CapabilityRefusal("provider conformance bytes are malformed") from exc
        if result.canonical_bytes != value:
            raise CapabilityRefusal("provider conformance bytes do not reconstruct exactly")
        return result


@dataclass(frozen=True)
class CapabilityProfile:
    """One owner/mode scoped, evidence-backed capability declaration."""
    owner_id: str
    mode: str
    profile_version: int
    observed_at: int
    expires_at: int
    conformance_evidence_address: str
    offers: tuple[Mapping[str, Any], ...]
    change_level: int = 0
    provider_entity_address: str | None = None
    provider_product_address: str | None = None
    provider_contract_address: str | None = None

    SCHEMA = "capability-profile/2"
    V3_SCHEMA = "capability-profile/3"
    SUPPORTED_SCHEMAS = frozenset({SCHEMA, V3_SCHEMA})

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id or self.mode not in _MODES:
            raise CapabilityRefusal("profile owner or mode is invalid")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (self.profile_version, self.change_level)) or self.profile_version < 1 or self.change_level not in (0, 1, 2, 3):
            raise CapabilityRefusal("profile version, timestamps, or change level is invalid")
        observed = _time_text(self.observed_at); expires = _time_text(self.expires_at)
        if type(observed) is not type(expires) or expires <= observed:
            raise CapabilityRefusal("profile version, timestamps, or change level is invalid")
        _address(self.conformance_evidence_address, "conformance evidence")
        identity = (self.provider_entity_address, self.provider_product_address, self.provider_contract_address)
        if any(value is not None for value in identity):
            if not all(value is not None for value in identity):
                raise CapabilityRefusal("profile provider identity must be complete")
            for value in identity:
                _address(value, "profile provider identity")
        normalized: list[Mapping[str, Any]] = []
        if len(self.offers) > _MAX_OFFERS:
            raise CapabilityRefusal("profile offer bound exceeded")
        legacy_offer_keys = {"instrument", "field", "timeframes",
            "maximum_history_bars", "maximum_freshness_seconds", "depth",
            "session", "alignment", "derived_local", "entitled", "known"}
        v3_offer_keys = legacy_offer_keys | {"available_from", "available_to"}
        offer_schema: str | None = None
        for offer in self.offers:
            if not isinstance(offer, Mapping):
                raise CapabilityRefusal("profile offer is not closed")
            offer_keys = set(offer)
            if offer_keys != legacy_offer_keys and offer_keys != v3_offer_keys:
                raise CapabilityRefusal("profile offer is not closed")
            current_schema = self.V3_SCHEMA if offer_keys == v3_offer_keys else self.SCHEMA
            if offer_schema is not None and current_schema != offer_schema:
                raise CapabilityRefusal("profile offer schema versions cannot be mixed")
            offer_schema = current_schema
            if offer["field"] not in _FIELDS or not isinstance(offer["timeframes"], (tuple, list)) or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in offer["timeframes"]):
                raise CapabilityRefusal("profile offer field or resolution is invalid")
            if any(not isinstance(offer[key], int) or isinstance(offer[key], bool) for key in ("maximum_history_bars", "maximum_freshness_seconds")) or offer["maximum_history_bars"] < 0 or offer["maximum_freshness_seconds"] < 0 or not isinstance(offer["instrument"], Mapping) or not isinstance(offer["depth"], Mapping) or not isinstance(offer["alignment"], Mapping) or not isinstance(offer["session"], str) or not isinstance(offer["derived_local"], bool) or not isinstance(offer["entitled"], bool) or not isinstance(offer["known"], bool):
                raise CapabilityRefusal("profile offer limits are invalid")
            if set(offer["instrument"]) != {"role", "type"} or not isinstance(offer["instrument"]["role"], str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", offer["instrument"]["role"]) is None or offer["instrument"]["type"] not in _INSTRUMENT_TYPES:
                raise CapabilityRefusal("profile offer instrument is invalid")
            if set(offer["depth"]) != {"kind", "levels"} or offer["depth"]["kind"] not in {"NONE", "TOP_OF_BOOK", "BOOK"} or (offer["depth"]["kind"] in {"NONE", "TOP_OF_BOOK"} and offer["depth"]["levels"] is not None) or (offer["depth"]["kind"] == "BOOK" and (isinstance(offer["depth"]["levels"], bool) or not isinstance(offer["depth"]["levels"], int) or offer["depth"]["levels"] < 1)):
                raise CapabilityRefusal("profile offer depth is invalid")
            if offer["session"] not in _SESSIONS or set(offer["alignment"]) != {"kind", "maximum_skew_seconds"} or offer["alignment"]["kind"] not in _ALIGNMENTS or isinstance(offer["alignment"]["maximum_skew_seconds"], bool) or not isinstance(offer["alignment"]["maximum_skew_seconds"], int) or offer["alignment"]["maximum_skew_seconds"] < 0:
                raise CapabilityRefusal("profile offer alignment is invalid")
            normalized_offer = {**offer, "timeframes": sorted(set(offer["timeframes"]))}
            if current_schema == self.V3_SCHEMA:
                start = offer["available_from"]
                end = offer["available_to"]
                if start is None or end is None:
                    if offer["known"] or start is not None or end is not None:
                        raise CapabilityRefusal("known profile offer requires an available interval")
                else:
                    available_from = _aware_datetime(start, "profile offer available interval")
                    available_to = _aware_datetime(end, "profile offer available interval")
                    if available_to <= available_from:
                        raise CapabilityRefusal("profile offer available interval is invalid")
                    normalized_offer["available_from"] = available_from.isoformat()
                    normalized_offer["available_to"] = available_to.isoformat()
            normalized.append(_freeze(normalized_offer))
        normalized.sort(key=lambda item: canonical_json(_plain(item)))
        object.__setattr__(self, "offers", tuple(normalized))

    @property
    def schema(self) -> str:
        return (self.V3_SCHEMA if self.offers
                and "available_from" in self.offers[0] else self.SCHEMA)

    @property
    def capability_profile_address(self) -> str:
        return canonical_fact_address(self.schema, self.to_dict())

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_fact_bytes(self.schema, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        result = {"owner_id": self.owner_id, "mode": self.mode, "profile_version": self.profile_version,
            "observed_at": _time_text(self.observed_at), "expires_at": _time_text(self.expires_at),
            "conformance_evidence_address": self.conformance_evidence_address,
            "offers": _plain(self.offers), "change_level": self.change_level}
        if self.provider_entity_address is not None:
            result.update(provider_entity_address=self.provider_entity_address,
                provider_product_address=self.provider_product_address,
                provider_contract_address=self.provider_contract_address)
        return result


def _depth_covers(evidence: Mapping[str, Any], offer: Mapping[str, Any]) -> bool:
    rank = {"NONE": 0, "TOP_OF_BOOK": 1, "BOOK": 2}
    if rank[evidence["kind"]] < rank[offer["kind"]]:
        return False
    return offer["kind"] != "BOOK" or (
        evidence["kind"] == "BOOK" and evidence["levels"] >= offer["levels"]
    )


def verify_profile_conformance(
    profile: CapabilityProfile,
    conformance: ProviderConformance,
) -> None:
    """Reject any known offer not dominated by one immutable v2 evidence row."""
    if profile.schema != profile.V3_SCHEMA and any(
            offer["known"] for offer in profile.offers):
        raise CapabilityRefusal("known legacy profile has no enforceable history range")
    for offer in profile.offers:
        if not offer["known"]:
            continue
        for resolution in offer["timeframes"]:
            matches = [row for row in conformance.coverage if (
                _plain(row["instrument"]) == _plain(offer["instrument"])
                and row["field"] == offer["field"]
                and row["resolution_seconds"] == resolution
                and row["history"]["bars"] >= offer["maximum_history_bars"]
                and row["history"]["from"] <= offer["available_from"]
                and row["history"]["to"] >= offer["available_to"]
                and row["maximum_freshness_seconds"] <= offer["maximum_freshness_seconds"]
                and _depth_covers(row["depth"], offer["depth"])
                and row["session"] == offer["session"]
                and row["alignment"]["kind"] == offer["alignment"]["kind"]
                and row["alignment"]["maximum_skew_seconds"]
                    <= offer["alignment"]["maximum_skew_seconds"]
                and row["derived_local"] == offer["derived_local"]
                and (not offer["entitled"] or row["entitlement"] == "VERIFIED")
            )]
            if not matches:
                raise CapabilityRefusal("profile offer exceeds conformance coverage")


@dataclass(frozen=True, init=False)
class CapabilityAssessment:
    owner_id: str
    mode: str
    plan_address: str
    registry_snapshot_address: str
    capability_profile_address: str
    dataset_manifest_address: str
    market_truth_snapshot_address: str
    evaluation_policy_address: str
    assessment_evidence_address: str
    requirement_results: tuple[Mapping[str, Any], ...]
    assessed_at: int = 0
    assessment_algorithm: str
    assessment_algorithm_version: str

    def __init__(self, *args, **kwargs) -> None:
        # Validate hostile direct rows enough to return a precise refusal, but never
        # create an authority value. The assessment algorithm owns construction.
        values = list(args)
        rows = kwargs.get("requirement_results", values[9] if len(values) > 9 else ())
        _validate_result_rows(rows)
        raise CapabilityRefusal("assessments may only be constructed by assess_capability")

    def _validate(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id or self.mode not in _MODES:
            raise CapabilityRefusal("assessment owner or mode is invalid")
        if isinstance(self.assessed_at, bool) or not isinstance(self.assessed_at, int):
            raise CapabilityRefusal("assessment time is invalid")
        for name in ("plan_address", "registry_snapshot_address", "capability_profile_address", "dataset_manifest_address", "market_truth_snapshot_address", "evaluation_policy_address", "assessment_evidence_address"):
            _address(getattr(self, name), name)
        rows = _validate_result_rows(self.requirement_results)
        if not self.assessment_algorithm or not self.assessment_algorithm_version:
            raise CapabilityRefusal("assessment algorithm identity is absent")
        object.__setattr__(self, "requirement_results", tuple(rows))

    @property
    def capability_assessment_address(self) -> str:
        # Public compatibility name for the sole typed assessment identity.
        return self.authority_address

    @property
    def authority_address(self) -> str:
        return canonical_fact_address(CAPABILITY_ASSESSMENT_SCHEMA, self.fact())

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_fact_bytes(CAPABILITY_ASSESSMENT_SCHEMA, self.fact())

    def to_dict(self) -> dict[str, Any]:
        return {"owner_id": self.owner_id, "mode": self.mode, "plan_address": self.plan_address, "registry_snapshot_address": self.registry_snapshot_address, "capability_profile_address": self.capability_profile_address, "dataset_manifest_address": self.dataset_manifest_address, "market_truth_snapshot_address": self.market_truth_snapshot_address, "evaluation_policy_address": self.evaluation_policy_address, "assessment_evidence_address": self.assessment_evidence_address, "assessed_at": self.assessed_at, "requirement_results": _plain(self.requirement_results)}

    def fact(self) -> dict[str, Any]:
        return {**self.to_dict(), "assessment_algorithm": self.assessment_algorithm,
            "assessment_algorithm_version": self.assessment_algorithm_version}


def _validate_result_rows(requirement_results):
    rows = []
    for row in requirement_results:
        if not isinstance(row, Mapping) or set(row) != {"selector", "result", "reason"} or not is_content_address(row["selector"]) or row["result"] not in _RESULTS or row["reason"] not in _REASONS[row["result"]]:
            raise CapabilityRefusal("assessment result is malformed")
        rows.append(_freeze(row))
    rows.sort(key=lambda row: row["selector"])
    if len({row["selector"] for row in rows}) != len(rows):
        raise CapabilityRefusal("assessment result selectors are duplicated")
    return rows


def _new_assessment(**values) -> CapabilityAssessment:
    result = object.__new__(CapabilityAssessment)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    result._validate()
    return result


def require_capability_assessment_authority_envelope(
    document: Any,
) -> tuple[dict[str, Any], str]:
    """Validate the sole persisted representation of assessment authority."""
    try:
        envelope = _plain(document)
    except (CapabilityRefusal, TypeError) as exc:
        raise CapabilityRefusal("assessment authority envelope is not closed") from exc
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema", "fact"}
        or envelope.get("schema") != CAPABILITY_ASSESSMENT_SCHEMA
        or not isinstance(envelope.get("fact"), dict)
        or set(envelope["fact"]) != _ASSESSMENT_FACT_KEYS
    ):
        raise CapabilityRefusal("assessment authority envelope is not closed")
    fact = envelope["fact"]
    try:
        invalid_identity = (
            not isinstance(fact["owner_id"], str)
            or not fact["owner_id"]
            or not isinstance(fact["mode"], str)
            or fact["mode"] not in _MODES
            or isinstance(fact["assessed_at"], bool)
            or not isinstance(fact["assessed_at"], int)
            or fact["assessment_algorithm"] != CAPABILITY_ASSESSMENT_ALGORITHM
            or fact["assessment_algorithm_version"]
            != CAPABILITY_ASSESSMENT_ALGORITHM_VERSION
        )
        for name in _ASSESSMENT_ADDRESS_KEYS:
            _address(fact[name], name)
        if not isinstance(fact["requirement_results"], list):
            raise CapabilityRefusal("assessment result rows must be a canonical list")
        normalized_rows = _plain(_validate_result_rows(fact["requirement_results"]))
    except (KeyError, TypeError) as exc:
        raise CapabilityRefusal("assessment authority identity is invalid") from exc
    if invalid_identity:
        raise CapabilityRefusal("assessment authority identity is invalid")
    if normalized_rows != fact["requirement_results"]:
        raise CapabilityRefusal("assessment result rows are not canonical")
    return envelope, canonical_fact_address(CAPABILITY_ASSESSMENT_SCHEMA, fact)


def capability_assessment_authority_envelope(
    assessment: CapabilityAssessment,
) -> dict[str, Any]:
    """Read the exact typed envelope from constructor-authorized canonical bytes."""
    _require_canonical_assessment(assessment)
    try:
        document = json.loads(assessment.canonical_bytes.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise CapabilityRefusal("assessment canonical bytes are malformed") from exc
    envelope, address = require_capability_assessment_authority_envelope(document)
    if address != assessment.authority_address:
        raise CapabilityRefusal("assessment canonical bytes have stale identity")
    return envelope


def _profile_time(profile, at_time):
    if isinstance(at_time, bool) or not isinstance(at_time, int):
        raise CapabilityRefusal("capability profile is stale")
    comparison = datetime.fromtimestamp(at_time, timezone.utc) if isinstance(profile.observed_at, datetime) else at_time
    if not profile.observed_at <= comparison <= profile.expires_at:
        raise CapabilityRefusal("capability profile is stale")
    return comparison


def _conformance_matches(profile, conformance):
    return (conformance is not None and conformance.result == "PASS"
        and conformance.address == profile.conformance_evidence_address
        and conformance.product_address == profile.provider_product_address
        and conformance.observed_from <= profile.observed_at <= conformance.observed_to)


def _contract_matches(profile, contract, comparison):
    return (contract is not None and contract.address == profile.provider_contract_address
        and contract.owner_id == profile.owner_id and contract.mode == profile.mode
        and contract.product_address == profile.provider_product_address
        and contract.effective_from <= comparison
        and (contract.effective_to is None or comparison < contract.effective_to))


def _verify_known_evidence(profile, conformance, contract, comparison):
    identity = (profile.provider_entity_address, profile.provider_product_address, profile.provider_contract_address)
    if (profile.schema != profile.V3_SCHEMA or not all(value is not None for value in identity)
            or not isinstance(profile.observed_at, datetime)
            or not _conformance_matches(profile, conformance)
            or not _contract_matches(profile, contract, comparison)):
        raise CapabilityRefusal("known profile evidence or contract is absent or mismatched")
    verify_profile_conformance(profile, conformance)


def _verify_assessment_profile(profile, owner_id, mode, at_time, conformance, provider_contract):
    if profile.owner_id != owner_id or profile.mode != mode or mode not in _MODES:
        raise CapabilityRefusal("profile owner or mode does not match assessment")
    comparison = _profile_time(profile, at_time)
    if any(offer["known"] for offer in profile.offers):
        _verify_known_evidence(profile, conformance, provider_contract, comparison)
    if profile.change_level == 2:
        raise CapabilityRefusal("capability change level requires reassessment")
    if profile.change_level == 3:
        raise CapabilityRefusal("capability semantic break refuses assessment")


def _requirement_selector(record):
    return content_address({"authored_node_id": record["authored_node_id"], "lowered_path": list(record["lowered_path"]), "leaf_component": {"component_id": record["leaf_component"][0], "component_version": record["leaf_component"][1]}, "requirement": _plain(record["requirement"])})


def _offer_matches(offer, requirement):
    return (offer["field"] == requirement["field"]
        and _plain(offer["instrument"]) == _plain(requirement["instrument"])
        and offer["session"] == requirement["session"]
        and _plain(offer["alignment"]) == _plain(requirement["alignment"])
        and offer["derived_local"] == requirement["derived_local"])


def _history_covers(offer, requirement):
    return offer["maximum_history_bars"] >= requirement["history"]["minimum_bars"] + requirement["history"]["warmup_bars"]


def _freshness_covers(offer, requirement):
    return offer["maximum_freshness_seconds"] <= requirement["freshness"]["maximum_age_seconds"]


def _offer_complete(offer, requirement):
    return (offer["known"] and offer["entitled"] and requirement["timeframe"] in offer["timeframes"]
        and _history_covers(offer, requirement) and _freshness_covers(offer, requirement)
        and offer["depth"].get("kind") == requirement["depth"]["kind"]
        and _depth_covers(offer["depth"], requirement["depth"]))


def _capacity_shortfall(matches, requirement):
    if not any(requirement["timeframe"] in offer["timeframes"] for offer in matches):
        return "INSUFFICIENT_RESOLUTION", "no complete offer has required resolution"
    if not any(_history_covers(offer, requirement) for offer in matches):
        return "INSUFFICIENT_RANGE", "no complete offer has required history"
    if not any(_freshness_covers(offer, requirement) for offer in matches):
        return "INSUFFICIENT_FRESHNESS", "no complete offer has required freshness"
    return "UNAVAILABLE", "no single offer covers the complete requirement"


def _requirement_outcome(matches, requirement):
    if any(_offer_complete(offer, requirement) for offer in matches):
        return "SATISFIED", "one declared offer covers the complete requirement"
    if not matches or any(not offer["known"] for offer in matches):
        return "UNKNOWN", "complete capability is unknown"
    if not any(offer["entitled"] for offer in matches):
        return "UNAVAILABLE", "entitlement is not verified"
    return _capacity_shortfall(matches, requirement)


def _assess_requirement(requirement, profile, selector):
    matches = [offer for offer in profile.offers if _offer_matches(offer, requirement)]
    result, reason = _requirement_outcome(matches, requirement)
    return {"selector": selector, "result": result, "reason": reason}


def assess_capability(*, plan: DataRequirementPlan, profile: CapabilityProfile,
        owner_id: str, mode: str, dataset_manifest_address: str,
        market_truth_snapshot_address: str, evaluation_policy_address: str,
        assessment_evidence_address: str, at_time: int,
        conformance: ProviderConformance | None = None,
        provider_contract: ProviderContract | None = None) -> CapabilityAssessment:
    """Assess each already-bound requirement without recompiling or inferring facts."""
    _verify_assessment_profile(profile, owner_id, mode, at_time, conformance, provider_contract)
    results = [_assess_requirement(record["requirement"], profile, _requirement_selector(record)) for record in plan.requirements]
    return _new_assessment(owner_id=owner_id, mode=mode, plan_address=plan.plan_address,
        registry_snapshot_address=plan.registry_snapshot_address,
        capability_profile_address=profile.capability_profile_address,
        dataset_manifest_address=dataset_manifest_address,
        market_truth_snapshot_address=market_truth_snapshot_address,
        evaluation_policy_address=evaluation_policy_address,
        assessment_evidence_address=assessment_evidence_address,
        requirement_results=tuple(results), assessed_at=at_time,
        assessment_algorithm=CAPABILITY_ASSESSMENT_ALGORITHM,
        assessment_algorithm_version=CAPABILITY_ASSESSMENT_ALGORITHM_VERSION)


def _require_canonical_assessment(assessment: CapabilityAssessment) -> None:
    if not isinstance(assessment, CapabilityAssessment):
        raise CapabilityRefusal("assessment lacks canonical construction authority")


def verify_assessment_coverage(assessment: CapabilityAssessment, plan: DataRequirementPlan) -> None:
    expected = {content_address({"authored_node_id": record["authored_node_id"], "lowered_path": list(record["lowered_path"]), "leaf_component": {"component_id": record["leaf_component"][0], "component_version": record["leaf_component"][1]}, "requirement": _plain(record["requirement"])}) for record in plan.requirements}
    actual = {row["selector"] for row in assessment.requirement_results}
    if actual != expected: raise CapabilityRefusal("assessment coverage does not exactly match plan")

__all__ = [
    "CAPABILITY_ASSESSMENT_ALGORITHM",
    "CAPABILITY_ASSESSMENT_ALGORITHM_VERSION",
    "CAPABILITY_ASSESSMENT_SCHEMA",
    "CapabilityAssessment", "CapabilityProfile", "CapabilityRefusal",
    "ProviderConformance", "assess_capability", "verify_profile_conformance",
    "capability_assessment_authority_envelope",
    "require_capability_assessment_authority_envelope",
    "verify_assessment_coverage",
]


# Source-bound capability is a distinct authority envelope; /2 stays singular.
BOUND_CAPABILITY_ASSESSMENT_SCHEMA = "capability-assessment/3"


@dataclass(frozen=True)
class CapabilitySourceBinding:
    graph_input_id: str
    source_input_id: str
    source_bindings: ContractInputBindings
    manifest: DatasetManifest
    profile: CapabilityProfile
    conformance: ProviderConformance
    provider_contract: ProviderContract


@dataclass(frozen=True, init=False)
class BoundCapabilityAssessment:
    document: Mapping[str, Any]

    def __init__(self, *_args, **_kwargs):
        raise CapabilityRefusal("bound assessments may only be constructed by assess_bound_capability")

    @property
    def authority_address(self):
        return canonical_fact_address(BOUND_CAPABILITY_ASSESSMENT_SCHEMA, self.fact())

    @property
    def canonical_bytes(self):
        return canonical_fact_bytes(BOUND_CAPABILITY_ASSESSMENT_SCHEMA, self.fact())

    @property
    def requirement_results(self):
        return self.document["requirement_results"]

    def fact(self):
        return _plain(self.document)


_BOUND_FACT_KEYS = frozenset({"owner_id", "mode", "plan_address", "registry_snapshot_address",
    "dataset_set_address", "input_binding_context_address", "evaluation_policy_address", "assessed_at",
    "assessment_algorithm", "assessment_algorithm_version", "sources", "requirement_sources", "requirement_results"})
_SOURCE_KEYS = frozenset({"graph_input_id", "source_input_id", "source_context_address", "source_binding_address",
    "projected_binding_address", "dataset_manifest_address", "canonical_instrument_address",
    "market_truth_snapshot_address", "capability_profile_address", "conformance_address",
    "provider_contract_address", "provider_product_address"})


def _bound_require(condition, reason):
    if not condition:
        raise CapabilityRefusal(reason)


def _bound_name(value):
    _bound_require(isinstance(value, str) and 0 < len(value) <= 128 and "\x00" not in value,
                   "bound source name is invalid")


def _bound_source_rows(rows):
    _bound_require(isinstance(rows, list) and 0 < len(rows) <= 32, "bound sources are outside their limit")
    names = []
    for row in rows:
        _bound_require(isinstance(row, dict) and set(row) == _SOURCE_KEYS, "bound source is not closed")
        for key in ("graph_input_id", "source_input_id"):
            _bound_name(row[key])
        for key in _SOURCE_KEYS - {"graph_input_id", "source_input_id"}:
            _address(row[key], key)
        names.append(row["graph_input_id"])
    _bound_require(names == sorted(set(names)), "bound sources are duplicated or unordered")
    return set(names)


def _bound_assignments(rows, names, results):
    _bound_require(isinstance(rows, list) and 0 < len(rows) <= 10000, "bound assignments are outside their limit")
    selectors, used = [], set()
    for row in rows:
        _bound_require(isinstance(row, dict) and set(row) == {"selector", "graph_input_id"}, "bound assignment is not closed")
        _address(row["selector"], "selector")
        _bound_require(row["graph_input_id"] in names, "bound assignment has an unknown input")
        selectors.append(row["selector"]); used.add(row["graph_input_id"])
    _bound_require(selectors == sorted(set(selectors)) and used == names, "bound assignment coverage differs")
    _bound_require(selectors == [row["selector"] for row in results], "bound result coverage differs")


def _parse_bound_capability_envelope(document):
    """Check closed bytes only. Admission must independently recompute authority."""
    envelope = _plain(document)
    _bound_require(isinstance(envelope, dict) and set(envelope) == {"schema", "fact"}
                   and envelope["schema"] == BOUND_CAPABILITY_ASSESSMENT_SCHEMA, "bound assessment envelope is not closed")
    fact = envelope["fact"]
    _bound_require(isinstance(fact, dict) and set(fact) == _BOUND_FACT_KEYS, "bound assessment fact is not closed")
    _bound_name(fact["owner_id"])
    _bound_require(fact["mode"] == "RESEARCH" and type(fact["assessed_at"]) is int,
                   "bound assessment mode or time is invalid")
    _bound_require((fact["assessment_algorithm"], fact["assessment_algorithm_version"])
                   == ("source-bound-capability-evaluation", "1"), "bound assessment algorithm differs")
    for key in ("plan_address", "registry_snapshot_address", "dataset_set_address", "input_binding_context_address", "evaluation_policy_address"):
        _address(fact[key], key)
    names = _bound_source_rows(fact["sources"])
    results = _validate_result_rows(fact["requirement_results"])
    _bound_require(_plain(results) == fact["requirement_results"], "bound results are not canonical")
    _bound_assignments(fact["requirement_sources"], names, results)
    canonical_fact_bytes(BOUND_CAPABILITY_ASSESSMENT_SCHEMA, fact)
    return envelope, canonical_fact_address(BOUND_CAPABILITY_ASSESSMENT_SCHEMA, fact)


def require_bound_capability_assessment_envelope(document):
    try:
        return _parse_bound_capability_envelope(document)
    except (KeyError, TypeError, ValueError) as exc:
        raise CapabilityRefusal("bound assessment envelope is invalid") from exc


def bound_capability_assessment_envelope(assessment):
    _bound_require(type(assessment) is BoundCapabilityAssessment, "bound assessment constructor authority is absent")
    envelope, address = require_bound_capability_assessment_envelope(
        {"schema": BOUND_CAPABILITY_ASSESSMENT_SCHEMA, "fact": assessment.fact()})
    _bound_require(address == assessment.authority_address, "bound assessment address differs")
    return envelope


def _source_relation(source, input_bindings, owner_id):
    from app.ir.first_party.analytical_v2.contracts import validate_input_bindings
    _bound_require(type(source) is CapabilitySourceBinding, "typed capability source is required")
    validate_input_bindings(source.source_bindings)
    original = source.source_bindings.document
    _bound_require(original["owner_id"] == owner_id and set(original["inputs"]) == {source.source_input_id},
                   "source owner or singleton input differs")
    _bound_require(source.graph_input_id in input_bindings.document["inputs"], "projected source is absent")
    old = original["inputs"][source.source_input_id]
    new = input_bindings.document["inputs"][source.graph_input_id]
    immutable = set(old["binding"]) - {"instrument", "dataset_context_address", "evaluation_context_address"}
    _bound_require(all(old["binding"][key] == new["binding"][key] for key in immutable)
                   and old["binding"]["instrument"]["type"] == new["binding"]["instrument"]["type"],
                   "projected source altered facts beyond its role and contexts")
    return old, new


def _source_manifest(source, fact, owner_id, mode):
    from app.backtest.dataset_store import DatasetManifest
    manifest, profile, contract = source.manifest, source.profile, source.provider_contract
    _bound_require(type(manifest) is DatasetManifest and DatasetManifest.from_bytes(manifest.canonical_bytes) == manifest,
                   "source manifest is not canonical")
    _bound_require(manifest.owner_id == owner_id and manifest.mode == mode
                   and manifest.capability_profile_address == profile.capability_profile_address,
                   "source manifest owner, mode or profile differs")
    expected = ((fact["dataset_manifest_address"], (manifest.manifest_address,)),
        (fact["canonical_instrument_address"], manifest.instrument_addresses),
        (fact["market_truth_address"], manifest.truth_snapshot_addresses),
        (fact["provider_product_address"], manifest.provider_product_addresses),
        (fact["provider_contract_address"], manifest.provider_contract_addresses))
    _bound_require(all(value in members for value, members in expected) and set(fact["fields"]) <= set(manifest.fields),
                   "source facts do not belong to the manifest")
    _bound_require(fact["provider_contract_address"] == contract.address
                   and fact["provider_product_address"] == profile.provider_product_address
                   and profile.provider_entity_address in manifest.provider_entity_addresses,
                   "source provider chain differs")


def _source_receipt(source, old, new):
    fact = old["binding"]
    return {"graph_input_id": source.graph_input_id, "source_input_id": source.source_input_id,
        "source_context_address": source.source_bindings.context_address,
        "source_binding_address": old["binding_address"], "projected_binding_address": new["binding_address"],
        "dataset_manifest_address": fact["dataset_manifest_address"],
        "canonical_instrument_address": fact["canonical_instrument_address"],
        "market_truth_snapshot_address": fact["market_truth_address"],
        "capability_profile_address": source.profile.capability_profile_address,
        "conformance_address": source.conformance.address, "provider_contract_address": source.provider_contract.address,
        "provider_product_address": source.profile.provider_product_address}


def _bound_sources(sources, input_bindings, owner_id, mode, at_time):
    _bound_require(isinstance(sources, tuple) and 0 < len(sources) <= 32, "typed sources are outside their limit")
    selected, receipts, roles = {}, [], set()
    for source in sources:
        old, new = _source_relation(source, input_bindings, owner_id)
        role = new["binding"]["instrument"]["role"]
        _bound_require(source.graph_input_id not in selected and role not in roles, "source inputs or roles are ambiguous")
        _bound_require(isinstance(source.profile, CapabilityProfile) and isinstance(source.conformance, ProviderConformance)
                       and isinstance(source.provider_contract, ProviderContract), "source provider evidence is not typed")
        _verify_assessment_profile(source.profile, owner_id, mode, at_time, source.conformance, source.provider_contract)
        _verify_known_evidence(source.profile, source.conformance, source.provider_contract, _profile_time(source.profile, at_time))
        _source_manifest(source, old["binding"], owner_id, mode)
        selected[source.graph_input_id] = (source, old["binding"], new["binding"])
        roles.add(role); receipts.append(_source_receipt(source, old, new))
    _bound_require(set(selected) == set(input_bindings.document["inputs"]), "source input coverage differs")
    return selected, sorted(receipts, key=lambda row: row["graph_input_id"])


def _assigned_source(requirement, selected):
    matches = [(name, row) for name, row in selected.items()
               if row[2]["instrument"]["role"] == requirement["instrument"]["role"]]
    _bound_require(len(matches) == 1, "requirement has no unique source role")
    name, (source, original, projected) = matches[0]
    _bound_require(requirement["instrument"] == projected["instrument"] and requirement["field"] in projected["fields"],
                   "requirement source instrument or field differs")
    return name, source, {**_plain(requirement), "instrument": _plain(original["instrument"])}


def assess_bound_capability(*, plan, resolved_graph, registry, input_bindings, sources,
        owner_id, mode, dataset_set_address, evaluation_policy_address, at_time):
    """Assess the verified full plan using each source's original provider evidence.

    Caller loads verified manifests/segments and original projection bindings. This
    function verifies the relation; it does not load or persist external authority.
    """
    from app.ir.first_party.analytical_v2.contracts import validate_input_bindings
    from app.market_data.requirements import verify_data_requirement_plan
    _bound_require(type(plan) is DataRequirementPlan and mode == "RESEARCH", "bound assessment requires a research plan")
    validate_input_bindings(input_bindings)
    _bound_require(input_bindings.document["owner_id"] == owner_id, "projected input owner differs")
    verify_data_requirement_plan(plan, resolved_graph, registry=registry, input_bindings=input_bindings)
    selected, receipts = _bound_sources(sources, input_bindings, owner_id, mode, at_time)
    _bound_require(0 < len(plan.requirements) <= 10000, "bound plan requirements are outside their limit")
    results, assignments = [], []
    for record in plan.requirements:
        selector = _requirement_selector(record)
        name, source, comparison = _assigned_source(record["requirement"], selected)
        results.append(_assess_requirement(comparison, source.profile, selector))
        assignments.append({"selector": selector, "graph_input_id": name})
    fact = {"owner_id": owner_id, "mode": mode, "plan_address": plan.plan_address,
        "registry_snapshot_address": plan.registry_snapshot_address, "dataset_set_address": dataset_set_address,
        "input_binding_context_address": input_bindings.context_address, "evaluation_policy_address": evaluation_policy_address,
        "assessed_at": at_time, "assessment_algorithm": "source-bound-capability-evaluation", "assessment_algorithm_version": "1",
        "sources": receipts, "requirement_sources": sorted(assignments, key=lambda row: row["selector"]),
        "requirement_results": sorted(results, key=lambda row: row["selector"])}
    require_bound_capability_assessment_envelope({"schema": BOUND_CAPABILITY_ASSESSMENT_SCHEMA, "fact": fact})
    result = object.__new__(BoundCapabilityAssessment)
    object.__setattr__(result, "document", _freeze(fact))
    return result


__all__ += ["BOUND_CAPABILITY_ASSESSMENT_SCHEMA", "CapabilitySourceBinding", "BoundCapabilityAssessment",
    "assess_bound_capability", "bound_capability_assessment_envelope", "require_bound_capability_assessment_envelope"]
