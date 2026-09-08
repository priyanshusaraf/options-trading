"""Closed, pure contracts for unpublished server-authored product facts.

This module only validates immutable values. It has no clock lookup, storage,
transport, configuration lookup, collection side effect, or publication path.
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
MAX_COLLECTION_ITEMS = 32
MAX_CANONICAL_BYTES = 16_384
MAX_JSON_DEPTH = 12
MIN_DIMENSION_INTEGER = -1_000_000_000
MAX_DIMENSION_INTEGER = 1_000_000_000

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]*\Z")


class ContractValidationError(ValueError):
    """A closed product-analytics contract refused invalid input."""


class DimensionKind(str, Enum):
    FINITE_ENUM = "FINITE_ENUM"
    BOOLEAN = "BOOLEAN"
    BOUNDED_INTEGER = "BOUNDED_INTEGER"


def _identifier(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be a machine identifier")
    if not 1 <= len(value) <= MAX_IDENTIFIER_LENGTH or not _IDENTIFIER.fullmatch(value):
        raise ContractValidationError(f"{field_name} is not a closed bounded machine identifier")
    return value


def _identifier_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if type(value) is not tuple or not 1 <= len(value) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError(f"{field_name} has an invalid immutable item count")
    result = tuple(_identifier(item, f"{field_name} item") for item in value)
    if result != tuple(sorted(set(result))):
        raise ContractValidationError(f"{field_name} must be sorted and unique")
    return result


def _strict_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise ContractValidationError(f"{field_name} must be a boolean")
    return value


def _strict_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractValidationError(f"{field_name} is outside supported integer bounds")
    return value


def _uuid(value: object, field_name: str) -> UUID:
    if type(value) is not UUID or value.int == 0 or value.variant != RFC_4122:
        raise ContractValidationError(f"{field_name} must be a non-zero RFC4122 UUID")
    return value


def _parse_uuid(value: object, field_name: str) -> UUID:
    if type(value) is not str:
        raise ContractValidationError(f"{field_name} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ContractValidationError(f"{field_name} is invalid") from exc
    if str(parsed) != value:
        raise ContractValidationError(f"{field_name} is not canonical UUID text")
    return _uuid(parsed, field_name)


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


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError("duplicate object key")
        result[key] = value
    return result


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
            stack.extend((child, depth) for child in current.values())
        elif type(current) is list:
            depth = parent_depth + 1
            maximum = max(maximum, depth)
            if maximum > MAX_JSON_DEPTH:
                return maximum
            stack.extend((child, depth) for child in current)
    return maximum


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
        return _cached_content_id(self)


@lru_cache(maxsize=256)
def _cached_content_id(value: _CanonicalContract) -> str:
    """Cache canonical content identity only; validation is never cached."""
    encoded = value.canonical_json()
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EnumDimensionDomain(_CanonicalContract):
    contract_type: ClassVar[str] = "EnumDimensionDomain"
    dimension_id: str
    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.dimension_id, "dimension_id")
        _identifier_tuple(self.allowed_values, "allowed_values")

    @property
    def kind(self) -> DimensionKind:
        return DimensionKind.FINITE_ENUM

    def _payload(self) -> dict[str, object]:
        return {"dimension_id": self.dimension_id, "allowed_values": list(self.allowed_values)}


@dataclass(frozen=True, slots=True)
class BooleanDimensionDomain(_CanonicalContract):
    contract_type: ClassVar[str] = "BooleanDimensionDomain"
    dimension_id: str

    def __post_init__(self) -> None:
        _identifier(self.dimension_id, "dimension_id")

    @property
    def kind(self) -> DimensionKind:
        return DimensionKind.BOOLEAN

    def _payload(self) -> dict[str, object]:
        return {"dimension_id": self.dimension_id}


@dataclass(frozen=True, slots=True)
class IntegerDimensionDomain(_CanonicalContract):
    contract_type: ClassVar[str] = "IntegerDimensionDomain"
    dimension_id: str
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        _identifier(self.dimension_id, "dimension_id")
        minimum = _strict_int(
            self.minimum, "minimum", MIN_DIMENSION_INTEGER, MAX_DIMENSION_INTEGER
        )
        maximum = _strict_int(
            self.maximum, "maximum", MIN_DIMENSION_INTEGER, MAX_DIMENSION_INTEGER
        )
        if minimum > maximum:
            raise ContractValidationError("integer dimension bounds are reversed")

    @property
    def kind(self) -> DimensionKind:
        return DimensionKind.BOUNDED_INTEGER

    def _payload(self) -> dict[str, object]:
        return {"dimension_id": self.dimension_id, "minimum": self.minimum, "maximum": self.maximum}


DimensionDomain = EnumDimensionDomain | BooleanDimensionDomain | IntegerDimensionDomain


@dataclass(frozen=True, slots=True)
class EnumDimension(_CanonicalContract):
    contract_type: ClassVar[str] = "EnumDimension"
    dimension_id: str
    value: str

    def __post_init__(self) -> None:
        _identifier(self.dimension_id, "dimension_id")
        _identifier(self.value, "value")

    @property
    def kind(self) -> DimensionKind:
        return DimensionKind.FINITE_ENUM

    def _payload(self) -> dict[str, object]:
        return {"dimension_id": self.dimension_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class BooleanDimension(_CanonicalContract):
    contract_type: ClassVar[str] = "BooleanDimension"
    dimension_id: str
    value: bool

    def __post_init__(self) -> None:
        _identifier(self.dimension_id, "dimension_id")
        _strict_bool(self.value, "value")

    @property
    def kind(self) -> DimensionKind:
        return DimensionKind.BOOLEAN

    def _payload(self) -> dict[str, object]:
        return {"dimension_id": self.dimension_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class IntegerDimension(_CanonicalContract):
    contract_type: ClassVar[str] = "IntegerDimension"
    dimension_id: str
    value: int

    def __post_init__(self) -> None:
        _identifier(self.dimension_id, "dimension_id")
        _strict_int(self.value, "value", MIN_DIMENSION_INTEGER, MAX_DIMENSION_INTEGER)

    @property
    def kind(self) -> DimensionKind:
        return DimensionKind.BOUNDED_INTEGER

    def _payload(self) -> dict[str, object]:
        return {"dimension_id": self.dimension_id, "value": self.value}


Dimension = EnumDimension | BooleanDimension | IntegerDimension


def _domain_tuple(value: object) -> tuple[DimensionDomain, ...]:
    if type(value) is not tuple or not 1 <= len(value) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError("dimension_domains has an invalid immutable item count")
    if any(type(item) not in (EnumDimensionDomain, BooleanDimensionDomain, IntegerDimensionDomain) for item in value):
        raise ContractValidationError("dimension_domains contains an open type")
    keys = tuple(item.dimension_id for item in value)
    if keys != tuple(sorted(set(keys))):
        raise ContractValidationError("dimension_domains must be sorted by unique dimension_id")
    return value


def _dimension_tuple(value: object) -> tuple[Dimension, ...]:
    if type(value) is not tuple or not 1 <= len(value) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError("dimensions has an invalid immutable item count")
    if any(type(item) not in (EnumDimension, BooleanDimension, IntegerDimension) for item in value):
        raise ContractValidationError("dimensions contains an open type")
    keys = tuple(item.dimension_id for item in value)
    if keys != tuple(sorted(set(keys))):
        raise ContractValidationError("dimensions must be sorted by unique dimension_id")
    return value


@dataclass(frozen=True, slots=True)
class ProductAnalyticsCatalogue(_CanonicalContract):
    contract_type: ClassVar[str] = "ProductAnalyticsCatalogue"
    catalogue_id: str
    provenance_id: str
    event_type_ids: tuple[str, ...]
    purpose_ids: tuple[str, ...]
    product_area_ids: tuple[str, ...]
    route_template_ids: tuple[str, ...]
    build_ids: tuple[str, ...]
    outcome_ids: tuple[str, ...]
    dimension_domains: tuple[DimensionDomain, ...]

    def __post_init__(self) -> None:
        _identifier(self.catalogue_id, "catalogue_id")
        _identifier(self.provenance_id, "provenance_id")
        for field_name in (
            "event_type_ids", "purpose_ids", "product_area_ids", "route_template_ids",
            "build_ids", "outcome_ids",
        ):
            _identifier_tuple(getattr(self, field_name), field_name)
        _domain_tuple(self.dimension_domains)

    def _payload(self) -> dict[str, object]:
        return {
            "catalogue_id": self.catalogue_id,
            "provenance_id": self.provenance_id,
            "event_type_ids": list(self.event_type_ids),
            "purpose_ids": list(self.purpose_ids),
            "product_area_ids": list(self.product_area_ids),
            "route_template_ids": list(self.route_template_ids),
            "build_ids": list(self.build_ids),
            "outcome_ids": list(self.outcome_ids),
            "dimension_domains": [item.canonical_dict() for item in self.dimension_domains],
        }


@dataclass(frozen=True, slots=True)
class AuthoritativeSourceContext(_CanonicalContract):
    contract_type: ClassVar[str] = "AuthoritativeSourceContext"
    source_context_id: str
    provenance_id: str

    def __post_init__(self) -> None:
        _identifier(self.source_context_id, "source_context_id")
        _identifier(self.provenance_id, "provenance_id")

    def _payload(self) -> dict[str, object]:
        return {"source_context_id": self.source_context_id, "provenance_id": self.provenance_id}


@dataclass(frozen=True, slots=True)
class CollectionAuthorityProof(_CanonicalContract):
    contract_type: ClassVar[str] = "CollectionAuthorityProof"
    authority_id: str
    policy_provenance_id: str
    catalogue_content_id: str
    catalogue_provenance_id: str
    source_context_content_id: str
    source_context_provenance_id: str
    collection_allowed: bool

    def __post_init__(self) -> None:
        _identifier(self.authority_id, "authority_id")
        _identifier(self.policy_provenance_id, "policy_provenance_id")
        _content_id(self.catalogue_content_id, "catalogue_content_id")
        _identifier(self.catalogue_provenance_id, "catalogue_provenance_id")
        _content_id(self.source_context_content_id, "source_context_content_id")
        _identifier(self.source_context_provenance_id, "source_context_provenance_id")
        _strict_bool(self.collection_allowed, "collection_allowed")

    def _payload(self) -> dict[str, object]:
        return {
            "authority_id": self.authority_id,
            "policy_provenance_id": self.policy_provenance_id,
            "catalogue_content_id": self.catalogue_content_id,
            "catalogue_provenance_id": self.catalogue_provenance_id,
            "source_context_content_id": self.source_context_content_id,
            "source_context_provenance_id": self.source_context_provenance_id,
            "collection_allowed": self.collection_allowed,
        }


def _content_id(value: object, field_name: str) -> str:
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ContractValidationError(f"{field_name} must be a canonical sha256 content ID")
    return value


@dataclass(frozen=True, slots=True)
class AuthoritativeSourceFactAddress(_CanonicalContract):
    contract_type: ClassVar[str] = "AuthoritativeSourceFactAddress"
    source_context_content_id: str
    source_fact_id: UUID
    source_fact_version: int

    def __post_init__(self) -> None:
        _content_id(self.source_context_content_id, "source_context_content_id")
        _uuid(self.source_fact_id, "source_fact_id")
        _strict_int(self.source_fact_version, "source_fact_version", 1, 2_147_483_647)

    def _payload(self) -> dict[str, object]:
        return {
            "source_context_content_id": self.source_context_content_id,
            "source_fact_id": str(self.source_fact_id),
            "source_fact_version": self.source_fact_version,
        }


@dataclass(frozen=True, slots=True)
class EventCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "EventCandidate"
    catalogue_content_id: str
    authority_content_id: str
    source_context_content_id: str
    subject_epoch_id: UUID
    tenant_epoch_id: UUID
    session_epoch_id: UUID
    source_fact_address: AuthoritativeSourceFactAddress
    event_type_id: str
    purpose_id: str
    product_area_id: str
    route_template_id: str
    build_id: str
    outcome_id: str
    dimensions: tuple[Dimension, ...]
    received_at: datetime

    def __post_init__(self) -> None:
        _content_id(self.catalogue_content_id, "catalogue_content_id")
        _content_id(self.authority_content_id, "authority_content_id")
        _content_id(self.source_context_content_id, "source_context_content_id")
        _uuid(self.subject_epoch_id, "subject_epoch_id")
        _uuid(self.tenant_epoch_id, "tenant_epoch_id")
        _uuid(self.session_epoch_id, "session_epoch_id")
        if type(self.source_fact_address) is not AuthoritativeSourceFactAddress:
            raise ContractValidationError("source_fact_address must be a closed source address")
        if self.source_fact_address.source_context_content_id != self.source_context_content_id:
            raise ContractValidationError("source address does not match source context")
        for field_name in (
            "event_type_id", "purpose_id", "product_area_id", "route_template_id",
            "build_id", "outcome_id",
        ):
            _identifier(getattr(self, field_name), field_name)
        _dimension_tuple(self.dimensions)
        _utc(self.received_at, "received_at")

    def _payload(self) -> dict[str, object]:
        return {
            "catalogue_content_id": self.catalogue_content_id,
            "authority_content_id": self.authority_content_id,
            "source_context_content_id": self.source_context_content_id,
            "subject_epoch_id": str(self.subject_epoch_id),
            "tenant_epoch_id": str(self.tenant_epoch_id),
            "session_epoch_id": str(self.session_epoch_id),
            "source_fact_address": self.source_fact_address.canonical_dict(),
            "event_type_id": self.event_type_id,
            "purpose_id": self.purpose_id,
            "product_area_id": self.product_area_id,
            "route_template_id": self.route_template_id,
            "build_id": self.build_id,
            "outcome_id": self.outcome_id,
            "dimensions": [item.canonical_dict() for item in self.dimensions],
            "received_at": _datetime_text(self.received_at),
        }


@dataclass(frozen=True, slots=True)
class AggregateDimensionsCandidate(_CanonicalContract):
    contract_type: ClassVar[str] = "AggregateDimensionsCandidate"
    catalogue_content_id: str
    authority_content_id: str
    event_type_id: str
    purpose_id: str
    product_area_id: str
    route_template_id: str
    build_id: str
    outcome_id: str
    dimensions: tuple[Dimension, ...]
    publishable: bool

    def __post_init__(self) -> None:
        _content_id(self.catalogue_content_id, "catalogue_content_id")
        _content_id(self.authority_content_id, "authority_content_id")
        for field_name in (
            "event_type_id", "purpose_id", "product_area_id", "route_template_id",
            "build_id", "outcome_id",
        ):
            _identifier(getattr(self, field_name), field_name)
        _dimension_tuple(self.dimensions)
        if _strict_bool(self.publishable, "publishable") is not False:
            raise ContractValidationError("aggregate dimensions must remain publishable=false")

    def _payload(self) -> dict[str, object]:
        return {
            "catalogue_content_id": self.catalogue_content_id,
            "authority_content_id": self.authority_content_id,
            "event_type_id": self.event_type_id,
            "purpose_id": self.purpose_id,
            "product_area_id": self.product_area_id,
            "route_template_id": self.route_template_id,
            "build_id": self.build_id,
            "outcome_id": self.outcome_id,
            "dimensions": [item.canonical_dict() for item in self.dimensions],
            "publishable": self.publishable,
        }


def _validate_domain_current(value: object) -> None:
    if type(value) is EnumDimensionDomain:
        _identifier(value.dimension_id, "dimension_id")
        _identifier_tuple(value.allowed_values, "allowed_values")
    elif type(value) is BooleanDimensionDomain:
        _identifier(value.dimension_id, "dimension_id")
    elif type(value) is IntegerDimensionDomain:
        _identifier(value.dimension_id, "dimension_id")
        minimum = _strict_int(
            value.minimum, "minimum", MIN_DIMENSION_INTEGER, MAX_DIMENSION_INTEGER
        )
        maximum = _strict_int(
            value.maximum, "maximum", MIN_DIMENSION_INTEGER, MAX_DIMENSION_INTEGER
        )
        if minimum > maximum:
            raise ContractValidationError("integer dimension bounds are reversed")
    else:
        raise ContractValidationError("dimension domain has an open type")


def _validate_dimension_current(value: object) -> None:
    if type(value) is EnumDimension:
        _identifier(value.dimension_id, "dimension_id")
        _identifier(value.value, "value")
    elif type(value) is BooleanDimension:
        _identifier(value.dimension_id, "dimension_id")
        _strict_bool(value.value, "value")
    elif type(value) is IntegerDimension:
        _identifier(value.dimension_id, "dimension_id")
        _strict_int(value.value, "value", MIN_DIMENSION_INTEGER, MAX_DIMENSION_INTEGER)
    else:
        raise ContractValidationError("dimension has an open type")


def _validate_catalogue_current(
    catalogue: object,
) -> tuple[ProductAnalyticsCatalogue, dict[str, DimensionDomain]]:
    if type(catalogue) is not ProductAnalyticsCatalogue:
        raise ContractValidationError("catalogue must be explicitly injected")
    _identifier(catalogue.catalogue_id, "catalogue_id")
    _identifier(catalogue.provenance_id, "provenance_id")
    for field_name in (
        "event_type_ids",
        "purpose_ids",
        "product_area_ids",
        "route_template_ids",
        "build_ids",
        "outcome_ids",
    ):
        _identifier_tuple(getattr(catalogue, field_name), field_name)
    if (
        type(catalogue.dimension_domains) is not tuple
        or not 1 <= len(catalogue.dimension_domains) <= MAX_COLLECTION_ITEMS
    ):
        raise ContractValidationError("dimension_domains has an invalid immutable item count")
    domain_ids: list[str] = []
    for domain in catalogue.dimension_domains:
        _validate_domain_current(domain)
        domain_ids.append(domain.dimension_id)
    if tuple(domain_ids) != tuple(sorted(set(domain_ids))):
        raise ContractValidationError(
            "dimension_domains must be sorted by unique dimension_id"
        )
    return catalogue, {
        domain.dimension_id: domain for domain in catalogue.dimension_domains
    }


def _validate_source_context_current(
    source_context: object,
) -> AuthoritativeSourceContext:
    if type(source_context) is not AuthoritativeSourceContext:
        raise ContractValidationError("source context must be explicitly injected")
    _identifier(source_context.source_context_id, "source_context_id")
    _identifier(source_context.provenance_id, "source context provenance_id")
    return source_context


def _validate_source_address_current(
    address: object,
) -> AuthoritativeSourceFactAddress:
    if type(address) is not AuthoritativeSourceFactAddress:
        raise ContractValidationError("source address must be explicitly injected")
    _content_id(address.source_context_content_id, "source_context_content_id")
    _uuid(address.source_fact_id, "source_fact_id")
    _strict_int(address.source_fact_version, "source_fact_version", 1, 2_147_483_647)
    return address


def _validate_authority_current(authority: object) -> CollectionAuthorityProof:
    if type(authority) is not CollectionAuthorityProof:
        raise ContractValidationError("authority must be explicitly injected")
    _identifier(authority.authority_id, "authority_id")
    _identifier(authority.policy_provenance_id, "policy_provenance_id")
    _content_id(authority.catalogue_content_id, "catalogue_content_id")
    _identifier(authority.catalogue_provenance_id, "catalogue_provenance_id")
    _content_id(authority.source_context_content_id, "source_context_content_id")
    _identifier(authority.source_context_provenance_id, "source_context_provenance_id")
    if _strict_bool(authority.collection_allowed, "collection_allowed") is not True:
        raise ContractValidationError("authority does not allow candidate collection")
    return authority


def _validate_dimensions(
    values: tuple[Dimension, ...], domains: dict[str, DimensionDomain]
) -> None:
    if type(values) is not tuple or not 1 <= len(values) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError("dimensions has an invalid immutable item count")
    value_ids: list[str] = []
    for value in values:
        _validate_dimension_current(value)
        value_ids.append(value.dimension_id)
    if tuple(value_ids) != tuple(sorted(set(value_ids))):
        raise ContractValidationError("dimensions must be sorted by unique dimension_id")
    if tuple(value_ids) != tuple(domains):
        raise ContractValidationError("dimensions do not exactly match catalogue domains")
    for value in values:
        domain = domains[value.dimension_id]
        if value.kind is not domain.kind:
            raise ContractValidationError("dimension kind does not match catalogue domain")
        if type(domain) is EnumDimensionDomain and value.value not in domain.allowed_values:
            raise ContractValidationError("enum dimension value is outside the finite domain")
        if type(domain) is IntegerDimensionDomain and not domain.minimum <= value.value <= domain.maximum:
            raise ContractValidationError("integer dimension value is outside the bounded domain")


def _validate_single_dimension(
    catalogue: ProductAnalyticsCatalogue, value: Dimension
) -> None:
    _, domains = _validate_catalogue_current(catalogue)
    _validate_dimension_current(value)
    domain = domains.get(value.dimension_id)
    if domain is None:
        raise ContractValidationError("dimension is absent from the injected catalogue")
    if value.kind is not domain.kind:
        raise ContractValidationError("dimension kind does not match catalogue domain")
    if type(domain) is EnumDimensionDomain and value.value not in domain.allowed_values:
        raise ContractValidationError("enum dimension value is outside the finite domain")
    if type(domain) is IntegerDimensionDomain and not domain.minimum <= value.value <= domain.maximum:
        raise ContractValidationError("integer dimension value is outside the bounded domain")


def _validate_bindings(
    catalogue: ProductAnalyticsCatalogue,
    authority: CollectionAuthorityProof,
    source_context: AuthoritativeSourceContext,
) -> tuple[str, str, str, dict[str, DimensionDomain]]:
    _, domains = _validate_catalogue_current(catalogue)
    _validate_source_context_current(source_context)
    _validate_authority_current(authority)
    catalogue_content_id = catalogue.content_id
    source_context_content_id = source_context.content_id
    authority_content_id = authority.content_id
    if authority.catalogue_content_id != catalogue_content_id:
        raise ContractValidationError("authority does not match catalogue")
    if authority.catalogue_provenance_id != catalogue.provenance_id:
        raise ContractValidationError("authority does not match catalogue provenance")
    if authority.source_context_content_id != source_context_content_id:
        raise ContractValidationError("authority does not match source context")
    if authority.source_context_provenance_id != source_context.provenance_id:
        raise ContractValidationError("authority does not match source context provenance")
    return (
        catalogue_content_id,
        authority_content_id,
        source_context_content_id,
        domains,
    )
def _validate_event_in_context(
    *,
    catalogue: ProductAnalyticsCatalogue,
    authority: CollectionAuthorityProof,
    source_context: AuthoritativeSourceContext,
    event: EventCandidate,
) -> tuple[str, str, str]:
    """Validate current untrusted event values against exact injected context."""
    if type(event) is not EventCandidate:
        raise ContractValidationError("event must be a closed event candidate")
    catalogue_id, authority_id, source_context_id, domains = _validate_bindings(
        catalogue, authority, source_context
    )
    _content_id(event.catalogue_content_id, "event catalogue_content_id")
    _content_id(event.authority_content_id, "event authority_content_id")
    _content_id(event.source_context_content_id, "event source_context_content_id")
    if event.catalogue_content_id != catalogue_id:
        raise ContractValidationError("event does not match catalogue")
    if event.authority_content_id != authority_id:
        raise ContractValidationError("event does not match authority")
    if event.source_context_content_id != source_context_id:
        raise ContractValidationError("event does not match source context")
    address = _validate_source_address_current(event.source_fact_address)
    if address.source_context_content_id != source_context_id:
        raise ContractValidationError("event source address does not match source context")
    _uuid(event.subject_epoch_id, "subject_epoch_id")
    _uuid(event.tenant_epoch_id, "tenant_epoch_id")
    _uuid(event.session_epoch_id, "session_epoch_id")
    _utc(event.received_at, "received_at")
    finite_fields = (
        (event.event_type_id, catalogue.event_type_ids, "event_type_id"),
        (event.purpose_id, catalogue.purpose_ids, "purpose_id"),
        (event.product_area_id, catalogue.product_area_ids, "product_area_id"),
        (event.route_template_id, catalogue.route_template_ids, "route_template_id"),
        (event.build_id, catalogue.build_ids, "build_id"),
        (event.outcome_id, catalogue.outcome_ids, "outcome_id"),
    )
    for value, allowed, field_name in finite_fields:
        _identifier(value, field_name)
        if value not in allowed:
            raise ContractValidationError(f"{field_name} is outside the injected catalogue")
    _validate_dimensions(event.dimensions, domains)
    return catalogue_id, authority_id, source_context_id


def create_event_candidate(
    *,
    catalogue: ProductAnalyticsCatalogue,
    authority: CollectionAuthorityProof,
    source_context: AuthoritativeSourceContext,
    subject_epoch_id: UUID,
    tenant_epoch_id: UUID,
    session_epoch_id: UUID,
    source_fact_address: AuthoritativeSourceFactAddress,
    event_type_id: str,
    purpose_id: str,
    product_area_id: str,
    route_template_id: str,
    build_id: str,
    outcome_id: str,
    dimensions: tuple[Dimension, ...],
    received_at: datetime,
) -> EventCandidate:
    if type(catalogue) is not ProductAnalyticsCatalogue:
        raise ContractValidationError("catalogue must be explicitly injected")
    if type(authority) is not CollectionAuthorityProof:
        raise ContractValidationError("authority must be explicitly injected")
    if type(source_context) is not AuthoritativeSourceContext:
        raise ContractValidationError("source context must be explicitly injected")
    if type(source_fact_address) is not AuthoritativeSourceFactAddress:
        raise ContractValidationError("source address must be explicitly injected")
    candidate = EventCandidate(
        catalogue_content_id=catalogue.content_id,
        authority_content_id=authority.content_id,
        source_context_content_id=source_context.content_id,
        subject_epoch_id=subject_epoch_id,
        tenant_epoch_id=tenant_epoch_id,
        session_epoch_id=session_epoch_id,
        source_fact_address=source_fact_address,
        event_type_id=event_type_id,
        purpose_id=purpose_id,
        product_area_id=product_area_id,
        route_template_id=route_template_id,
        build_id=build_id,
        outcome_id=outcome_id,
        dimensions=dimensions,
        received_at=received_at,
    )
    _validate_event_in_context(
        catalogue=catalogue,
        authority=authority,
        source_context=source_context,
        event=candidate,
    )
    return candidate


def create_aggregate_dimensions(
    *,
    catalogue: ProductAnalyticsCatalogue,
    authority: CollectionAuthorityProof,
    source_context: AuthoritativeSourceContext,
    event: EventCandidate,
    expected_subject_epoch_id: UUID,
    expected_tenant_epoch_id: UUID,
    expected_session_epoch_id: UUID,
) -> AggregateDimensionsCandidate:
    catalogue_id, authority_id, _ = _validate_event_in_context(
        catalogue=catalogue,
        authority=authority,
        source_context=source_context,
        event=event,
    )
    expected = (
        (_uuid(expected_subject_epoch_id, "expected_subject_epoch_id"), event.subject_epoch_id, "subject"),
        (_uuid(expected_tenant_epoch_id, "expected_tenant_epoch_id"), event.tenant_epoch_id, "tenant"),
        (_uuid(expected_session_epoch_id, "expected_session_epoch_id"), event.session_epoch_id, "session"),
    )
    for requested, observed, name in expected:
        if requested != observed:
            raise ContractValidationError(f"event does not match expected {name} epoch")
    candidate = AggregateDimensionsCandidate(
        catalogue_content_id=catalogue_id,
        authority_content_id=authority_id,
        event_type_id=event.event_type_id,
        purpose_id=event.purpose_id,
        product_area_id=event.product_area_id,
        route_template_id=event.route_template_id,
        build_id=event.build_id,
        outcome_id=event.outcome_id,
        dimensions=event.dimensions,
        publishable=False,
    )
    return candidate


def _decode_domain(raw: object) -> DimensionDomain:
    if type(raw) is not dict:
        raise ContractValidationError("dimension domain must be an object")
    contract_type = raw.get("contract_type")
    if contract_type == "EnumDimensionDomain":
        data = _versioned(raw, contract_type, {"dimension_id", "allowed_values"})
        return EnumDimensionDomain(data["dimension_id"], _tuple(data["allowed_values"], "allowed_values"))
    if contract_type == "BooleanDimensionDomain":
        data = _versioned(raw, contract_type, {"dimension_id"})
        return BooleanDimensionDomain(data["dimension_id"])
    if contract_type == "IntegerDimensionDomain":
        data = _versioned(raw, contract_type, {"dimension_id", "minimum", "maximum"})
        return IntegerDimensionDomain(data["dimension_id"], data["minimum"], data["maximum"])
    raise ContractValidationError("unknown dimension domain contract type")


def _decode_dimension(raw: object) -> Dimension:
    if type(raw) is not dict:
        raise ContractValidationError("dimension must be an object")
    contract_type = raw.get("contract_type")
    fields = {"dimension_id", "value"}
    data = _versioned(raw, str(contract_type), fields)
    if contract_type == "EnumDimension":
        return EnumDimension(data["dimension_id"], data["value"])
    if contract_type == "BooleanDimension":
        return BooleanDimension(data["dimension_id"], data["value"])
    if contract_type == "IntegerDimension":
        return IntegerDimension(data["dimension_id"], data["value"])
    raise ContractValidationError("unknown dimension contract type")


def _tuple(raw: object, field_name: str) -> tuple[Any, ...]:
    if type(raw) is not list or not 1 <= len(raw) <= MAX_COLLECTION_ITEMS:
        raise ContractValidationError(f"{field_name} has an invalid item count")
    return tuple(raw)


def _rederive_aggregate_for_decode(
    *,
    raw: dict[str, Any],
    catalogue: ProductAnalyticsCatalogue,
    authority: CollectionAuthorityProof,
    source_context: AuthoritativeSourceContext,
    event: EventCandidate,
) -> AggregateDimensionsCandidate:
    expected = create_aggregate_dimensions(
        catalogue=catalogue,
        authority=authority,
        source_context=source_context,
        event=event,
        expected_subject_epoch_id=event.subject_epoch_id,
        expected_tenant_epoch_id=event.tenant_epoch_id,
        expected_session_epoch_id=event.session_epoch_id,
    )
    if _canonical_json(raw) != expected.canonical_json():
        raise ContractValidationError("aggregate does not exactly derive from injected event")
    return expected


def canonical_deserialize(
    encoded: str,
    *,
    catalogue: ProductAnalyticsCatalogue | None = None,
    authority: CollectionAuthorityProof | None = None,
    source_context: AuthoritativeSourceContext | None = None,
    event: EventCandidate | None = None,
) -> _CanonicalContract:
    if type(encoded) is not str or len(encoded.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise ContractValidationError("encoded contract exceeds size bound")
    if not encoded.isascii():
        raise ContractValidationError("encoded contract must use canonical ASCII JSON")
    try:
        raw = json.loads(
            encoded,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ContractValidationError(f"invalid JSON constant {value}")
            ),
        )
    except ContractValidationError:
        raise
    except (json.JSONDecodeError, RecursionError, UnicodeError, ValueError) as exc:
        raise ContractValidationError("encoded contract is invalid JSON") from exc
    if _json_depth(raw) > MAX_JSON_DEPTH:
        raise ContractValidationError("encoded contract exceeds depth bound")
    if _canonical_json(raw) != encoded:
        raise ContractValidationError("encoded contract is not exact canonical JSON")
    if type(raw) is not dict or type(raw.get("contract_type")) is not str:
        raise ContractValidationError("encoded contract has no closed contract type")
    kind = raw["contract_type"]
    if kind.endswith("DimensionDomain"):
        return _decode_domain(raw)
    if kind in {"EnumDimension", "BooleanDimension", "IntegerDimension"}:
        result = _decode_dimension(raw)
        if type(catalogue) is not ProductAnalyticsCatalogue:
            raise ContractValidationError("dimension decode requires exact injected catalogue")
        _validate_single_dimension(catalogue, result)
        return result
    if kind == "ProductAnalyticsCatalogue":
        data = _versioned(raw, kind, {
            "catalogue_id", "provenance_id", "event_type_ids", "purpose_ids",
            "product_area_ids", "route_template_ids", "build_ids", "outcome_ids",
            "dimension_domains",
        })
        return ProductAnalyticsCatalogue(
            data["catalogue_id"], data["provenance_id"],
            _tuple(data["event_type_ids"], "event_type_ids"),
            _tuple(data["purpose_ids"], "purpose_ids"),
            _tuple(data["product_area_ids"], "product_area_ids"),
            _tuple(data["route_template_ids"], "route_template_ids"),
            _tuple(data["build_ids"], "build_ids"),
            _tuple(data["outcome_ids"], "outcome_ids"),
            tuple(_decode_domain(item) for item in _tuple(data["dimension_domains"], "dimension_domains")),
        )
    if kind == "AuthoritativeSourceContext":
        data = _versioned(raw, kind, {"source_context_id", "provenance_id"})
        return AuthoritativeSourceContext(data["source_context_id"], data["provenance_id"])
    if kind == "CollectionAuthorityProof":
        data = _versioned(raw, kind, {
            "authority_id", "policy_provenance_id", "catalogue_content_id",
            "catalogue_provenance_id", "source_context_content_id",
            "source_context_provenance_id", "collection_allowed",
        })
        result = CollectionAuthorityProof(**{name: data[name] for name in data if name not in {"contract_type", "contract_version"}})
        if type(catalogue) is not ProductAnalyticsCatalogue or type(source_context) is not AuthoritativeSourceContext:
            raise ContractValidationError("authority decode requires exact catalogue and source context")
        _validate_bindings(catalogue, result, source_context)
        return result
    if kind == "AuthoritativeSourceFactAddress":
        data = _versioned(raw, kind, {"source_context_content_id", "source_fact_id", "source_fact_version"})
        result = AuthoritativeSourceFactAddress(
            data["source_context_content_id"], _parse_uuid(data["source_fact_id"], "source_fact_id"),
            data["source_fact_version"],
        )
        if type(source_context) is not AuthoritativeSourceContext or result.source_context_content_id != source_context.content_id:
            raise ContractValidationError("source address decode requires exact source context")
        return result
    if kind == "EventCandidate":
        data = _versioned(raw, kind, {
            "catalogue_content_id", "authority_content_id", "source_context_content_id",
            "subject_epoch_id", "tenant_epoch_id", "session_epoch_id", "source_fact_address",
            "event_type_id", "purpose_id", "product_area_id", "route_template_id", "build_id",
            "outcome_id", "dimensions", "received_at",
        })
        if type(catalogue) is not ProductAnalyticsCatalogue or type(authority) is not CollectionAuthorityProof or type(source_context) is not AuthoritativeSourceContext:
            raise ContractValidationError("event decode requires exact catalogue, authority and source context")
        address = _decode_source_address(data["source_fact_address"], source_context)
        candidate = create_event_candidate(
            catalogue=catalogue, authority=authority, source_context=source_context,
            subject_epoch_id=_parse_uuid(data["subject_epoch_id"], "subject_epoch_id"),
            tenant_epoch_id=_parse_uuid(data["tenant_epoch_id"], "tenant_epoch_id"),
            session_epoch_id=_parse_uuid(data["session_epoch_id"], "session_epoch_id"),
            source_fact_address=address, event_type_id=data["event_type_id"],
            purpose_id=data["purpose_id"], product_area_id=data["product_area_id"],
            route_template_id=data["route_template_id"], build_id=data["build_id"],
            outcome_id=data["outcome_id"],
            dimensions=tuple(_decode_dimension(item) for item in _tuple(data["dimensions"], "dimensions")),
            received_at=_parse_datetime(data["received_at"], "received_at"),
        )
        if candidate.canonical_dict() != raw:
            raise ContractValidationError("event does not match exact injected authority context")
        _validate_event_in_context(
            catalogue=catalogue,
            authority=authority,
            source_context=source_context,
            event=candidate,
        )
        return candidate
    if kind == "AggregateDimensionsCandidate":
        data = _versioned(raw, kind, {
            "catalogue_content_id", "authority_content_id", "event_type_id", "purpose_id",
            "product_area_id", "route_template_id", "build_id", "outcome_id", "dimensions",
            "publishable",
        })
        if (
            type(catalogue) is not ProductAnalyticsCatalogue
            or type(authority) is not CollectionAuthorityProof
            or type(source_context) is not AuthoritativeSourceContext
            or type(event) is not EventCandidate
        ):
            raise ContractValidationError(
                "aggregate decode requires exact catalogue, authority, source context and event"
            )
        _validate_event_in_context(
            catalogue=catalogue,
            authority=authority,
            source_context=source_context,
            event=event,
        )
        return _rederive_aggregate_for_decode(
            raw=raw,
            catalogue=catalogue,
            authority=authority,
            source_context=source_context,
            event=event,
        )
    raise ContractValidationError("unknown contract type")


def _decode_source_address(
    raw: object, source_context: AuthoritativeSourceContext
) -> AuthoritativeSourceFactAddress:
    if type(raw) is not dict:
        raise ContractValidationError("source address must be an object")
    encoded = _canonical_json(raw)
    result = canonical_deserialize(encoded, source_context=source_context)
    if type(result) is not AuthoritativeSourceFactAddress:
        raise ContractValidationError("source address has the wrong closed type")
    return result
