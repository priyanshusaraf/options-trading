"""E4 — a manual close that the broker REFUSED must not be reported as success.

The route discarded `broker.close_position`'s return value and unconditionally logged
MANUAL CLOSE, blocked same-day re-entry, nulled the WS display state and answered
`{"closed": true}`. LiveBroker returns None on real failure paths (ownership guard,
SL-M-cancel abort, account re-check), so with real money the cockpit said "closed"
while the position was still open at the exchange — and the owner lost the display
state they needed to act on it.
"""
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    r.arm(True)
    return TestClient(app), r


def _open(c):
    op = c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()
    assert op.get("opened") is True, op


def test_refused_close_is_reported_as_a_failure_not_a_success():
    c, r = _client()
    _open(c)
    r.broker.close_position = lambda *a, **k: None      # broker refuses the close

    res = c.post("/api/positions/NIFTY/close").json()

    assert res.get("closed") is not True, f"phantom close reported as success: {res}"
    assert "error" in res, f"failure must be surfaced to the cockpit: {res}"


def test_refused_close_leaves_the_position_visible_and_unblocked():
    """The owner must still be able to see and retry the position they failed to close."""
    c, r = _client()
    _open(c)
    r.state.setdefault("NIFTY", {})["position"] = {"tradingsymbol": "X"}
    r.broker.close_position = lambda *a, **k: None

    c.post("/api/positions/NIFTY/close")

    assert r.broker.position_for("NIFTY") is not None      # still open, as it truly is
    assert r.state["NIFTY"]["position"] is not None, (
        "display state was nulled for a position that never closed")
    assert "NIFTY" not in r.entry_blocks, (
        "a failed close must not block same-day re-entry")


def test_a_real_close_still_succeeds():
    """Guard against over-correcting: the happy path must be untouched."""
    c, r = _client()
    _open(c)

    res = c.post("/api/positions/NIFTY/close").json()

    assert res.get("closed") is True, res
    assert r.broker.position_for("NIFTY") is None
    assert "NIFTY" in r.entry_blocks
