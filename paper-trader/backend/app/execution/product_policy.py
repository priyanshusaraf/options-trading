"""Pure execution-product policy contracts.

This module validates already-resolved facts. It owns no provider, registry,
strategy selection, sizing, reservation, broker or order path.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

from app.ir.hashing import content_address
from app.strategy.admission import GraphAttributionRefused, require_attribution_tuple


PRODUCT_FAMILIES = frozenset({"options", "equity", "futures"})
EXECUTION_MODES = frozenset({"paper", "live"})
PURPOSES = frozenset({"ENTRY", "TARGET_ADJUSTMENT", "RISK_REDUCTION"})


class ProductPolicyRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require_address(value: object, *, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 71
            or not value.startswith("sha256:")
            or any(char not in "0123456789abcdef" for char in value[7:])):
        raise ProductPolicyRefused(f"INVALID_{field.upper()}")
    return value


def _plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _plain(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if not field.name.startswith("_")
        }
    if isinstance(value, Mapping):
        return {str(key): _plain(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, dt.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ProductPolicyRefused("NAIVE_TIME")
        return value.astimezone(dt.timezone.utc).isoformat()
    return value


def contract_address(schema: str, value: object) -> str:
    return content_address({"schema": schema, "value": _plain(value)})


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProductPolicyRefused(f"INVALID_{field.upper()}")
    return value


@dataclasses.dataclass(frozen=True)
class ExecutionProductPolicy:
    policy_id: str
    version: int
    product_family: str
    execution_modes: tuple[str, ...]
    selector_version: str
    allowed_order_types: tuple[str, ...]
    max_fact_age_seconds: int

    def __post_init__(self) -> None:
        if not self.policy_id or not self.selector_version:
            raise ProductPolicyRefused("INVALID_POLICY_IDENTITY")
        _positive_int(self.version, field="policy_version")
        if self.product_family not in PRODUCT_FAMILIES:
            raise ProductPolicyRefused("UNSUPPORTED_PRODUCT_FAMILY")
        if (not self.execution_modes
                or set(self.execution_modes) - EXECUTION_MODES
                or tuple(sorted(set(self.execution_modes))) != self.execution_modes):
            raise ProductPolicyRefused("INVALID_EXECUTION_MODES")
        if (not self.allowed_order_types
                or tuple(sorted(set(self.allowed_order_types))) != self.allowed_order_types
                or any(not item for item in self.allowed_order_types)):
            raise ProductPolicyRefused("INVALID_ORDER_TYPES")
        _positive_int(self.max_fact_age_seconds, field="max_fact_age_seconds")

    @property
    def address(self) -> str:
        return contract_address("execution-product-policy/1", self)


@dataclasses.dataclass(frozen=True)
class ProductResolutionRequest:
    owner_id: str
    broker_account_id: str
    book: str
    deployment_id: int
    binding_instrument_key: str
    strategy_key: str
    strategy_version: str
    admission_address: str
    graph_address: str | None
    attribution_state: str
    binding_authority: str
    execution_mode: str
    signal_instrument_key: str
    direction: str
    purpose: str
    decision_at: dt.datetime
    market_snapshot_address: str
    capability_address: str

    def __post_init__(self) -> None:
        for field in (
                "owner_id", "broker_account_id", "book", "binding_instrument_key",
                "strategy_key", "strategy_version", "signal_instrument_key"):
            if not getattr(self, field):
                raise ProductPolicyRefused(f"INVALID_{field.upper()}")
        _positive_int(self.deployment_id, field="deployment_id")
        if self.book not in {"paper", "live"} or self.execution_mode != self.book:
            raise ProductPolicyRefused("BOOK_MODE_MISMATCH")
        if self.binding_authority != "authoritative":
            raise ProductPolicyRefused("AUTHORITY_NOT_GRANTED")
        if self.direction not in {"LONG", "SHORT"}:
            raise ProductPolicyRefused("INVALID_DIRECTION")
        if self.purpose not in PURPOSES:
            raise ProductPolicyRefused("INVALID_PURPOSE")
        if self.decision_at.tzinfo is None or self.decision_at.utcoffset() is None:
            raise ProductPolicyRefused("NAIVE_TIME")
        require_address(self.admission_address, field="admission_address")
        require_address(self.market_snapshot_address, field="market_snapshot_address")
        require_address(self.capability_address, field="capability_address")
        try:
            require_attribution_tuple(
                strategy_key=self.strategy_key,
                strategy_version=self.strategy_version,
                graph_address=self.graph_address,
                admission_address=self.admission_address,
                attribution_state=self.attribution_state)
        except GraphAttributionRefused as exc:
            raise ProductPolicyRefused(exc.code) from exc

    @property
    def address(self) -> str:
        return contract_address("product-resolution-request/1", self)


@dataclasses.dataclass(frozen=True)
class ProductCandidateFacts:
    signal_instrument_key: str
    execution_instrument_key: str
    product_family: str
    tradingsymbol: str
    exchange: str
    product_code: str
    order_types: tuple[str, ...]
    lot_size: int
    quantity_step: int
    tick_size_minor: int
    observed_at: dt.datetime
    source_address: str
    selection_evidence_address: str

    def __post_init__(self) -> None:
        for field in (
                "signal_instrument_key", "execution_instrument_key", "tradingsymbol",
                "exchange", "product_code"):
            if not getattr(self, field):
                raise ProductPolicyRefused(f"INVALID_{field.upper()}")
        if self.product_family not in PRODUCT_FAMILIES:
            raise ProductPolicyRefused("UNSUPPORTED_PRODUCT_FAMILY")
        if (not self.order_types
                or tuple(sorted(set(self.order_types))) != self.order_types):
            raise ProductPolicyRefused("INVALID_ORDER_TYPES")
        _positive_int(self.lot_size, field="lot_size")
        _positive_int(self.quantity_step, field="quantity_step")
        _positive_int(self.tick_size_minor, field="tick_size_minor")
        if self.lot_size % self.quantity_step:
            raise ProductPolicyRefused("LOT_STEP_MISMATCH")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ProductPolicyRefused("NAIVE_TIME")
        require_address(self.source_address, field="source_address")
        require_address(self.selection_evidence_address,
                        field="selection_evidence_address")

    @property
    def address(self) -> str:
        return contract_address("execution-product-candidate/1", self)


@dataclasses.dataclass(frozen=True)
class ResolvedExecutionProduct:
    policy_address: str
    request_address: str
    candidate_address: str
    canonical_execution_instrument_key: str
    product_family: str
    tradingsymbol: str
    exchange: str
    product_code: str
    allowed_order_types: tuple[str, ...]
    lot_size: int
    quantity_step: int
    tick_size_minor: int
    source_address: str
    selection_evidence_address: str

    @property
    def address(self) -> str:
        return contract_address("resolved-execution-product/1", self)


def resolve_product(
        policy: ExecutionProductPolicy,
        request: ProductResolutionRequest,
        candidate: ProductCandidateFacts) -> ResolvedExecutionProduct:
    """Validate one already-selected product candidate; perform no lookup or I/O."""
    if request.execution_mode not in policy.execution_modes:
        raise ProductPolicyRefused("MODE_NOT_ALLOWED")
    if candidate.product_family != policy.product_family:
        raise ProductPolicyRefused("PRODUCT_FAMILY_MISMATCH")
    if candidate.signal_instrument_key != request.signal_instrument_key:
        raise ProductPolicyRefused("SIGNAL_INSTRUMENT_MISMATCH")
    if request.binding_instrument_key != request.signal_instrument_key:
        raise ProductPolicyRefused("BINDING_INSTRUMENT_MISMATCH")
    if not set(candidate.order_types).issubset(policy.allowed_order_types):
        raise ProductPolicyRefused("ORDER_TYPE_NOT_ALLOWED")
    age = (request.decision_at.astimezone(dt.timezone.utc)
           - candidate.observed_at.astimezone(dt.timezone.utc)).total_seconds()
    if age < 0:
        raise ProductPolicyRefused("FUTURE_PRODUCT_FACT")
    if age > policy.max_fact_age_seconds:
        raise ProductPolicyRefused("STALE_PRODUCT_FACT")
    return ResolvedExecutionProduct(
        policy.address, request.address, candidate.address,
        candidate.execution_instrument_key, candidate.product_family,
        candidate.tradingsymbol, candidate.exchange, candidate.product_code,
        candidate.order_types, candidate.lot_size, candidate.quantity_step,
        candidate.tick_size_minor, candidate.source_address,
        candidate.selection_evidence_address)


__all__ = [
    "ExecutionProductPolicy", "ProductCandidateFacts", "ProductPolicyRefused",
    "ProductResolutionRequest", "ResolvedExecutionProduct", "contract_address",
    "require_address", "resolve_product",
]
