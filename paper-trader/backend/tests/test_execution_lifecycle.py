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


def test_latency_uses_persisted_signal_intent_submit_ack_and_first_fill_times():
    state = reduce_execution_events(_request(signal_at=BASE_TIME), [
        _row("intent-1", _event("INTENT_CREATED", source_event_id="intent", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME + dt.timedelta(milliseconds=100)),
        _row("intent-1", _event("SUBMIT_STARTED", source_event_id="submit", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME + dt.timedelta(milliseconds=200)),
        _row("intent-1", _event("ACKNOWLEDGED", source_event_id="ack", observed_at=BASE_TIME,
                                 source="engine", broker_order_id="order-1"),
             BASE_TIME + dt.timedelta(milliseconds=300)),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="partial", observed_at=BASE_TIME,
                                 broker_status="OPEN", cumulative_filled_qty=25,
                                 avg_price=100), BASE_TIME + dt.timedelta(milliseconds=400)),
    ])

    assert state.signal_to_intent_ms == 100.0
    assert state.intent_to_submit_ms == 100.0
    assert state.submit_to_ack_ms == 100.0
    assert state.ack_to_fill_ms == 100.0
    assert not hasattr(state, "ack_to_terminal_ms")
    assert not hasattr(state, "intent_to_terminal_ms")


def test_latency_ignores_rejection_and_returns_none_for_regressed_timestamps():
    intent_at = BASE_TIME + dt.timedelta(seconds=2)
    ack_at = BASE_TIME + dt.timedelta(seconds=1)
    state = reduce_execution_events(_request(signal_at=BASE_TIME + dt.timedelta(seconds=3)), [
        _row("intent-1", _event("INTENT_CREATED", source_event_id="intent", observed_at=BASE_TIME,
                                 source="engine"), intent_at),
        _row("intent-1", _event("SUBMIT_STARTED", source_event_id="submit", observed_at=BASE_TIME,
                                 source="engine"), BASE_TIME),
        _row("intent-1", _event("ACKNOWLEDGED", source_event_id="ack", observed_at=BASE_TIME,
                                 source="engine", broker_order_id="order-1"), ack_at),
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="rejected", observed_at=BASE_TIME,
                                 broker_status="REJECTED"), BASE_TIME + dt.timedelta(seconds=3)),
    ])

    assert state.signal_to_intent_ms is None
    assert state.intent_to_submit_ms is None
    assert state.submit_to_ack_ms == 1000.0
    assert state.ack_to_fill_ms is None
    assert f"signal_to_intent timestamps regressed: {(BASE_TIME + dt.timedelta(seconds=3)).isoformat()} > {intent_at.isoformat()}" in state.anomalies
    assert f"intent_to_submit timestamps regressed: {intent_at.isoformat()} > {BASE_TIME.isoformat()}" in state.anomalies


def test_sell_adverse_slippage_is_positive():
    state = reduce_execution_events(_request(side="SELL", decision_price=100.0), [
        _row("intent-1", _event("STATUS_OBSERVED", source_event_id="complete", observed_at=BASE_TIME,
                                 broker_status="COMPLETE", cumulative_filled_qty=100,
                                 avg_price=98.5), BASE_TIME),
    ])

    assert state.slippage_amount == 1.5
    assert state.slippage_bps == 150.0


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


@pytest.mark.parametrize(
    ("change", "now"),
    [
        ({"kind": "ACKNOWLEDGED"}, BASE_TIME),
        ({"broker_order_id": "order-2"}, BASE_TIME),
        ({"broker_status": "COMPLETE"}, BASE_TIME),
        ({"cumulative_filled_qty": 1}, BASE_TIME),
        ({"avg_price": 100.5}, BASE_TIME),
        ({"payload": {"changed": True}}, BASE_TIME),
        ({"anomaly": "changed"}, BASE_TIME),
        ({}, BASE_TIME + dt.timedelta(microseconds=1)),
    ],
)
def test_store_rejects_collision_when_any_durable_field_differs(tmp_path, change, now):
    session = _session(tmp_path)
    store = ExecutionLifecycleStore(session)
    intent = store.create_intent(_request(), {}, BASE_TIME)
    store.append_event(intent.client_intent_id, _event(
        "STATUS_OBSERVED", source_event_id="obs-1", observed_at=BASE_TIME,
        broker_order_id="order-1", broker_status="OPEN", cumulative_filled_qty=0,
        avg_price=100.0, payload={"same": True}, anomaly="original",
    ), BASE_TIME)

    values = {
        "kind": "STATUS_OBSERVED",
        "source_event_id": "obs-1",
        "observed_at": BASE_TIME,
        "broker_order_id": "order-1",
        "broker_status": "OPEN",
        "cumulative_filled_qty": 0,
        "avg_price": 100.0,
        "payload": {"same": True},
        "anomaly": "original",
    }
    values.update(change)
    with pytest.raises(ValueError, match="different content"):
        store.append_event(intent.client_intent_id, _event(**values), now)


def test_create_intent_rolls_back_after_commit_failure_and_can_write_later(tmp_path, monkeypatch):
    session = _session(tmp_path)
    store = ExecutionLifecycleStore(session)
    original_commit = session.commit

    def fail_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="database unavailable"):
        store.create_intent(_request(), {}, BASE_TIME)

    assert session.in_transaction() is False
    monkeypatch.setattr(session, "commit", original_commit)
    intent = store.create_intent(_request(), {}, BASE_TIME)
    assert intent.client_intent_id


def test_append_event_rolls_back_after_commit_failure_and_can_write_later(tmp_path, monkeypatch):
    session = _session(tmp_path)
    store = ExecutionLifecycleStore(session)
    intent = store.create_intent(_request(), {}, BASE_TIME)
    original_commit = session.commit

    def fail_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="database unavailable"):
        store.append_event(intent.client_intent_id, _event(
            "INTENT_CREATED", source_event_id="intent", observed_at=BASE_TIME, source="engine"),
            BASE_TIME)

    assert session.in_transaction() is False
    monkeypatch.setattr(session, "commit", original_commit)
    event = store.append_event(intent.client_intent_id, _event(
        "INTENT_CREATED", source_event_id="intent", observed_at=BASE_TIME, source="engine"),
        BASE_TIME)
    assert event.id is not None


@pytest.mark.parametrize("count", [1, 3, 5])
def test_unresolved_entries_scope_on_all_three_fields_and_use_two_queries(tmp_path, count):
    session = _session(tmp_path)
    store = ExecutionLifecycleStore(session)
    scoped = [
        store.create_intent(_request(), {}, BASE_TIME + dt.timedelta(seconds=index))
        for index in range(count)
    ]
    terminal = store.create_intent(_request(), {}, BASE_TIME + dt.timedelta(seconds=4))
    different_account = store.create_intent(_request(account_scope="account.other"), {}, BASE_TIME)
    different_connection = store.create_intent(
        _request(connection_scope="kite:other"), {}, BASE_TIME)
    for intent in scoped[: max(0, count - 1)]:
        store.append_event(intent.client_intent_id, _event(
            "STATUS_OBSERVED", source_event_id=f"open-{intent.client_intent_id}",
            observed_at=BASE_TIME, broker_status="OPEN"), BASE_TIME)
    store.append_event(terminal.client_intent_id, _event(
        "STATUS_OBSERVED", source_event_id="complete", observed_at=BASE_TIME,
        broker_status="COMPLETE", cumulative_filled_qty=100, avg_price=100), BASE_TIME)
    store.append_event(different_account.client_intent_id, _event(
        "STATUS_OBSERVED", source_event_id="other-account", observed_at=BASE_TIME,
        broker_status="OPEN"), BASE_TIME)
    store.append_event(different_connection.client_intent_id, _event(
        "STATUS_OBSERVED", source_event_id="other-connection", observed_at=BASE_TIME,
        broker_status="OPEN"), BASE_TIME)

    statements: list[str] = []

    @sa.event.listens_for(session.get_bind(), "before_cursor_execute")
    def count_queries(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    try:
        unresolved = store.unresolved_entries(1, "account.default", "kite:legacy")
    finally:
        sa.event.remove(session.get_bind(), "before_cursor_execute", count_queries)

    assert [intent.client_intent_id for intent in unresolved] == [
        intent.client_intent_id for intent in scoped
    ]
    assert len(statements) == 2


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
