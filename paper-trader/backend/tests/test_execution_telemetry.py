"""Persisted-fact execution telemetry contracts."""
import datetime as dt

import pytest

from app.db.models import ExecutionOrderEvent
from app.engine.execution_lifecycle import (
    NewExecutionIntent,
    execution_metrics,
    reduce_execution_events,
)


BASE = dt.datetime(2026, 8, 9, 9, 15)


def _intent(*, side="BUY", decision_price=100.0):
    return NewExecutionIntent(
        deployment_id=1,
        broker="kite",
        account_scope="default",
        connection_scope="kite:legacy",
        intent="ENTRY",
        instrument_key="NIFTY",
        tradingsymbol="TEST",
        exchange="NSE",
        side=side,
        product="MIS",
        order_type="MARKET",
        requested_qty=100,
        limit_price=None,
        decision_price=decision_price,
        signal_at=BASE,
        strategy_key="test",
        strategy_version="v1",
        context={},
    )


def _row(kind, offset_ms, *, status="", filled=0, avg=0.0):
    return ExecutionOrderEvent(owner_id='owner', broker_account_id='account.default',
        client_intent_id="intent-1",
        source="engine" if kind in {"INTENT_CREATED", "SUBMIT_STARTED"} else "broker",
        source_event_id=f"{kind.lower()}-{offset_ms}",
        kind=kind,
        broker_order_id="OID-1" if kind in {"ACKNOWLEDGED", "STATUS_OBSERVED"} else None,
        broker_status=status,
        cumulative_filled_qty=filled,
        avg_price=avg,
        observed_at=BASE + dt.timedelta(milliseconds=offset_ms),
        payload_json="{}",
        anomaly="",
    )


def _state(*, side="BUY", fill_price=101.0):
    intent = _intent(side=side)
    state = reduce_execution_events(intent, [
        _row("INTENT_CREATED", 100),
        _row("SUBMIT_STARTED", 200),
        _row("ACKNOWLEDGED", 300),
        _row("STATUS_OBSERVED", 400, status="COMPLETE", filled=100,
             avg=fill_price),
        _row("POSITION_PROTECTED", 500, filled=100, avg=fill_price),
        _row("POSITION_BOOKED", 600, filled=100, avg=fill_price),
    ])
    return intent, state


def test_slippage_uses_persisted_decision_reference_after_quote_changes():
    intent, state = _state(side="BUY", fill_price=101.0)
    latest_provider_quote = 150.0

    metrics = execution_metrics(intent, state)

    assert latest_provider_quote != metrics["decision_price"]
    assert metrics["decision_price"] == 100.0
    assert metrics["average_fill_price"] == 101.0
    assert metrics["slippage_amount"] == 1.0
    assert metrics["slippage_bps"] == 100.0


@pytest.mark.parametrize(
    ("side", "fill_price"), [("BUY", 101.0), ("SELL", 99.0)])
def test_buy_and_sell_adverse_slippage_are_positive(side, fill_price):
    intent, state = _state(side=side, fill_price=fill_price)

    metrics = execution_metrics(intent, state)

    assert metrics["slippage_amount"] == 1.0
    assert metrics["slippage_bps"] == 100.0


def test_latency_uses_persisted_signal_submit_ack_and_fill_times():
    intent, state = _state()

    metrics = execution_metrics(intent, state)

    assert metrics["signal_to_intent_ms"] == 100.0
    assert metrics["intent_to_submit_ms"] == 100.0
    assert metrics["submit_to_ack_ms"] == 100.0
    assert metrics["ack_to_fill_ms"] == 100.0
    assert metrics["requested_qty"] == 100
    assert metrics["filled_qty"] == 100
    assert metrics["booked_qty"] == 100
    assert metrics["protected_qty"] == 100
    assert metrics["fill_ratio"] == 1.0
