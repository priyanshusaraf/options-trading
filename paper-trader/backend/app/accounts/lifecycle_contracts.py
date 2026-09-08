"""Pure, immutable account-lifecycle authority candidates.

The values in this module do not authenticate, persist, export, delete, retain,
bind an operator, or activate access. Callers must inject every policy, time,
and proof address. Use-site factories and the strict codec revalidate those
facts against the caller's current context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, ClassVar
from uuid import RFC_4122, UUID


CONTRACT_VERSION = 1
MAX_CANONICAL_BYTES = 16_384
MAX_JSON_DEPTH = 12
MAX_POLICY_ITEMS = 32
MAX_CODE_LENGTH = 64

_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_CONTENT_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ContractValidationError(ValueError):
    """A closed lifecycle contract rejected untrusted input."""


def _strict_code(value: object, field_name: str) -> str:
    if type(value) is not str or not _CODE.fullmatch(value):
        raise ContractValidationError(f"{field_name} must be a closed canonical code")
    return value


def _content_address(value: object, field_name: str) -> str:
    if type(value) is not str or not _CONTENT_ADDRESS.fullmatch(value):
        raise ContractValidationError(f"{field_name} must be a sha256 content address")
    return value


def _opaque_uuid(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be a canonical RFC4122 UUID")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ContractValidationError(f"{field_name} must be a canonical RFC4122 UUID") from exc
    if str(parsed) != value or parsed.variant != RFC_4122 or parsed.int == 0:
        raise ContractValidationError(f"{field_name} must be a non-nil canonical RFC4122 UUID")
    return value


def _utc(value: object, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ContractValidationError(f"{field_name} must be an injected UTC datetime")
    if not 1970 <= value.year <= 9998:
        raise ContractValidationError(f"{field_name} is outside supported bounds")
    return value.astimezone(timezone.utc)


def _datetime_text(value: datetime) -> str:
    return _utc(value, "datetime").isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_datetime(value: object, field_name: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ContractValidationError(f"{field_name} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} is invalid") from exc
    if _datetime_text(parsed) != value:
        raise ContractValidationError(f"{field_name} is not canonical")
    return parsed


def _strict_false(value: object, field_name: str) -> bool:
    if type(value) is not bool or value is not False:
        raise ContractValidationError(f"{field_name} must remain false")
    return value


def _codes(value: object, field_name: str) -> tuple[str, ...]:
    if type(value) is not tuple or not value or len(value) > MAX_POLICY_ITEMS:
        raise ContractValidationError(f"{field_name} must be a non-empty bounded tuple")
    checked = tuple(_strict_code(item, f"{field_name} item") for item in value)
    if tuple(sorted(set(checked))) != checked:
        raise ContractValidationError(f"{field_name} must be sorted and unique")
    return checked


def _member(value: object, allowed: tuple[str, ...], field_name: str) -> str:
    checked = _strict_code(value, field_name)
    if checked not in allowed:
        raise ContractValidationError(f"{field_name} is not allowed by the current policy")
    return checked


def _expect_exact_type(value: object, expected: type, field_name: str) -> None:
    if type(value) is not expected:
        raise ContractValidationError(f"{field_name} must be an exact {expected.__name__}")


def _canonical_json(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("contract is not canonical JSON data") from exc
    if len(encoded.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("canonical contract exceeds the size bound")
    return encoded


def _expect_keys(value: object, expected: set[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ContractValidationError(f"{name} must be an object")
    actual = set(value)
    if actual != expected:
        raise ContractValidationError(
            f"{name} fields mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _exact_version(value: object) -> None:
    if type(value) is not int or value != CONTRACT_VERSION:
        raise ContractValidationError("contract_version must be exact integer 1")


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
class AccountLifecyclePolicy(_CanonicalContract):
    contract_type: ClassVar[str] = "AccountLifecyclePolicy"
    policy_address: str
    issuer_classes: tuple[str, ...]
    account_states: tuple[str, ...]
    onboarding_steps: tuple[str, ...]
    request_types: tuple[str, ...]
    retained_exception_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _content_address(self.policy_address, "policy_address")
        _codes(self.issuer_classes, "issuer_classes")
        _codes(self.account_states, "account_states")
        _codes(self.onboarding_steps, "onboarding_steps")
        _codes(self.request_types, "request_types")
        _codes(self.retained_exception_codes, "retained_exception_codes")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_address": self.policy_address,
            "issuer_classes": list(self.issuer_classes),
            "account_states": list(self.account_states),
            "onboarding_steps": list(self.onboarding_steps),
            "request_types": list(self.request_types),
            "retained_exception_codes": list(self.retained_exception_codes),
        }


@dataclass(frozen=True, slots=True)
class CurrentAccountAuthority(_CanonicalContract):
    """Independently supplied current authority from the accepted auth seam."""

    contract_type: ClassVar[str] = "CurrentAccountAuthority"
    user_id: str
    tenant_id: str
    session_authority_address: str
    session_policy_address: str
    lifecycle_policy_id: str
    issuer_class: str
    account_state: str
    onboarding_step: str
    authenticated_at: datetime

    def __post_init__(self) -> None:
        _opaque_uuid(self.user_id, "user_id")
        _opaque_uuid(self.tenant_id, "tenant_id")
        _content_address(self.session_authority_address, "session_authority_address")
        _content_address(self.session_policy_address, "session_policy_address")
        _content_address(self.lifecycle_policy_id, "lifecycle_policy_id")
        _strict_code(self.issuer_class, "issuer_class")
        _strict_code(self.account_state, "account_state")
        _strict_code(self.onboarding_step, "onboarding_step")
        _utc(self.authenticated_at, "authenticated_at")

    def _payload(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "session_authority_address": self.session_authority_address,
            "session_policy_address": self.session_policy_address,
            "lifecycle_policy_id": self.lifecycle_policy_id,
            "issuer_class": self.issuer_class,
            "account_state": self.account_state,
            "onboarding_step": self.onboarding_step,
            "authenticated_at": _datetime_text(self.authenticated_at),
        }


@dataclass(frozen=True, slots=True)
class AuthenticatedAccountContext(_CanonicalContract):
    contract_type: ClassVar[str] = "AuthenticatedAccountContext"
    user_id: str
    tenant_id: str
    session_authority_address: str
    session_policy_address: str
    lifecycle_policy_id: str
    issuer_class: str
    account_state: str
    onboarding_step: str
    authenticated_at: datetime

    def __post_init__(self) -> None:
        _opaque_uuid(self.user_id, "user_id")
        _opaque_uuid(self.tenant_id, "tenant_id")
        _content_address(self.session_authority_address, "session_authority_address")
        _content_address(self.session_policy_address, "session_policy_address")
        _content_address(self.lifecycle_policy_id, "lifecycle_policy_id")
        _strict_code(self.issuer_class, "issuer_class")
        _strict_code(self.account_state, "account_state")
        _strict_code(self.onboarding_step, "onboarding_step")
        _utc(self.authenticated_at, "authenticated_at")

    def _payload(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "session_authority_address": self.session_authority_address,
            "session_policy_address": self.session_policy_address,
            "lifecycle_policy_id": self.lifecycle_policy_id,
            "issuer_class": self.issuer_class,
            "account_state": self.account_state,
            "onboarding_step": self.onboarding_step,
            "authenticated_at": _datetime_text(self.authenticated_at),
        }


@dataclass(frozen=True, slots=True)
class LifecycleRequestCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "LifecycleRequestCandidate"
    authenticated_context_address: str
    lifecycle_policy_id: str
    user_id: str
    tenant_id: str
    session_authority_address: str
    request_type: str
    reauth_proof_address: str
    reauth_policy_address: str
    requested_at: datetime
    effected: bool

    def __post_init__(self) -> None:
        for name in (
            "authenticated_context_address",
            "lifecycle_policy_id",
            "session_authority_address",
            "reauth_proof_address",
            "reauth_policy_address",
        ):
            _content_address(getattr(self, name), name)
        _opaque_uuid(self.user_id, "user_id")
        _opaque_uuid(self.tenant_id, "tenant_id")
        _strict_code(self.request_type, "request_type")
        _utc(self.requested_at, "requested_at")
        _strict_false(self.effected, "effected")

    def _payload(self) -> dict[str, object]:
        return {
            "authenticated_context_address": self.authenticated_context_address,
            "lifecycle_policy_id": self.lifecycle_policy_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "session_authority_address": self.session_authority_address,
            "request_type": self.request_type,
            "reauth_proof_address": self.reauth_proof_address,
            "reauth_policy_address": self.reauth_policy_address,
            "requested_at": _datetime_text(self.requested_at),
            "effected": self.effected,
        }


@dataclass(frozen=True, slots=True)
class RetainedExceptionCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "RetainedExceptionCandidate"
    lifecycle_request_address: str
    lifecycle_policy_id: str
    exception_codes: tuple[str, ...]
    evaluated_at: datetime
    effected: bool

    def __post_init__(self) -> None:
        _content_address(self.lifecycle_request_address, "lifecycle_request_address")
        _content_address(self.lifecycle_policy_id, "lifecycle_policy_id")
        _codes(self.exception_codes, "exception_codes")
        _utc(self.evaluated_at, "evaluated_at")
        _strict_false(self.effected, "effected")

    def _payload(self) -> dict[str, object]:
        return {
            "lifecycle_request_address": self.lifecycle_request_address,
            "lifecycle_policy_id": self.lifecycle_policy_id,
            "exception_codes": list(self.exception_codes),
            "evaluated_at": _datetime_text(self.evaluated_at),
            "effected": self.effected,
        }


@dataclass(frozen=True, slots=True)
class FounderMatchProofReference(_CanonicalContract):
    contract_type: ClassVar[str] = "FounderMatchProofReference"
    match_proof_address: str
    match_policy_address: str

    def __post_init__(self) -> None:
        _content_address(self.match_proof_address, "match_proof_address")
        _content_address(self.match_policy_address, "match_policy_address")

    def _payload(self) -> dict[str, object]:
        return {
            "match_proof_address": self.match_proof_address,
            "match_policy_address": self.match_policy_address,
        }


@dataclass(frozen=True, slots=True)
class OperatorBindingCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "OperatorBindingCandidate"
    slot: str
    user_id: str
    authenticated_context_address: str
    lifecycle_policy_id: str
    founder_match_reference_address: str
    permission_policy_address: str
    bootstrap_policy_address: str
    complimentary_entitlement_candidate_address: str | None
    created_at: datetime
    activated: bool

    def __post_init__(self) -> None:
        if self.slot != "FOUNDER":
            raise ContractValidationError("slot must be the singleton FOUNDER slot")
        _opaque_uuid(self.user_id, "user_id")
        for name in (
            "authenticated_context_address",
            "lifecycle_policy_id",
            "founder_match_reference_address",
            "permission_policy_address",
            "bootstrap_policy_address",
        ):
            _content_address(getattr(self, name), name)
        if self.complimentary_entitlement_candidate_address is not None:
            _content_address(
                self.complimentary_entitlement_candidate_address,
                "complimentary_entitlement_candidate_address",
            )
        _utc(self.created_at, "created_at")
        _strict_false(self.activated, "activated")

    def _payload(self) -> dict[str, object]:
        return {
            "slot": self.slot,
            "user_id": self.user_id,
            "authenticated_context_address": self.authenticated_context_address,
            "lifecycle_policy_id": self.lifecycle_policy_id,
            "founder_match_reference_address": self.founder_match_reference_address,
            "permission_policy_address": self.permission_policy_address,
            "bootstrap_policy_address": self.bootstrap_policy_address,
            "complimentary_entitlement_candidate_address": self.complimentary_entitlement_candidate_address,
            "created_at": _datetime_text(self.created_at),
            "activated": self.activated,
        }


def _validate_policy(policy: AccountLifecyclePolicy) -> None:
    _expect_exact_type(policy, AccountLifecyclePolicy, "policy")
    AccountLifecyclePolicy(**{name: getattr(policy, name) for name in (
        "policy_address", "issuer_classes", "account_states", "onboarding_steps",
        "request_types", "retained_exception_codes",
    )})


def _validate_current_authority(
    authority: CurrentAccountAuthority,
    policy: AccountLifecyclePolicy,
) -> None:
    _expect_exact_type(authority, CurrentAccountAuthority, "current_account_authority")
    _validate_policy(policy)
    CurrentAccountAuthority(**{name: getattr(authority, name) for name in (
        "user_id", "tenant_id", "session_authority_address", "session_policy_address",
        "lifecycle_policy_id", "issuer_class", "account_state", "onboarding_step",
        "authenticated_at",
    )})
    if authority.lifecycle_policy_id != policy.content_id:
        raise ContractValidationError("current account authority does not match current policy")
    _member(authority.issuer_class, policy.issuer_classes, "issuer_class")
    _member(authority.account_state, policy.account_states, "account_state")
    _member(authority.onboarding_step, policy.onboarding_steps, "onboarding_step")


def _validate_context(
    context: AuthenticatedAccountContext,
    policy: AccountLifecyclePolicy,
    current_account_authority: CurrentAccountAuthority,
    expected_authenticated_context_address: str,
) -> None:
    _expect_exact_type(context, AuthenticatedAccountContext, "context")
    _validate_policy(policy)
    AuthenticatedAccountContext(**{name: getattr(context, name) for name in (
        "user_id", "tenant_id", "session_authority_address", "session_policy_address",
        "lifecycle_policy_id", "issuer_class", "account_state", "onboarding_step",
        "authenticated_at",
    )})
    if context.lifecycle_policy_id != policy.content_id:
        raise ContractValidationError("context lifecycle policy does not match current policy")
    _validate_current_authority(current_account_authority, policy)
    if context.content_id != _content_address(
        expected_authenticated_context_address, "expected_authenticated_context_address"
    ):
        raise ContractValidationError("context does not match its current authenticated address")
    _member(context.issuer_class, policy.issuer_classes, "issuer_class")
    _member(context.account_state, policy.account_states, "account_state")
    _member(context.onboarding_step, policy.onboarding_steps, "onboarding_step")
    expected_authority = (
        current_account_authority.user_id,
        current_account_authority.tenant_id,
        current_account_authority.session_authority_address,
        current_account_authority.session_policy_address,
        current_account_authority.lifecycle_policy_id,
        current_account_authority.issuer_class,
        current_account_authority.account_state,
        current_account_authority.onboarding_step,
        current_account_authority.authenticated_at,
    )
    actual_context = (
        context.user_id, context.tenant_id, context.session_authority_address,
        context.session_policy_address, context.lifecycle_policy_id, context.issuer_class,
        context.account_state, context.onboarding_step, context.authenticated_at,
    )
    if actual_context != expected_authority:
        raise ContractValidationError("context does not match independent current account authority")


def _validate_request(
    request: LifecycleRequestCandidate,
    policy: AccountLifecyclePolicy,
    context: AuthenticatedAccountContext,
    current_account_authority: CurrentAccountAuthority,
    expected_authenticated_context_address: str,
    reauth_proof_address: str,
    reauth_policy_address: str,
    expected_requested_at: datetime,
) -> None:
    _expect_exact_type(request, LifecycleRequestCandidate, "request")
    _validate_context(
        context, policy, current_account_authority,
        expected_authenticated_context_address,
    )
    LifecycleRequestCandidate(**{name: getattr(request, name) for name in (
        "authenticated_context_address", "lifecycle_policy_id", "user_id", "tenant_id",
        "session_authority_address", "request_type", "reauth_proof_address",
        "reauth_policy_address", "requested_at", "effected",
    )})
    expected = (
        context.content_id, policy.content_id, context.user_id, context.tenant_id,
        context.session_authority_address, _content_address(reauth_proof_address, "reauth_proof_address"),
        _content_address(reauth_policy_address, "reauth_policy_address"),
    )
    actual = (
        request.authenticated_context_address, request.lifecycle_policy_id, request.user_id,
        request.tenant_id, request.session_authority_address, request.reauth_proof_address,
        request.reauth_policy_address,
    )
    if actual != expected:
        raise ContractValidationError("request does not match current context, policy, or reauth proof")
    _member(request.request_type, policy.request_types, "request_type")
    if request.requested_at != _utc(expected_requested_at, "expected_requested_at"):
        raise ContractValidationError("request time does not match the current injected time")


def _validate_founder_reference(
    reference: FounderMatchProofReference,
    match_proof_address: str,
    match_policy_address: str,
) -> None:
    _expect_exact_type(reference, FounderMatchProofReference, "founder_reference")
    FounderMatchProofReference(
        match_proof_address=reference.match_proof_address,
        match_policy_address=reference.match_policy_address,
    )
    if reference.match_proof_address != _content_address(match_proof_address, "match_proof_address"):
        raise ContractValidationError("founder match proof does not match current proof")
    if reference.match_policy_address != _content_address(match_policy_address, "match_policy_address"):
        raise ContractValidationError("founder match policy does not match current policy")


def create_authenticated_account_context(
    *,
    policy: AccountLifecyclePolicy,
    user_id: str,
    tenant_id: str,
    session_authority_address: str,
    session_policy_address: str,
    issuer_class: str,
    account_state: str,
    onboarding_step: str,
    authenticated_at: datetime,
) -> AuthenticatedAccountContext:
    _validate_policy(policy)
    candidate = AuthenticatedAccountContext(
        user_id=user_id,
        tenant_id=tenant_id,
        session_authority_address=session_authority_address,
        session_policy_address=session_policy_address,
        lifecycle_policy_id=policy.content_id,
        issuer_class=_member(issuer_class, policy.issuer_classes, "issuer_class"),
        account_state=_member(account_state, policy.account_states, "account_state"),
        onboarding_step=_member(onboarding_step, policy.onboarding_steps, "onboarding_step"),
        authenticated_at=authenticated_at,
    )
    AuthenticatedAccountContext(**{name: getattr(candidate, name) for name in (
        "user_id", "tenant_id", "session_authority_address", "session_policy_address",
        "lifecycle_policy_id", "issuer_class", "account_state", "onboarding_step",
        "authenticated_at",
    )})
    return candidate


def create_current_account_authority(
    *,
    policy: AccountLifecyclePolicy,
    user_id: str,
    tenant_id: str,
    session_authority_address: str,
    session_policy_address: str,
    issuer_class: str,
    account_state: str,
    onboarding_step: str,
    authenticated_at: datetime,
) -> CurrentAccountAuthority:
    _validate_policy(policy)
    authority = CurrentAccountAuthority(
        user_id=user_id,
        tenant_id=tenant_id,
        session_authority_address=session_authority_address,
        session_policy_address=session_policy_address,
        lifecycle_policy_id=policy.content_id,
        issuer_class=_member(issuer_class, policy.issuer_classes, "issuer_class"),
        account_state=_member(account_state, policy.account_states, "account_state"),
        onboarding_step=_member(onboarding_step, policy.onboarding_steps, "onboarding_step"),
        authenticated_at=authenticated_at,
    )
    _validate_current_authority(authority, policy)
    return authority


def create_lifecycle_request_candidate(
    *,
    policy: AccountLifecyclePolicy,
    context: AuthenticatedAccountContext,
    current_account_authority: CurrentAccountAuthority,
    expected_authenticated_context_address: str,
    request_type: str,
    reauth_proof_address: str,
    reauth_policy_address: str,
    requested_at: datetime,
) -> LifecycleRequestCandidate:
    _validate_context(
        context, policy, current_account_authority,
        expected_authenticated_context_address,
    )
    candidate = LifecycleRequestCandidate(
        authenticated_context_address=context.content_id,
        lifecycle_policy_id=policy.content_id,
        user_id=context.user_id,
        tenant_id=context.tenant_id,
        session_authority_address=context.session_authority_address,
        request_type=_member(request_type, policy.request_types, "request_type"),
        reauth_proof_address=reauth_proof_address,
        reauth_policy_address=reauth_policy_address,
        requested_at=requested_at,
        effected=False,
    )
    _validate_request(
        candidate, policy, context, current_account_authority,
        expected_authenticated_context_address, reauth_proof_address,
        reauth_policy_address, requested_at,
    )
    return candidate


def create_retained_exception_candidate(
    *,
    policy: AccountLifecyclePolicy,
    context: AuthenticatedAccountContext,
    current_account_authority: CurrentAccountAuthority,
    expected_authenticated_context_address: str,
    request: LifecycleRequestCandidate,
    reauth_proof_address: str,
    reauth_policy_address: str,
    expected_requested_at: datetime,
    exception_codes: tuple[str, ...],
    evaluated_at: datetime,
) -> RetainedExceptionCandidate:
    _validate_request(
        request, policy, context, current_account_authority,
        expected_authenticated_context_address, reauth_proof_address,
        reauth_policy_address, expected_requested_at,
    )
    checked = _codes(exception_codes, "exception_codes")
    for code in checked:
        _member(code, policy.retained_exception_codes, "exception_code")
    candidate = RetainedExceptionCandidate(
        lifecycle_request_address=request.content_id,
        lifecycle_policy_id=policy.content_id,
        exception_codes=checked,
        evaluated_at=evaluated_at,
        effected=False,
    )
    _validate_retained(candidate, policy, request)
    return candidate


def _validate_retained(
    candidate: RetainedExceptionCandidate,
    policy: AccountLifecyclePolicy,
    request: LifecycleRequestCandidate,
) -> None:
    _expect_exact_type(candidate, RetainedExceptionCandidate, "retained_exception")
    _validate_policy(policy)
    _expect_exact_type(request, LifecycleRequestCandidate, "request")
    RetainedExceptionCandidate(**{name: getattr(candidate, name) for name in (
        "lifecycle_request_address", "lifecycle_policy_id", "exception_codes",
        "evaluated_at", "effected",
    )})
    if candidate.lifecycle_request_address != request.content_id or candidate.lifecycle_policy_id != policy.content_id:
        raise ContractValidationError("retained exception does not match current request and policy")
    for code in candidate.exception_codes:
        _member(code, policy.retained_exception_codes, "exception_code")


def create_founder_match_proof_reference(
    *, match_proof_address: str, match_policy_address: str
) -> FounderMatchProofReference:
    candidate = FounderMatchProofReference(
        match_proof_address=match_proof_address,
        match_policy_address=match_policy_address,
    )
    _validate_founder_reference(candidate, match_proof_address, match_policy_address)
    return candidate


def create_operator_binding_candidate(
    *,
    policy: AccountLifecyclePolicy,
    context: AuthenticatedAccountContext,
    current_account_authority: CurrentAccountAuthority,
    expected_authenticated_context_address: str,
    founder_reference: FounderMatchProofReference,
    match_proof_address: str,
    match_policy_address: str,
    permission_policy_address: str,
    bootstrap_policy_address: str,
    complimentary_entitlement_candidate_address: str | None,
    created_at: datetime,
) -> OperatorBindingCandidate:
    _validate_context(
        context, policy, current_account_authority,
        expected_authenticated_context_address,
    )
    _validate_founder_reference(founder_reference, match_proof_address, match_policy_address)
    candidate = OperatorBindingCandidate(
        slot="FOUNDER",
        user_id=context.user_id,
        authenticated_context_address=context.content_id,
        lifecycle_policy_id=policy.content_id,
        founder_match_reference_address=founder_reference.content_id,
        permission_policy_address=permission_policy_address,
        bootstrap_policy_address=bootstrap_policy_address,
        complimentary_entitlement_candidate_address=complimentary_entitlement_candidate_address,
        created_at=created_at,
        activated=False,
    )
    _validate_operator(
        candidate, policy, context, current_account_authority,
        expected_authenticated_context_address,
        founder_reference, match_proof_address,
        match_policy_address, permission_policy_address, bootstrap_policy_address,
        complimentary_entitlement_candidate_address,
    )
    return candidate


def _validate_operator(
    candidate: OperatorBindingCandidate,
    policy: AccountLifecyclePolicy,
    context: AuthenticatedAccountContext,
    current_account_authority: CurrentAccountAuthority,
    expected_authenticated_context_address: str,
    founder_reference: FounderMatchProofReference,
    match_proof_address: str,
    match_policy_address: str,
    permission_policy_address: str,
    bootstrap_policy_address: str,
    complimentary_entitlement_candidate_address: str | None,
) -> None:
    _expect_exact_type(candidate, OperatorBindingCandidate, "operator_candidate")
    _validate_context(
        context, policy, current_account_authority,
        expected_authenticated_context_address,
    )
    _validate_founder_reference(founder_reference, match_proof_address, match_policy_address)
    OperatorBindingCandidate(**{name: getattr(candidate, name) for name in (
        "slot", "user_id", "authenticated_context_address", "lifecycle_policy_id",
        "founder_match_reference_address", "permission_policy_address",
        "bootstrap_policy_address", "complimentary_entitlement_candidate_address",
        "created_at", "activated",
    )})
    expected_optional = None if complimentary_entitlement_candidate_address is None else _content_address(
        complimentary_entitlement_candidate_address, "complimentary_entitlement_candidate_address"
    )
    expected = (
        "FOUNDER", context.user_id, context.content_id, policy.content_id,
        founder_reference.content_id,
        _content_address(permission_policy_address, "permission_policy_address"),
        _content_address(bootstrap_policy_address, "bootstrap_policy_address"),
        expected_optional,
    )
    actual = (
        candidate.slot, candidate.user_id, candidate.authenticated_context_address,
        candidate.lifecycle_policy_id, candidate.founder_match_reference_address,
        candidate.permission_policy_address, candidate.bootstrap_policy_address,
        candidate.complimentary_entitlement_candidate_address,
    )
    if actual != expected:
        raise ContractValidationError("operator candidate does not match current context or proof policies")


def _json_depth(value: object, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        raise ContractValidationError("JSON nesting exceeds the depth bound")
    if type(value) is dict:
        for item in value.values():
            _json_depth(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _json_depth(item, depth + 1)
    return depth


def _reject_constant(value: str) -> None:
    raise ContractValidationError(f"non-finite JSON constant {value} is forbidden")


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError("duplicate JSON object key")
        result[key] = value
    return result


def _decode_raw(encoded: object) -> dict[str, Any]:
    if type(encoded) is not str:
        raise ContractValidationError("encoded contract must be text")
    raw_bytes = encoded.encode("utf-8")
    if not raw_bytes or len(raw_bytes) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("encoded contract has an invalid size")
    try:
        raw = json.loads(encoded, object_pairs_hook=_object_pairs, parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ContractValidationError("encoded contract is invalid JSON") from exc
    _json_depth(raw)
    if _canonical_json(raw) != encoded:
        raise ContractValidationError("encoded contract is not canonical JSON")
    if type(raw) is not dict:
        raise ContractValidationError("encoded contract root must be an object")
    return raw


def canonical_deserialize(
    encoded: object,
    *,
    current_policy: AccountLifecyclePolicy | None = None,
    current_account_authority: CurrentAccountAuthority | None = None,
    expected_context: AuthenticatedAccountContext | None = None,
    expected_authenticated_context_address: str | None = None,
    expected_request: LifecycleRequestCandidate | None = None,
    expected_founder_reference: FounderMatchProofReference | None = None,
    reauth_proof_address: str | None = None,
    reauth_policy_address: str | None = None,
    match_proof_address: str | None = None,
    match_policy_address: str | None = None,
    permission_policy_address: str | None = None,
    bootstrap_policy_address: str | None = None,
    complimentary_entitlement_candidate_address: str | None = None,
    expected_requested_at: datetime | None = None,
    expected_evaluated_at: datetime | None = None,
    expected_created_at: datetime | None = None,
) -> _CanonicalContract:
    """Decode one exact contract and revalidate all required current facts."""
    raw = _decode_raw(encoded)
    contract_type = raw.get("contract_type")
    _exact_version(raw.get("contract_version"))

    def body(expected: set[str]) -> dict[str, Any]:
        checked = _expect_keys(raw, expected | {"contract_type", "contract_version"}, str(contract_type))
        return checked

    if contract_type == AccountLifecyclePolicy.contract_type:
        data = body({"policy_address", "issuer_classes", "account_states", "onboarding_steps", "request_types", "retained_exception_codes"})
        value = AccountLifecyclePolicy(
            policy_address=data["policy_address"],
            issuer_classes=tuple(data["issuer_classes"]) if type(data["issuer_classes"]) is list else data["issuer_classes"],
            account_states=tuple(data["account_states"]) if type(data["account_states"]) is list else data["account_states"],
            onboarding_steps=tuple(data["onboarding_steps"]) if type(data["onboarding_steps"]) is list else data["onboarding_steps"],
            request_types=tuple(data["request_types"]) if type(data["request_types"]) is list else data["request_types"],
            retained_exception_codes=tuple(data["retained_exception_codes"]) if type(data["retained_exception_codes"]) is list else data["retained_exception_codes"],
        )
        if current_policy is not None and value != current_policy:
            raise ContractValidationError("decoded policy does not match current policy")
        _validate_policy(value)
        return value

    if current_policy is None:
        raise ContractValidationError("current_policy is required for use-time decoding")
    _validate_policy(current_policy)
    if contract_type == CurrentAccountAuthority.contract_type:
        if current_account_authority is None:
            raise ContractValidationError("authority decoding requires current account authority")
        data = body({"user_id", "tenant_id", "session_authority_address", "session_policy_address", "lifecycle_policy_id", "issuer_class", "account_state", "onboarding_step", "authenticated_at"})
        value = CurrentAccountAuthority(
            user_id=data["user_id"], tenant_id=data["tenant_id"],
            session_authority_address=data["session_authority_address"],
            session_policy_address=data["session_policy_address"],
            lifecycle_policy_id=data["lifecycle_policy_id"], issuer_class=data["issuer_class"],
            account_state=data["account_state"], onboarding_step=data["onboarding_step"],
            authenticated_at=_parse_datetime(data["authenticated_at"], "authenticated_at"),
        )
        _validate_current_authority(value, current_policy)
        if value != current_account_authority:
            raise ContractValidationError("decoded authority does not match current account authority")
        return value
    if contract_type == AuthenticatedAccountContext.contract_type:
        data = body({"user_id", "tenant_id", "session_authority_address", "session_policy_address", "lifecycle_policy_id", "issuer_class", "account_state", "onboarding_step", "authenticated_at"})
        value = AuthenticatedAccountContext(
            user_id=data["user_id"], tenant_id=data["tenant_id"],
            session_authority_address=data["session_authority_address"],
            session_policy_address=data["session_policy_address"],
            lifecycle_policy_id=data["lifecycle_policy_id"], issuer_class=data["issuer_class"],
            account_state=data["account_state"], onboarding_step=data["onboarding_step"],
            authenticated_at=_parse_datetime(data["authenticated_at"], "authenticated_at"),
        )
        if any(item is None for item in (
            current_account_authority, expected_context,
            expected_authenticated_context_address,
        )):
            raise ContractValidationError("context decoding requires the exact current context")
        _validate_context(
            value, current_policy, current_account_authority,
            expected_authenticated_context_address,
        )
        if value != expected_context:
            raise ContractValidationError("decoded context does not match expected current context")
        return value

    if contract_type == LifecycleRequestCandidate.contract_type:
        if any(item is None for item in (
            current_account_authority, expected_context,
            expected_authenticated_context_address, reauth_proof_address,
            reauth_policy_address, expected_requested_at,
        )):
            raise ContractValidationError("request decoding requires current context and reauth proof addresses")
        data = body({"authenticated_context_address", "lifecycle_policy_id", "user_id", "tenant_id", "session_authority_address", "request_type", "reauth_proof_address", "reauth_policy_address", "requested_at", "effected"})
        value = LifecycleRequestCandidate(
            authenticated_context_address=data["authenticated_context_address"], lifecycle_policy_id=data["lifecycle_policy_id"],
            user_id=data["user_id"], tenant_id=data["tenant_id"], session_authority_address=data["session_authority_address"],
            request_type=data["request_type"], reauth_proof_address=data["reauth_proof_address"],
            reauth_policy_address=data["reauth_policy_address"], requested_at=_parse_datetime(data["requested_at"], "requested_at"),
            effected=data["effected"],
        )
        _validate_request(
            value, current_policy, expected_context, current_account_authority,
            expected_authenticated_context_address, reauth_proof_address,
            reauth_policy_address, expected_requested_at,
        )
        return value

    if contract_type == RetainedExceptionCandidate.contract_type:
        required = (
            current_account_authority, expected_context,
            expected_authenticated_context_address, expected_request,
            reauth_proof_address, reauth_policy_address,
            expected_requested_at, expected_evaluated_at,
        )
        if any(item is None for item in required):
            raise ContractValidationError("retained-exception decoding requires the current request")
        data = body({"lifecycle_request_address", "lifecycle_policy_id", "exception_codes", "evaluated_at", "effected"})
        value = RetainedExceptionCandidate(
            lifecycle_request_address=data["lifecycle_request_address"], lifecycle_policy_id=data["lifecycle_policy_id"],
            exception_codes=tuple(data["exception_codes"]) if type(data["exception_codes"]) is list else data["exception_codes"],
            evaluated_at=_parse_datetime(data["evaluated_at"], "evaluated_at"), effected=data["effected"],
        )
        _validate_request(
            expected_request, current_policy, expected_context,
            current_account_authority, expected_authenticated_context_address,
            reauth_proof_address, reauth_policy_address,
            expected_requested_at,
        )
        _validate_retained(value, current_policy, expected_request)
        if value.evaluated_at != _utc(expected_evaluated_at, "expected_evaluated_at"):
            raise ContractValidationError("exception time does not match the current injected time")
        return value

    if contract_type == FounderMatchProofReference.contract_type:
        if match_proof_address is None or match_policy_address is None:
            raise ContractValidationError("founder-reference decoding requires current proof addresses")
        data = body({"match_proof_address", "match_policy_address"})
        value = FounderMatchProofReference(data["match_proof_address"], data["match_policy_address"])
        _validate_founder_reference(value, match_proof_address, match_policy_address)
        return value

    if contract_type == OperatorBindingCandidate.contract_type:
        required = (
            current_account_authority, expected_context,
            expected_authenticated_context_address,
            expected_founder_reference, match_proof_address,
            match_policy_address, permission_policy_address, bootstrap_policy_address,
            expected_created_at,
        )
        if any(item is None for item in required):
            raise ContractValidationError("operator decoding requires current context and proof policies")
        data = body({"slot", "user_id", "authenticated_context_address", "lifecycle_policy_id", "founder_match_reference_address", "permission_policy_address", "bootstrap_policy_address", "complimentary_entitlement_candidate_address", "created_at", "activated"})
        value = OperatorBindingCandidate(
            slot=data["slot"], user_id=data["user_id"],
            authenticated_context_address=data["authenticated_context_address"], lifecycle_policy_id=data["lifecycle_policy_id"],
            founder_match_reference_address=data["founder_match_reference_address"], permission_policy_address=data["permission_policy_address"],
            bootstrap_policy_address=data["bootstrap_policy_address"], complimentary_entitlement_candidate_address=data["complimentary_entitlement_candidate_address"],
            created_at=_parse_datetime(data["created_at"], "created_at"), activated=data["activated"],
        )
        _validate_operator(
            value, current_policy, expected_context, current_account_authority,
            expected_authenticated_context_address,
            expected_founder_reference,
            match_proof_address, match_policy_address, permission_policy_address,
            bootstrap_policy_address, complimentary_entitlement_candidate_address,
        )
        if value.created_at != _utc(expected_created_at, "expected_created_at"):
            raise ContractValidationError("operator time does not match the current injected time")
        return value
    raise ContractValidationError("unknown contract_type")
