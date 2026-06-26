"""Backtest result rows expose has_options for product inference."""
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
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
    app.state.runner = EngineRunner()
    return TestClient(app)


def test_results_carry_has_options():
    c = _client()
    with SessionLocal() as s:
        s.add(BacktestRun(id=1, status="done", scope="liquid"))
        s.add(BacktestResult(run_id=1, instrument_key="NIFTY", interval="15minute",
                             trades=5, win_rate=60.0, return_pct=10.0, net_pnl=500.0))
        s.commit()
    rows = c.get("/api/backtest/results?run_id=1&min_trades=1").json()["results"]
    assert rows and "has_options" in rows[0]
    assert isinstance(rows[0]["has_options"], bool)
