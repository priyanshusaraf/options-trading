"""RED characterization for KPV5-B-002.

The reducer observes events in insertion order.  A cancellation can race a
completion at the venue, and a delayed cumulative completion must not leave the
derived state labelled CANCELLED while also carrying the full fill.
"""

import datetime as dt
from types import SimpleNamespace

from app.engine.execution_lifecycle import reduce_execution_events


def _event(event_id: int, *, status: str, filled: int, price: float):
    return SimpleNamespace(
        client_intent_id="intent-1",
        source="broker",
        source_event_id=f"observation-{event_id}",
        kind="STATUS_OBSERVED",
        broker_order_id="order-1",
        broker_status=status,
        cumulative_filled_qty=filled,
        avg_price=price,
        observed_at=dt.datetime(2026, 8, 31, 9, 15, event_id),
        payload_json="{}",
        anomaly="",
    )


def test_later_full_fill_cannot_remain_labelled_cancelled():
    intent = SimpleNamespace(
        client_intent_id="intent-1",
        requested_qty=10,
        side="BUY",
        decision_price=100.0,
        signal_at=dt.datetime(2026, 8, 31, 9, 14, 59),
    )
    state = reduce_execution_events(
        intent,
        [
            _event(1, status="CANCELLED", filled=0, price=0.0),
            _event(2, status="COMPLETE", filled=10, price=101.0),
        ],
    )

    assert state.status == "COMPLETE", (
        f"derived state is {state.status} with {state.filled_qty}/{intent.requested_qty} "
        "filled; terminal conflict policy is internally inconsistent"
    )
