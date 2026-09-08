"""Closed, privacy-minimised contracts for the platform operations plane.

These values are deliberately less expressive than arbitrary JSON.  Platform
operations may identify an account by an opaque, server-supplied reference, but
it must never carry a strategy, research, monitoring, execution or money fact.
"""
from __future__ import annotations

import datetime as dt
import enum
import re
from dataclasses import dataclass


class OperationsRefused(ValueError):
    """A command is outside the closed operations contract."""


class OperationsConflict(RuntimeError):
    """A durable fact conflicts with an existing fact of the same identity."""


class OperationsNotFound(LookupError):
    """No row exists inside the caller's server-derived scope."""


class OperationsCorrupt(RuntimeError):
    """Persisted operations data violates the closed contract."""


class MembershipState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class BillingMode(str, enum.Enum):
    TEST = "TEST"
    LIVE = "LIVE"
    INTERNAL = "INTERNAL"


class PolicyState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


class BillingInterval(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    MONTH = "MONTH"
    YEAR = "YEAR"


class CouponState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


class EntitlementEffectTiming(str, enum.Enum):
    FIXED_ABSOLUTE = "FIXED_ABSOLUTE"
    DYNAMIC_DURATION = "DYNAMIC_DURATION"


class BindingState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class BillingEventType(str, enum.Enum):
    SUBSCRIPTION_AUTHENTICATED = "SUBSCRIPTION_AUTHENTICATED"
    SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED"
    SUBSCRIPTION_CHARGED = "SUBSCRIPTION_CHARGED"
    SUBSCRIPTION_PAUSED = "SUBSCRIPTION_PAUSED"
    SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    PAYMENT_FAILED = "PAYMENT_FAILED"


class BillingEventState(str, enum.Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class EntitlementTransition(str, enum.Enum):
    GRANT = "GRANT"
    RENEW = "RENEW"
    EXPIRE = "EXPIRE"
    REVOKE = "REVOKE"


class EntitlementState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class EntitlementSource(str, enum.Enum):
    BILLING_RECEIPT = "BILLING_RECEIPT"
    COUPON_REDEMPTION = "COUPON_REDEMPTION"
    COMPLIMENTARY_GRANT = "COMPLIMENTARY_GRANT"
    BETA_TRIAL = "BETA_TRIAL"


class GrantAction(str, enum.Enum):
    GRANT = "GRANT"
    REVOKE = "REVOKE"


class AnalyticsEventType(str, enum.Enum):
    SESSION_STARTED = "SESSION_STARTED"
    WORKSPACE_OPENED = "WORKSPACE_OPENED"
    RESEARCH_STARTED = "RESEARCH_STARTED"
    RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
    DEPLOYMENT_FLOW_OPENED = "DEPLOYMENT_FLOW_OPENED"
    ERROR_SHOWN = "ERROR_SHOWN"


class AnalyticsSurface(str, enum.Enum):
    SHELL = "SHELL"
    WORKSPACE = "WORKSPACE"
    RESEARCH = "RESEARCH"
    DEPLOYMENT = "DEPLOYMENT"


class AnalyticsOutcome(str, enum.Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
    UNKNOWN = "UNKNOWN"


class SupportCategory(str, enum.Enum):
    ACCOUNT_ACCESS = "ACCOUNT_ACCESS"
    BILLING = "BILLING"
    PRODUCT_USAGE = "PRODUCT_USAGE"
    DATA_QUALITY = "DATA_QUALITY"
    OTHER_STRUCTURED = "OTHER_STRUCTURED"


class SupportStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class OperatorBindingState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class OperatorPermission(str, enum.Enum):
    BILLING_READ = "BILLING_READ"
    SUPPORT_WRITE = "SUPPORT_WRITE"
    ENTITLEMENT_WRITE = "ENTITLEMENT_WRITE"
    AUDIT_WRITE = "AUDIT_WRITE"


class OperatorAction(str, enum.Enum):
    VIEW_AGGREGATE = "VIEW_AGGREGATE"
    REPLY_SUPPORT = "REPLY_SUPPORT"
    ISSUE_COMPLIMENTARY = "ISSUE_COMPLIMENTARY"
    REVOKE_COMPLIMENTARY = "REVOKE_COMPLIMENTARY"
    CHANGE_BINDING = "CHANGE_BINDING"


class OperatorTarget(str, enum.Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    SUPPORT_REQUEST = "SUPPORT_REQUEST"
    ENTITLEMENT = "ENTITLEMENT"
    OPERATOR_BINDING = "OPERATOR_BINDING"


class OperatorOutcome(str, enum.Enum):
    SUCCEEDED = "SUCCEEDED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_REDACTED = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN = (
    "strategy", "graph", "component", "parameter", "annotation", "dataset",
    "research", "monitoring", "alert", "signal", "instrument", "nifty",
    "banknifty", "broker", "provider_account", "credential", "secret", "token", "position", "order",
    "trade", "balance", "capital", "pnl", "profit", "loss", "raw_request",
    "raw_response", "raw_webhook", "card", "upi", "free_text", "attachment",
    "diagnostic",
)

SUPPORT_DETAIL_CODES = frozenset({
    "LOGIN_FAILED", "PAYMENT_FAILED", "PRODUCT_GUIDANCE", "DATA_MISMATCH",
    "OTHER_DECLARED",
})
SUPPORT_RESPONSE_CODES = frozenset({
    "ACKNOWLEDGED", "NEEDS_ACCOUNT_ACTION", "BILLING_REVIEWED",
    "RESOLVED_WITH_GUIDANCE", "CANNOT_ASSIST",
})
ANALYTICS_DIMENSION_CODES = frozenset({
    "DESKTOP", "WEB", "EMPTY", "RETRY", "MANUAL",
})
_SYSTEM_VOCABULARY = frozenset(
    item.value
    for enum_type in (
        BillingMode, PolicyState, BillingInterval, CouponState, EntitlementEffectTiming,
        BindingState,
        BillingEventType, BillingEventState, EntitlementTransition, EntitlementState,
        EntitlementSource, GrantAction, AnalyticsEventType, AnalyticsSurface,
        AnalyticsOutcome, SupportCategory, SupportStatus, OperatorBindingState,
        OperatorPermission, OperatorAction, OperatorTarget, OperatorOutcome,
    )
    for item in enum_type
) | SUPPORT_DETAIL_CODES | SUPPORT_RESPONSE_CODES | ANALYTICS_DIMENSION_CODES | {
    "ACCEPTED", "REVOKED", "FOUNDER",
}


def _privacy(value: str, label: str) -> str:
    lowered = value.lower()
    if any(sentinel in lowered for sentinel in _FORBIDDEN):
        raise OperationsRefused(f"{label} contains forbidden platform content")
    return value


def reference(value: object, label: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or len(value) > maximum or not _REFERENCE.fullmatch(value):
        raise OperationsRefused(f"{label} must be an opaque bounded reference")
    return _privacy(value, label)


def code(value: object, label: str) -> str:
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        raise OperationsRefused(f"{label} must be a closed code")
    return _privacy(value, label)


def support_detail_code(value: object) -> str:
    value = code(value, "support detail")
    if value not in SUPPORT_DETAIL_CODES:
        raise OperationsRefused("unsupported support detail code version 1")
    return value


def support_response_code(value: object) -> str:
    value = code(value, "support response")
    if value not in SUPPORT_RESPONSE_CODES:
        raise OperationsRefused("unsupported support response code version 1")
    return value


def analytics_dimension_code(value: object) -> str:
    value = code(value, "analytics dimension")
    if value not in ANALYTICS_DIMENSION_CODES:
        raise OperationsRefused("unsupported analytics dimension code version 1")
    return value


def validate_persisted_text(value: object, label: str) -> None:
    """Rescan restored text while permitting only declared system vocabulary."""
    if value is None:
        return
    if not isinstance(value, str):
        raise OperationsRefused(f"{label} text value is invalid")
    if value in _SYSTEM_VOCABULARY or _DIGEST.fullmatch(value) or _ADDRESS.fullmatch(value):
        return
    _privacy(value, label)


def digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise OperationsRefused(f"{label} must be a lowercase SHA-256 digest")
    return value


def address(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise OperationsRefused(f"{label} must be a SHA-256 content address")
    return value


def currency(value: object) -> str:
    if not isinstance(value, str) or not _CURRENCY.fullmatch(value):
        raise OperationsRefused("currency must be an uppercase ISO 4217 code")
    return value


def utc(value: object, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is not dt.timezone.utc:
        raise OperationsRefused(f"{label} must be UTC")
    return value


def redacted_id(value: object) -> str:
    if not isinstance(value, str) or not _REDACTED.fullmatch(value):
        raise OperationsRefused("operator target must be a one-way redacted identifier")
    return value


@dataclass(frozen=True, slots=True)
class TenantAuthority:
    """Identity assembled by account/session authority, never from a request body."""

    owner_ref: str
    principal_ref: str
    membership_state: MembershipState

    def __post_init__(self) -> None:
        reference(self.owner_ref, "owner")
        reference(self.principal_ref, "principal")


@dataclass(frozen=True, slots=True)
class OperatorAuthority:
    """Future operator-session output; tenant roles are intentionally absent."""

    binding_id: str
    principal_ref: str

    def __post_init__(self) -> None:
        reference(self.binding_id, "operator binding")
        reference(self.principal_ref, "operator principal")


@dataclass(frozen=True, slots=True)
class BillingVerifierAuthority:
    """Internal verified-provider seam, distinct from tenant membership."""

    verifier_ref: str
    mode: BillingMode
    merchant_address: str
    integration_address: str

    def __post_init__(self) -> None:
        reference(self.verifier_ref, "billing verifier")
        if not isinstance(self.mode, BillingMode):
            raise OperationsRefused("billing verifier mode is invalid")
        if self.mode is BillingMode.INTERNAL:
            raise OperationsRefused("billing verifier requires test or live mode")
        address(self.merchant_address, "billing verifier merchant")
        address(self.integration_address, "billing verifier integration")


@dataclass(frozen=True, slots=True)
class PlanVersion:
    plan_version_id: str
    plan_code: str
    version: int
    amount_minor: int
    currency: str
    billing_interval: BillingInterval
    entitlement_set_address: str
    policy_state: PolicyState
    created_at: dt.datetime


@dataclass(frozen=True, slots=True)
class CouponRedemption:
    redemption_id: str
    coupon_id: str
    owner_ref: str
    policy_address: str
    redeemed_at: dt.datetime
    entitlement_valid_from: dt.datetime
    entitlement_valid_until: dt.datetime | None


@dataclass(frozen=True, slots=True)
class BillingReceipt:
    receipt_id: str
    binding_id: str
    owner_ref: str
    mode: BillingMode
    provider_event_id: str
    event_type: BillingEventType
    event_state: BillingEventState
    raw_body_digest: str
    received_at: dt.datetime


@dataclass(frozen=True, slots=True)
class CurrentEntitlement:
    owner_ref: str
    entitlement_code: str
    mode: BillingMode
    state: EntitlementState
    source_event_id: str | None
    effective_at: dt.datetime | None
    valid_until: dt.datetime | None


@dataclass(frozen=True, slots=True)
class AnalyticsSubject:
    owner_ref: str
    subject_id: str
    created_at: dt.datetime
    deleted_at: dt.datetime | None
    exported_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class SupportRequest:
    request_id: str
    owner_ref: str
    category: SupportCategory
    detail_code: str
    status: SupportStatus
    created_at: dt.datetime
    updated_at: dt.datetime
    deleted_at: dt.datetime | None
    exported_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class Page:
    items: tuple[object, ...]
    next_cursor: str | None


def page_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise OperationsRefused("page limit must be between 1 and 100")
    return value
