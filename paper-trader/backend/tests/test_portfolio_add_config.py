"""Single add carries strategy_key + product into InstrumentState + live runner dicts."""
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


def test_single_add_carries_strategy_and_product():
    c, r = _client()
    res = c.post("/api/portfolio/add", json={
        "key": "CRUDEOIL", "product": "equity_intraday",
        "strategy_key": "expanding_z_v4", "interval": "15minute"}).json()
    assert "error" not in res
    assert res.get("product") == "equity_intraday"
    assert res.get("strategy_key") == "expanding_z_v4"
    assert r.products.get("CRUDEOIL") == "equity_intraday"
    assert r.strategy_keys.get("CRUDEOIL") == "expanding_z_v4"
    assert "CRUDEOIL" in r.enabled
