"""Bulk add: carries config, enables each item, reports skipped."""
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_add_bulk_carries_config_and_enables():
    c, r = _client()
    body = {"items": [
        {"key": "CRUDEOIL", "interval": "15minute",
         "strategy_key": "expanding_z_v4", "product": "equity_intraday"},
        {"key": "SILVERM", "interval": "30minute", "product": "options"},
        {"key": "NOPE_NOT_REAL", "product": "options"}]}
    res = c.post("/api/portfolio/add-bulk", json=body).json()
    added = {a["key"] for a in res["added"]}
    skipped = {s["key"] for s in res["skipped"]}
    assert {"CRUDEOIL", "SILVERM"} <= added
    assert "NOPE_NOT_REAL" in skipped
    assert "CRUDEOIL" in r.enabled and "SILVERM" in r.enabled
    assert r.products.get("CRUDEOIL") == "equity_intraday"
    assert r.strategy_keys.get("CRUDEOIL") == "expanding_z_v4"
