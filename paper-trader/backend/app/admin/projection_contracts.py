"""Pure, thresholded, unpublished founder/admin aggregate projection contracts.

These frozen values authenticate nobody and activate no access.  The module has
no storage, transport, clock, configuration, publication, or mutation effect.
All policy, proof, source, threshold, family, and time facts are injected and
revalidated at every use site because direct and copied instances are untrusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import re
from typing import Any, ClassVar


CONTRACT_VERSION = 1
MAX_IDENTIFIER_LENGTH = 96
MAX_DIMENSIONS = 16
MAX_COUNT = 1_000_000_000
MAX_CANONICAL_BYTES = 16_384
MAX_JSON_DEPTH = 12

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]*\Z")
_CONTENT_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ContractValidationError(ValueError):
    """A closed aggregate projection contract refused an unsafe value."""


def _family_dimension_vocabulary(family: int) -> tuple[int, ...]:
    """Return immutable exact integer codes for one aggregate family."""
    if family == 101:
        return (1, 2)
    if family == 102:
        return (3, 4)
    if family == 103:
        return (5, 6)
    if family == 104:
        return (7, 8)
    if family == 105:
        return (9, 10)
    raise ContractValidationError("family has no fixed admin dimension vocabulary")


def _identifier(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be a machine identifier")
    if not 1 <= len(value) <= MAX_IDENTIFIER_LENGTH or not _IDENTIFIER.fullmatch(value):
        raise ContractValidationError(f"{field_name} is not a closed bounded identifier")
    return value


def _content_address(value: object, field_name: str) -> str:
    if type(value) is not str or not _CONTENT_ADDRESS.fullmatch(value):
        raise ContractValidationError(f"{field_name} must be a canonical content address")
    return value


def _strict_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractValidationError(f"{field_name} is outside supported integer bounds")
    return value


def _strict_false(value: object, field_name: str) -> bool:
    if type(value) is not bool or value is not False:
        raise ContractValidationError(f"{field_name} must remain false")
    return value


def _family(value: object, field_name: str = "family") -> int:
    if type(value) is not int or value not in (101, 102, 103, 104, 105):
        raise ContractValidationError(f"{field_name} must be an exact built-in family code")
    return value


def _band_code(value: object, field_name: str = "operational_band_code") -> int:
    if type(value) is not int or value not in (201, 202, 203):
        raise ContractValidationError(f"{field_name} must be an exact built-in band code")
    return value


def _dimension_tuple(value: object, field_name: str) -> tuple[int, ...]:
    if type(value) is not tuple or not 1 <= len(value) <= MAX_DIMENSIONS:
        raise ContractValidationError(f"{field_name} has an invalid immutable item count")
    if any(type(item) is not int or not 1 <= item <= 10 for item in value):
        raise ContractValidationError(f"{field_name} must use exact built-in int codes 1..10")
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise ContractValidationError(f"{field_name} must be sorted and unique")
    return result


def _utc(value: object, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ContractValidationError(f"{field_name} must be an injected UTC datetime")
    if not 2000 <= value.year <= 9998:
        raise ContractValidationError(f"{field_name} is outside supported time bounds")
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
        raise ContractValidationError(f"{field_name} is not canonical UTC text")
    return parsed


def _closed_family(value: object, field_name: str) -> int:
    return _family(value, field_name)


def _closed_dimension(value: object, field_name: str) -> int:
    if type(value) is not int or not 1 <= value <= 10:
        raise ContractValidationError(f"{field_name} must be an exact JSON integer code 1..10")
    return value


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


def _expect_keys(value: object, expected: set[str], contract_name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ContractValidationError(f"{contract_name} must be an object")
    actual = set(value)
    if actual != expected:
        raise ContractValidationError(
            f"{contract_name} fields mismatch: missing={sorted(expected-actual)}, "
            f"extra={sorted(actual-expected)}"
        )
    return value


def _versioned(value: object, contract_type: str, fields: set[str]) -> dict[str, Any]:
    raw = _expect_keys(value, {"contract_type", "contract_version", *fields}, contract_type)
    if raw["contract_type"] != contract_type:
        raise ContractValidationError("contract_type does not match the closed shape")
    if type(raw["contract_version"]) is not int or raw["contract_version"] != CONTRACT_VERSION:
        raise ContractValidationError("contract_version must be exact built-in integer 1")
    return raw


class _CanonicalContract:
    contract_type: ClassVar[str]

    def _payload(self) -> dict[str, object]:
        raise NotImplementedError

    def canonical_dict(self) -> dict[str, object]:
        self.__post_init__()
        return {"contract_type": self.contract_type, "contract_version": CONTRACT_VERSION, **self._payload()}

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())

    @property
    def content_id(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@lru_cache(maxsize=128)
def _validated_content_id(value: _CanonicalContract) -> str:
    """Memoize canonical identity only after the caller revalidates current fields."""
    return value.content_id


@dataclass(frozen=True, slots=True)
class FamilyProjectionPolicy(_CanonicalContract):
    contract_type: ClassVar[str] = "FamilyProjectionPolicy"
    family: int
    allowed_dimension_codes: tuple[int, ...]

    def __post_init__(self) -> None:
        family = _family(self.family)
        dimensions = _dimension_tuple(self.allowed_dimension_codes, "allowed_dimension_codes")
        if any(item not in _family_dimension_vocabulary(family) for item in dimensions):
            raise ContractValidationError("dimension is not valid for the declared family")

    def _payload(self) -> dict[str, object]:
        return {"family": self.family, "allowed_dimension_codes": list(self.allowed_dimension_codes)}


@dataclass(frozen=True, slots=True)
class OperationalBand(_CanonicalContract):
    contract_type: ClassVar[str] = "OperationalBand"
    code: int
    minimum_count: int
    maximum_count: int

    def __post_init__(self) -> None:
        _band_code(self.code, "code")
        minimum = _strict_int(self.minimum_count, "minimum_count", 0, MAX_COUNT)
        maximum = _strict_int(self.maximum_count, "maximum_count", 0, MAX_COUNT)
        if minimum > maximum:
            raise ContractValidationError("operational band bounds are reversed")

    def _payload(self) -> dict[str, object]:
        return {"code": self.code, "minimum_count": self.minimum_count, "maximum_count": self.maximum_count}


@dataclass(frozen=True, slots=True)
class ProjectionPolicy(_CanonicalContract):
    contract_type: ClassVar[str] = "ProjectionPolicy"
    policy_provenance_address: str
    family_policies: tuple[FamilyProjectionPolicy, ...]
    operational_bands: tuple[OperationalBand, ...]
    minimum_cohort_threshold: int

    def __post_init__(self) -> None:
        _content_address(self.policy_provenance_address, "policy_provenance_address")
        _strict_int(self.minimum_cohort_threshold, "minimum_cohort_threshold", 1, MAX_COUNT)
        if type(self.family_policies) is not tuple or len(self.family_policies) != 5:
            raise ContractValidationError("family_policies must contain all five families exactly once")
        for item in self.family_policies:
            if type(item) is not FamilyProjectionPolicy:
                raise ContractValidationError("family_policies contains an invalid value")
            item.__post_init__()
        families = tuple(item.family for item in self.family_policies)
        expected = (101, 102, 103, 104, 105)
        if families != expected:
            raise ContractValidationError("family_policies must be sorted and cover all five families")
        if type(self.operational_bands) is not tuple or not 1 <= len(self.operational_bands) <= MAX_DIMENSIONS:
            raise ContractValidationError("operational_bands has an invalid immutable item count")
        previous_maximum = -1
        codes: list[int] = []
        for item in self.operational_bands:
            if type(item) is not OperationalBand:
                raise ContractValidationError("operational_bands contains an invalid value")
            item.__post_init__()
            if item.minimum_count != previous_maximum + 1:
                raise ContractValidationError("operational_bands must be contiguous from zero")
            previous_maximum = item.maximum_count
            codes.append(item.code)
        if previous_maximum != MAX_COUNT or codes != sorted(set(codes)):
            raise ContractValidationError("operational_bands must cover the count bound with sorted unique codes")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_provenance_address": self.policy_provenance_address,
            "family_policies": [item.canonical_dict() for item in self.family_policies],
            "operational_bands": [item.canonical_dict() for item in self.operational_bands],
            "minimum_cohort_threshold": self.minimum_cohort_threshold,
        }


@dataclass(frozen=True, slots=True)
class OperatorProofReferences(_CanonicalContract):
    contract_type: ClassVar[str] = "OperatorProofReferences"
    binding_address: str
    permission_policy_address: str
    step_up_proof_address: str

    def __post_init__(self) -> None:
        _content_address(self.binding_address, "binding_address")
        _content_address(self.permission_policy_address, "permission_policy_address")
        _content_address(self.step_up_proof_address, "step_up_proof_address")

    def _payload(self) -> dict[str, object]:
        return {
            "binding_address": self.binding_address,
            "permission_policy_address": self.permission_policy_address,
            "step_up_proof_address": self.step_up_proof_address,
        }


@dataclass(frozen=True, slots=True)
class SafeAggregateInput(_CanonicalContract):
    contract_type: ClassVar[str] = "SafeAggregateInput"
    policy_content_id: str
    operator_proofs_content_id: str
    family: int
    dimensions: tuple[int, ...]
    count: int
    source_receipt_address: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        _content_address(self.policy_content_id, "policy_content_id")
        _content_address(self.operator_proofs_content_id, "operator_proofs_content_id")
        family = _family(self.family)
        dimensions = _dimension_tuple(self.dimensions, "dimensions")
        if any(item not in _family_dimension_vocabulary(family) for item in dimensions):
            raise ContractValidationError("dimension is not valid for the aggregate input family")
        _strict_int(self.count, "count", 1, MAX_COUNT)
        _content_address(self.source_receipt_address, "source_receipt_address")
        _utc(self.evaluated_at, "evaluated_at")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_content_id": self.policy_content_id,
            "operator_proofs_content_id": self.operator_proofs_content_id,
            "family": self.family,
            "dimensions": list(self.dimensions),
            "count": self.count,
            "source_receipt_address": self.source_receipt_address,
            "evaluated_at": _datetime_text(self.evaluated_at),
        }


@dataclass(frozen=True, slots=True)
class AdminAggregateProjectionCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "AdminAggregateProjectionCandidate"
    policy_content_id: str
    operator_proofs_content_id: str
    aggregate_input_content_id: str
    family: int
    dimensions: tuple[int, ...]
    count: int
    operational_band_code: int
    source_receipt_address: str
    evaluated_at: datetime
    publishable: bool
    access_activated: bool

    def __post_init__(self) -> None:
        _content_address(self.policy_content_id, "policy_content_id")
        _content_address(self.operator_proofs_content_id, "operator_proofs_content_id")
        _content_address(self.aggregate_input_content_id, "aggregate_input_content_id")
        family = _family(self.family)
        dimensions = _dimension_tuple(self.dimensions, "dimensions")
        if any(item not in _family_dimension_vocabulary(family) for item in dimensions):
            raise ContractValidationError("dimension is not valid for the projection family")
        _strict_int(self.count, "count", 1, MAX_COUNT)
        _band_code(self.operational_band_code)
        _content_address(self.source_receipt_address, "source_receipt_address")
        _utc(self.evaluated_at, "evaluated_at")
        _strict_false(self.publishable, "publishable")
        _strict_false(self.access_activated, "access_activated")

    def _payload(self) -> dict[str, object]:
        return {
            "policy_content_id": self.policy_content_id,
            "operator_proofs_content_id": self.operator_proofs_content_id,
            "aggregate_input_content_id": self.aggregate_input_content_id,
            "family": self.family,
            "dimensions": list(self.dimensions),
            "count": self.count,
            "operational_band_code": self.operational_band_code,
            "source_receipt_address": self.source_receipt_address,
            "evaluated_at": _datetime_text(self.evaluated_at),
            "publishable": self.publishable,
            "access_activated": self.access_activated,
        }


def _validated_policy(policy: object, expected_content_id: str) -> ProjectionPolicy:
    if type(policy) is not ProjectionPolicy:
        raise ContractValidationError("policy must be a ProjectionPolicy")
    policy.__post_init__()
    _content_address(expected_content_id, "expected_policy_content_id")
    if _validated_content_id(policy) != expected_content_id:
        raise ContractValidationError("policy does not match the exact expected content identity")
    return policy


def _validated_proofs(
    proofs: object,
    *,
    expected_binding_address: str,
    expected_permission_policy_address: str,
    expected_step_up_proof_address: str,
) -> OperatorProofReferences:
    if type(proofs) is not OperatorProofReferences:
        raise ContractValidationError("operator_proofs must be OperatorProofReferences")
    proofs.__post_init__()
    expected = (
        _content_address(expected_binding_address, "expected_binding_address"),
        _content_address(expected_permission_policy_address, "expected_permission_policy_address"),
        _content_address(expected_step_up_proof_address, "expected_step_up_proof_address"),
    )
    actual = (proofs.binding_address, proofs.permission_policy_address, proofs.step_up_proof_address)
    if actual != expected:
        raise ContractValidationError("operator proof references do not match exact expected addresses")
    return proofs


def _family_policy(policy: ProjectionPolicy, family: int) -> FamilyProjectionPolicy:
    for item in policy.family_policies:
        if item.family == family:
            return item
    raise ContractValidationError("family is absent from the projection policy")


def _band_for_count(policy: ProjectionPolicy, count: int) -> OperationalBand:
    for band in policy.operational_bands:
        if band.minimum_count <= count <= band.maximum_count:
            return band
    raise ContractValidationError("count is absent from operational bands")


def create_projection_policy(
    *, policy_provenance_address: str, family_policies: tuple[FamilyProjectionPolicy, ...],
    operational_bands: tuple[OperationalBand, ...], minimum_cohort_threshold: int,
) -> ProjectionPolicy:
    return ProjectionPolicy(policy_provenance_address, family_policies, operational_bands, minimum_cohort_threshold)


def create_operator_proof_references(
    *, binding_address: str, permission_policy_address: str, step_up_proof_address: str,
) -> OperatorProofReferences:
    return OperatorProofReferences(binding_address, permission_policy_address, step_up_proof_address)


def create_safe_aggregate_input(
    *, policy: ProjectionPolicy, operator_proofs: OperatorProofReferences,
    expected_policy_content_id: str, expected_binding_address: str,
    expected_permission_policy_address: str, expected_step_up_proof_address: str,
    expected_minimum_cohort_threshold: int,
    family: int, dimensions: tuple[int, ...], count: int,
    source_receipt_address: str, expected_source_receipt_address: str,
    evaluated_at: datetime, expected_evaluated_at: datetime,
) -> SafeAggregateInput:
    policy = _validated_policy(policy, expected_policy_content_id)
    if policy.minimum_cohort_threshold != _strict_int(
        expected_minimum_cohort_threshold, "expected_minimum_cohort_threshold", 1, MAX_COUNT
    ):
        raise ContractValidationError("minimum cohort threshold does not match exact injected policy")
    proofs = _validated_proofs(
        operator_proofs,
        expected_binding_address=expected_binding_address,
        expected_permission_policy_address=expected_permission_policy_address,
        expected_step_up_proof_address=expected_step_up_proof_address,
    )
    family = _family(family)
    dimensions = _dimension_tuple(dimensions, "dimensions")
    allowed = _family_policy(policy, family).allowed_dimension_codes
    if any(item not in allowed for item in dimensions):
        raise ContractValidationError("dimensions are outside the injected family policy")
    source_receipt_address = _content_address(source_receipt_address, "source_receipt_address")
    if source_receipt_address != _content_address(expected_source_receipt_address, "expected_source_receipt_address"):
        raise ContractValidationError("source receipt does not match the exact expected address")
    evaluated_at = _utc(evaluated_at, "evaluated_at")
    if evaluated_at != _utc(expected_evaluated_at, "expected_evaluated_at"):
        raise ContractValidationError("evaluated time does not match the exact injected time")
    policy_content_id = expected_policy_content_id
    proofs_content_id = _validated_content_id(proofs)
    return SafeAggregateInput(policy_content_id, proofs_content_id, family, dimensions, count, source_receipt_address, evaluated_at)


def _validated_input(
    aggregate_input: object, *, policy: ProjectionPolicy, proofs: OperatorProofReferences,
    expected_source_receipt_address: str, expected_family: int,
    expected_evaluated_at: datetime, policy_content_id: str | None = None,
    proofs_content_id: str | None = None,
) -> SafeAggregateInput:
    if type(aggregate_input) is not SafeAggregateInput:
        raise ContractValidationError("aggregate_input must be a SafeAggregateInput")
    aggregate_input.__post_init__()
    policy_content_id = _validated_content_id(policy) if policy_content_id is None else policy_content_id
    proofs_content_id = _validated_content_id(proofs) if proofs_content_id is None else proofs_content_id
    if aggregate_input.policy_content_id != policy_content_id:
        raise ContractValidationError("aggregate input uses a different policy")
    if aggregate_input.operator_proofs_content_id != proofs_content_id:
        raise ContractValidationError("aggregate input uses different operator proof references")
    if aggregate_input.source_receipt_address != _content_address(expected_source_receipt_address, "expected_source_receipt_address"):
        raise ContractValidationError("aggregate input uses a different source receipt")
    if aggregate_input.family != _family(expected_family, "expected_family"):
        raise ContractValidationError("aggregate input uses a different family")
    if aggregate_input.evaluated_at != _utc(expected_evaluated_at, "expected_evaluated_at"):
        raise ContractValidationError("aggregate input uses a different evaluated time")
    allowed = _family_policy(policy, aggregate_input.family).allowed_dimension_codes
    if any(item not in allowed for item in aggregate_input.dimensions):
        raise ContractValidationError("aggregate input dimensions are outside policy")
    return aggregate_input


def derive_admin_aggregate_projection(
    *, policy: ProjectionPolicy, operator_proofs: OperatorProofReferences,
    aggregate_input: SafeAggregateInput, expected_policy_content_id: str,
    expected_binding_address: str, expected_permission_policy_address: str,
    expected_step_up_proof_address: str, expected_source_receipt_address: str,
    expected_family: int, expected_evaluated_at: datetime,
    expected_minimum_cohort_threshold: int, expected_aggregate_input_content_id: str,
) -> AdminAggregateProjectionCandidate:
    policy = _validated_policy(policy, expected_policy_content_id)
    proofs = _validated_proofs(
        operator_proofs,
        expected_binding_address=expected_binding_address,
        expected_permission_policy_address=expected_permission_policy_address,
        expected_step_up_proof_address=expected_step_up_proof_address,
    )
    if policy.minimum_cohort_threshold != _strict_int(
        expected_minimum_cohort_threshold, "expected_minimum_cohort_threshold", 1, MAX_COUNT
    ):
        raise ContractValidationError("minimum cohort threshold does not match exact injected policy")
    policy_content_id = expected_policy_content_id
    proofs_content_id = _validated_content_id(proofs)
    aggregate_input = _validated_input(
        aggregate_input, policy=policy, proofs=proofs,
        expected_source_receipt_address=expected_source_receipt_address,
        expected_family=expected_family, expected_evaluated_at=expected_evaluated_at,
        policy_content_id=policy_content_id, proofs_content_id=proofs_content_id,
    )
    if aggregate_input.count < policy.minimum_cohort_threshold:
        raise ContractValidationError("aggregate count is below the injected minimum cohort threshold")
    band = _band_for_count(policy, aggregate_input.count)
    aggregate_input_content_id = _validated_content_id(aggregate_input)
    if aggregate_input_content_id != _content_address(
        expected_aggregate_input_content_id, "expected_aggregate_input_content_id"
    ):
        raise ContractValidationError("aggregate input does not match its exact expected identity")
    return AdminAggregateProjectionCandidate(
        policy_content_id, proofs_content_id, aggregate_input_content_id,
        aggregate_input.family, aggregate_input.dimensions, aggregate_input.count,
        band.code, aggregate_input.source_receipt_address, aggregate_input.evaluated_at,
        False, False,
    )


def validate_admin_aggregate_projection(
    projection: object, *, policy: ProjectionPolicy, operator_proofs: OperatorProofReferences,
    aggregate_input: SafeAggregateInput, expected_policy_content_id: str,
    expected_binding_address: str, expected_permission_policy_address: str,
    expected_step_up_proof_address: str, expected_source_receipt_address: str,
    expected_family: int, expected_evaluated_at: datetime,
    expected_minimum_cohort_threshold: int, expected_aggregate_input_content_id: str,
) -> AdminAggregateProjectionCandidate:
    if type(projection) is not AdminAggregateProjectionCandidate:
        raise ContractValidationError("projection must be an AdminAggregateProjectionCandidate")
    projection.__post_init__()
    expected = derive_admin_aggregate_projection(
        policy=policy, operator_proofs=operator_proofs, aggregate_input=aggregate_input,
        expected_policy_content_id=expected_policy_content_id,
        expected_binding_address=expected_binding_address,
        expected_permission_policy_address=expected_permission_policy_address,
        expected_step_up_proof_address=expected_step_up_proof_address,
        expected_source_receipt_address=expected_source_receipt_address,
        expected_family=expected_family, expected_evaluated_at=expected_evaluated_at,
        expected_minimum_cohort_threshold=expected_minimum_cohort_threshold,
        expected_aggregate_input_content_id=expected_aggregate_input_content_id,
    )
    if projection != expected or projection.content_id != expected.content_id:
        raise ContractValidationError("projection is not the exact derivation of current inputs")
    return projection


def _decode_family_policy(raw: object) -> FamilyProjectionPolicy:
    value = _versioned(raw, "FamilyProjectionPolicy", {"family", "allowed_dimension_codes"})
    dimensions = value["allowed_dimension_codes"]
    if type(dimensions) is not list:
        raise ContractValidationError("allowed_dimension_codes must be an array")
    return FamilyProjectionPolicy(
        _closed_family(value["family"], "family"),
        tuple(_closed_dimension(item, "allowed_dimension_codes item") for item in dimensions),
    )


def _decode_band(raw: object) -> OperationalBand:
    value = _versioned(raw, "OperationalBand", {"code", "minimum_count", "maximum_count"})
    return OperationalBand(_band_code(value["code"], "code"), value["minimum_count"], value["maximum_count"])


def canonical_deserialize(
    encoded: object, *, policy: ProjectionPolicy | None = None,
    operator_proofs: OperatorProofReferences | None = None,
    aggregate_input: SafeAggregateInput | None = None,
    expected_policy_content_id: str | None = None,
    expected_binding_address: str | None = None,
    expected_permission_policy_address: str | None = None,
    expected_step_up_proof_address: str | None = None,
    expected_source_receipt_address: str | None = None,
    expected_family: int | None = None,
    expected_evaluated_at: datetime | None = None,
    expected_minimum_cohort_threshold: int | None = None,
    expected_aggregate_input_content_id: str | None = None,
) -> _CanonicalContract:
    if type(encoded) is not str or not 1 <= len(encoded.encode("utf-8")) <= MAX_CANONICAL_BYTES:
        raise ContractValidationError("encoded contract must be bounded JSON text")
    try:
        raw = json.loads(encoded, object_pairs_hook=_reject_duplicate_pairs)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ContractValidationError("encoded contract is invalid JSON") from exc
    if _json_depth(raw) > MAX_JSON_DEPTH or type(raw) is not dict:
        raise ContractValidationError("encoded contract exceeds depth or shape bounds")
    if _canonical_json(raw) != encoded:
        raise ContractValidationError("encoded contract is not exact canonical JSON")
    contract_type = raw.get("contract_type")
    if contract_type == "FamilyProjectionPolicy":
        return _decode_family_policy(raw)
    if contract_type == "OperationalBand":
        return _decode_band(raw)
    if contract_type == "ProjectionPolicy":
        value = _versioned(raw, contract_type, {"policy_provenance_address", "family_policies", "operational_bands", "minimum_cohort_threshold"})
        if type(value["family_policies"]) is not list or type(value["operational_bands"]) is not list:
            raise ContractValidationError("policy collections must be arrays")
        result = ProjectionPolicy(
            value["policy_provenance_address"],
            tuple(_decode_family_policy(item) for item in value["family_policies"]),
            tuple(_decode_band(item) for item in value["operational_bands"]),
            value["minimum_cohort_threshold"],
        )
        if expected_policy_content_id is None:
            raise ContractValidationError("policy decode requires its exact expected content identity")
        return _validated_policy(result, expected_policy_content_id)
    if contract_type == "OperatorProofReferences":
        value = _versioned(raw, contract_type, {"binding_address", "permission_policy_address", "step_up_proof_address"})
        result = OperatorProofReferences(value["binding_address"], value["permission_policy_address"], value["step_up_proof_address"])
        if None in (expected_binding_address, expected_permission_policy_address, expected_step_up_proof_address):
            raise ContractValidationError("proof decode requires all exact expected addresses")
        return _validated_proofs(
            result, expected_binding_address=expected_binding_address,
            expected_permission_policy_address=expected_permission_policy_address,
            expected_step_up_proof_address=expected_step_up_proof_address,
        )
    context = (
        policy, operator_proofs, expected_policy_content_id, expected_binding_address,
        expected_permission_policy_address, expected_step_up_proof_address,
        expected_source_receipt_address, expected_family, expected_evaluated_at,
        expected_minimum_cohort_threshold, expected_aggregate_input_content_id,
    )
    if any(item is None for item in context):
        raise ContractValidationError("input/projection decode requires complete exact context")
    if contract_type == "SafeAggregateInput":
        value = _versioned(raw, contract_type, {"policy_content_id", "operator_proofs_content_id", "family", "dimensions", "count", "source_receipt_address", "evaluated_at"})
        if type(value["dimensions"]) is not list:
            raise ContractValidationError("dimensions must be an array")
        result = SafeAggregateInput(
            value["policy_content_id"], value["operator_proofs_content_id"],
            _closed_family(value["family"], "family"),
            tuple(_closed_dimension(item, "dimensions item") for item in value["dimensions"]),
            value["count"], value["source_receipt_address"], _parse_datetime(value["evaluated_at"], "evaluated_at"),
        )
        _validated_policy(policy, expected_policy_content_id)
        if policy.minimum_cohort_threshold != _strict_int(
            expected_minimum_cohort_threshold, "expected_minimum_cohort_threshold", 1, MAX_COUNT
        ):
            raise ContractValidationError("minimum cohort threshold does not match exact injected policy")
        proofs = _validated_proofs(
            operator_proofs, expected_binding_address=expected_binding_address,
            expected_permission_policy_address=expected_permission_policy_address,
            expected_step_up_proof_address=expected_step_up_proof_address,
        )
        result = _validated_input(
            result, policy=policy, proofs=proofs,
            expected_source_receipt_address=expected_source_receipt_address,
            expected_family=expected_family, expected_evaluated_at=expected_evaluated_at,
        )
        if _validated_content_id(result) != _content_address(
            expected_aggregate_input_content_id, "expected_aggregate_input_content_id"
        ):
            raise ContractValidationError("aggregate input does not match its exact expected identity")
        return result
    if contract_type == "AdminAggregateProjectionCandidate":
        value = _versioned(raw, contract_type, {"policy_content_id", "operator_proofs_content_id", "aggregate_input_content_id", "family", "dimensions", "count", "operational_band_code", "source_receipt_address", "evaluated_at", "publishable", "access_activated"})
        if type(value["dimensions"]) is not list:
            raise ContractValidationError("dimensions must be an array")
        result = AdminAggregateProjectionCandidate(
            value["policy_content_id"], value["operator_proofs_content_id"],
            value["aggregate_input_content_id"], _closed_family(value["family"], "family"),
            tuple(_closed_dimension(item, "dimensions item") for item in value["dimensions"]),
            value["count"], _band_code(value["operational_band_code"]),
            value["source_receipt_address"], _parse_datetime(value["evaluated_at"], "evaluated_at"),
            value["publishable"], value["access_activated"],
        )
        return validate_admin_aggregate_projection(
            result, policy=policy, operator_proofs=operator_proofs,
            aggregate_input=aggregate_input, expected_policy_content_id=expected_policy_content_id,
            expected_binding_address=expected_binding_address,
            expected_permission_policy_address=expected_permission_policy_address,
            expected_step_up_proof_address=expected_step_up_proof_address,
            expected_source_receipt_address=expected_source_receipt_address,
            expected_family=expected_family, expected_evaluated_at=expected_evaluated_at,
            expected_minimum_cohort_threshold=expected_minimum_cohort_threshold,
            expected_aggregate_input_content_id=expected_aggregate_input_content_id,
        )
    raise ContractValidationError("unknown contract_type")


__all__ = [
    "CONTRACT_VERSION", "MAX_CANONICAL_BYTES", "MAX_COUNT", "MAX_JSON_DEPTH",
    "AdminAggregateProjectionCandidate", "ContractValidationError",
    "FamilyProjectionPolicy", "OperationalBand", "OperatorProofReferences",
    "ProjectionPolicy", "SafeAggregateInput",
    "canonical_deserialize", "create_operator_proof_references",
    "create_projection_policy", "create_safe_aggregate_input",
    "derive_admin_aggregate_projection", "validate_admin_aggregate_projection",
]
