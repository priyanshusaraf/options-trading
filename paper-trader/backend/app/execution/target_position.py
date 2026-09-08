"""Pure target-position delta over explicit held and pending evidence."""
from __future__ import annotations

import dataclasses
import datetime as dt

from app.execution.product_policy import contract_address, require_address
from app.strategy.admission import GraphAttributionRefused, require_attribution_tuple


class TargetPositionRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _signed_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TargetPositionRefused(f"INVALID_{field.upper()}")
    return value


@dataclasses.dataclass(frozen=True)
class TargetPositionRequest:
    request_id: str
    owner_id: str
    broker_account_id: str
    book: str
    deployment_id: int
    strategy_key: str
    strategy_version: str
    admission_address: str
    graph_address: str | None
    attribution_state: str
    canonical_instrument_key: str
    product_address: str
    target_quantity: int
    purpose: str
    decision_at: dt.datetime

    def __post_init__(self) -> None:
        for field in (
                "request_id", "owner_id", "broker_account_id", "strategy_key",
                "strategy_version", "canonical_instrument_key"):
            if not getattr(self, field):
                raise TargetPositionRefused(f"INVALID_{field.upper()}")
        if self.book not in {"paper", "live"}:
            raise TargetPositionRefused("INVALID_BOOK")
        if isinstance(self.deployment_id, bool) or not isinstance(
                self.deployment_id, int) or self.deployment_id < 1:
            raise TargetPositionRefused("INVALID_DEPLOYMENT_ID")
        _signed_integer(self.target_quantity, field="target_quantity")
        if self.purpose not in {"ENTRY", "TARGET_ADJUSTMENT", "RISK_REDUCTION"}:
            raise TargetPositionRefused("INVALID_PURPOSE")
        if self.decision_at.tzinfo is None or self.decision_at.utcoffset() is None:
            raise TargetPositionRefused("NAIVE_TIME")
        for value, field in (
            (self.admission_address, "admission_address"),
            (self.product_address, "product_address"),
        ):
            require_address(value, field=field)
        if self.graph_address is not None:
            require_address(self.graph_address, field="graph_address")
        try:
            require_attribution_tuple(
                strategy_key=self.strategy_key,
                strategy_version=self.strategy_version,
                graph_address=self.graph_address,
                admission_address=self.admission_address,
                attribution_state=self.attribution_state)
        except GraphAttributionRefused as exc:
            raise TargetPositionRefused(exc.code) from exc

    @property
    def address(self) -> str:
        return contract_address("target-position-request/1", self)


@dataclasses.dataclass(frozen=True)
class PendingQuantityEvidence:
    evidence_id: str
    owner_id: str
    broker_account_id: str
    book: str
    canonical_instrument_key: str
    product_address: str
    signed_remaining_quantity: int
    state: str
    uncertain: bool
    source_address: str

    def __post_init__(self) -> None:
        for field in (
                "evidence_id", "owner_id", "broker_account_id", "book",
                "canonical_instrument_key", "state"):
            if not getattr(self, field):
                raise TargetPositionRefused(f"INVALID_{field.upper()}")
        _signed_integer(
            self.signed_remaining_quantity, field="signed_remaining_quantity")
        if not isinstance(self.uncertain, bool):
            raise TargetPositionRefused("INVALID_UNCERTAINTY")
        require_address(self.product_address, field="product_address")
        require_address(self.source_address, field="source_address")

    @property
    def address(self) -> str:
        return contract_address("pending-quantity-evidence/1", self)


@dataclasses.dataclass(frozen=True)
class TargetDeltaDecision:
    request_address: str
    accepted: bool
    held_quantity: int
    known_pending_quantity: int
    requested_delta: int
    risk_reducing: bool
    bypass_entry_admission: bool
    reason_code: str
    pending_evidence_addresses: tuple[str, ...]

    @property
    def address(self) -> str:
        return contract_address("target-delta-decision/1", self)


def _risk_reducing(held: int, target: int) -> bool:
    if held == 0:
        return False
    same_direction_or_flat = target == 0 or (held > 0) == (target > 0)
    return same_direction_or_flat and abs(target) < abs(held)


def derive_target_delta(
        request: TargetPositionRequest, *, held_quantity: int,
        pending: tuple[PendingQuantityEvidence, ...] = ()) -> TargetDeltaDecision:
    """Derive a signed delta. Unknown broker state blocks additions, never exits."""
    held = _signed_integer(held_quantity, field="held_quantity")
    addresses = []
    known_pending = 0
    uncertain = False
    identities = set()
    for item in pending:
        if item.evidence_id in identities:
            raise TargetPositionRefused("DUPLICATE_PENDING_EVIDENCE")
        identities.add(item.evidence_id)
        if (item.owner_id != request.owner_id
                or item.broker_account_id != request.broker_account_id
                or item.book != request.book
                or item.canonical_instrument_key != request.canonical_instrument_key
                or item.product_address != request.product_address):
            raise TargetPositionRefused("PENDING_IDENTITY_MISMATCH")
        addresses.append(item.address)
        if item.uncertain:
            uncertain = True
        else:
            known_pending += item.signed_remaining_quantity
    sorted_addresses = tuple(sorted(addresses))
    if uncertain:
        effective = held + known_pending
        reducing = _risk_reducing(effective, request.target_quantity)
        same_held_direction = (
            held != 0 and effective != 0 and (held > 0) == (effective > 0))
        if reducing and same_held_direction:
            desired = request.target_quantity - effective
            bounded = min(abs(desired), abs(held), abs(effective))
            delta = bounded if desired > 0 else -bounded
            if delta == 0:
                reducing = False
        if reducing and same_held_direction:
            return TargetDeltaDecision(
                request.address, True, held, known_pending,
                delta, True, True,
                "RISK_REDUCTION_BYPASSES_ENTRY_UNCERTAINTY", sorted_addresses)
        return TargetDeltaDecision(
            request.address, False, held, known_pending, 0, False, False,
            "BROKER_UNCERTAINTY_BLOCKS_ENTRY", sorted_addresses)
    reducing = _risk_reducing(held + known_pending, request.target_quantity)
    delta = request.target_quantity - held - known_pending
    return TargetDeltaDecision(
        request.address, True, held, known_pending, delta, reducing,
        reducing, "TARGET_DELTA", sorted_addresses)


__all__ = [
    "PendingQuantityEvidence", "TargetDeltaDecision", "TargetPositionRefused",
    "TargetPositionRequest", "derive_target_delta",
]
