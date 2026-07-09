"""SEC-3: manual-open must respect the ARM gate.

The documented safety model gates every ENTRY on the engine being armed (armed
is False on every process start). manual-open is a human-initiated entry, but
today it bypasses ARM entirely and calls straight into broker.manual_open —
so a disarmed engine can still open a real paper (or, if PT_EXECUTION=live,
real-money) position via the REST route. This must be rejected the same way
process_entries rejects an auto-signal entry when disarmed."""
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_manual_open_rejected_when_disarmed():
    c, r = _client()
    assert r.armed is False  # disarmed on every process start
    res = c.post(
        "/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}
    ).json()
    assert "error" in res
    assert r.broker.position_for("NIFTY") is None


def test_manual_open_allowed_when_armed():
    c, r = _client()
    r.arm(True)
    res = c.post(
        "/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}
    ).json()
    assert res.get("opened") is True, res
    assert r.broker.position_for("NIFTY") is not None
