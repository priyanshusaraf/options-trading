"""REST surface for the cockpit: signals list, positions, health, interval/block,
manual open/close. Uses FastAPI TestClient with a directly-attached runner (no
background loops)."""
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner()
    # No warmup ticks: /api/signals lists all instruments regardless of state, and
    # a clean book keeps manual-open deterministic (ticking can auto-open NIFTY).
    app.state.runner = r
    return TestClient(app), r


def test_signals_list_is_lightweight():
    c, _ = _client()
    res = c.get("/api/signals").json()
    assert "instruments" in res and isinstance(res["instruments"], list)
    assert res["instruments"]
    row = res["instruments"][0]
    for k in ("key", "signal", "interval", "has_position", "has_options", "stale"):
        assert k in row


def test_set_interval_route():
    c, r = _client()
    res = c.post("/api/instruments/NIFTY/interval", json={"interval": "60minute"}).json()
    assert res["interval"] == "60minute"
    assert r._interval_for("NIFTY") == "60minute"


def test_block_entries_route():
    c, r = _client()
    c.post("/api/instruments/NIFTY/block-entries", json={"blocked": True})
    assert "NIFTY" in r.entry_blocks


def test_manual_open_then_close_and_positions():
    c, r = _client()
    op = c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()
    assert op.get("opened") is True, op
    pos = c.get("/api/positions").json()
    assert any(p["instrument_key"] == "NIFTY" for p in pos["positions"])
    cl = c.post("/api/positions/NIFTY/close").json()
    assert cl.get("closed") is True, cl
    assert r.broker.position_for("NIFTY") is None


def test_provider_health_route():
    c, _ = _client()
    h = c.get("/api/provider-health").json()
    assert "quote" in h and "candle" in h


def test_promote_carries_supported_interval():
    c, r = _client()
    res = c.post("/api/portfolio/add", json={"key": "NIFTY", "interval": "30minute"}).json()
    assert "error" not in res, res
    assert res.get("interval") == "30minute"
    assert r._interval_for("NIFTY") == "30minute"


def test_promote_unsupported_interval_falls_back_with_warning():
    c, _ = _client()
    res = c.post("/api/portfolio/add", json={"key": "NIFTY", "interval": "minute"}).json()
    assert res.get("interval") == "15minute"     # clamped to default
    assert res.get("interval_warning")
