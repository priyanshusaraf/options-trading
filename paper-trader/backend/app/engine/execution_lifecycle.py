"""Durable entry-intent persistence and pure observation reduction.

This module owns no broker connection.  It turns the immutable rows from the
execution lifecycle schema into a current view, and provides the small
transactional boundary used before an entry is submitted.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ExecutionIntent, ExecutionOrderEvent


_TERMINAL_STATUSES = frozenset({"COMPLETE", "CANCELLED", "REJECTED", "FAILED"})


def _canonical_json(value: Mapping[str, Any]) -> str:
    """Encode a JSON object deterministically for durable comparisons."""
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def make_intent_id() -> str:
    """Return a new 32-character client identity, independent of a broker."""
    return uuid.uuid4().hex


def make_broker_tag(client_intent_id: str) -> str:
    """Return the tag used to find this intent in a broker order book."""
    return f"pti-{client_intent_id[:16]}"


def _observation_value(payload: Mapping[str, Any], *names: str, default: Any) -> Any:
    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
    return default


def broker_observation_id(order_id: str, payload: dict) -> str:
    """Fingerprint the broker facts that identify one cumulative observation."""
    status = str(_observation_value(payload, "status", "broker_status", default="")).upper()
    filled = int(_observation_value(
        payload, "cumulative_filled_qty", "filled_qty", "filled_quantity", default=0))
    average = round(float(_observation_value(
        payload, "avg_price", "average_price", "average", default=0.0)), 6)
    reason = str(_observation_value(payload, "reason", "status_message", default=""))
    canonical = _canonical_json({
        "order_id": order_id,
        "status": status,
        "cumulative_filled_qty": filled,
        "avg_price": average,
        "reason": reason,
    })
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NewExecutionIntent:
    deployment_id: int
    broker: str
    account_scope: str
    connection_scope: str
    intent: str
    instrument_key: str
    tradingsymbol: str
    exchange: str
    side: str
    product: str | None
    order_type: str
    requested_qty: int
    limit_price: float | None
    decision_price: float | None
    signal_at: dt.datetime | None
    strategy_key: str | None
    strategy_version: str | None
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NewExecutionEvent:
    source: str
    source_event_id: str
    kind: str
    broker_order_id: str | None
    broker_status: str
    cumulative_filled_qty: int
    avg_price: float
    payload: Mapping[str, Any] = field(default_factory=dict)
    anomaly: str = ""


@dataclass(frozen=True)
class ExecutionState:
    client_intent_id: str
    status: str
    broker_order_id: str | None
    filled_qty: int
    avg_price: float
    remaining_qty: int
    terminal: bool
    reconciliation_required: bool
    anomalies: tuple[str, ...]
    signal_to_intent_ms: float | None
    intent_to_submit_ms: float | None
    submit_to_ack_ms: float | None
    ack_to_fill_ms: float | None
    slippage_amount: float | None
    slippage_bps: float | None
    booked_qty: int = 0
    protected_qty: int = 0
    last_fill_delta: int = 0
    last_fill_price: float | None = None


def _latency_ms(
    name: str,
    start: dt.datetime | None,
    end: dt.datetime | None,
    anomalies: list[str],
) -> float | None:
    if start is None or end is None:
        return None
    if end < start:
        anomalies.append(
            f"{name} timestamps regressed: {start.isoformat()} > {end.isoformat()}")
        return None
    return round((end - start).total_seconds() * 1000.0, 3)


def _intent_id(intent: ExecutionIntent | NewExecutionIntent,
               events: list[ExecutionOrderEvent]) -> str:
    value = getattr(intent, "client_intent_id", None)
    return str(value or (events[0].client_intent_id if events else ""))


def reduce_execution_events(
    intent: ExecutionIntent | NewExecutionIntent,
    events: Iterable[ExecutionOrderEvent],
) -> ExecutionState:
    """Derive one entry's current state from events in their insertion order.

    The reducer never repairs history.  Conflicting and stale observations stay in
    the event log, while this derived view preserves the safer prior fact and names
    the conflict for recovery or review.
    """
    rows = list(events)
    client_intent_id = _intent_id(intent, rows)
    requested_qty = int(intent.requested_qty)
    side = str(intent.side).upper()
    decision_price = intent.decision_price

    status = "PENDING"
    broker_order_id: str | None = None
    filled_qty = 0
    avg_price = 0.0
    terminal = False
    submit_seen = False
    acknowledged = False
    booked_qty = 0
    protected_qty = 0
    anomalies: list[str] = []
    seen_identities: set[tuple[str, str]] = set()
    intent_at: dt.datetime | None = None
    submit_at: dt.datetime | None = None
    acknowledged_at: dt.datetime | None = None
    first_fill_at: dt.datetime | None = None
    last_fill_delta = 0
    last_fill_price: float | None = None

    for row in rows:
        identity = (row.source, row.source_event_id)
        if identity in seen_identities:
            continue
        seen_identities.add(identity)

        kind = row.kind.upper()
        observed_at = row.observed_at
        row_status = (row.broker_status or "").upper()
        if row.anomaly:
            anomalies.append(row.anomaly)

        if kind == "INTENT_CREATED" and intent_at is None:
            intent_at = observed_at
        if kind == "SUBMIT_STARTED":
            submit_seen = True
            if submit_at is None:
                submit_at = observed_at
        if kind == "ACKNOWLEDGED":
            acknowledged = True
            if acknowledged_at is None:
                acknowledged_at = observed_at
        if kind == "POSITION_BOOKED":
            booked_qty = max(booked_qty, row.cumulative_filled_qty)
        if kind == "POSITION_PROTECTED":
            protected_qty = max(protected_qty, row.cumulative_filled_qty)

        if row.broker_order_id:
            if broker_order_id is None:
                broker_order_id = row.broker_order_id
            elif broker_order_id != row.broker_order_id:
                anomalies.append(
                    f"broker order ID changed from {broker_order_id} to {row.broker_order_id}")

        if kind in {
            "POSITION_BOOKED", "POSITION_PROTECTED",
            "PROTECTION_SUBMIT_STARTED", "PROTECTION_NOT_FOUND",
            "PROTECTION_RETRY_ALLOWED",
        }:
            continue

        if row.cumulative_filled_qty < filled_qty:
            anomalies.append(
                f"lower cumulative fill {row.cumulative_filled_qty} after {filled_qty}")
        elif row.cumulative_filled_qty > filled_qty:
            previous_qty = filled_qty
            previous_avg = avg_price
            filled_qty = row.cumulative_filled_qty
            avg_price = row.avg_price
            if previous_qty == 0 and first_fill_at is None:
                first_fill_at = observed_at
            last_fill_delta = filled_qty - previous_qty
            last_fill_price = round(
                ((filled_qty * avg_price) - (previous_qty * previous_avg)) / last_fill_delta, 8)

        next_status = row_status or kind
        next_terminal = row_status in _TERMINAL_STATUSES or kind in _TERMINAL_STATUSES
        if terminal:
            if next_status and next_status != status:
                anomalies.append(f"terminal order cannot reopen as {next_status}")
            continue

        status = next_status
        if next_terminal:
            terminal = True

    unbooked_fill = filled_qty > booked_qty
    unprotected_fill = filled_qty > protected_qty
    reconciliation_required = (
        unbooked_fill or unprotected_fill or (submit_seen and not terminal))
    remaining_qty = max(0, requested_qty - filled_qty)
    slippage_amount: float | None = None
    slippage_bps: float | None = None
    if filled_qty and decision_price is not None and decision_price != 0:
        slippage_amount = round(avg_price - decision_price if side == "BUY"
                                else decision_price - avg_price, 8)
        slippage_bps = round(slippage_amount / decision_price * 10_000.0, 8)
    signal_to_intent_ms = _latency_ms(
        "signal_to_intent", intent.signal_at, intent_at, anomalies)
    intent_to_submit_ms = _latency_ms("intent_to_submit", intent_at, submit_at, anomalies)
    submit_to_ack_ms = _latency_ms("submit_to_ack", submit_at, acknowledged_at, anomalies)
    ack_to_fill_ms = _latency_ms("ack_to_fill", acknowledged_at, first_fill_at, anomalies)

    return ExecutionState(
        client_intent_id=client_intent_id,
        status=status,
        broker_order_id=broker_order_id,
        filled_qty=filled_qty,
        avg_price=avg_price,
        remaining_qty=remaining_qty,
        terminal=terminal,
        reconciliation_required=reconciliation_required,
        anomalies=tuple(anomalies),
        signal_to_intent_ms=signal_to_intent_ms,
        intent_to_submit_ms=intent_to_submit_ms,
        submit_to_ack_ms=submit_to_ack_ms,
        ack_to_fill_ms=ack_to_fill_ms,
        slippage_amount=slippage_amount,
        slippage_bps=slippage_bps,
        booked_qty=booked_qty,
        protected_qty=protected_qty,
        last_fill_delta=last_fill_delta,
        last_fill_price=last_fill_price,
    )


class ExecutionLifecycleStore:
    """Commit immutable lifecycle facts with explicit, retry-safe collision handling."""

    def __init__(self, session: Session):
        self.session = session

    def create_intent(
        self,
        request: NewExecutionIntent,
        context: dict,
        now: dt.datetime,
    ) -> ExecutionIntent:
        for attempt in range(3):
            client_intent_id = make_intent_id()
            row = ExecutionIntent(
                client_intent_id=client_intent_id,
                deployment_id=request.deployment_id,
                broker=request.broker,
                account_scope=request.account_scope,
                connection_scope=request.connection_scope,
                broker_tag=make_broker_tag(client_intent_id),
                intent=request.intent,
                instrument_key=request.instrument_key,
                tradingsymbol=request.tradingsymbol,
                exchange=request.exchange,
                side=request.side,
                product=request.product,
                order_type=request.order_type,
                requested_qty=request.requested_qty,
                limit_price=request.limit_price,
                decision_price=request.decision_price,
                signal_at=request.signal_at,
                strategy_key=request.strategy_key,
                strategy_version=request.strategy_version,
                context_json=_canonical_json(context),
                created_at=now,
            )
            self.session.add(row)
            self.session.add(ExecutionOrderEvent(
                client_intent_id=client_intent_id,
                source="engine",
                source_event_id="intent-created",
                kind="INTENT_CREATED",
                broker_order_id=None,
                broker_status="",
                cumulative_filled_qty=0,
                avg_price=0.0,
                observed_at=now,
                payload_json="{}",
                anomaly="",
            ))
            try:
                self.session.commit()
                return row
            except IntegrityError as exc:
                self.session.rollback()
                if not self._is_identity_collision(exc) or attempt == 2:
                    raise
            except Exception:
                self.session.rollback()
                raise
        raise AssertionError("unreachable")

    @staticmethod
    def _is_identity_collision(exc: IntegrityError) -> bool:
        """Only generated intent-id/tag collisions are safe to retry."""
        detail = str(getattr(exc, "orig", exc)).lower()
        identity_column = (
            "execution_intents.client_intent_id" in detail
            or "execution_intents.broker_tag" in detail
        )
        return identity_column and ("unique" in detail or "duplicate" in detail)

    def append_event(
        self,
        client_intent_id: str,
        event: NewExecutionEvent,
        now: dt.datetime,
    ) -> ExecutionOrderEvent:
        payload_json = _canonical_json(event.payload)
        row = ExecutionOrderEvent(
            client_intent_id=client_intent_id,
            source=event.source,
            source_event_id=event.source_event_id,
            kind=event.kind,
            broker_order_id=event.broker_order_id,
            broker_status=event.broker_status,
            cumulative_filled_qty=event.cumulative_filled_qty,
            avg_price=event.avg_price,
            observed_at=now,
            payload_json=payload_json,
            anomaly=event.anomaly,
        )
        self.session.add(row)
        try:
            self.session.commit()
            return row
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(ExecutionOrderEvent).where(
                    ExecutionOrderEvent.client_intent_id == client_intent_id,
                    ExecutionOrderEvent.source == event.source,
                    ExecutionOrderEvent.source_event_id == event.source_event_id,
                ))
            if existing is not None and self._same_event(existing, row):
                return existing
            if existing is not None:
                raise ValueError("event identity already exists with different content")
            raise
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _same_event(existing: ExecutionOrderEvent, candidate: ExecutionOrderEvent) -> bool:
        return (
            existing.kind == candidate.kind
            and existing.broker_order_id == candidate.broker_order_id
            and existing.broker_status == candidate.broker_status
            and existing.cumulative_filled_qty == candidate.cumulative_filled_qty
            and existing.avg_price == candidate.avg_price
            and existing.observed_at == candidate.observed_at
            and existing.payload_json == candidate.payload_json
            and existing.anomaly == candidate.anomaly
        )

    def state_for(self, client_intent_id: str) -> ExecutionState:
        intent = self.session.get(ExecutionIntent, client_intent_id)
        if intent is None:
            raise LookupError(f"unknown execution intent {client_intent_id}")
        events = list(self.session.scalars(
            select(ExecutionOrderEvent)
            .where(ExecutionOrderEvent.client_intent_id == client_intent_id)
            .order_by(ExecutionOrderEvent.id)))
        return reduce_execution_events(intent, events)

    def unresolved_entries(
        self,
        deployment_id: int,
        account_scope: str,
        connection_scope: str,
    ) -> list[ExecutionIntent]:
        intents = list(self.session.scalars(
            select(ExecutionIntent)
            .where(
                ExecutionIntent.deployment_id == deployment_id,
                ExecutionIntent.account_scope == account_scope,
                ExecutionIntent.connection_scope == connection_scope,
            )
            .order_by(ExecutionIntent.created_at, ExecutionIntent.client_intent_id)))
        if not intents:
            return []
        intent_ids = [intent.client_intent_id for intent in intents]
        events_by_intent: dict[str, list[ExecutionOrderEvent]] = {
            client_intent_id: [] for client_intent_id in intent_ids
        }
        events = self.session.scalars(
            select(ExecutionOrderEvent)
            .where(ExecutionOrderEvent.client_intent_id.in_(intent_ids))
            .order_by(ExecutionOrderEvent.id))
        for event in events:
            events_by_intent[event.client_intent_id].append(event)
        unresolved: list[ExecutionIntent] = []
        for intent in intents:
            state = reduce_execution_events(
                intent, events_by_intent[intent.client_intent_id])
            if not state.terminal or state.reconciliation_required:
                unresolved.append(intent)
        return unresolved


__all__ = [
    "ExecutionLifecycleStore",
    "ExecutionState",
    "NewExecutionEvent",
    "NewExecutionIntent",
    "broker_observation_id",
    "make_broker_tag",
    "make_intent_id",
    "reduce_execution_events",
]
