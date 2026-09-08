"""Immutable, non-activating entitlement policy contracts.

This module has no persistence, transport, configuration, provider, or money
effect. Every policy fact is injected by its caller and every successful
evaluation is only a candidate for a later, separately authorized reducer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, ClassVar


CONTRACT_VERSION = 1
MAX_IDENTIFIER_LENGTH = 128
MAX_COLLECTION_ITEMS = 64
MAX_CANONICAL_BYTES = 16_384
MAX_JSON_DEPTH = 16
MAX_TRIAL_DURATION_SECONDS = 315_360_000
V0_EXAMPLE_BETA_TRIAL_SECONDS = 1_296_000

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]*\Z")


class ContractValidationError(ValueError):
    """A closed contract rejected malformed, unknown, or inconsistent input."""


class GrantSource(str, Enum):
    BETA_TRIAL = "BETA_TRIAL"
    COUPON_TRIAL_ACCESS = "COUPON_TRIAL_ACCESS"
    FOUNDER_COMPLIMENTARY = "FOUNDER_COMPLIMENTARY"


class CouponEffect(str, Enum):
    TRIAL_ACCESS = "TRIAL_ACCESS"
    PRICE_ADJUSTMENT = "PRICE_ADJUSTMENT"


class RefusalCode(str, Enum):
    MISSING_PROFILE_EVIDENCE = "MISSING_PROFILE_EVIDENCE"
    TRIAL_INELIGIBLE = "TRIAL_INELIGIBLE"
    PRIOR_TRIAL_USED = "PRIOR_TRIAL_USED"
    COUPON_PROOF_REQUIRED = "COUPON_PROOF_REQUIRED"
    COUPON_PROOF_MISMATCH = "COUPON_PROOF_MISMATCH"
    PRICE_ADJUSTMENT_UNAVAILABLE = "PRICE_ADJUSTMENT_UNAVAILABLE"
    FOUNDER_BINDING_REQUIRED = "FOUNDER_BINDING_REQUIRED"
    REVOCATION_AUTHORITY_REQUIRED = "REVOCATION_AUTHORITY_REQUIRED"


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field_name} must be a string")
    if not 1 <= len(value) <= MAX_IDENTIFIER_LENGTH or not _IDENTIFIER.fullmatch(value):
        raise ContractValidationError(f"{field_name} is not a closed bounded identifier")
    return value


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field_name)


def _identifier_tuple(value: object, field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ContractValidationError(f"{field_name} must be an immutable tuple")
    if (not allow_empty and not value) or len(value) > MAX_COLLECTION_ITEMS:
        raise ContractValidationError(f"{field_name} has an invalid item count")
    validated = tuple(_identifier(item, f"{field_name} item") for item in value)
    if tuple(sorted(set(validated))) != validated:
        raise ContractValidationError(f"{field_name} must be sorted and unique")
    return validated


def _utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ContractValidationError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ContractValidationError(f"{field_name} must be UTC")
    if not 1970 <= value.year <= 9998:
        raise ContractValidationError(f"{field_name} is outside supported bounds")
    return value.astimezone(timezone.utc)


def _datetime_text(value: datetime) -> str:
    return _utc(value, "datetime").isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractValidationError(f"{field_name} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} is invalid") from exc
    if _datetime_text(parsed) != value:
        raise ContractValidationError(f"{field_name} is not canonical")
    return parsed


def _strict_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise ContractValidationError(f"{field_name} must be a boolean")
    return value


def _strict_int(value: object, field_name: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractValidationError(f"{field_name} is outside supported bounds")
    return value


def _is_contract_version(value: object) -> bool:
    return type(value) is int and value == CONTRACT_VERSION


def _enum(enum_type: type[Enum], value: object, field_name: str) -> Enum:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field_name} must be a closed enum string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} is unknown") from exc


def _expect_keys(value: object, expected: set[str], contract_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ContractValidationError(f"{contract_name} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractValidationError(f"{contract_name} fields mismatch: missing={missing}, extra={extra}")
    return value


def _canonical_json(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("contract is not canonical JSON data") from exc
    if len(encoded.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("canonical contract exceeds size bound")
    return encoded


def _hash_payload(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class _CanonicalContract:
    contract_type: ClassVar[str]

    def _payload(self) -> dict[str, object]:
        raise NotImplementedError

    def canonical_dict(self) -> dict[str, object]:
        return {
            "contract_type": self.contract_type,
            "contract_version": CONTRACT_VERSION,
            **self._payload(),
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())

    @property
    def content_id(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EntitlementPolicy(_CanonicalContract):
    contract_type: ClassVar[str] = "EntitlementPolicy"
    policy_address: str
    entitlement_set_id: str
    entitlements: tuple[str, ...]
    required_profile_fields: tuple[str, ...]
    trial_duration_seconds: int

    def __post_init__(self) -> None:
        _identifier(self.policy_address, "policy_address")
        _identifier(self.entitlement_set_id, "entitlement_set_id")
        _identifier_tuple(self.entitlements, "entitlements")
        _identifier_tuple(self.required_profile_fields, "required_profile_fields", allow_empty=True)
        _strict_int(
            self.trial_duration_seconds,
            "trial_duration_seconds",
            minimum=1,
            maximum=MAX_TRIAL_DURATION_SECONDS,
        )

    def _payload(self) -> dict[str, object]:
        return {
            "policy_address": self.policy_address,
            "entitlement_set_id": self.entitlement_set_id,
            "entitlements": list(self.entitlements),
            "required_profile_fields": list(self.required_profile_fields),
            "trial_duration_seconds": self.trial_duration_seconds,
        }


@dataclass(frozen=True, slots=True)
class ProfileEvidence(_CanonicalContract):
    contract_type: ClassVar[str] = "ProfileEvidence"
    policy_address: str
    owner_id: str
    user_id: str
    evidence_address: str
    satisfied_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("policy_address", "owner_id", "user_id", "evidence_address"):
            _identifier(getattr(self, field_name), field_name)
        _identifier_tuple(self.satisfied_fields, "satisfied_fields", allow_empty=True)

    def _payload(self) -> dict[str, object]:
        return {
            "policy_address": self.policy_address,
            "owner_id": self.owner_id,
            "user_id": self.user_id,
            "evidence_address": self.evidence_address,
            "satisfied_fields": list(self.satisfied_fields),
        }


@dataclass(frozen=True, slots=True)
class TrialEligibilityEvidence(_CanonicalContract):
    contract_type: ClassVar[str] = "TrialEligibilityEvidence"
    policy_address: str
    owner_id: str
    user_id: str
    eligibility_authority_address: str
    eligible: bool
    prior_use_authority_address: str
    prior_used: bool

    def __post_init__(self) -> None:
        for field_name in (
            "policy_address",
            "owner_id",
            "user_id",
            "eligibility_authority_address",
            "prior_use_authority_address",
        ):
            _identifier(getattr(self, field_name), field_name)
        _strict_bool(self.eligible, "eligible")
        _strict_bool(self.prior_used, "prior_used")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_address": self.policy_address,
            "owner_id": self.owner_id,
            "user_id": self.user_id,
            "eligibility_authority_address": self.eligibility_authority_address,
            "eligible": self.eligible,
            "prior_use_authority_address": self.prior_use_authority_address,
            "prior_used": self.prior_used,
        }


@dataclass(frozen=True, slots=True)
class CouponPolicy(_CanonicalContract):
    contract_type: ClassVar[str] = "CouponPolicy"
    policy_address: str
    entitlement_policy_address: str
    verifier_address: str
    effect: CouponEffect
    effect_policy_address: str

    def __post_init__(self) -> None:
        for field_name in (
            "policy_address",
            "entitlement_policy_address",
            "verifier_address",
            "effect_policy_address",
        ):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.effect, CouponEffect):
            raise ContractValidationError("effect must be a closed CouponEffect")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_address": self.policy_address,
            "entitlement_policy_address": self.entitlement_policy_address,
            "verifier_address": self.verifier_address,
            "effect": self.effect.value,
            "effect_policy_address": self.effect_policy_address,
        }


@dataclass(frozen=True, slots=True)
class CouponProof(_CanonicalContract):
    contract_type: ClassVar[str] = "CouponProof"
    coupon_policy_address: str
    verifier_address: str
    proof_address: str
    owner_id: str
    user_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "coupon_policy_address",
            "verifier_address",
            "proof_address",
            "owner_id",
            "user_id",
        ):
            _identifier(getattr(self, field_name), field_name)

    def _payload(self) -> dict[str, object]:
        return {
            "coupon_policy_address": self.coupon_policy_address,
            "verifier_address": self.verifier_address,
            "proof_address": self.proof_address,
            "owner_id": self.owner_id,
            "user_id": self.user_id,
        }


@dataclass(frozen=True, slots=True)
class DecisionCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "DecisionCandidate"
    source: GrantSource
    policy_address: str
    owner_id: str
    user_id: str
    entitlement_set_id: str
    starts_at: datetime
    expires_at: datetime | None
    source_authority_address: str
    revocation_authority_address: str
    decision_basis_address: str
    access_activated: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source, GrantSource):
            raise ContractValidationError("source must be a closed GrantSource")
        for field_name in (
            "policy_address",
            "owner_id",
            "user_id",
            "entitlement_set_id",
            "source_authority_address",
            "revocation_authority_address",
            "decision_basis_address",
        ):
            _identifier(getattr(self, field_name), field_name)
        starts_at = _utc(self.starts_at, "starts_at")
        if self.expires_at is not None and _utc(self.expires_at, "expires_at") <= starts_at:
            raise ContractValidationError("expires_at must be later than starts_at")
        if _strict_bool(self.access_activated, "access_activated") is not False:
            raise ContractValidationError("a pure decision candidate cannot activate access")

    def _payload(self) -> dict[str, object]:
        return {
            "source": self.source.value,
            "policy_address": self.policy_address,
            "owner_id": self.owner_id,
            "user_id": self.user_id,
            "entitlement_set_id": self.entitlement_set_id,
            "starts_at": _datetime_text(self.starts_at),
            "expires_at": None if self.expires_at is None else _datetime_text(self.expires_at),
            "source_authority_address": self.source_authority_address,
            "revocation_authority_address": self.revocation_authority_address,
            "decision_basis_address": self.decision_basis_address,
            "access_activated": self.access_activated,
        }


@dataclass(frozen=True, slots=True)
class DecisionRefusal(_CanonicalContract):
    contract_type: ClassVar[str] = "DecisionRefusal"
    code: RefusalCode
    source: GrantSource
    policy_address: str
    owner_id: str
    user_id: str
    evaluated_at: datetime
    decision_basis_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, RefusalCode):
            raise ContractValidationError("code must be a closed RefusalCode")
        if not isinstance(self.source, GrantSource):
            raise ContractValidationError("source must be a closed GrantSource")
        for field_name in ("policy_address", "owner_id", "user_id", "decision_basis_address"):
            _identifier(getattr(self, field_name), field_name)
        _utc(self.evaluated_at, "evaluated_at")

    def _payload(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "source": self.source.value,
            "policy_address": self.policy_address,
            "owner_id": self.owner_id,
            "user_id": self.user_id,
            "evaluated_at": _datetime_text(self.evaluated_at),
            "decision_basis_address": self.decision_basis_address,
        }


@dataclass(frozen=True, slots=True)
class DecisionResult(_CanonicalContract):
    contract_type: ClassVar[str] = "DecisionResult"
    candidate: DecisionCandidate | None
    refusal: DecisionRefusal | None

    def __post_init__(self) -> None:
        if (self.candidate is None) == (self.refusal is None):
            raise ContractValidationError("a result must contain exactly one candidate or refusal")
        if self.candidate is not None and not isinstance(self.candidate, DecisionCandidate):
            raise ContractValidationError("candidate has the wrong closed type")
        if self.refusal is not None and not isinstance(self.refusal, DecisionRefusal):
            raise ContractValidationError("refusal has the wrong closed type")

    def _payload(self) -> dict[str, object]:
        return {
            "candidate": None if self.candidate is None else self.candidate.canonical_dict(),
            "refusal": None if self.refusal is None else self.refusal.canonical_dict(),
        }


def v0_example_beta_trial_policy(
    *,
    policy_address: str,
    entitlement_set_id: str,
    entitlements: tuple[str, ...],
    required_profile_fields: tuple[str, ...],
) -> EntitlementPolicy:
    """Build the named synthetic V0 example, not a production default."""

    return EntitlementPolicy(
        policy_address=policy_address,
        entitlement_set_id=entitlement_set_id,
        entitlements=entitlements,
        required_profile_fields=required_profile_fields,
        trial_duration_seconds=V0_EXAMPLE_BETA_TRIAL_SECONDS,
    )


def _binding(policy: EntitlementPolicy, profile: ProfileEvidence, eligibility: TrialEligibilityEvidence) -> None:
    if profile.policy_address != policy.policy_address or eligibility.policy_address != policy.policy_address:
        raise ContractValidationError("policy evidence substitution refused")
    if (profile.owner_id, profile.user_id) != (eligibility.owner_id, eligibility.user_id):
        raise ContractValidationError("owner or user evidence substitution refused")


def _trial_refusal(
    policy: EntitlementPolicy,
    profile: ProfileEvidence,
    eligibility: TrialEligibilityEvidence,
) -> RefusalCode | None:
    if not set(policy.required_profile_fields).issubset(profile.satisfied_fields):
        return RefusalCode.MISSING_PROFILE_EVIDENCE
    if not eligibility.eligible:
        return RefusalCode.TRIAL_INELIGIBLE
    if eligibility.prior_used:
        return RefusalCode.PRIOR_TRIAL_USED
    return None


def _refused(
    *,
    code: RefusalCode,
    source: GrantSource,
    policy_address: str,
    owner_id: str,
    user_id: str,
    evaluated_at: datetime,
    basis: dict[str, object],
) -> DecisionResult:
    return DecisionResult(
        candidate=None,
        refusal=DecisionRefusal(
            code=code,
            source=source,
            policy_address=policy_address,
            owner_id=owner_id,
            user_id=user_id,
            evaluated_at=_utc(evaluated_at, "evaluated_at"),
            decision_basis_address=_hash_payload(basis),
        ),
    )


def _accepted(
    *,
    source: GrantSource,
    policy: EntitlementPolicy,
    owner_id: str,
    user_id: str,
    starts_at: datetime,
    expires_at: datetime | None,
    source_authority_address: str,
    revocation_authority_address: str,
    basis: dict[str, object],
) -> DecisionResult:
    return DecisionResult(
        candidate=DecisionCandidate(
            source=source,
            policy_address=policy.policy_address,
            owner_id=owner_id,
            user_id=user_id,
            entitlement_set_id=policy.entitlement_set_id,
            starts_at=_utc(starts_at, "starts_at"),
            expires_at=None if expires_at is None else _utc(expires_at, "expires_at"),
            source_authority_address=_identifier(
                source_authority_address, "source_authority_address"
            ),
            revocation_authority_address=_identifier(
                revocation_authority_address, "revocation_authority_address"
            ),
            decision_basis_address=_hash_payload(basis),
            access_activated=False,
        ),
        refusal=None,
    )


def evaluate_trial(
    *,
    policy: EntitlementPolicy,
    profile_evidence: ProfileEvidence,
    eligibility_evidence: TrialEligibilityEvidence,
    server_time: datetime,
    revocation_authority_address: str,
) -> DecisionResult:
    if not isinstance(policy, EntitlementPolicy):
        raise ContractValidationError("policy has the wrong closed type")
    if not isinstance(profile_evidence, ProfileEvidence) or not isinstance(
        eligibility_evidence, TrialEligibilityEvidence
    ):
        raise ContractValidationError("trial evidence has the wrong closed type")
    _binding(policy, profile_evidence, eligibility_evidence)
    evaluated_at = _utc(server_time, "server_time")
    _identifier(revocation_authority_address, "revocation_authority_address")
    basis = {
        "evaluation": "trial",
        "policy": policy.canonical_dict(),
        "profile_evidence": profile_evidence.canonical_dict(),
        "eligibility_evidence": eligibility_evidence.canonical_dict(),
        "server_time": _datetime_text(evaluated_at),
        "revocation_authority_address": revocation_authority_address,
    }
    refusal = _trial_refusal(policy, profile_evidence, eligibility_evidence)
    if refusal is not None:
        return _refused(
            code=refusal,
            source=GrantSource.BETA_TRIAL,
            policy_address=policy.policy_address,
            owner_id=profile_evidence.owner_id,
            user_id=profile_evidence.user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    try:
        expires_at = evaluated_at + timedelta(seconds=policy.trial_duration_seconds)
    except OverflowError as exc:
        raise ContractValidationError("trial expiry exceeds supported time") from exc
    if expires_at.year > 9998:
        raise ContractValidationError("trial expiry exceeds supported time")
    return _accepted(
        source=GrantSource.BETA_TRIAL,
        policy=policy,
        owner_id=profile_evidence.owner_id,
        user_id=profile_evidence.user_id,
        starts_at=evaluated_at,
        expires_at=expires_at,
        source_authority_address=eligibility_evidence.eligibility_authority_address,
        revocation_authority_address=revocation_authority_address,
        basis=basis,
    )


def evaluate_coupon(
    *,
    policy: EntitlementPolicy,
    coupon_policy: CouponPolicy,
    coupon_proof: CouponProof | None,
    profile_evidence: ProfileEvidence,
    eligibility_evidence: TrialEligibilityEvidence,
    server_time: datetime,
    revocation_authority_address: str,
) -> DecisionResult:
    if not isinstance(coupon_policy, CouponPolicy):
        raise ContractValidationError("coupon_policy has the wrong closed type")
    _binding(policy, profile_evidence, eligibility_evidence)
    if coupon_policy.entitlement_policy_address != policy.policy_address:
        raise ContractValidationError("coupon entitlement policy substitution refused")
    evaluated_at = _utc(server_time, "server_time")
    _identifier(revocation_authority_address, "revocation_authority_address")
    basis = {
        "evaluation": "coupon",
        "policy": policy.canonical_dict(),
        "coupon_policy": coupon_policy.canonical_dict(),
        "coupon_proof": None if coupon_proof is None else coupon_proof.canonical_dict(),
        "profile_evidence": profile_evidence.canonical_dict(),
        "eligibility_evidence": eligibility_evidence.canonical_dict(),
        "server_time": _datetime_text(evaluated_at),
        "revocation_authority_address": revocation_authority_address,
    }
    if coupon_policy.effect is CouponEffect.PRICE_ADJUSTMENT:
        return _refused(
            code=RefusalCode.PRICE_ADJUSTMENT_UNAVAILABLE,
            source=GrantSource.COUPON_TRIAL_ACCESS,
            policy_address=policy.policy_address,
            owner_id=profile_evidence.owner_id,
            user_id=profile_evidence.user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    if coupon_proof is None:
        return _refused(
            code=RefusalCode.COUPON_PROOF_REQUIRED,
            source=GrantSource.COUPON_TRIAL_ACCESS,
            policy_address=policy.policy_address,
            owner_id=profile_evidence.owner_id,
            user_id=profile_evidence.user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    if not isinstance(coupon_proof, CouponProof):
        raise ContractValidationError("coupon_proof has the wrong closed type")
    proof_matches = (
        coupon_proof.coupon_policy_address == coupon_policy.policy_address
        and coupon_proof.verifier_address == coupon_policy.verifier_address
        and coupon_proof.owner_id == profile_evidence.owner_id
        and coupon_proof.user_id == profile_evidence.user_id
    )
    if not proof_matches:
        return _refused(
            code=RefusalCode.COUPON_PROOF_MISMATCH,
            source=GrantSource.COUPON_TRIAL_ACCESS,
            policy_address=policy.policy_address,
            owner_id=profile_evidence.owner_id,
            user_id=profile_evidence.user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    refusal = _trial_refusal(policy, profile_evidence, eligibility_evidence)
    if refusal is not None:
        return _refused(
            code=refusal,
            source=GrantSource.COUPON_TRIAL_ACCESS,
            policy_address=policy.policy_address,
            owner_id=profile_evidence.owner_id,
            user_id=profile_evidence.user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    try:
        expires_at = evaluated_at + timedelta(seconds=policy.trial_duration_seconds)
    except OverflowError as exc:
        raise ContractValidationError("coupon trial expiry exceeds supported time") from exc
    if expires_at.year > 9998:
        raise ContractValidationError("coupon trial expiry exceeds supported time")
    return _accepted(
        source=GrantSource.COUPON_TRIAL_ACCESS,
        policy=policy,
        owner_id=profile_evidence.owner_id,
        user_id=profile_evidence.user_id,
        starts_at=evaluated_at,
        expires_at=expires_at,
        source_authority_address=coupon_proof.proof_address,
        revocation_authority_address=revocation_authority_address,
        basis=basis,
    )


def evaluate_founder_complimentary(
    *,
    policy: EntitlementPolicy,
    owner_id: str,
    user_id: str,
    server_time: datetime,
    binding_address: str | None,
    revocation_authority_address: str | None,
) -> DecisionResult:
    if not isinstance(policy, EntitlementPolicy):
        raise ContractValidationError("policy has the wrong closed type")
    _identifier(owner_id, "owner_id")
    _identifier(user_id, "user_id")
    evaluated_at = _utc(server_time, "server_time")
    _optional_identifier(binding_address, "binding_address")
    _optional_identifier(revocation_authority_address, "revocation_authority_address")
    basis = {
        "evaluation": "founder_complimentary",
        "policy": policy.canonical_dict(),
        "owner_id": owner_id,
        "user_id": user_id,
        "server_time": _datetime_text(evaluated_at),
        "binding_address": binding_address,
        "revocation_authority_address": revocation_authority_address,
    }
    if binding_address is None:
        return _refused(
            code=RefusalCode.FOUNDER_BINDING_REQUIRED,
            source=GrantSource.FOUNDER_COMPLIMENTARY,
            policy_address=policy.policy_address,
            owner_id=owner_id,
            user_id=user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    if revocation_authority_address is None:
        return _refused(
            code=RefusalCode.REVOCATION_AUTHORITY_REQUIRED,
            source=GrantSource.FOUNDER_COMPLIMENTARY,
            policy_address=policy.policy_address,
            owner_id=owner_id,
            user_id=user_id,
            evaluated_at=evaluated_at,
            basis=basis,
        )
    return _accepted(
        source=GrantSource.FOUNDER_COMPLIMENTARY,
        policy=policy,
        owner_id=owner_id,
        user_id=user_id,
        starts_at=evaluated_at,
        expires_at=None,
        source_authority_address=binding_address,
        revocation_authority_address=revocation_authority_address,
        basis=basis,
    )


def _scan_depth(raw: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in raw:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ContractValidationError("canonical contract exceeds depth bound")
        elif character in "]}":
            depth -= 1
            if depth < 0:
                raise ContractValidationError("canonical contract has unbalanced depth")
    if depth != 0 or in_string:
        raise ContractValidationError("canonical contract has unbalanced depth")


def canonical_deserialize(raw: str) -> _CanonicalContract:
    if not isinstance(raw, str):
        raise ContractValidationError("canonical input must be text")
    if len(raw.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("canonical contract exceeds size bound")
    _scan_depth(raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractValidationError("canonical contract is invalid JSON") from exc
    if _canonical_json(value) != raw:
        raise ContractValidationError("contract JSON is not canonical")
    if not isinstance(value, dict):
        raise ContractValidationError("canonical contract must be an object")
    contract_type = value.get("contract_type")
    parser = _PARSERS.get(contract_type) if isinstance(contract_type, str) else None
    if parser is None:
        raise ContractValidationError("unknown contract type")
    if not _is_contract_version(value.get("contract_version")):
        raise ContractValidationError("unknown contract version")
    return parser(value)


def _base(value: object, fields: set[str], name: str) -> dict[str, Any]:
    data = _expect_keys(value, fields | {"contract_type", "contract_version"}, name)
    if data["contract_type"] != name or not _is_contract_version(data["contract_version"]):
        raise ContractValidationError(f"{name} type or version mismatch")
    return data


def _parse_policy(value: object) -> EntitlementPolicy:
    data = _base(
        value,
        {"policy_address", "entitlement_set_id", "entitlements", "required_profile_fields", "trial_duration_seconds"},
        "EntitlementPolicy",
    )
    return EntitlementPolicy(
        policy_address=data["policy_address"],
        entitlement_set_id=data["entitlement_set_id"],
        entitlements=tuple(data["entitlements"]) if isinstance(data["entitlements"], list) else data["entitlements"],
        required_profile_fields=tuple(data["required_profile_fields"])
        if isinstance(data["required_profile_fields"], list)
        else data["required_profile_fields"],
        trial_duration_seconds=data["trial_duration_seconds"],
    )


def _parse_profile(value: object) -> ProfileEvidence:
    data = _base(
        value,
        {"policy_address", "owner_id", "user_id", "evidence_address", "satisfied_fields"},
        "ProfileEvidence",
    )
    return ProfileEvidence(
        policy_address=data["policy_address"],
        owner_id=data["owner_id"],
        user_id=data["user_id"],
        evidence_address=data["evidence_address"],
        satisfied_fields=tuple(data["satisfied_fields"])
        if isinstance(data["satisfied_fields"], list)
        else data["satisfied_fields"],
    )


def _parse_eligibility(value: object) -> TrialEligibilityEvidence:
    data = _base(
        value,
        {
            "policy_address",
            "owner_id",
            "user_id",
            "eligibility_authority_address",
            "eligible",
            "prior_use_authority_address",
            "prior_used",
        },
        "TrialEligibilityEvidence",
    )
    return TrialEligibilityEvidence(
        policy_address=data["policy_address"],
        owner_id=data["owner_id"],
        user_id=data["user_id"],
        eligibility_authority_address=data["eligibility_authority_address"],
        eligible=data["eligible"],
        prior_use_authority_address=data["prior_use_authority_address"],
        prior_used=data["prior_used"],
    )


def _parse_coupon_policy(value: object) -> CouponPolicy:
    data = _base(
        value,
        {"policy_address", "entitlement_policy_address", "verifier_address", "effect", "effect_policy_address"},
        "CouponPolicy",
    )
    return CouponPolicy(
        policy_address=data["policy_address"],
        entitlement_policy_address=data["entitlement_policy_address"],
        verifier_address=data["verifier_address"],
        effect=_enum(CouponEffect, data["effect"], "effect"),
        effect_policy_address=data["effect_policy_address"],
    )


def _parse_coupon_proof(value: object) -> CouponProof:
    data = _base(
        value,
        {"coupon_policy_address", "verifier_address", "proof_address", "owner_id", "user_id"},
        "CouponProof",
    )
    return CouponProof(
        coupon_policy_address=data["coupon_policy_address"],
        verifier_address=data["verifier_address"],
        proof_address=data["proof_address"],
        owner_id=data["owner_id"],
        user_id=data["user_id"],
    )


def _parse_candidate(value: object) -> DecisionCandidate:
    data = _base(
        value,
        {
            "source",
            "policy_address",
            "owner_id",
            "user_id",
            "entitlement_set_id",
            "starts_at",
            "expires_at",
            "source_authority_address",
            "revocation_authority_address",
            "decision_basis_address",
            "access_activated",
        },
        "DecisionCandidate",
    )
    return DecisionCandidate(
        source=_enum(GrantSource, data["source"], "source"),
        policy_address=data["policy_address"],
        owner_id=data["owner_id"],
        user_id=data["user_id"],
        entitlement_set_id=data["entitlement_set_id"],
        starts_at=_parse_datetime(data["starts_at"], "starts_at"),
        expires_at=None
        if data["expires_at"] is None
        else _parse_datetime(data["expires_at"], "expires_at"),
        source_authority_address=data["source_authority_address"],
        revocation_authority_address=data["revocation_authority_address"],
        decision_basis_address=data["decision_basis_address"],
        access_activated=data["access_activated"],
    )


def _parse_refusal(value: object) -> DecisionRefusal:
    data = _base(
        value,
        {"code", "source", "policy_address", "owner_id", "user_id", "evaluated_at", "decision_basis_address"},
        "DecisionRefusal",
    )
    return DecisionRefusal(
        code=_enum(RefusalCode, data["code"], "code"),
        source=_enum(GrantSource, data["source"], "source"),
        policy_address=data["policy_address"],
        owner_id=data["owner_id"],
        user_id=data["user_id"],
        evaluated_at=_parse_datetime(data["evaluated_at"], "evaluated_at"),
        decision_basis_address=data["decision_basis_address"],
    )


def _parse_result(value: object) -> DecisionResult:
    data = _base(value, {"candidate", "refusal"}, "DecisionResult")
    candidate = None if data["candidate"] is None else _parse_candidate(data["candidate"])
    refusal = None if data["refusal"] is None else _parse_refusal(data["refusal"])
    return DecisionResult(candidate=candidate, refusal=refusal)


_PARSERS = {
    EntitlementPolicy.contract_type: _parse_policy,
    ProfileEvidence.contract_type: _parse_profile,
    TrialEligibilityEvidence.contract_type: _parse_eligibility,
    CouponPolicy.contract_type: _parse_coupon_policy,
    CouponProof.contract_type: _parse_coupon_proof,
    DecisionCandidate.contract_type: _parse_candidate,
    DecisionRefusal.contract_type: _parse_refusal,
    DecisionResult.contract_type: _parse_result,
}
