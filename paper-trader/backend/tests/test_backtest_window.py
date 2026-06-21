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


# ── data-validity regressions ────────────────────────────────────────────────

def test_lookback_silently_diverges_per_interval():
    """A single requested lookback maps to wildly different actual coverage per
    interval because each is clamped to Kite's per-interval MAX_DAYS — yet the
    run is labelled with one window string ('3y') for all of them. This test
    pins the CURRENT (misleading) behaviour so any intended fix is deliberate:
    a '3y' sweep on the minute interval really only covers 60 days."""
    requested = 1095  # "3y"
    by_interval = {iv: sweep._fetch_days(iv, requested, None)
                   for iv in ("minute", "5minute", "15minute", "60minute", "day")}
    # the minute interval covers only 60 days despite the '3y' request/label
    assert by_interval["minute"] == 60
    assert by_interval["5minute"] == 100
    assert by_interval["15minute"] == 200
    assert by_interval["day"] == 1095
    # the divergence is real: same request -> 18x difference in coverage
    assert max(by_interval.values()) / min(by_interval.values()) >= 18
    # and they all carry the SAME human label, so the UI cannot tell them apart
    assert sweep.window_label(requested, None, None) == "3y"


def test_custom_window_end_date_is_honored():
    """A past [start,end] window that is BOTH inside Kite's reach must fetch that
    range (anchored to end_date), not the most-recent N days. The mock advances a
    synthetic clock, so we assert the returned candles never run past end_date."""
    import datetime as dt
    from app.providers.mock import MockProvider
    from app.core.instruments import get_instrument
    prov = MockProvider()
    inst = get_instrument("NIFTY")
    # the mock clock starts 2025-01-01; pick an end inside the generated series
    all_candles = prov.get_candles(inst, "day", 3650)
    assert all_candles, "mock should generate candles"
    mid = all_candles[len(all_candles) // 2].ts.date()
    end = mid.isoformat()
    days = sweep._fetch_days("day", None, None, end)   # accepts end_date now
    assert days > 0
    # provider with end-anchoring drops everything after `end`
    fetched = prov.get_candles(inst, "day", 3650, end=end)
    assert fetched and all(c.ts.date() <= mid for c in fetched)
    # without end-anchoring the series runs to the simulated "now" (strictly later)
    assert all_candles[-1].ts.date() > mid


def test_out_of_range_window_gets_distinct_status():
    """A custom window entirely older than Kite's per-interval ceiling (a 2018
    window) must yield a result row whose status string explains 'older than Kite
    max', NOT the generic, silently-hidden 'insufficient history'."""
    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["day"], instruments=["NIFTY"],
                            start_date="2018-01-01", end_date="2018-06-01", provider=prov)
    sweep._join()
    with SessionLocal() as s:
        rows = list(s.scalars(select_results(rid)))
    assert rows, "an out-of-range window must still record an explanatory row"
    r = rows[0]
    assert "older than kite max" in r.error.lower()
    assert "insufficient history" not in r.error.lower()


def test_window_out_of_range_helper():
    # a 2018 window is older than even the deepest (day=2000d ≈ 5.5y) ceiling
    assert sweep._window_out_of_range("day", "2018-01-01", "2018-06-01") is True
    # a recent window is reachable
    import datetime as dt
    recent = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    assert sweep._window_out_of_range("day", recent, None) is False
    # no custom window -> never out of range
    assert sweep._window_out_of_range("day", None, None) is False


def test_per_interval_results_record_true_span():
    """One sweep across two intervals under the SAME lookback must record TRUE
    per-cell coverage (first_ts/last_ts/effective_days) derived from each cell's
    actual candles via ist_epoch, plus a PER-INTERVAL clamp flag — so a trader is
    never shown two intervals under one window label as if comparable."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.market_hours import ist_epoch
    from app.core.instruments import get_instrument
    init_db(reset=True)
    prov = MockProvider()
    # lookback 100d: 'minute' caps at 60d (CLAMPED), 'day' caps at 2000d (not clamped)
    rid = sweep.start_sweep(scope="liquid", intervals=["minute", "day"],
                            instruments=["NIFTY"], lookback_days=100, provider=prov)
    sweep._join()
    c = TestClient(app)
    d = c.get(f"/api/backtest/results?run_id={rid}&min_trades=0").json()
    by_iv = {r["interval"]: r for r in d["results"]}
    assert "minute" in by_iv and "day" in by_iv
    m_row, d_row = by_iv["minute"], by_iv["day"]
    for r in (m_row, d_row):
        assert r["first_ts"] > 0 and r["last_ts"] >= r["first_ts"]
        assert r["effective_days"] >= 0
        # the stored span is IST-epoch of the cell's actual first/last candle
        cand = prov.get_candles(get_instrument("NIFTY"), r["interval"], 100)
        assert r["first_ts"] == ist_epoch(cand[0].ts)
        assert r["last_ts"] == ist_epoch(cand[-1].ts)
    # the clamp flag is genuinely per-interval — the honest disclosure that the
    # same '100d' label means different real coverage per timeframe:
    assert m_row["clamped"] is True     # minute clamped (100 > Kite's 60d ceiling)
    assert d_row["clamped"] is False    # day not clamped (100 < 2000d ceiling)


def test_all_presets_offered():
    """The instrument picker must offer the full owner-requested preset set,
    including 7y/10y and an entire-history option."""
    from fastapi.testclient import TestClient
    from app.main import app
    init_db(reset=True)
    c = TestClient(app)
    d = c.get("/api/backtest/instruments").json()
    presets = d["presets"]
    for p in ("1w", "2w", "1m", "3m", "6m", "1y", "3y", "7y", "10y"):
        assert p in presets, f"missing preset {p}"
    assert "max" in presets                      # entire-history option
    assert d["preset_days"]["10y"] == 3650
    assert d["preset_days"]["7y"] == 2555
    assert d["preset_days"]["max"] is None       # max => entire available history


def test_sweep_restricted_to_commodities():
    """An instruments-only sweep runs EXACTLY the chosen keys, nothing else."""
    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["day"],
                            instruments=["GOLDM", "SILVERM", "COPPERM"], provider=prov)
    sweep._join()
    with SessionLocal() as s:
        keys = {r.instrument_key for r in s.scalars(select_results(rid))}
    assert keys == {"GOLDM", "SILVERM", "COPPERM"}


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
