"""Read-only paper/mock comparison receipts for capital admission.

Nothing in this module can place an order, mutate an allocator result, or grant
authority.  It observes the current allocator and reconstructs the new immutable
batch into one common comparison shape.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    CandidateIntentRecord,
    CapitalReservationRecord,
    DecisionBatchRecord,
    PortfolioAdmissionDecisionRecord,
)
from app.engine.allocator import Candidate as CurrentCandidate
from app.engine.allocator import allocate as current_allocate
from app.ir.hashing import canonical_json, content_address


class ShadowRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AllocatorCandidate:
    candidate_intent_id: str
    instrument_key: str
    direction: str
    requested_quantity: int
    cost_minor: int

    def __post_init__(self) -> None:
        if not self.candidate_intent_id or not self.instrument_key:
            raise ShadowRefused("INVALID_CURRENT_CANDIDATE")
        if self.direction not in {"LONG", "SHORT"} or self.requested_quantity == 0:
            raise ShadowRefused("INVALID_CURRENT_CANDIDATE")
        if isinstance(self.cost_minor, bool) or self.cost_minor < 0:
            raise ShadowRefused("INVALID_CURRENT_CANDIDATE")


@dataclass(frozen=True)
class ComparisonItem:
    candidate_intent_id: str
    status: str
    requested_quantity: int
    admitted_quantity: int
    required_capital_minor: int
    held_capital_minor: int
    reason_code: str

    def comparison_document(self) -> dict:
        return {
            "candidate_intent_id": self.candidate_intent_id,
            "status": self.status,
            "requested_quantity": self.requested_quantity,
            "admitted_quantity": self.admitted_quantity,
            "required_capital_minor": self.required_capital_minor,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class WhyReceipt:
    candidate_intent_id: str
    candidate_address: str
    status: str
    reason_code: str
    requested_quantity: int
    admitted_quantity: int
    required_capital_minor: int
    held_capital_minor: int
    rank_json: str
    constraints_json: str
    reservation_id: str | None
    reservation_state: str | None
    held_pending_digest: str
    graph_address: str | None
    admission_address: str | None
    product_address: str
    sizing_decision_address: str
    product_policy_address: str
    sizing_policy_address: str
    portfolio_policy_address: str


@dataclass(frozen=True)
class ShadowComparison:
    batch_id: str
    batch_address: str
    current_json: str
    admission_json: str
    parity: bool
    why: tuple[WhyReceipt, ...]
    replay_digest: str

    @property
    def receipt_address(self) -> str:
        return content_address({
            "schema": "strategy-os.capital-shadow-receipt/v1",
            "batch_id": self.batch_id,
            "batch_address": self.batch_address,
            "current_json": self.current_json,
            "admission_json": self.admission_json,
            "parity": self.parity,
            "replay_digest": self.replay_digest,
        })


def observe_current_allocator(
        candidates: tuple[AllocatorCandidate, ...], *,
        available_cash_minor: int) -> tuple[ComparisonItem, ...]:
    """Run the actual current allocator without changing its returned decision."""
    if isinstance(available_cash_minor, bool) or available_cash_minor < 0:
        raise ShadowRefused("INVALID_AVAILABLE_CASH")
    current_rows: list[CurrentCandidate] = []
    identities: dict[int, AllocatorCandidate] = {}
    for candidate in candidates:
        row = CurrentCandidate(
            candidate.instrument_key, candidate.direction,
            candidate.cost_minor / 100,
        )
        current_rows.append(row)
        identities[id(row)] = candidate
    allocation = current_allocate(current_rows, available_cash_minor / 100)
    items = []
    for row in allocation.funded:
        candidate = identities[id(row)]
        items.append(ComparisonItem(
            candidate.candidate_intent_id, "admitted",
            candidate.requested_quantity, candidate.requested_quantity,
            candidate.cost_minor, candidate.cost_minor, "ADMITTED",
        ))
    for row, _reason in allocation.skipped:
        candidate = identities[id(row)]
        items.append(ComparisonItem(
            candidate.candidate_intent_id, "rejected",
            candidate.requested_quantity, 0,
            candidate.cost_minor, 0, "INSUFFICIENT_CAPITAL",
        ))
    return tuple(sorted(items, key=lambda item: item.candidate_intent_id))


def _admission_items(
        session: Session, batch: DecisionBatchRecord,
        decisions: tuple[PortfolioAdmissionDecisionRecord, ...],
        candidates: dict[str, CandidateIntentRecord],
        reservations: dict[str, CapitalReservationRecord]) -> tuple[
            tuple[ComparisonItem, ...], tuple[WhyReceipt, ...]]:
    items = []
    receipts = []
    for decision in decisions:
        candidate = candidates.get(decision.candidate_intent_id)
        if candidate is None:
            raise ShadowRefused("INCOMPLETE_BATCH")
        reservation = (reservations.get(decision.reservation_id)
                       if decision.reservation_id is not None else None)
        if decision.status in {"admitted", "resized"} \
                and decision.held_capital_minor > 0 and reservation is None:
            raise ShadowRefused("INCOMPLETE_BATCH")
        item = ComparisonItem(
            decision.candidate_intent_id, decision.status,
            decision.requested_quantity, decision.admitted_quantity,
            decision.required_capital_minor, decision.held_capital_minor,
            decision.reason_code,
        )
        items.append(item)
        receipts.append(WhyReceipt(
            candidate_intent_id=candidate.candidate_intent_id,
            candidate_address=candidate.candidate_address,
            status=decision.status, reason_code=decision.reason_code,
            requested_quantity=decision.requested_quantity,
            admitted_quantity=decision.admitted_quantity,
            required_capital_minor=decision.required_capital_minor,
            held_capital_minor=decision.held_capital_minor,
            rank_json=decision.rank_json,
            constraints_json=decision.constraints_json,
            reservation_id=decision.reservation_id,
            reservation_state=reservation.state if reservation is not None else None,
            held_pending_digest=candidate.held_pending_digest,
            graph_address=candidate.graph_address,
            admission_address=candidate.admission_address,
            product_address=candidate.product_address,
            sizing_decision_address=candidate.sizing_decision_address,
            product_policy_address=batch.product_policy_address,
            sizing_policy_address=batch.sizing_policy_address,
            portfolio_policy_address=batch.portfolio_policy_address,
        ))
    ordered_items = tuple(sorted(items, key=lambda item: item.candidate_intent_id))
    ordered_receipts = tuple(sorted(receipts, key=lambda item: item.candidate_intent_id))
    return ordered_items, ordered_receipts


def compare_paper_shadow(
        session: Session, *, batch_id: str,
        current: tuple[ComparisonItem, ...]) -> ShadowComparison:
    """Reconstruct one immutable batch and compare only; perform no writes."""
    batch = session.get(DecisionBatchRecord, batch_id)
    if batch is None:
        raise ShadowRefused("BATCH_MISSING")
    if batch.book != "paper":
        raise ShadowRefused("PAPER_SHADOW_ONLY")
    decisions = tuple(session.scalars(select(
        PortfolioAdmissionDecisionRecord).where(
            PortfolioAdmissionDecisionRecord.batch_id == batch_id).order_by(
                PortfolioAdmissionDecisionRecord.candidate_intent_id)))
    candidates = {
        row.candidate_intent_id: row for row in session.scalars(select(
            CandidateIntentRecord).where(
                CandidateIntentRecord.candidate_intent_id.in_([
                    item.candidate_intent_id for item in decisions])))
    }
    reservations = {
        row.reservation_id: row for row in session.scalars(select(
            CapitalReservationRecord).where(
                CapitalReservationRecord.batch_id == batch_id))
    }
    if len(decisions) != len(candidates) or len(decisions) != len(current):
        raise ShadowRefused("INCOMPLETE_BATCH")
    admission, why = _admission_items(
        session, batch, decisions, candidates, reservations)
    current_ordered = tuple(sorted(current, key=lambda item: item.candidate_intent_id))
    current_json = canonical_json([
        item.comparison_document() for item in current_ordered])
    admission_json = canonical_json([
        item.comparison_document() for item in admission])
    replay_digest = content_address({
        "batch_address": batch.batch_address,
        "candidate_set_digest": batch.candidate_set_digest,
        "admission": admission_json,
    })
    return ShadowComparison(
        batch.decision_batch_id, batch.batch_address,
        current_json, admission_json, current_json == admission_json,
        why, replay_digest,
    )


def compare_documents(current: object, admission: object) -> dict:
    """Offline script seam: compare canonical JSON bytes without authority."""
    current_json = canonical_json(current)
    admission_json = canonical_json(admission)
    return {
        "current_json": current_json,
        "admission_json": admission_json,
        "parity": current_json == admission_json,
        "comparison_address": content_address({
            "current_json": current_json, "admission_json": admission_json,
        }),
    }


__all__ = [
    "AllocatorCandidate", "ComparisonItem", "ShadowComparison", "ShadowRefused",
    "WhyReceipt", "compare_documents", "compare_paper_shadow",
    "observe_current_allocator",
]
