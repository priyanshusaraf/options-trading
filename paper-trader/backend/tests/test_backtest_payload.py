"""
Backtest results PAYLOAD honesty (BT-1, BT-2, DV-1):

The scan-level /results + /export payloads must carry the DENOMINATOR (notional,
lots, affordable) beside Net P&L, and the response must disclose how many cells
were SKIPPED so the visible set is never mistaken for the whole universe.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backtest import sweep
from app.backtest.metrics import BTTrade, compute_metrics
from app.db.models import BacktestResult, BacktestRun
from app.db.session import init_db, SessionLocal
from app.main import app
from app.providers.mock import MockProvider


def test_results_payload_carries_notional_and_lots(admitted_backtest_receipt):
    """A real 1-interval sweep, then GET /results: each visible result dict must
    have a numeric notional, an integer lots/qty, a boolean affordable, and the
    notional must be ≈ entry_price × qty for that instrument's sized position."""
    init_db(reset=True)
    prov = MockProvider()
    # Large capital makes the verified-charge index lots affordable. Commodity
    # fees remain explicitly unverified; this test covers payload arithmetic.
    rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["day"],
                            instruments=["NIFTY", "BANKNIFTY"],
                            capital=20_000_000, provider=prov,
                            **admitted_backtest_receipt())
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


def test_metrics_to_dict_includes_notional_and_option_cost():
    t = BTTrade("LONG", 0, 1000.0, 86400, 1050.0, 5, gross_pnl=250, charges=0.0,
                net_pnl=250, reason="STRATEGY_EXIT", bars_held=1,
                notional=5000.0, lots=1)
    m = compute_metrics([t], 50_000)
    m.option_cost = 1234.0
    d = m.to_dict()
    assert "notional" in d and "option_cost" in d and "lots" in d
    assert d["notional"] == 5000.0 and d["lots"] == 1 and d["option_cost"] == 1234.0


def _assert_survivorship_complete(payload: dict, durable_total: int) -> None:
    """The survivorship-disclosure contract G5 proves: the visible rows plus
    EVERY disclosed skipped bucket must account for the durable run's own
    universe total — read from the database, never from a fixture constant."""
    breakdown = payload.get("skipped_breakdown")
    assert isinstance(breakdown, dict) and breakdown, "skip buckets missing"
    assert payload["count"] >= 0 and payload["skipped"] >= 0
    assert payload["skipped"] == sum(breakdown.values()), (
        f"disclosed skip count {payload['skipped']} != buckets {breakdown}")
    assert payload["count"] + sum(breakdown.values()) == durable_total, (
        f"survivorship hole: visible {payload['count']} + skipped "
        f"{breakdown} != durable total {durable_total}")


def test_results_reports_skipped_count_bound_to_durable_total():
    """Seed a run whose durable `total` equals the ACTUAL expected universe
    (six cells), then prove: visible + every disclosed bucket == the total read
    back from the stored run row (survivorship disclosure)."""
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="day",
                          capital=50_000.0, total=6, done=6)
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
        # One LOW-TRADES cell (no error, but under min_trades) and one FILTERED
        # cell (trades fine, fails the profit-factor gate) — so every bucket of
        # the survivorship disclosure is exercised.
        s.add(BacktestResult(run_id=rid, instrument_key="LOW1", interval="day",
                             trades=0, wins=0, win_rate=0.0, return_pct=0.0,
                             affordable=True, error=""))
        s.add(BacktestResult(run_id=rid, instrument_key="FILT1", interval="day",
                             trades=6, wins=1, win_rate=16.7, return_pct=-3.0,
                             profit_factor=0.4, max_drawdown_pct=9.0,
                             affordable=True, error=""))
        s.commit()
    c = TestClient(app)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=1&min_profit_factor=1.0").json()
    assert d["count"] == 2                       # GOOD1, GOOD2
    # Exact-bucket assertion: omitting ANY category fails, not just sums.
    assert d["skipped_breakdown"] == {"errored": 2, "low_trades": 1, "filtered": 1}
    # The universe is read from the STORED run, binding the identity to what
    # actually persisted — a stale or edited fixture total cannot satisfy it.
    with SessionLocal() as s:
        stored_total = s.get(BacktestRun, rid).total
    _assert_survivorship_complete(d, stored_total)


def test_survivorship_identity_fails_on_a_tampered_durable_total():
    """Self-negative control: changing the durable total breaks the identity."""
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="day",
                          capital=1_000.0, total=1, done=1)
        s.add(run)
        s.commit()
        rid = run.id
        s.add(BacktestResult(run_id=rid, instrument_key="ONLY", interval="day",
                             trades=2, wins=1, win_rate=50.0, return_pct=1.0,
                             affordable=True, error=""))
        s.commit()
    c = TestClient(app)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=1&min_profit_factor=1.0").json()
    _assert_survivorship_complete(d, d["count"] + sum(d["skipped_breakdown"].values()))
    # Deliberate tamper: pretend the durable universe was larger.
    with pytest.raises(AssertionError, match="survivorship hole"):
        _assert_survivorship_complete(d, d["count"]
                                      + sum(d["skipped_breakdown"].values()) + 1)


def test_option_unaffordable_rows_are_visible_and_badged_not_skipped(monkeypatch):
    """A name whose ATM OPTION costs more than the budget stays in the visible
    results (badged affordable_options=False) so a promising edge stays on the
    radar — it is NOT hidden, and the payload counts it under `unaffordable`. Both
    rows trade (1-lot model); only the budget-relative option flag differs."""
    init_db(reset=True)
    with SessionLocal() as s:
        run = BacktestRun(status="done", scope="liquid", intervals="day",
                          capital=50_000.0, total=2, done=2)
        s.add(run)
        s.commit()
        rid = run.id
        # CHEAP option cost (far below any budget) vs HUGE (above any budget)
        s.add(BacktestResult(run_id=rid, instrument_key="CHEAP", interval="day",
                             trades=5, wins=3, win_rate=60.0, return_pct=10.0,
                             lots=1, notional=300_000.0, option_cost=1_000.0, error=""))
        s.add(BacktestResult(run_id=rid, instrument_key="PRICEY", interval="day",
                             trades=6, wins=4, win_rate=66.0, return_pct=40.0,
                             lots=1, notional=5_000_000.0, option_cost=10_000_000.0, error=""))
        s.commit()
    c = TestClient(app)
    from app.api import backtest_routes
    monkeypatch.setattr(backtest_routes, "_budget", lambda _request, _principal: 50_000.0)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=1").json()
    keys = {r["instrument_key"] for r in d["results"]}
    assert {"CHEAP", "PRICEY"} <= keys              # both surfaced, neither hidden
    assert d["skipped"] == 0
    assert d["unaffordable"] == 1                   # only PRICEY is unaffordable as options
    cheap = next(r for r in d["results"] if r["instrument_key"] == "CHEAP")
    pricey = next(r for r in d["results"] if r["instrument_key"] == "PRICEY")
    assert cheap["affordable_options"] is True
    assert pricey["affordable_options"] is False
    assert pricey["affordable_futures"] is False    # ₹50L future never fits the budget
