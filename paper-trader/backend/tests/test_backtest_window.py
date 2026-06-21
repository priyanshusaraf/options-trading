"""
Selectable backtest scope: the owner must be able to (a) run only chosen
instruments (e.g. just GOLD/SILVER/COPPER), and (b) pick the lookback window
(preset or custom dates), with the window recorded + disclosed on the run.
"""
from __future__ import annotations

import datetime as dt

from app.backtest import sweep
from app.db.session import init_db, SessionLocal
from app.db.models import BacktestRun, BacktestResult
from app.providers.mock import MockProvider


def test_window_label():
    assert sweep.window_label(None, None, None) == "max"
    assert sweep.window_label(365, None, None) == "1y"
    assert sweep.window_label(7, None, None) == "1w"
    assert sweep.window_label(123, None, None) == "123d"          # non-preset day count
    assert sweep.window_label(None, "2024-01-01", "2024-06-01") == "2024-01-01→2024-06-01"


def test_fetch_days_clamps_to_kite_max():
    # 15minute caps at 200 days; a 10y request is clamped, a 1m request passes through
    assert sweep._fetch_days("15minute", 3650, None) == 200
    assert sweep._fetch_days("15minute", 30, None) == 30
    assert sweep._fetch_days("day", 3650, None) == 2000          # day caps at 2000
    assert sweep._fetch_days("15minute", None, None) == 200      # max


def test_clip_to_window_filters_by_date():
    class C:
        def __init__(self, d): self.ts = dt.datetime(d.year, d.month, d.day, 10, 0)
    candles = [C(dt.date(2024, 1, 1)), C(dt.date(2024, 3, 1)), C(dt.date(2024, 6, 1))]
    clipped = sweep._clip_to_window(candles, "2024-02-01", "2024-04-01")
    assert len(clipped) == 1 and clipped[0].ts.date() == dt.date(2024, 3, 1)
    assert sweep._clip_to_window(candles, None, None) == candles  # no window = passthrough


def test_sweep_restricted_to_chosen_instruments_records_window():
    init_db(reset=True)
    prov = MockProvider()
    # mock universe = curated seed list; restrict to NIFTY only, 1-year window
    rid = sweep.start_sweep(scope="liquid", intervals=["day"], instruments=["NIFTY"],
                            lookback_days=365, provider=prov)
    sweep._join()
    with SessionLocal() as s:
        run = s.get(BacktestRun, rid)
        assert run.window == "1y"
        assert run.instruments == "NIFTY"
        keys = {r.instrument_key for r in s.scalars(
            select_results(rid))}
    assert keys == {"NIFTY"}   # nothing else was swept


def select_results(rid):
    from sqlalchemy import select
    return select(BacktestResult).where(BacktestResult.run_id == rid)


def test_instruments_endpoint_lists_universe_and_presets():
    from fastapi.testclient import TestClient
    from app.main import app
    init_db(reset=True)
    c = TestClient(app)
    d = c.get("/api/backtest/instruments").json()
    assert d["instruments"] and any(i["key"] == "NIFTY" for i in d["instruments"])
    assert "1y" in d["presets"] and d["preset_days"]["1y"] == 365
    assert d["max_days"]["15minute"] == 200       # disclosed Kite ceiling


def test_sweep_rejects_unknown_instrument():
    init_db(reset=True)
    prov = MockProvider()
    try:
        sweep.start_sweep(scope="liquid", intervals=["day"],
                          instruments=["NOT_A_REAL_INSTRUMENT"], provider=prov)
        assert False, "expected a failure for an unknown instrument"
    except RuntimeError as e:
        assert "none of the requested instruments" in str(e).lower()
    finally:
        # the guard must release the running lock so later sweeps can start
        assert sweep.is_running() is False
