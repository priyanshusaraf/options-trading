"""
Backtest results PAYLOAD honesty (BT-1, BT-2, DV-1):

The scan-level /results + /export payloads must carry the DENOMINATOR (notional,
lots, affordable) beside Net P&L, and the response must disclose how many cells
were SKIPPED so the visible set is never mistaken for the whole universe.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backtest import sweep
from app.backtest.metrics import BTTrade, compute_metrics
from app.db.models import BacktestResult, BacktestRun
from app.db.session import init_db, SessionLocal
from app.main import app
from app.providers.mock import MockProvider


def test_results_payload_carries_notional_and_lots():
    """A real 1-interval sweep, then GET /results: each visible result dict must
    have a numeric notional, an integer lots/qty, a boolean affordable, and the
    notional must be ≈ entry_price × qty for that instrument's sized position."""
    init_db(reset=True)
    prov = MockProvider()
    # large capital so index/commodity lots are affordable and trades fire
    rid = sweep.start_sweep(scope="liquid", intervals=["day"],
                            capital=20_000_000, provider=prov)
    sweep._join()
    c = TestClient(app)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=1").json()
    assert d["results"], "expected at least one visible result"
    for r in d["results"]:
        assert isinstance(r["notional"], (int, float))
        assert isinstance(r["lots"], int)
        assert isinstance(r["affordable"], bool)
    # cross-check notional ≈ entry_price × qty against the cell's first trade
    sample = d["results"][0]
    detail = c.get(f"/api/backtest/result/{sample['instrument_key']}/{sample['interval']}"
                   f"?run_id={rid}").json()
    if detail.get("trades"):
        t0 = detail["trades"][0]
        assert abs(sample["notional"] - t0["entry_price"] * t0["qty"]) <= max(
            1.0, 0.01 * t0["entry_price"] * t0["qty"])


def test_metrics_to_dict_includes_notional_and_affordable():
    t = BTTrade("LONG", 0, 1000.0, 86400, 1050.0, 5, gross_pnl=250, charges=0.0,
                net_pnl=250, reason="STRATEGY_EXIT", bars_held=1,
                notional=5000.0, lots=1, affordable=True)
    d = compute_metrics([t], 50_000).to_dict()
    assert "notional" in d and "affordable" in d and "lots" in d
    assert d["notional"] == 5000.0 and d["affordable"] is True and d["lots"] == 1


def test_results_reports_skipped_count():
    """Seed a run with some error rows + some good rows, GET /results: the
    response.skipped must equal the excluded cells and response.count the visible
    ones (survivorship disclosure)."""
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="day",
                          capital=50_000.0, total=4, done=4)
        s.add(run)
        s.commit()
        rid = run.id
        # 2 good (affordable, traded), 2 errored
        s.add(BacktestResult(run_id=rid, instrument_key="GOOD1", interval="day",
                             trades=5, wins=3, win_rate=60.0, return_pct=10.0,
                             affordable=True, error=""))
        s.add(BacktestResult(run_id=rid, instrument_key="GOOD2", interval="day",
                             trades=8, wins=5, win_rate=62.5, return_pct=4.0,
                             affordable=True, error=""))
        s.add(BacktestResult(run_id=rid, instrument_key="BAD1", interval="day",
                             trades=0, error="insufficient history"))
        s.add(BacktestResult(run_id=rid, instrument_key="BAD2", interval="minute",
                             trades=0, error="window older than Kite max for this interval"))
        s.commit()
    c = TestClient(app)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=1").json()
    assert d["count"] == 2                       # GOOD1, GOOD2
    assert d["skipped"] == 2                      # BAD1, BAD2
    assert d["skipped_breakdown"]["errored"] == 2


def test_unaffordable_rows_are_visible_and_badged_not_skipped():
    """An unaffordable cell (one lot > capital) is a DISTINCT status: it stays in
    the visible results (so the UI can badge it), not counted under `skipped`."""
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="day",
                          capital=50_000.0, total=2, done=2)
        s.add(run)
        s.commit()
        rid = run.id
        s.add(BacktestResult(run_id=rid, instrument_key="GOOD", interval="day",
                             trades=5, wins=3, win_rate=60.0, return_pct=10.0,
                             affordable=True, error=""))
        s.add(BacktestResult(run_id=rid, instrument_key="TOOBIG", interval="day",
                             trades=0, affordable=False, lots=0, notional=1_820_000.0,
                             error=""))
        s.commit()
    c = TestClient(app)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=1").json()
    keys = {r["instrument_key"] for r in d["results"]}
    assert "TOOBIG" in keys                       # surfaced, not hidden
    assert d["unaffordable"] == 1
    assert d["skipped"] == 0                       # not counted as a silent drop
    too = next(r for r in d["results"] if r["instrument_key"] == "TOOBIG")
    assert too["affordable"] is False and too["lots"] == 0
