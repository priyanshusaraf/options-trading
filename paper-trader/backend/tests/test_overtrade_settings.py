"""Overtrading thresholds are overridable + bounded and reach effective()."""
from fastapi.testclient import TestClient

from app.core import runtime_config
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner()
    return TestClient(app)


def test_overtrade_thresholds_overridable_and_bounded():
    c = _client()
    keys = {r["key"] for r in c.get("/api/settings").json()["params"]}
    assert {"overtrade_today_threshold", "overtrade_rolling_threshold",
            "overtrade_rolling_days"} <= keys
    c.post("/api/settings", json={"key": "overtrade_today_threshold", "value": "3"})
    assert runtime_config.effective()["overtrade_today_threshold"] == 3
    bad = c.post("/api/settings", json={"key": "overtrade_rolling_days", "value": "999"}).json()
    assert "error" in bad   # rolling_days capped at 90
