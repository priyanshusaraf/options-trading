"""Fenced, closed-batch capital admission with no broker or order side effect.

The caller owns the outer transaction and its commit.  This module owns the
single account/book/currency decision boundary inside that transaction.  It is
deliberately unwired from runners and transports.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.concurrency import begin_after_clean_reads, caller_owned_savepoint, locked_rows
from app.db.models import (
    AccountExecutionCommand,
    CandidateIntentRecord,
    CapitalReservationEventRecord,
    CapitalReservationHead,
    CapitalReservationRecord,
    CapitalState,
    DecisionBatchRecord,
    ExecutionIntent,
    ExecutionOrderEvent,
    PortfolioAdmissionDecisionRecord,
    SizingDecisionRecord,
    TargetPositionRequestRecord,
)
from app.engine.execution_lifecycle import reduce_execution_events
from app.execution.leases import LeaseRepository, LeaseToken, _append_execution_change
from app.ir.hashing import canonical_json, content_address


COMPATIBILITY_POLICY = "FUND_ALL_ELSE_PRIORITY_GREEDY_NO_RESIZE"
TIE_BREAK_POLICY = "PRIORITY_SCORE_FRESHNESS_DEPLOYMENT_CANDIDATE_V1"
ACTIVE_RESERVATION_STATES = (
    "held", "submission_pending", "partially_consumed", "reconciliation_required",
)
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_INT32_MAX = 2_147_483_647
_INT64_MAX = 9_223_372_036_854_775_807


class CapitalAdmissionRefused(RuntimeError):
    """The proposed transaction did not obtain admission authority."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _identifier(kind: str, *parts: object) -> str:
    document = "\x00".join((kind, *(str(part) for part in parts)))
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def _exact_int(
        value: object, *, code: str, minimum: int | None = None,
        maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CapitalAdmissionRefused(code)
    if minimum is not None and value < minimum:
        raise CapitalAdmissionRefused(code)
    if maximum is not None and value > maximum:
        raise CapitalAdmissionRefused(code)
    return value


def _candidate_payload(candidate: "AdmissionCandidate", batch: "AdmissionBatch") -> dict:
    return {
        "schema": "strategy-os.candidate-intent/v1",
        "candidate_intent_id": candidate.candidate_intent_id,
        "owner_id": batch.owner_id,
        "broker_account_id": batch.broker_account_id,
        "book": batch.book,
        "currency": batch.currency,
        "fence_epoch": batch.fence_epoch,
        "deployment_id": candidate.deployment_id,
        "strategy_key": candidate.strategy_key,
        "strategy_version": candidate.strategy_version,
        "admission_address": candidate.admission_address,
        "graph_address": candidate.graph_address,
        "attribution_state": candidate.attribution_state,
        "signal_instrument_key": candidate.signal_instrument_key,
        "execution_instrument_key": candidate.execution_instrument_key,
        "product_address": candidate.product_address,
        "sizing_decision_address": candidate.sizing_decision_address,
        "target_position_request_id": candidate.target_position_request_id,
        "direction": candidate.direction,
        "purpose": candidate.purpose,
        "requested_quantity": candidate.requested_quantity,
        "required_capital_minor": candidate.required_capital_minor,
        "group_id": candidate.group_id,
        "group_semantics": candidate.group_semantics,
        "freshness_deadline": candidate.freshness_deadline.isoformat(timespec="microseconds"),
        "priority": candidate.priority,
        "score_scaled": candidate.score_scaled,
        "held_pending_digest": candidate.held_pending_digest,
        "created_at": candidate.created_at.isoformat(timespec="microseconds"),
    }


def _rank(candidate: "AdmissionCandidate", address: str) -> tuple:
    return (
        candidate.priority,
        -candidate.score_scaled,
        candidate.freshness_deadline,
        candidate.deployment_id,
        address,
    )


def _rank_document(candidate: "AdmissionCandidate", address: str) -> dict:
    return {
        "policy": TIE_BREAK_POLICY,
        "priority": candidate.priority,
        "score_scaled_desc": candidate.score_scaled,
        "freshness_deadline": candidate.freshness_deadline.isoformat(timespec="microseconds"),
        "deployment_id": candidate.deployment_id,
        "candidate_address": address,
    }


@dataclass(frozen=True)
class AdmissionCandidate:
    candidate_intent_id: str
    deployment_id: int
    strategy_key: str | None
    strategy_version: str | None
    admission_address: str | None
    graph_address: str | None
    attribution_state: str
    signal_instrument_key: str
    execution_instrument_key: str
    product_address: str
    sizing_decision_address: str
    target_position_request_id: str
    direction: str
    purpose: str
    requested_quantity: int
    required_capital_minor: int
    group_id: str
    group_semantics: str
    freshness_deadline: dt.datetime
    priority: int
    score_scaled: int
    held_pending_digest: str
    created_at: dt.datetime


@dataclass(frozen=True)
class AdmissionBatch:
    decision_batch_id: str
    owner_id: str
    broker_account_id: str
    book: str
    currency: str
    fence_epoch: int
    decision_at: dt.datetime
    effective_at: dt.datetime
    capital_snapshot_minor: int
    capital_snapshot_address: str
    margin_available_minor: int
    margin_source: str
    margin_observed_at: dt.datetime
    margin_snapshot_address: str
    safety_buffer_minor: int
    expected_head_revision: int
    product_policy_address: str
    sizing_policy_address: str
    portfolio_policy_address: str
    candidates: tuple[AdmissionCandidate, ...]
    reservation_ttl_seconds: int = 60
    contention_policy: str = COMPATIBILITY_POLICY
    tie_break_policy: str = TIE_BREAK_POLICY

    def candidate_address(self, candidate: AdmissionCandidate) -> str:
        return content_address(_candidate_payload(candidate, self))

    @property
    def candidate_set_digest(self) -> str:
        addresses = sorted(self.candidate_address(candidate) for candidate in self.candidates)
        return hashlib.sha256(canonical_json(addresses).encode("utf-8")).hexdigest()

    @property
    def batch_address(self) -> str:
        return content_address({
            "schema": "strategy-os.capital-admission-batch/v1",
            "decision_batch_id": self.decision_batch_id,
            "owner_id": self.owner_id,
            "broker_account_id": self.broker_account_id,
            "book": self.book,
            "currency": self.currency,
            "fence_epoch": self.fence_epoch,
            "decision_at": self.decision_at.isoformat(timespec="microseconds"),
            "effective_at": self.effective_at.isoformat(timespec="microseconds"),
            "capital_snapshot_minor": self.capital_snapshot_minor,
            "capital_snapshot_address": self.capital_snapshot_address,
            "margin_available_minor": self.margin_available_minor,
            "margin_source": self.margin_source,
            "margin_observed_at": self.margin_observed_at.isoformat(timespec="microseconds"),
            "margin_snapshot_address": self.margin_snapshot_address,
            "safety_buffer_minor": self.safety_buffer_minor,
            "expected_head_revision": self.expected_head_revision,
            "product_policy_address": self.product_policy_address,
            "sizing_policy_address": self.sizing_policy_address,
            "portfolio_policy_address": self.portfolio_policy_address,
            "candidate_set_digest": self.candidate_set_digest,
            "contention_policy": self.contention_policy,
            "tie_break_policy": self.tie_break_policy,
            "reservation_ttl_seconds": self.reservation_ttl_seconds,
        })


@dataclass(frozen=True)
class AdmissionDecision:
    candidate_intent_id: str
    status: str
    admitted_quantity: int
    held_capital_minor: int
    reason_code: str
    reservation_id: str | None


@dataclass(frozen=True)
class AdmissionResult:
    decision_batch_id: str
    batch_address: str
    head_revision: int
    decisions: tuple[AdmissionDecision, ...]
    duplicate: bool = False


def _validate(batch: AdmissionBatch, token: LeaseToken) -> None:
    if (batch.owner_id, batch.broker_account_id, batch.fence_epoch) != (
            token.owner_id, token.broker_account_id, token.fence_epoch):
        raise CapitalAdmissionRefused("LEASE_SCOPE_MISMATCH")
    if not batch.decision_batch_id or len(batch.decision_batch_id) > 64:
        raise CapitalAdmissionRefused("INVALID_BATCH_ID")
    if batch.book not in {"paper", "live"} or batch.currency != batch.currency.upper() \
            or len(batch.currency) != 3:
        raise CapitalAdmissionRefused("INVALID_SCOPE")
    _exact_int(batch.fence_epoch, code="INVALID_REVISION",
               minimum=1, maximum=_INT32_MAX)
    _exact_int(batch.expected_head_revision, code="INVALID_REVISION",
               minimum=0, maximum=_INT32_MAX)
    for address in (
            batch.capital_snapshot_address, batch.margin_snapshot_address,
            batch.product_policy_address, batch.sizing_policy_address,
            batch.portfolio_policy_address):
        if not _ADDRESS.fullmatch(address):
            raise CapitalAdmissionRefused("INVALID_EVIDENCE_ADDRESS")
    for value in (batch.capital_snapshot_minor, batch.margin_available_minor,
                  batch.safety_buffer_minor):
        _exact_int(value, code="INVALID_MONEY", minimum=0, maximum=_INT64_MAX)
    if not batch.margin_source or len(batch.margin_source) > 64:
        raise CapitalAdmissionRefused("INVALID_MARGIN_SOURCE")
    for value in (batch.decision_at, batch.effective_at, batch.margin_observed_at):
        if not isinstance(value, dt.datetime) or value.tzinfo is not None:
            raise CapitalAdmissionRefused("INVALID_TIMESTAMP")
    if batch.contention_policy != COMPATIBILITY_POLICY \
            or batch.tie_break_policy != TIE_BREAK_POLICY:
        raise CapitalAdmissionRefused("UNSUPPORTED_POLICY")
    _exact_int(batch.reservation_ttl_seconds, code="INVALID_BATCH_SHAPE",
               minimum=1, maximum=3600)
    if not batch.candidates:
        raise CapitalAdmissionRefused("INVALID_BATCH_SHAPE")
    ids: set[str] = set()
    addresses: set[str] = set()
    group_semantics: dict[str, str] = {}
    for candidate in batch.candidates:
        if not candidate.candidate_intent_id or len(candidate.candidate_intent_id) > 64 \
                or candidate.candidate_intent_id in ids:
            raise CapitalAdmissionRefused("DUPLICATE_CANDIDATE")
        ids.add(candidate.candidate_intent_id)
        if candidate.direction not in {"LONG", "SHORT"} \
                or candidate.purpose not in {"ENTRY", "TARGET_ADJUSTMENT", "RISK_REDUCTION"} \
                or candidate.group_semantics not in {"INDEPENDENT", "ATOMIC", "RESIZABLE"}:
            raise CapitalAdmissionRefused("INVALID_CANDIDATE")
        _exact_int(candidate.deployment_id, code="INVALID_CANDIDATE",
                   minimum=1, maximum=_INT32_MAX)
        requested = _exact_int(
            candidate.requested_quantity, code="INVALID_CANDIDATE",
            minimum=-_INT32_MAX, maximum=_INT32_MAX)
        if requested == 0:
            raise CapitalAdmissionRefused("INVALID_CANDIDATE")
        _exact_int(candidate.required_capital_minor, code="INVALID_CANDIDATE",
                   minimum=0, maximum=_INT64_MAX)
        _exact_int(candidate.priority, code="INVALID_CANDIDATE",
                   minimum=0, maximum=_INT32_MAX)
        _exact_int(candidate.score_scaled, code="INVALID_CANDIDATE",
                   minimum=-_INT64_MAX, maximum=_INT64_MAX)
        if candidate.purpose != "RISK_REDUCTION" and candidate.required_capital_minor == 0:
            raise CapitalAdmissionRefused("CAPITAL_REQUIRED")
        if (candidate.direction == "LONG") != (candidate.requested_quantity > 0):
            raise CapitalAdmissionRefused("DIRECTION_QUANTITY_MISMATCH")
        if candidate.purpose == "RISK_REDUCTION" and candidate.required_capital_minor != 0:
            raise CapitalAdmissionRefused("RISK_REDUCTION_CAPITAL_MISMATCH")
        if candidate.purpose == "RISK_REDUCTION" \
                and candidate.group_semantics != "INDEPENDENT":
            raise CapitalAdmissionRefused("RISK_REDUCTION_MUST_BE_INDEPENDENT")
        if not _DIGEST.fullmatch(candidate.held_pending_digest):
            raise CapitalAdmissionRefused("INVALID_PENDING_DIGEST")
        if candidate.freshness_deadline.tzinfo is not None \
                or candidate.created_at.tzinfo is not None:
            raise CapitalAdmissionRefused("INVALID_TIMESTAMP")
        if not candidate.group_id and candidate.group_semantics != "INDEPENDENT":
            raise CapitalAdmissionRefused("GROUP_ID_REQUIRED")
        if candidate.group_id:
            previous = group_semantics.setdefault(
                candidate.group_id, candidate.group_semantics)
            if previous != candidate.group_semantics:
                raise CapitalAdmissionRefused("INCONSISTENT_GROUP_SEMANTICS")
        address = batch.candidate_address(candidate)
        if address in addresses:
            raise CapitalAdmissionRefused("DUPLICATE_CANDIDATE")
        addresses.add(address)
    if len({candidate.held_pending_digest for candidate in batch.candidates}) != 1:
        raise CapitalAdmissionRefused("INCONSISTENT_PENDING_DIGEST")


def _cash_minor(row: CapitalState) -> int:
    value = Decimal(str(row.cash)) * 100
    if not value.is_finite() or value != value.to_integral_value() or value < 0:
        raise CapitalAdmissionRefused("CAPITAL_STATE_NOT_EXACT_MINOR")
    return int(value)


def _intent_book(intent: ExecutionIntent) -> str:
    try:
        context = json.loads(intent.context_json or "{}")
    except (TypeError, ValueError):
        return "live"
    value = str(context.get("book") or context.get("mode") or "live").lower()
    return value if value in {"paper", "live"} else "live"


def _held_pending_state(
        session: Session, *, owner_id: str, broker_account_id: str,
        book: str, currency: str) -> tuple[str, int, tuple[str, ...]]:
    reservations = list(session.scalars(select(CapitalReservationRecord).where(
        CapitalReservationRecord.owner_id == owner_id,
        CapitalReservationRecord.broker_account_id == broker_account_id,
        CapitalReservationRecord.book == book,
        CapitalReservationRecord.currency == currency,
        CapitalReservationRecord.state.in_(ACTIVE_RESERVATION_STATES),
    ).order_by(CapitalReservationRecord.reservation_id)))
    commands = list(session.scalars(select(AccountExecutionCommand).where(
        AccountExecutionCommand.owner_id == owner_id,
        AccountExecutionCommand.broker_account_id == broker_account_id,
        AccountExecutionCommand.state.in_((
            "prepared", "processing", "sent_unknown", "acknowledged", "blocked",
        )),
        ~AccountExecutionCommand.kind.like("control_%"),
    ).order_by(AccountExecutionCommand.command_id)))
    intents = list(session.scalars(select(ExecutionIntent).where(
        ExecutionIntent.owner_id == owner_id,
        ExecutionIntent.broker_account_id == broker_account_id,
    ).order_by(ExecutionIntent.created_at, ExecutionIntent.client_intent_id)))
    intents = [row for row in intents if _intent_book(row) == book]
    events_by_intent: dict[str, list[ExecutionOrderEvent]] = {
        row.client_intent_id: [] for row in intents
    }
    if events_by_intent:
        events = session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.owner_id == owner_id,
            ExecutionOrderEvent.broker_account_id == broker_account_id,
            ExecutionOrderEvent.client_intent_id.in_(events_by_intent),
        ).order_by(ExecutionOrderEvent.id))
        for event in events:
            events_by_intent[event.client_intent_id].append(event)
    unresolved_intents = []
    for intent in intents:
        state = reduce_execution_events(
            intent, events_by_intent[intent.client_intent_id])
        if not state.terminal or state.reconciliation_required:
            unresolved_intents.append(intent)
    active_command_ids = {row.command_id for row in reservations if row.command_id}
    blockers = [f"intent:{row.client_intent_id}" for row in unresolved_intents]
    blockers.extend(
        f"command:{row.command_id}"
        for row in commands
        if row.state in {"sent_unknown", "blocked"}
        or row.command_id not in active_command_ids)
    document = {
        "reservations": [{
            "reservation_id": row.reservation_id,
            "reservation_address": row.reservation_address,
            "state": row.state,
            "remaining_minor": row.estimated_minor - row.consumed_minor,
            "remaining_quantity": abs(row.admitted_quantity) - row.consumed_quantity,
            "fence_epoch": row.fence_epoch,
            "command_id": row.command_id,
            "revision": row.revision,
        } for row in reservations],
        "commands": [{
            "command_id": row.command_id,
            "state": row.state,
            "kind": row.kind,
            "target_id": row.target_id,
            "request_digest": row.request_digest,
            "fence_epoch": row.fence_epoch,
        } for row in commands],
        "unresolved_intents": [{
            "client_intent_id": intent.client_intent_id,
            "deployment_id": intent.deployment_id,
            "broker": intent.broker,
            "account_scope": intent.account_scope,
            "connection_scope": intent.connection_scope,
            "broker_tag": intent.broker_tag,
            "intent": intent.intent,
            "instrument_key": intent.instrument_key,
            "tradingsymbol": intent.tradingsymbol,
            "exchange": intent.exchange,
            "side": intent.side,
            "product": intent.product,
            "order_type": intent.order_type,
            "requested_qty": intent.requested_qty,
            "limit_price": intent.limit_price,
            "decision_price": intent.decision_price,
            "signal_at": intent.signal_at.isoformat(timespec="microseconds")
                if intent.signal_at else None,
            "strategy_key": intent.strategy_key,
            "strategy_version": intent.strategy_version,
            "admission_address": intent.admission_address,
            "graph_address": intent.graph_address,
            "attribution_state": intent.attribution_state,
            "context_json": intent.context_json,
            "fence_epoch": intent.fence_epoch,
            "created_at": intent.created_at.isoformat(timespec="microseconds"),
            "events": [{
                "id": event.id,
                "source": event.source,
                "source_event_id": event.source_event_id,
                "kind": event.kind,
                "broker_order_id": event.broker_order_id,
                "broker_status": event.broker_status,
                "cumulative_filled_qty": event.cumulative_filled_qty,
                "avg_price": event.avg_price,
                "observed_at": event.observed_at.isoformat(timespec="microseconds"),
                "payload_json": event.payload_json,
                "anomaly": event.anomaly,
                "fence_epoch": event.fence_epoch,
            } for event in events_by_intent[intent.client_intent_id]],
        } for intent in unresolved_intents],
    }
    digest = hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
    active_minor = sum(row.estimated_minor - row.consumed_minor for row in reservations)
    return digest, active_minor, tuple(sorted(blockers))


def current_held_pending_digest(
        session: Session, *, owner_id: str, broker_account_id: str,
        book: str, currency: str) -> str:
    """Read the exact evidence digest that a proposed closed batch must carry."""
    return _held_pending_state(
        session, owner_id=owner_id, broker_account_id=broker_account_id,
        book=book, currency=currency,
    )[0]


def _load_duplicate(session: Session, batch: AdmissionBatch) -> AdmissionResult | None:
    stored = session.scalar(select(DecisionBatchRecord).where(or_(
        DecisionBatchRecord.decision_batch_id == batch.decision_batch_id,
        DecisionBatchRecord.batch_address == batch.batch_address,
    )))
    if stored is None:
        return None
    if stored.decision_batch_id != batch.decision_batch_id \
            or stored.batch_address != batch.batch_address:
        raise CapitalAdmissionRefused("CONFLICTING_DUPLICATE")
    decisions = list(session.scalars(select(PortfolioAdmissionDecisionRecord).where(
        PortfolioAdmissionDecisionRecord.batch_id == batch.decision_batch_id).order_by(
            PortfolioAdmissionDecisionRecord.candidate_intent_id)))
    expected_ids = sorted(candidate.candidate_intent_id for candidate in batch.candidates)
    if [row.candidate_intent_id for row in decisions] != expected_ids:
        raise CapitalAdmissionRefused("INCOMPLETE_DUPLICATE")
    admitted = [row for row in decisions if row.status in {"admitted", "resized"}]
    reservations = session.scalar(select(func.count()).select_from(CapitalReservationRecord).where(
        CapitalReservationRecord.batch_id == batch.decision_batch_id))
    expected_reservations = sum(row.held_capital_minor > 0 for row in admitted)
    if reservations != expected_reservations:
        raise CapitalAdmissionRefused("INCOMPLETE_DUPLICATE")
    return AdmissionResult(
        decision_batch_id=stored.decision_batch_id,
        batch_address=stored.batch_address,
        head_revision=stored.reservation_head_revision + 1,
        decisions=tuple(AdmissionDecision(
            row.candidate_intent_id, row.status, row.admitted_quantity,
            row.held_capital_minor, row.reason_code, row.reservation_id,
        ) for row in decisions),
        duplicate=True,
    )


def _assert_candidate_dependencies(session: Session, batch: AdmissionBatch) -> None:
    for candidate in batch.candidates:
        sizing = session.get(SizingDecisionRecord, candidate.sizing_decision_address)
        target = session.get(TargetPositionRequestRecord, candidate.target_position_request_id)
        if sizing is None or target is None or not sizing.accepted:
            raise CapitalAdmissionRefused("CANDIDATE_EVIDENCE_MISSING")
        if sizing.policy_address != batch.sizing_policy_address \
                or sizing.product_address != candidate.product_address \
                or sizing.admitted_quantity != abs(candidate.requested_quantity) \
                or sizing.required_capital_minor != candidate.required_capital_minor:
            raise CapitalAdmissionRefused("SIZING_EVIDENCE_MISMATCH")
        if (target.owner_id, target.broker_account_id, target.book) != (
                batch.owner_id, batch.broker_account_id, batch.book) \
                or target.deployment_id != candidate.deployment_id \
                or target.sizing_decision_address != candidate.sizing_decision_address \
                or target.product_address != candidate.product_address \
                or target.target_quantity != candidate.requested_quantity \
                or target.purpose != candidate.purpose:
            raise CapitalAdmissionRefused("TARGET_EVIDENCE_MISMATCH")
        if (target.strategy_key, target.strategy_version, target.admission_address,
                target.graph_address, target.attribution_state) != (
                candidate.strategy_key, candidate.strategy_version, candidate.admission_address,
                candidate.graph_address, candidate.attribution_state):
            raise CapitalAdmissionRefused("ATTRIBUTION_EVIDENCE_MISMATCH")
        if candidate.freshness_deadline < batch.effective_at:
            raise CapitalAdmissionRefused("STALE_CANDIDATE")


def _allocate(batch: AdmissionBatch, available_minor: int) -> dict[str, tuple[bool, str]]:
    """Allocate whole deterministic group units; compatibility never resizes."""
    risk_reductions = [candidate for candidate in batch.candidates
                       if candidate.purpose == "RISK_REDUCTION"]
    normal = [candidate for candidate in batch.candidates
              if candidate.purpose != "RISK_REDUCTION"]
    outcome = {candidate.candidate_intent_id: (True, "RISK_REDUCTION_AVAILABLE")
               for candidate in risk_reductions}
    units: list[tuple[tuple, int, tuple[AdmissionCandidate, ...]]] = []
    grouped: dict[tuple[str, str], list[AdmissionCandidate]] = {}
    for candidate in normal:
        if candidate.group_semantics == "RESIZABLE":
            outcome[candidate.candidate_intent_id] = (False, "RESIZE_NOT_AUTHORIZED")
            continue
        key = ((candidate.group_id or candidate.candidate_intent_id),
               candidate.group_semantics)
        grouped.setdefault(key, []).append(candidate)
    for (_group_id, semantics), members in grouped.items():
        if semantics == "ATOMIC":
            ordered_members = tuple(sorted(
                members, key=lambda candidate: _rank(
                    candidate, batch.candidate_address(candidate))))
            unit_rank = _rank(ordered_members[0], batch.candidate_address(ordered_members[0]))
            units.append((unit_rank, sum(row.required_capital_minor for row in members),
                          ordered_members))
        else:
            for candidate in members:
                units.append((_rank(candidate, batch.candidate_address(candidate)),
                              candidate.required_capital_minor, (candidate,)))
    units.sort(key=lambda row: row[0])
    remaining = available_minor
    for _unit_rank, cost, members in units:
        if cost <= remaining:
            remaining -= cost
            for candidate in members:
                outcome[candidate.candidate_intent_id] = (True, "ADMITTED")
        else:
            reason = "ATOMIC_GROUP_INSUFFICIENT_CAPITAL" if len(members) > 1 \
                else "INSUFFICIENT_CAPITAL"
            for candidate in members:
                outcome[candidate.candidate_intent_id] = (False, reason)
    return outcome


def admit_closed_batch(
        session: Session, leases: LeaseRepository, token: LeaseToken,
        batch: AdmissionBatch) -> AdmissionResult:
    """Persist one complete decision batch; never commit and never perform I/O."""
    _validate(batch, token)
    leases.bind_money_session(session, token)
    scope = (f"capital-admission:{batch.owner_id}:{batch.broker_account_id}:"
             f"{batch.book}:{batch.currency}")
    begin_after_clean_reads(session, scope=scope)
    with caller_owned_savepoint(session, scope=scope):
        leases.require_current_in_session(session, token, active=True, lock=True)
        head = session.scalar(locked_rows(select(CapitalReservationHead).where(
            CapitalReservationHead.owner_id == batch.owner_id,
            CapitalReservationHead.broker_account_id == batch.broker_account_id,
            CapitalReservationHead.book == batch.book,
            CapitalReservationHead.currency == batch.currency,
        ), session))
        if head is None:
            raise CapitalAdmissionRefused("RESERVATION_HEAD_MISSING")

        duplicate = _load_duplicate(session, batch)
        if duplicate is not None:
            return duplicate
        db_now = leases.database_time(session)
        if batch.decision_at > db_now or (
                batch.decision_at + dt.timedelta(
                    seconds=batch.reservation_ttl_seconds) <= db_now):
            raise CapitalAdmissionRefused("DECISION_TIME_INVALID")
        if head.revision != batch.expected_head_revision:
            raise CapitalAdmissionRefused("STALE_HEAD_REVISION")

        capital = session.get(CapitalState, (batch.broker_account_id, batch.book))
        if capital is None:
            raise CapitalAdmissionRefused("CAPITAL_STATE_MISSING")
        if _cash_minor(capital) != batch.capital_snapshot_minor:
            raise CapitalAdmissionRefused("CAPITAL_SNAPSHOT_STALE")
        _assert_candidate_dependencies(session, batch)

        pending_digest, active_minor, pending_blockers = _held_pending_state(
            session, owner_id=batch.owner_id,
            broker_account_id=batch.broker_account_id,
            book=batch.book, currency=batch.currency,
        )
        if any(candidate.held_pending_digest != pending_digest
               for candidate in batch.candidates):
            raise CapitalAdmissionRefused("HELD_PENDING_SNAPSHOT_STALE")
        if pending_blockers:
            raise CapitalAdmissionRefused("BROKER_RECONCILIATION_REQUIRED")
        available = max(0, min(batch.capital_snapshot_minor, batch.margin_available_minor)
                        - int(active_minor) - batch.safety_buffer_minor)
        allocation = _allocate(batch, available)
        now = batch.decision_at

        candidate_rows: list[CandidateIntentRecord] = []
        for candidate in batch.candidates:
            address = batch.candidate_address(candidate)
            collision = session.scalar(select(CandidateIntentRecord).where(or_(
                CandidateIntentRecord.candidate_intent_id == candidate.candidate_intent_id,
                CandidateIntentRecord.candidate_address == address,
            )))
            if collision is not None:
                raise CapitalAdmissionRefused("CANDIDATE_IDENTITY_CONFLICT")
            row = CandidateIntentRecord(
                candidate_intent_id=candidate.candidate_intent_id,
                candidate_address=address,
                owner_id=batch.owner_id, broker_account_id=batch.broker_account_id,
                book=batch.book, currency=batch.currency, fence_epoch=batch.fence_epoch,
                deployment_id=candidate.deployment_id,
                strategy_key=candidate.strategy_key, strategy_version=candidate.strategy_version,
                admission_address=candidate.admission_address,
                graph_address=candidate.graph_address,
                attribution_state=candidate.attribution_state,
                signal_instrument_key=candidate.signal_instrument_key,
                execution_instrument_key=candidate.execution_instrument_key,
                product_address=candidate.product_address,
                sizing_decision_address=candidate.sizing_decision_address,
                target_position_request_id=candidate.target_position_request_id,
                direction=candidate.direction, purpose=candidate.purpose,
                requested_quantity=candidate.requested_quantity,
                required_capital_minor=candidate.required_capital_minor,
                group_id=candidate.group_id, group_semantics=candidate.group_semantics,
                freshness_deadline=candidate.freshness_deadline,
                priority=candidate.priority, score_scaled=candidate.score_scaled,
                rank_json=canonical_json(_rank_document(candidate, address)),
                held_pending_digest=candidate.held_pending_digest,
                created_at=candidate.created_at,
            )
            session.add(row)
            candidate_rows.append(row)

        session.add(DecisionBatchRecord(
            decision_batch_id=batch.decision_batch_id,
            batch_address=batch.batch_address,
            owner_id=batch.owner_id, broker_account_id=batch.broker_account_id,
            book=batch.book, currency=batch.currency, fence_epoch=batch.fence_epoch,
            decision_at=batch.decision_at, effective_at=batch.effective_at,
            capital_snapshot_address=batch.capital_snapshot_address,
            margin_available_minor=batch.margin_available_minor,
            margin_source=batch.margin_source,
            margin_observed_at=batch.margin_observed_at,
            margin_snapshot_address=batch.margin_snapshot_address,
            active_reservation_minor=int(active_minor),
            safety_buffer_minor=batch.safety_buffer_minor,
            reservation_head_revision=head.revision,
            product_policy_address=batch.product_policy_address,
            sizing_policy_address=batch.sizing_policy_address,
            portfolio_policy_address=batch.portfolio_policy_address,
            candidate_set_digest=batch.candidate_set_digest,
            contention_policy=batch.contention_policy,
            tie_break_policy=batch.tie_break_policy,
            status="decided", refusal_reason="",
        ))

        head.revision += 1
        head.updated_at = now
        # These records deliberately have no ORM relationships.  Make each FK
        # layer durable inside the savepoint before constructing the next one.
        session.flush()

        decisions: list[AdmissionDecision] = []
        decision_rows: list[PortfolioAdmissionDecisionRecord] = []
        reservation_rows: list[CapitalReservationRecord] = []
        reservation_events: list[CapitalReservationEventRecord] = []
        for candidate in sorted(batch.candidates, key=lambda row: row.candidate_intent_id):
            admitted, reason = allocation[candidate.candidate_intent_id]
            held_minor = candidate.required_capital_minor if admitted else 0
            reservation_id = (_identifier("reservation", batch.batch_address,
                                          batch.candidate_address(candidate))
                              if held_minor > 0 else None)
            decision_id = _identifier("decision", batch.batch_address,
                                      batch.candidate_address(candidate))
            decision_document = {
                "schema": "strategy-os.portfolio-admission-decision/v1",
                "decision_id": decision_id,
                "batch_address": batch.batch_address,
                "candidate_address": batch.candidate_address(candidate),
                "status": "admitted" if admitted else "rejected",
                "requested_quantity": candidate.requested_quantity,
                "admitted_quantity": candidate.requested_quantity if admitted else 0,
                "held_capital_minor": held_minor,
                "reason_code": reason,
                "reservation_id": reservation_id,
            }
            decision_address = content_address(decision_document)
            decision_rows.append(PortfolioAdmissionDecisionRecord(
                decision_id=decision_id, decision_address=decision_address,
                batch_id=batch.decision_batch_id,
                candidate_intent_id=candidate.candidate_intent_id,
                status="admitted" if admitted else "rejected",
                requested_quantity=candidate.requested_quantity,
                admitted_quantity=candidate.requested_quantity if admitted else 0,
                required_capital_minor=candidate.required_capital_minor,
                held_capital_minor=held_minor, score_scaled=candidate.score_scaled,
                rank_json=canonical_json(_rank_document(
                    candidate, batch.candidate_address(candidate))),
                constraints_json=canonical_json({
                    "available_minor": available,
                    "active_reservation_minor": int(active_minor),
                    "policy": batch.contention_policy,
                }),
                reason_code=reason,
                explanation=("candidate admitted by the closed batch"
                             if admitted else "candidate rejected by the closed batch"),
                reservation_id=reservation_id,
            ))
            if reservation_id is not None:
                reservation_document = {
                    "schema": "strategy-os.capital-reservation/v1",
                    "reservation_id": reservation_id,
                    "decision_address": decision_address,
                    "owner_id": batch.owner_id,
                    "broker_account_id": batch.broker_account_id,
                    "book": batch.book, "currency": batch.currency,
                    "estimated_minor": held_minor,
                    "requested_quantity": candidate.requested_quantity,
                    "admitted_quantity": candidate.requested_quantity,
                    "fence_epoch": batch.fence_epoch,
                    "created_at": now.isoformat(timespec="microseconds"),
                }
                reservation_address = content_address(reservation_document)
                reservation_rows.append(CapitalReservationRecord(
                    reservation_id=reservation_id,
                    reservation_address=reservation_address,
                    owner_id=batch.owner_id, broker_account_id=batch.broker_account_id,
                    book=batch.book, currency=batch.currency,
                    batch_id=batch.decision_batch_id,
                    candidate_intent_id=candidate.candidate_intent_id,
                    decision_id=decision_id,
                    estimated_minor=held_minor, consumed_minor=0,
                    requested_quantity=candidate.requested_quantity,
                    admitted_quantity=candidate.requested_quantity,
                    consumed_quantity=0, state="held", fence_epoch=batch.fence_epoch,
                    created_at=now,
                    expires_at=now + dt.timedelta(seconds=batch.reservation_ttl_seconds),
                    command_id=None, last_reconciled_at=None, revision=0,
                ))
                event_id = _identifier("reservation-event", reservation_id, 0)
                event_document = {
                    "schema": "strategy-os.capital-reservation-event/v1",
                    "event_id": event_id, "reservation_address": reservation_address,
                    "revision": 0, "from_state": None, "to_state": "held",
                    "consumed_minor": 0, "consumed_quantity": 0,
                    "fence_epoch": batch.fence_epoch,
                    "evidence_address": batch.batch_address,
                    "reason_code": "BATCH_ADMISSION",
                    "occurred_at": now.isoformat(timespec="microseconds"),
                }
                reservation_events.append(CapitalReservationEventRecord(
                    event_id=event_id, event_address=content_address(event_document),
                    reservation_id=reservation_id, revision=0,
                    from_state=None, to_state="held", consumed_minor=0,
                    consumed_quantity=0, fence_epoch=batch.fence_epoch,
                    evidence_address=batch.batch_address,
                    reason_code="BATCH_ADMISSION", occurred_at=now,
                ))
            decisions.append(AdmissionDecision(
                candidate.candidate_intent_id,
                "admitted" if admitted else "rejected",
                candidate.requested_quantity if admitted else 0,
                held_minor, reason, reservation_id,
            ))

        session.add_all(decision_rows)
        session.flush()
        session.add_all(reservation_rows)
        session.flush()
        session.add_all(reservation_events)
        _append_execution_change(
            session, owner_id=batch.owner_id,
            broker_account_id=batch.broker_account_id,
            aggregate_type="capital_admission",
            aggregate_id=batch.decision_batch_id,
            event_type="execution.money.changed",
            producer_key=f"capital-admission:{batch.decision_batch_id}",
            payload={
                "projection": "capital_admission",
                "state": "decided",
                "batch_address": batch.batch_address,
                "fence_epoch": batch.fence_epoch,
                "head_revision": head.revision,
                "candidate_count": len(batch.candidates),
            },
        )
        session.flush()
        leases.require_current_in_session(session, token, active=True, lock=True)
        return AdmissionResult(
            batch.decision_batch_id, batch.batch_address, head.revision,
            tuple(decisions), duplicate=False,
        )


__all__ = [
    "ACTIVE_RESERVATION_STATES", "AdmissionBatch", "AdmissionCandidate",
    "AdmissionDecision", "AdmissionResult", "CapitalAdmissionRefused",
    "COMPATIBILITY_POLICY", "TIE_BREAK_POLICY", "admit_closed_batch",
    "current_held_pending_digest",
]
