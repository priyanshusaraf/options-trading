"""Pure, unpublished contracts for closed structured support facts.

The module validates immutable candidates only. It has no persistence,
transport, configuration lookup, clock, or external effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
import hashlib
import json
import re
from typing import Any, ClassVar
from uuid import RFC_4122, UUID


CONTRACT_VERSION = 1
MAX_IDENTIFIER_LENGTH = 96
MAX_COLLECTION_ITEMS = 64
MAX_CANONICAL_BYTES = 16_384
MAX_JSON_DEPTH = 14
MIN_INTEGER_ANSWER = -1_000_000_000
MAX_INTEGER_ANSWER = 1_000_000_000

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]*\Z")


class ContractValidationError(ValueError):
    """A closed contract rejected malformed, open, or inconsistent input."""


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKING = "BLOCKING"


class SupportStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    REVIEWING = "REVIEWING"
    RESPONDED = "RESPONDED"
    CLOSED = "CLOSED"


class AnswerKind(str, Enum):
    FINITE_ENUM = "FINITE_ENUM"
    BOOLEAN = "BOOLEAN"
    BOUNDED_INTEGER = "BOUNDED_INTEGER"


def _identifier(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be a string")
    if not 1 <= len(value) <= MAX_IDENTIFIER_LENGTH or not _IDENTIFIER.fullmatch(value):
        raise ContractValidationError(f"{field_name} is not a closed bounded identifier")
    return value


def _identifier_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if type(value) is not tuple or not 1 <= len(value) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError(f"{field_name} has an invalid immutable item count")
    validated = tuple(_identifier(item, f"{field_name} item") for item in value)
    if validated != tuple(sorted(set(validated))):
        raise ContractValidationError(f"{field_name} must be sorted and unique")
    return validated


def _uuid(value: object, field_name: str) -> UUID:
    if type(value) is not UUID or value.int == 0 or value.variant != RFC_4122:
        raise ContractValidationError(f"{field_name} must be a UUID")
    return value


def _parse_uuid(value: object, field_name: str) -> UUID:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ContractValidationError(f"{field_name} is invalid") from exc
    if str(parsed) != value:
        raise ContractValidationError(f"{field_name} is not canonical")
    return parsed


def _utc(value: object, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ContractValidationError(f"{field_name} must be a UTC datetime")
    if not 2000 <= value.year <= 9998:
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


def _strict_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise ContractValidationError(f"{field_name} must be a boolean")
    return value


def _strict_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractValidationError(f"{field_name} is outside supported bounds")
    return value


def _closed_enum(enum_type: type[Enum], value: object, field_name: str) -> Enum:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be a closed enum string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} is unknown") from exc


def _expect_keys(value: object, expected: set[str], contract_name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ContractValidationError(f"{contract_name} must be an object")
    actual = set(value)
    if actual != expected:
        raise ContractValidationError(
            f"{contract_name} fields mismatch: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return value


def _versioned(value: object, contract_type: str, fields: set[str]) -> dict[str, Any]:
    raw = _expect_keys(value, {"contract_type", "contract_version", *fields}, contract_type)
    if raw["contract_type"] != contract_type:
        raise ContractValidationError("contract_type does not match the closed shape")
    if type(raw["contract_version"]) is not int or raw["contract_version"] != CONTRACT_VERSION:
        raise ContractValidationError("contract_version must be the exact built-in integer 1")
    return raw


def _canonical_json(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("contract is not canonical JSON data") from exc
    if len(encoded.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("canonical contract exceeds size bound")
    return encoded


def _json_depth(value: object) -> int:
    maximum = 0
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        current, parent_depth = stack.pop()
        if type(current) is dict:
            depth = parent_depth + 1
            maximum = max(maximum, depth)
            if maximum > MAX_JSON_DEPTH:
                return maximum
            stack.extend((item, depth) for item in current.values())
        elif type(current) is list:
            depth = parent_depth + 1
            maximum = max(maximum, depth)
            if maximum > MAX_JSON_DEPTH:
                return maximum
            stack.extend((item, depth) for item in current)
    return maximum


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError("duplicate object key")
        result[key] = value
    return result


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
class EnumAnswerDomain(_CanonicalContract):
    contract_type: ClassVar[str] = "EnumAnswerDomain"
    question_id: str
    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.question_id, "question_id")
        _identifier_tuple(self.allowed_values, "allowed_values")

    @property
    def kind(self) -> AnswerKind:
        return AnswerKind.FINITE_ENUM

    def _payload(self) -> dict[str, object]:
        return {"question_id": self.question_id, "allowed_values": list(self.allowed_values)}


@dataclass(frozen=True, slots=True)
class BooleanAnswerDomain(_CanonicalContract):
    contract_type: ClassVar[str] = "BooleanAnswerDomain"
    question_id: str

    def __post_init__(self) -> None:
        _identifier(self.question_id, "question_id")

    @property
    def kind(self) -> AnswerKind:
        return AnswerKind.BOOLEAN

    def _payload(self) -> dict[str, object]:
        return {"question_id": self.question_id}


@dataclass(frozen=True, slots=True)
class IntegerAnswerDomain(_CanonicalContract):
    contract_type: ClassVar[str] = "IntegerAnswerDomain"
    question_id: str
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        _identifier(self.question_id, "question_id")
        minimum = _strict_int(
            self.minimum, "minimum", MIN_INTEGER_ANSWER, MAX_INTEGER_ANSWER
        )
        maximum = _strict_int(
            self.maximum, "maximum", MIN_INTEGER_ANSWER, MAX_INTEGER_ANSWER
        )
        if minimum > maximum:
            raise ContractValidationError("integer answer bounds are reversed")

    @property
    def kind(self) -> AnswerKind:
        return AnswerKind.BOUNDED_INTEGER

    def _payload(self) -> dict[str, object]:
        return {"question_id": self.question_id, "minimum": self.minimum, "maximum": self.maximum}


AnswerDomain = EnumAnswerDomain | BooleanAnswerDomain | IntegerAnswerDomain


@dataclass(frozen=True, slots=True)
class EnumAnswer(_CanonicalContract):
    contract_type: ClassVar[str] = "EnumAnswer"
    question_id: str
    value: str

    def __post_init__(self) -> None:
        _identifier(self.question_id, "question_id")
        _identifier(self.value, "value")

    @property
    def kind(self) -> AnswerKind:
        return AnswerKind.FINITE_ENUM

    def _payload(self) -> dict[str, object]:
        return {"question_id": self.question_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class BooleanAnswer(_CanonicalContract):
    contract_type: ClassVar[str] = "BooleanAnswer"
    question_id: str
    value: bool

    def __post_init__(self) -> None:
        _identifier(self.question_id, "question_id")
        _strict_bool(self.value, "value")

    @property
    def kind(self) -> AnswerKind:
        return AnswerKind.BOOLEAN

    def _payload(self) -> dict[str, object]:
        return {"question_id": self.question_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class IntegerAnswer(_CanonicalContract):
    contract_type: ClassVar[str] = "IntegerAnswer"
    question_id: str
    value: int

    def __post_init__(self) -> None:
        _identifier(self.question_id, "question_id")
        _strict_int(self.value, "value", MIN_INTEGER_ANSWER, MAX_INTEGER_ANSWER)

    @property
    def kind(self) -> AnswerKind:
        return AnswerKind.BOUNDED_INTEGER

    def _payload(self) -> dict[str, object]:
        return {"question_id": self.question_id, "value": self.value}


TypedAnswer = EnumAnswer | BooleanAnswer | IntegerAnswer


@dataclass(frozen=True, slots=True)
class StatusTransition(_CanonicalContract):
    contract_type: ClassVar[str] = "StatusTransition"
    from_status: SupportStatus
    to_status: SupportStatus

    def __post_init__(self) -> None:
        if not isinstance(self.from_status, SupportStatus) or not isinstance(
            self.to_status, SupportStatus
        ):
            raise ContractValidationError("status transition must use closed statuses")
        if self.from_status is self.to_status:
            raise ContractValidationError("status transition cannot be a no-op")

    def _payload(self) -> dict[str, object]:
        return {"from_status": self.from_status.value, "to_status": self.to_status.value}


@dataclass(frozen=True, slots=True)
class SupportPolicy(_CanonicalContract):
    contract_type: ClassVar[str] = "SupportPolicy"
    policy_id: str
    category_ids: tuple[str, ...]
    product_area_ids: tuple[str, ...]
    route_template_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    build_ids: tuple[str, ...]
    context_ids: tuple[str, ...]
    answer_domains: tuple[AnswerDomain, ...]
    response_template_ids: tuple[str, ...]
    status_transitions: tuple[StatusTransition, ...]

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        for field_name in (
            "category_ids",
            "product_area_ids",
            "route_template_ids",
            "component_ids",
            "build_ids",
            "context_ids",
            "response_template_ids",
        ):
            _identifier_tuple(getattr(self, field_name), field_name)
        if type(self.answer_domains) is not tuple or not 1 <= len(self.answer_domains) <= MAX_COLLECTION_ITEMS:
            raise ContractValidationError("answer_domains has an invalid immutable item count")
        if any(
            type(item) not in (EnumAnswerDomain, BooleanAnswerDomain, IntegerAnswerDomain)
            for item in self.answer_domains
        ):
            raise ContractValidationError("answer_domains contains an open type")
        question_ids = tuple(item.question_id for item in self.answer_domains)
        if question_ids != tuple(sorted(set(question_ids))):
            raise ContractValidationError("answer_domains must be sorted by unique question_id")
        if type(self.status_transitions) is not tuple or not 1 <= len(self.status_transitions) <= MAX_COLLECTION_ITEMS:
            raise ContractValidationError("status_transitions has an invalid immutable item count")
        if any(type(item) is not StatusTransition for item in self.status_transitions):
            raise ContractValidationError("status_transitions contains an open type")
        transition_keys = tuple(
            (item.from_status.value, item.to_status.value) for item in self.status_transitions
        )
        if transition_keys != tuple(sorted(set(transition_keys))):
            raise ContractValidationError("status_transitions must be sorted and unique")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "category_ids": list(self.category_ids),
            "product_area_ids": list(self.product_area_ids),
            "route_template_ids": list(self.route_template_ids),
            "component_ids": list(self.component_ids),
            "build_ids": list(self.build_ids),
            "context_ids": list(self.context_ids),
            "answer_domains": [item.canonical_dict() for item in self.answer_domains],
            "response_template_ids": list(self.response_template_ids),
            "status_transitions": [item.canonical_dict() for item in self.status_transitions],
        }


@lru_cache(maxsize=64)
def _policy_content_id(policy: SupportPolicy) -> str:
    """Memoize immutable policy identity for bounded repeated pure decisions."""
    return policy.content_id


def _validate_answers(policy: SupportPolicy, answers: object) -> tuple[TypedAnswer, ...]:
    if type(answers) is not tuple or not 1 <= len(answers) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError("answers has an invalid immutable item count")
    if any(type(item) not in (EnumAnswer, BooleanAnswer, IntegerAnswer) for item in answers):
        raise ContractValidationError("answers contains an open type")
    question_ids = tuple(item.question_id for item in answers)
    expected_ids = tuple(domain.question_id for domain in policy.answer_domains)
    if question_ids != expected_ids:
        raise ContractValidationError("answers must match the exact sorted policy question set")
    for domain, answer in zip(policy.answer_domains, answers, strict=True):
        if isinstance(domain, EnumAnswerDomain):
            if not isinstance(answer, EnumAnswer) or answer.value not in domain.allowed_values:
                raise ContractValidationError("enum answer is outside its finite domain")
        elif isinstance(domain, BooleanAnswerDomain):
            if not isinstance(answer, BooleanAnswer):
                raise ContractValidationError("boolean answer has the wrong closed kind")
        elif not isinstance(answer, IntegerAnswer) or not domain.minimum <= answer.value <= domain.maximum:
            raise ContractValidationError("integer answer is outside its policy bounds")
    return answers


@dataclass(frozen=True, slots=True)
class SubmissionCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "SubmissionCandidate"
    support_case_id: UUID
    account_subject_id: UUID
    tenant_scope_id: UUID
    policy_id: str
    policy_content_id: str
    category_id: str
    product_area_id: str
    route_template_id: str
    component_id: str
    build_id: str
    context_id: str
    severity: Severity
    typed_answers: tuple[TypedAnswer, ...]
    status: SupportStatus
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("support_case_id", "account_subject_id", "tenant_scope_id"):
            _uuid(getattr(self, field_name), field_name)
        for field_name in (
            "policy_id", "policy_content_id", "category_id", "product_area_id",
            "route_template_id", "component_id", "build_id", "context_id",
        ):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.severity, Severity):
            raise ContractValidationError("severity must use the closed enum")
        if type(self.typed_answers) is not tuple or not 1 <= len(self.typed_answers) <= MAX_COLLECTION_ITEMS:
            raise ContractValidationError("typed_answers has an invalid immutable item count")
        if any(type(item) not in (EnumAnswer, BooleanAnswer, IntegerAnswer) for item in self.typed_answers):
            raise ContractValidationError("typed_answers contains an open type")
        if not isinstance(self.status, SupportStatus) or self.status is not SupportStatus.SUBMITTED:
            raise ContractValidationError("a new submission must have SUBMITTED status")
        _utc(self.created_at, "created_at")

    def _payload(self) -> dict[str, object]:
        return {
            "support_case_id": str(self.support_case_id),
            "account_subject_id": str(self.account_subject_id),
            "tenant_scope_id": str(self.tenant_scope_id),
            "policy_id": self.policy_id,
            "policy_content_id": self.policy_content_id,
            "category_id": self.category_id,
            "product_area_id": self.product_area_id,
            "route_template_id": self.route_template_id,
            "component_id": self.component_id,
            "build_id": self.build_id,
            "context_id": self.context_id,
            "severity": self.severity.value,
            "typed_answers": [item.canonical_dict() for item in self.typed_answers],
            "status": self.status.value,
            "created_at": _datetime_text(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class OperatorProjection(SubmissionCandidate):
    contract_type: ClassVar[str] = "OperatorProjection"


@dataclass(frozen=True, slots=True)
class OperatorActionCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "OperatorActionCandidate"
    support_case_id: UUID
    account_subject_id: UUID
    tenant_scope_id: UUID
    policy_id: str
    policy_content_id: str
    status: SupportStatus
    response_template_id: str
    acted_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("support_case_id", "account_subject_id", "tenant_scope_id"):
            _uuid(getattr(self, field_name), field_name)
        for field_name in ("policy_id", "policy_content_id", "response_template_id"):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.status, SupportStatus):
            raise ContractValidationError("status must use the closed enum")
        _utc(self.acted_at, "acted_at")

    def _payload(self) -> dict[str, object]:
        return {
            "support_case_id": str(self.support_case_id),
            "account_subject_id": str(self.account_subject_id),
            "tenant_scope_id": str(self.tenant_scope_id),
            "policy_id": self.policy_id,
            "policy_content_id": self.policy_content_id,
            "status": self.status.value,
            "response_template_id": self.response_template_id,
            "acted_at": _datetime_text(self.acted_at),
        }


@dataclass(frozen=True, slots=True)
class InAppDeliveryCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "InAppDeliveryCandidate"
    support_case_id: UUID
    account_subject_id: UUID
    tenant_scope_id: UUID
    policy_id: str
    policy_content_id: str
    status: SupportStatus
    response_template_id: str
    created_at: datetime
    delivery_effected: bool

    def __post_init__(self) -> None:
        for field_name in ("support_case_id", "account_subject_id", "tenant_scope_id"):
            _uuid(getattr(self, field_name), field_name)
        for field_name in ("policy_id", "policy_content_id", "response_template_id"):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.status, SupportStatus):
            raise ContractValidationError("status must use the closed enum")
        _utc(self.created_at, "created_at")
        if _strict_bool(self.delivery_effected, "delivery_effected") is not False:
            raise ContractValidationError("a delivery candidate cannot effect delivery")

    def _payload(self) -> dict[str, object]:
        return {
            "support_case_id": str(self.support_case_id),
            "account_subject_id": str(self.account_subject_id),
            "tenant_scope_id": str(self.tenant_scope_id),
            "policy_id": self.policy_id,
            "policy_content_id": self.policy_content_id,
            "status": self.status.value,
            "response_template_id": self.response_template_id,
            "created_at": _datetime_text(self.created_at),
            "delivery_effected": self.delivery_effected,
        }


@dataclass(frozen=True, slots=True)
class AnalyticsDimensionsCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "AnalyticsDimensionsCandidate"
    category_id: str
    product_area_id: str
    severity: Severity
    status: SupportStatus

    def __post_init__(self) -> None:
        _identifier(self.category_id, "category_id")
        _identifier(self.product_area_id, "product_area_id")
        if not isinstance(self.severity, Severity) or not isinstance(self.status, SupportStatus):
            raise ContractValidationError("analytics dimensions use closed enums")

    def _payload(self) -> dict[str, object]:
        return {
            "category_id": self.category_id,
            "product_area_id": self.product_area_id,
            "severity": self.severity.value,
            "status": self.status.value,
        }


def create_submission_candidate(
    *, policy: SupportPolicy, support_case_id: UUID, account_subject_id: UUID,
    tenant_scope_id: UUID, category_id: str, product_area_id: str,
    route_template_id: str, component_id: str, build_id: str, context_id: str,
    severity: Severity, typed_answers: tuple[TypedAnswer, ...], created_at: datetime,
) -> SubmissionCandidate:
    if type(policy) is not SupportPolicy:
        raise ContractValidationError("policy must use the closed type")
    selected = (
        (category_id, policy.category_ids, "category_id"),
        (product_area_id, policy.product_area_ids, "product_area_id"),
        (route_template_id, policy.route_template_ids, "route_template_id"),
        (component_id, policy.component_ids, "component_id"),
        (build_id, policy.build_ids, "build_id"),
        (context_id, policy.context_ids, "context_id"),
    )
    for value, allowed, field_name in selected:
        if _identifier(value, field_name) not in allowed:
            raise ContractValidationError(f"{field_name} is outside the injected policy")
    answers = _validate_answers(policy, typed_answers)
    return SubmissionCandidate(
        support_case_id=support_case_id, account_subject_id=account_subject_id,
        tenant_scope_id=tenant_scope_id, policy_id=policy.policy_id,
        policy_content_id=policy.content_id, category_id=category_id,
        product_area_id=product_area_id, route_template_id=route_template_id,
        component_id=component_id, build_id=build_id, context_id=context_id,
        severity=severity, typed_answers=answers, status=SupportStatus.SUBMITTED,
        created_at=created_at,
    )


def _submission_matches_policy(
    policy: SupportPolicy, submission: SubmissionCandidate,
    policy_content_id: str | None = None,
) -> bool:
    expected_content_id = _policy_content_id(policy) if policy_content_id is None else policy_content_id
    if (
        submission.policy_id != policy.policy_id
        or submission.policy_content_id != expected_content_id
    ):
        return False
    selected = (
        (submission.category_id, policy.category_ids),
        (submission.product_area_id, policy.product_area_ids),
        (submission.route_template_id, policy.route_template_ids),
        (submission.component_id, policy.component_ids),
        (submission.build_id, policy.build_ids),
        (submission.context_id, policy.context_ids),
    )
    if any(value not in allowed for value, allowed in selected):
        return False
    try:
        _validate_answers(policy, submission.typed_answers)
    except ContractValidationError:
        return False
    return True


def _action_matches_sources(
    policy: SupportPolicy,
    projection: OperatorProjection,
    action: OperatorActionCandidate,
) -> bool:
    policy_content_id = _policy_content_id(policy) if type(policy) is SupportPolicy else ""
    return (
        type(policy) is SupportPolicy
        and type(projection) is OperatorProjection
        and type(action) is OperatorActionCandidate
        and _submission_matches_policy(policy, projection, policy_content_id)
        and action.support_case_id == projection.support_case_id
        and action.account_subject_id == projection.account_subject_id
        and action.tenant_scope_id == projection.tenant_scope_id
        and action.policy_id == projection.policy_id == policy.policy_id
        and action.policy_content_id == projection.policy_content_id == policy_content_id
        and action.response_template_id in policy.response_template_ids
        and any(
            item.from_status is projection.status and item.to_status is action.status
            for item in policy.status_transitions
        )
    )


def _delivery_matches_sources(
    policy: SupportPolicy,
    projection: OperatorProjection,
    action: OperatorActionCandidate,
    delivery: InAppDeliveryCandidate,
) -> bool:
    return (
        _action_matches_sources(policy, projection, action)
        and type(delivery) is InAppDeliveryCandidate
        and delivery.support_case_id == projection.support_case_id == action.support_case_id
        and delivery.account_subject_id == projection.account_subject_id == action.account_subject_id
        and delivery.tenant_scope_id == projection.tenant_scope_id == action.tenant_scope_id
        and delivery.policy_id == projection.policy_id == action.policy_id
        and delivery.policy_content_id == projection.policy_content_id == action.policy_content_id
        and delivery.status is action.status
        and delivery.response_template_id == action.response_template_id
        and delivery.created_at == action.acted_at
        and delivery.delivery_effected is False
    )


def create_operator_projection(
    *, policy: SupportPolicy, submission: SubmissionCandidate,
    account_subject_id: UUID, tenant_scope_id: UUID,
) -> OperatorProjection | None:
    if (
        type(policy) is not SupportPolicy
        or type(submission) is not SubmissionCandidate
        or submission.policy_id != policy.policy_id
        or submission.policy_content_id != policy.content_id
        or submission.account_subject_id != account_subject_id
        or submission.tenant_scope_id != tenant_scope_id
        or not _submission_matches_policy(policy, submission)
    ):
        return None
    return OperatorProjection(
        support_case_id=submission.support_case_id,
        account_subject_id=submission.account_subject_id,
        tenant_scope_id=submission.tenant_scope_id,
        policy_id=submission.policy_id,
        policy_content_id=submission.policy_content_id,
        category_id=submission.category_id,
        product_area_id=submission.product_area_id,
        route_template_id=submission.route_template_id,
        component_id=submission.component_id,
        build_id=submission.build_id,
        context_id=submission.context_id,
        severity=submission.severity,
        typed_answers=submission.typed_answers,
        status=submission.status,
        created_at=submission.created_at,
    )


def create_operator_action_candidate(
    *, policy: SupportPolicy, projection: OperatorProjection, support_case_id: UUID,
    account_subject_id: UUID, tenant_scope_id: UUID, status: SupportStatus,
    response_template_id: str, acted_at: datetime,
) -> OperatorActionCandidate | None:
    if type(policy) is not SupportPolicy or type(projection) is not OperatorProjection:
        return None
    candidate = OperatorActionCandidate(
        support_case_id=support_case_id, account_subject_id=account_subject_id,
        tenant_scope_id=tenant_scope_id, policy_id=policy.policy_id,
        policy_content_id=policy.content_id, status=status,
        response_template_id=response_template_id, acted_at=acted_at,
    )
    return candidate if _action_matches_sources(policy, projection, candidate) else None


def create_in_app_delivery_candidate(
    *, policy: SupportPolicy, projection: OperatorProjection, action: OperatorActionCandidate,
    support_case_id: UUID, account_subject_id: UUID, tenant_scope_id: UUID,
) -> InAppDeliveryCandidate | None:
    if (
        type(policy) is not SupportPolicy
        or type(projection) is not OperatorProjection
        or type(action) is not OperatorActionCandidate
    ):
        return None
    candidate = InAppDeliveryCandidate(
        support_case_id=support_case_id, account_subject_id=account_subject_id,
        tenant_scope_id=tenant_scope_id, policy_id=action.policy_id,
        policy_content_id=action.policy_content_id, status=action.status,
        response_template_id=action.response_template_id, created_at=action.acted_at,
        delivery_effected=False,
    )
    return candidate if _delivery_matches_sources(policy, projection, action, candidate) else None


def create_analytics_dimensions(
    *, policy: SupportPolicy, projection: OperatorProjection,
    action: OperatorActionCandidate | None = None,
) -> AnalyticsDimensionsCandidate:
    if (
        type(policy) is not SupportPolicy
        or type(projection) is not OperatorProjection
        or not _submission_matches_policy(policy, projection)
        or (
            action is not None
            and not _action_matches_sources(policy, projection, action)
        )
    ):
        raise ContractValidationError("analytics dimensions require an exact source fact")
    status = projection.status if action is None else action.status
    return AnalyticsDimensionsCandidate(
        category_id=projection.category_id, product_area_id=projection.product_area_id,
        severity=projection.severity, status=status,
    )


def _decode_contract(raw: object) -> _CanonicalContract:
    if type(raw) is not dict:
        raise ContractValidationError("contract must be an object")
    contract_type = raw.get("contract_type")
    if type(contract_type) is not str:
        raise ContractValidationError("contract_type must be a closed string")
    if contract_type == "EnumAnswerDomain":
        value = _versioned(raw, contract_type, {"question_id", "allowed_values"})
        return EnumAnswerDomain(value["question_id"], tuple(value["allowed_values"]) if type(value["allowed_values"]) is list else value["allowed_values"])
    if contract_type == "BooleanAnswerDomain":
        value = _versioned(raw, contract_type, {"question_id"})
        return BooleanAnswerDomain(value["question_id"])
    if contract_type == "IntegerAnswerDomain":
        value = _versioned(raw, contract_type, {"question_id", "minimum", "maximum"})
        return IntegerAnswerDomain(value["question_id"], value["minimum"], value["maximum"])
    if contract_type == "EnumAnswer":
        value = _versioned(raw, contract_type, {"question_id", "value"})
        return EnumAnswer(value["question_id"], value["value"])
    if contract_type == "BooleanAnswer":
        value = _versioned(raw, contract_type, {"question_id", "value"})
        return BooleanAnswer(value["question_id"], value["value"])
    if contract_type == "IntegerAnswer":
        value = _versioned(raw, contract_type, {"question_id", "value"})
        return IntegerAnswer(value["question_id"], value["value"])
    if contract_type == "StatusTransition":
        value = _versioned(raw, contract_type, {"from_status", "to_status"})
        return StatusTransition(
            _closed_enum(SupportStatus, value["from_status"], "from_status"),
            _closed_enum(SupportStatus, value["to_status"], "to_status"),
        )
    if contract_type == "SupportPolicy":
        fields = {"policy_id", "category_ids", "product_area_ids", "route_template_ids", "component_ids", "build_ids", "context_ids", "answer_domains", "response_template_ids", "status_transitions"}
        value = _versioned(raw, contract_type, fields)
        list_fields = fields - {"policy_id", "answer_domains", "status_transitions"}
        for field_name in list_fields:
            if type(value[field_name]) is not list:
                raise ContractValidationError(f"{field_name} must be an array")
        if type(value["answer_domains"]) is not list or type(value["status_transitions"]) is not list:
            raise ContractValidationError("nested policy contracts must be arrays")
        return SupportPolicy(
            policy_id=value["policy_id"],
            category_ids=tuple(value["category_ids"]), product_area_ids=tuple(value["product_area_ids"]),
            route_template_ids=tuple(value["route_template_ids"]), component_ids=tuple(value["component_ids"]),
            build_ids=tuple(value["build_ids"]), context_ids=tuple(value["context_ids"]),
            answer_domains=tuple(_decode_contract(item) for item in value["answer_domains"]),
            response_template_ids=tuple(value["response_template_ids"]),
            status_transitions=tuple(_decode_contract(item) for item in value["status_transitions"]),
        )
    if contract_type in {"SubmissionCandidate", "OperatorProjection"}:
        fields = {"support_case_id", "account_subject_id", "tenant_scope_id", "policy_id", "policy_content_id", "category_id", "product_area_id", "route_template_id", "component_id", "build_id", "context_id", "severity", "typed_answers", "status", "created_at"}
        value = _versioned(raw, contract_type, fields)
        if type(value["typed_answers"]) is not list:
            raise ContractValidationError("typed_answers must be an array")
        cls = SubmissionCandidate if contract_type == "SubmissionCandidate" else OperatorProjection
        return cls(
            support_case_id=_parse_uuid(value["support_case_id"], "support_case_id"),
            account_subject_id=_parse_uuid(value["account_subject_id"], "account_subject_id"),
            tenant_scope_id=_parse_uuid(value["tenant_scope_id"], "tenant_scope_id"),
            policy_id=value["policy_id"], policy_content_id=value["policy_content_id"],
            category_id=value["category_id"], product_area_id=value["product_area_id"],
            route_template_id=value["route_template_id"], component_id=value["component_id"],
            build_id=value["build_id"], context_id=value["context_id"],
            severity=_closed_enum(Severity, value["severity"], "severity"),
            typed_answers=tuple(_decode_contract(item) for item in value["typed_answers"]),
            status=_closed_enum(SupportStatus, value["status"], "status"),
            created_at=_parse_datetime(value["created_at"], "created_at"),
        )
    if contract_type == "OperatorActionCandidate":
        value = _versioned(raw, contract_type, {"support_case_id", "account_subject_id", "tenant_scope_id", "policy_id", "policy_content_id", "status", "response_template_id", "acted_at"})
        return OperatorActionCandidate(
            _parse_uuid(value["support_case_id"], "support_case_id"),
            _parse_uuid(value["account_subject_id"], "account_subject_id"),
            _parse_uuid(value["tenant_scope_id"], "tenant_scope_id"),
            value["policy_id"], value["policy_content_id"],
            _closed_enum(SupportStatus, value["status"], "status"),
            value["response_template_id"], _parse_datetime(value["acted_at"], "acted_at"),
        )
    if contract_type == "InAppDeliveryCandidate":
        value = _versioned(raw, contract_type, {"support_case_id", "account_subject_id", "tenant_scope_id", "policy_id", "policy_content_id", "status", "response_template_id", "created_at", "delivery_effected"})
        return InAppDeliveryCandidate(
            _parse_uuid(value["support_case_id"], "support_case_id"),
            _parse_uuid(value["account_subject_id"], "account_subject_id"),
            _parse_uuid(value["tenant_scope_id"], "tenant_scope_id"),
            value["policy_id"], value["policy_content_id"],
            _closed_enum(SupportStatus, value["status"], "status"),
            value["response_template_id"], _parse_datetime(value["created_at"], "created_at"),
            value["delivery_effected"],
        )
    if contract_type == "AnalyticsDimensionsCandidate":
        value = _versioned(raw, contract_type, {"category_id", "product_area_id", "severity", "status"})
        return AnalyticsDimensionsCandidate(
            value["category_id"], value["product_area_id"],
            _closed_enum(Severity, value["severity"], "severity"),
            _closed_enum(SupportStatus, value["status"], "status"),
        )
    raise ContractValidationError("unknown contract_type")


def canonical_deserialize(
    encoded: str, *, policy: SupportPolicy | None = None,
    projection: OperatorProjection | None = None,
    action: OperatorActionCandidate | None = None,
) -> _CanonicalContract:
    if type(encoded) is not str or len(encoded.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("encoded contract has invalid type or size")
    try:
        raw = json.loads(
            encoded, object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ContractValidationError(f"invalid JSON constant {value}")
            ),
        )
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ContractValidationError("encoded contract is invalid JSON") from exc
    if _json_depth(raw) > MAX_JSON_DEPTH:
        raise ContractValidationError("encoded contract exceeds depth bound")
    result = _decode_contract(raw)
    if result.canonical_json() != encoded:
        raise ContractValidationError("encoded contract is not canonical")
    policy_bound = isinstance(
        result,
        (
            SubmissionCandidate, OperatorProjection, OperatorActionCandidate,
            InAppDeliveryCandidate, AnalyticsDimensionsCandidate,
        ),
    )
    if policy_bound and type(policy) is not SupportPolicy:
        raise ContractValidationError("a policy-bound contract requires its injected policy")
    if isinstance(result, (SubmissionCandidate, OperatorProjection)) and (
        result.policy_id != policy.policy_id
        or result.policy_content_id != policy.content_id
        or not _submission_matches_policy(policy, result)
    ):
        raise ContractValidationError("submission contract does not match its injected policy")
    if isinstance(result, OperatorActionCandidate) and not _action_matches_sources(
        policy, projection, result,
    ):
        raise ContractValidationError("action contract does not match its exact source projection")
    if isinstance(result, InAppDeliveryCandidate) and not _delivery_matches_sources(
        policy, projection, action, result,
    ):
        raise ContractValidationError("delivery contract does not match its exact source facts")
    if isinstance(result, AnalyticsDimensionsCandidate):
        if type(projection) is not OperatorProjection:
            raise ContractValidationError("analytics dimensions require their exact source projection")
        expected = create_analytics_dimensions(
            policy=policy, projection=projection, action=action,
        )
        if result != expected:
            raise ContractValidationError("analytics dimensions do not match their exact source facts")
    return result


__all__ = [
    "CONTRACT_VERSION", "MAX_IDENTIFIER_LENGTH", "MAX_COLLECTION_ITEMS",
    "MAX_CANONICAL_BYTES", "MAX_JSON_DEPTH", "MIN_INTEGER_ANSWER",
    "MAX_INTEGER_ANSWER", "ContractValidationError", "Severity", "SupportStatus",
    "AnswerKind", "EnumAnswerDomain", "BooleanAnswerDomain", "IntegerAnswerDomain",
    "EnumAnswer", "BooleanAnswer", "IntegerAnswer", "StatusTransition", "SupportPolicy",
    "SubmissionCandidate", "OperatorProjection", "OperatorActionCandidate",
    "InAppDeliveryCandidate", "AnalyticsDimensionsCandidate", "create_submission_candidate",
    "create_operator_projection", "create_operator_action_candidate",
    "create_in_app_delivery_candidate", "create_analytics_dimensions", "canonical_deserialize",
]
