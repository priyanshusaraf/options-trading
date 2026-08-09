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
    intent_to_submit_ms: float | None
    submit_to_ack_ms: float | None
    ack_to_terminal_ms: float | None
    intent_to_terminal_ms: float | None
    slippage_amount: float | None
    slippage_bps: float | None
    last_fill_delta: int = 0
    last_fill_price: float | None = None


def _milliseconds(start: dt.datetime | None, end: dt.datetime | None) -> float | None:
    if start is None or end is None:
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
    anomalies: list[str] = []
    seen_identities: set[tuple[str, str]] = set()
    intent_at: dt.datetime | None = None
    submit_at: dt.datetime | None = None
    acknowledged_at: dt.datetime | None = None
    terminal_at: dt.datetime | None = None
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

        if row.broker_order_id:
            if broker_order_id is None:
                broker_order_id = row.broker_order_id
            elif broker_order_id != row.broker_order_id:
                anomalies.append(
                    f"broker order ID changed from {broker_order_id} to {row.broker_order_id}")

        if row.cumulative_filled_qty < filled_qty:
            anomalies.append(
                f"lower cumulative fill {row.cumulative_filled_qty} after {filled_qty}")
        elif row.cumulative_filled_qty > filled_qty:
            previous_qty = filled_qty
            previous_avg = avg_price
            filled_qty = row.cumulative_filled_qty
            avg_price = row.avg_price
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
            terminal_at = observed_at

    reconciliation_required = submit_seen and not acknowledged
    remaining_qty = max(0, requested_qty - filled_qty)
    slippage_amount: float | None = None
    slippage_bps: float | None = None
    if filled_qty and decision_price is not None and decision_price != 0:
        slippage_amount = round(avg_price - decision_price if side == "BUY"
                                else decision_price - avg_price, 8)
        slippage_bps = round(slippage_amount / decision_price * 10_000.0, 8)

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
        intent_to_submit_ms=_milliseconds(intent_at, submit_at),
        submit_to_ack_ms=_milliseconds(submit_at, acknowledged_at),
        ack_to_terminal_ms=_milliseconds(acknowledged_at, terminal_at),
        intent_to_terminal_ms=_milliseconds(intent_at, terminal_at),
        slippage_amount=slippage_amount,
        slippage_bps=slippage_bps,
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
        self.session.commit()
        return row

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
        return [intent for intent in intents if not self.state_for(intent.client_intent_id).terminal]


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
