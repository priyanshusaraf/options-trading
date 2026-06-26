"""Real-order lifecycle: place ONCE, poll to a terminal state, and report the
ACTUAL fill. Tested against a fake order client — no exchange, no money, no Kite.
The 'never double-place' and 'never assume a fill on timeout' guarantees are what
keep a real-money path safe."""
from app.engine.order_executor import OrderRequest, execute_order


class FakeClient:
    """Returns the scripted status on each poll (repeats the last once exhausted)."""
    def __init__(self, statuses, place_raises=False):
        self._statuses = list(statuses)
        self.places = 0
        self.status_calls = 0
        self.place_raises = place_raises

    def place(self, req):
        self.places += 1
        if self.place_raises:
            raise RuntimeError("insufficient margin")
        return "OID-1"

    def status(self, order_id):
        self.status_calls += 1
        return self._statuses[min(self.status_calls - 1, len(self._statuses) - 1)]


def _noslp(_):
    pass


def _buy(order_type="MARKET", limit=None):
    return OrderRequest("NIFTY25...CE", "NFO", "BUY", 75, order_type, limit)


def test_fill_on_first_poll():
    c = FakeClient([{"status": "COMPLETE", "filled_qty": 75, "avg_price": 101.2}])
    r = execute_order(c, _buy(), sleep_fn=_noslp)
    assert r.status == "FILLED" and r.filled_qty == 75 and r.avg_price == 101.2
    assert c.places == 1


def test_rejected_order():
    c = FakeClient([{"status": "REJECTED", "reason": "insufficient funds"}])
    r = execute_order(c, _buy(), sleep_fn=_noslp)
    assert r.status == "REJECTED" and "funds" in r.reason
    assert c.places == 1


def test_open_then_complete_polls_until_filled():
    c = FakeClient([{"status": "OPEN", "filled_qty": 0},
                    {"status": "OPEN", "filled_qty": 0},
                    {"status": "COMPLETE", "filled_qty": 75, "avg_price": 100.0}])
    r = execute_order(c, _buy("LIMIT", 100.0), poll_seconds=0.1,
                      timeout_seconds=5.0, sleep_fn=_noslp)
    assert r.status == "FILLED" and c.places == 1


def test_partial_then_timeout_reports_partial():
    c = FakeClient([{"status": "OPEN", "filled_qty": 25, "avg_price": 100.0}])
    r = execute_order(c, _buy("LIMIT", 100.0), poll_seconds=1.0,
                      timeout_seconds=2.0, sleep_fn=_noslp)
    assert r.status == "PARTIAL" and r.filled_qty == 25


def test_never_fills_times_out_without_assuming_fill():
    c = FakeClient([{"status": "OPEN", "filled_qty": 0}])
    r = execute_order(c, _buy(), poll_seconds=1.0, timeout_seconds=2.0, sleep_fn=_noslp)
    assert r.status == "TIMEOUT" and r.filled_qty == 0


def test_place_failure_is_error_and_never_double_places():
    c = FakeClient([], place_raises=True)
    r = execute_order(c, _buy(), sleep_fn=_noslp)
    assert r.status == "ERROR" and c.places == 1


def test_cancelled_after_partial_is_partial():
    c = FakeClient([{"status": "CANCELLED", "filled_qty": 50, "avg_price": 100.0}])
    r = execute_order(c, _buy(), sleep_fn=_noslp)
    assert r.status == "PARTIAL" and r.filled_qty == 50


def test_rejected_variant_is_terminal_immediately_not_polled_to_timeout():
    # L9: a REJECTED-family status (any spelling containing REJECT) is terminal — we
    # must NOT keep polling a dead order until the timeout and misreport it as TIMEOUT.
    c = FakeClient([{"status": "REJECTED BY EXCHANGE", "reason": "rms block"}])
    r = execute_order(c, _buy(), poll_seconds=1.0, timeout_seconds=5.0, sleep_fn=_noslp)
    assert r.status == "REJECTED"
    assert c.status_calls == 1            # terminal on the first poll, not polled out


def test_timeout_reason_carries_the_last_raw_status_for_reconciliation():
    # L9: an unmapped status that never goes terminal still times out, but the raw
    # last status must be surfaced (not silently dropped) so the broker/owner can
    # reconcile what actually happened.
    c = FakeClient([{"status": "SOME_NEW_STATUS", "filled_qty": 0}])
    r = execute_order(c, _buy(), poll_seconds=1.0, timeout_seconds=2.0, sleep_fn=_noslp)
    assert r.status == "TIMEOUT"
    assert "SOME_NEW_STATUS" in r.reason
