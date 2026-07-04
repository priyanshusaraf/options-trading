"""
Past sweeps must be browsable and exportable so a completed run is never wasted
(re-running a full sweep is expensive and pointless if nothing changed).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import init_db, SessionLocal
from app.db.models import BacktestRun, BacktestResult
from app.main import app


def _seed_run() -> int:
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="15minute,day",
                          capital=50_000.0, total=2, done=2, note="seed")
        s.add(run); s.commit()
        rid = run.id
        s.add(BacktestResult(run_id=rid, instrument_key="NIFTY", name="Nifty 50",
                             segment="NFO_FUT", interval="15minute", trades=10, wins=6,
                             win_rate=60.0, profit_factor=1.8, max_drawdown_pct=12.0,
                             return_pct=24.0, net_pnl=12000, gross_pnl=12500, charges=500,
                             expectancy=1200, cagr=30.0, bars=5000, error=""))
        s.add(BacktestResult(run_id=rid, instrument_key="CRUDEOIL", name="Crude Oil",
                             segment="MCX_FUT", interval="day", trades=5, wins=2,
                             win_rate=40.0, profit_factor=0.9, max_drawdown_pct=20.0,
                             return_pct=-5.0, net_pnl=-2500, gross_pnl=-2000, charges=500,
                             expectancy=-500, cagr=-6.0, bars=400, error=""))
        s.commit()
    return rid


def test_runs_lists_past_sweeps_with_counts():
    rid = _seed_run()
    c = TestClient(app)
    data = c.get("/api/backtest/runs").json()
    assert "runs" in data and len(data["runs"]) >= 1
    row = next(r for r in data["runs"] if r["id"] == rid)
    assert row["result_count"] == 2 and row["status"] == "done"


def test_export_returns_csv():
    rid = _seed_run()
    c = TestClient(app)
    res = c.get(f"/api/backtest/export?run_id={rid}")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert f"backtest_run_{rid}.csv" in res.headers["content-disposition"]
    body = res.text.splitlines()
    assert body[0].startswith("instrument_key,name,segment,strategy_key,interval")
    assert any(line.startswith("NIFTY,") for line in body)
    assert any(line.startswith("CRUDEOIL,") for line in body)


def _seed_multistrategy_run() -> int:
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="15minute",
                          capital=50_000.0, total=2, done=2,
                          strategies="trend_impulse_v3,expanding_z_v4", note="seed")
        s.add(run); s.commit()
        rid = run.id
        for sk, ret in (("trend_impulse_v3", 24.0), ("expanding_z_v4", 31.0)):
            s.add(BacktestResult(run_id=rid, instrument_key="NIFTY", name="Nifty 50",
                                 segment="NFO_FUT", strategy_key=sk, interval="15minute",
                                 trades=10, wins=6, win_rate=60.0, profit_factor=1.8,
                                 max_drawdown_pct=12.0, return_pct=ret, net_pnl=ret * 500,
                                 gross_pnl=ret * 520, charges=500, expectancy=1200,
                                 cagr=30.0, bars=5000, error=""))
        s.commit()
    return rid


def test_results_filter_by_strategy():
    rid = _seed_multistrategy_run()
    c = TestClient(app)
    # unfiltered: both strategies' rows present, each tagged
    allr = c.get(f"/api/backtest/results?run_id={rid}").json()
    assert {r["strategy_key"] for r in allr["results"]} == {"trend_impulse_v3", "expanding_z_v4"}
    # filtered to one strategy
    v4 = c.get(f"/api/backtest/results?run_id={rid}&strategy=expanding_z_v4").json()
    assert all(r["strategy_key"] == "expanding_z_v4" for r in v4["results"])
    assert len(v4["results"]) == 1
    # drill-down disambiguates by strategy
    detail = c.get(f"/api/backtest/result/NIFTY/15minute?run_id={rid}&strategy=expanding_z_v4").json()
    assert detail["strategy_key"] == "expanding_z_v4"
    assert detail["return_pct"] == 31.0


def test_instruments_endpoint_lists_strategies():
    init_db(reset=True)
    c = TestClient(app)
    data = c.get("/api/backtest/instruments").json()
    keys = {s["key"] for s in data["strategies"]}
    assert {"trend_impulse_v3", "expanding_z_v4"} <= keys
    assert all("display_name" in s for s in data["strategies"])
