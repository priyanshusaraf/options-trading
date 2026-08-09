"""Reducer and persistence contract for immutable entry observations."""
from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Deployment, ExecutionOrderEvent
from app.engine.execution_lifecycle import (
    ExecutionLifecycleStore,
    NewExecutionEvent,
    NewExecutionIntent,
    broker_observation_id,
    make_broker_tag,
    make_intent_id,
    reduce_execution_events,
)


BASE_TIME = dt.datetime(2026, 8, 9, 9, 15)


def _session(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'execution-lifecycle.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = Session()
    session.add(Deployment(id=1, name="default"))
    session.commit()
    return session


def _request(**changes) -> NewExecutionIntent:
    values = {
        "deployment_id": 1,
        "broker": "kite",
        "account_scope": "account.default",
        "connection_scope": "kite:legacy",
        "intent": "ENTRY",
        "instrument_key": "NSE_EQ|INE002A01018",
        "tradingsymbol": "RELIANCE",
        "exchange": "NSE",
        "side": "BUY",
        "product": "MIS",
        "order_type": "MARKET",
        "requested_qty": 100,
        "limit_price": None,
        "decision_price": 99.0,
        "signal_at": BASE_TIME,
        "strategy_key": "mean-revert",
        "strategy_version": "v1",
        "context": {"setup": "test"},
    }
    values.update(changes)
    return NewExecutionIntent(**values)


def _event(kind: str, *, source_event_id: str, observed_at: dt.datetime,
           broker_order_id: str | None = None, broker_status: str = "",
           cumulative_filled_qty: int = 0, avg_price: float = 0.0,
           source: str = "broker", payload: dict | None = None,
           anomaly: str = "") -> NewExecutionEvent:
    return NewExecutionEvent(
        source=source,
        source_event_id=source_event_id,
        kind=kind,
        broker_order_id=broker_order_id,
        broker_status=broker_status,
        cumulative_filled_qty=cumulative_filled_qty,
        avg_price=avg_price,
        payload={} if payload is None else payload,
        anomaly=anomaly,
    )


def _row(intent_id: str, event: NewExecutionEvent, observed_at: dt.datetime) -> ExecutionOrderEvent:
    return ExecutionOrderEvent(
        client_intent_id=intent_id,
        source=event.source,
        source_event_id=event.source_event_id,
        kind=event.kind,
        broker_order_id=event.broker_order_id,
        broker_status=event.broker_status,
        cumulative_filled_qty=event.cumulative_filled_qty,
        avg_price=event.avg_price,
        observed_at=observed_at,
        payload_json="{}",
        anomaly=event.anomaly,
    )


def test_duplicate_source_event_is_idempotent():
    event = _event("ACKNOWLEDGED", source_event_id="ack-1", observed_at=BASE_TIME,
                   broker_order_id="order-1")

    state = reduce_execution_events(_request(), [
        _row("intent-1", event, BASE_TIME), _row("intent-1", event, BASE_TIME),
    ])

    assert state.broker_order_id == "order-1"
    assert state.anomalies == ()


def test_out_of_order_lower_fill_cannot_reduce_quantity():
    state = reduce_execution_events(_request(), [
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="75", observed_at=BASE_TIME,
                                 cumulative_filled_qty=75, avg_price=102), BASE_TIME),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="25", observed_at=BASE_TIME,
                                 cumulative_filled_qty=25, avg_price=100), BASE_TIME),
    ])

    assert state.filled_qty == 75
    assert state.remaining_qty == 25
    assert state.avg_price == 102
    assert "lower cumulative fill 25 after 75" in state.anomalies


def test_terminal_order_cannot_reopen():
    state = reduce_execution_events(_request(), [
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="complete", observed_at=BASE_TIME,
                                 broker_status="COMPLETE", cumulative_filled_qty=100,
                                 avg_price=101), BASE_TIME),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="open", observed_at=BASE_TIME,
                                 broker_status="OPEN", cumulative_filled_qty=100,
                                 avg_price=101), BASE_TIME),
    ])

    assert state.status == "COMPLETE"
    assert state.terminal is True
    assert "terminal order cannot reopen as OPEN" in state.anomalies


def test_broker_order_id_cannot_change_after_ack():
    state = reduce_execution_events(_request(), [
        _row("intent-1", _event("ACKNOWLEDGED", source_event_id="ack", observed_at=BASE_TIME,
                                 broker_order_id="order-1"), BASE_TIME),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="status", observed_at=BASE_TIME,
                                 broker_order_id="order-2", broker_status="OPEN"), BASE_TIME),
    ])

    assert state.broker_order_id == "order-1"
    assert "broker order ID changed from order-1 to order-2" in state.anomalies


def test_two_partial_observations_derive_vwap_remaining_and_new_fill_delta():
    state = reduce_execution_events(_request(), [
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="25", observed_at=BASE_TIME,
                                 cumulative_filled_qty=25, avg_price=100), BASE_TIME),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="75",
                                 observed_at=BASE_TIME + dt.timedelta(seconds=1),
                                 cumulative_filled_qty=75, avg_price=102),
             BASE_TIME + dt.timedelta(seconds=1)),
    ])

    assert state.filled_qty == 75
    assert state.avg_price == 102
    assert state.remaining_qty == 25
    assert state.last_fill_delta == 50
    assert state.last_fill_price == 103


def test_submit_started_without_ack_requires_reconciliation():
    state = reduce_execution_events(_request(), [
        _row("intent-1", _event("INTENT_CREATED", source_event_id="intent", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME),
        _row("intent-1", _event("SUBMIT_STARTED", source_event_id="submit", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME),
    ])

    assert state.status == "SUBMIT_STARTED"
    assert state.reconciliation_required is True


def test_realised_slippage_uses_intent_decision_price():
    state = reduce_execution_events(_request(decision_price=100.0), [
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="complete", observed_at=BASE_TIME,
                                 broker_status="COMPLETE", cumulative_filled_qty=100,
                                 avg_price=101.5), BASE_TIME),
    ])

    assert state.slippage_amount == 1.5
    assert state.slippage_bps == 150.0


def test_latency_uses_persisted_event_times():
    state = reduce_execution_events(_request(), [
        _row("intent-1", _event("INTENT_CREATED", source_event_id="intent", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME),
        _row("intent-1", _event("SUBMIT_STARTED", source_event_id="submit", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME + dt.timedelta(milliseconds=200)),
        _row("intent-1", _event("ACKNOWLEDGED", source_event_id="ack", observed_at=BASE_TIME,
                                 source="engine", broker_order_id="order-1"),
             BASE_TIME + dt.timedelta(milliseconds=500)),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="complete", observed_at=BASE_TIME,
                                 broker_status="COMPLETE", cumulative_filled_qty=100,
                                 avg_price=100), BASE_TIME + dt.timedelta(milliseconds=900)),
    ])

    assert state.intent_to_submit_ms == 200.0
    assert state.submit_to_ack_ms == 300.0
    assert state.ack_to_terminal_ms == 400.0
    assert state.intent_to_terminal_ms == 900.0


def test_store_canonicalizes_json_and_rejects_identity_collisions(tmp_path):
    session = _session(tmp_path)
    store = ExecutionLifecycleStore(session)
    intent = store.create_intent(_request(context={"b": 2, "a": 1}), {"b": 2, "a": 1}, BASE_TIME)
    event = _event("STATUS_OBSERVED", source_event_id="obs-1", observed_at=BASE_TIME,
                   broker_status="OPEN", payload={"b": 2, "a": 1})

    original = store.append_event(intent.client_intent_id, event, BASE_TIME)
    repeated = store.append_event(
        intent.client_intent_id,
        _event("STATUS_OBSERVED", source_event_id="obs-1", observed_at=BASE_TIME,
               broker_status="OPEN", payload={"a": 1, "b": 2}),
        BASE_TIME,
    )

    assert intent.context_json == '{"a":1,"b":2}'
    assert original.id == repeated.id
    with pytest.raises(ValueError, match="different content"):
        store.append_event(
            intent.client_intent_id,
            _event("STATUS_OBSERVED", source_event_id="obs-1", observed_at=BASE_TIME,
                   broker_status="COMPLETE", payload={"a": 1, "b": 2}),
            BASE_TIME,
        )


def test_identifiers_follow_the_entry_lifecycle_contract():
    intent_id = make_intent_id()

    assert len(intent_id) == 32
    assert make_broker_tag(intent_id) == f"pti-{intent_id[:16]}"
    assert broker_observation_id("order-1", {
        "status": "complete", "filled_qty": "5", "average_price": 100.1234567,
        "status_message": "done",
    }) == broker_observation_id("order-1", {
        "average_price": 100.12345671, "filled_quantity": 5, "status": "COMPLETE",
        "reason": "done",
    })
