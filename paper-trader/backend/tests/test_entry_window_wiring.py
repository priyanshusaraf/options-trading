"""WIRING for the two owner day-shape rules, on the live entry path:

  • #16b entry window — NO new entry before 09:30 (the volatile first 15 minutes are
    sat out even though the session opens 09:15). Session gating (pre-open/after-close)
    is covered in test_session_entry_guard.py; this is the stricter same-day gate.
  • #9 (extended) weekly-expiry weekday — the "no trades on Tuesday" rule now covers
    ALL entries (options AND intraday), not just the intraday branch.

Wiring tests, per the #15 lesson (a pure test passed while live wiring stayed broken)."""
import datetime as dt

from app.core.logging import log
from app.core.market_hours import ist_epoch
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner(key="NIFTY", product="equity_intraday", bar: dt.datetime | None = None,
            block_weekday=-1):
    init_db(reset=True)
    r = EngineRunner()
    r.enabled = {key}
    r.products[key] = product
    r.params = {**r.params, "intraday_enabled": True,
                "intraday_block_weekday": block_weekday}
    r.armed = True
    r.state[key] = {"signal": "LONG_ENTRY", "z": 2.5, "slope": 1.0, "close": 100.0,
                    "time": ist_epoch(bar) if bar else None}
    return r, key


def _open_intraday(r):
    return [p for p in r.broker.open_positions() if p.segment == "equity_intraday"]


def _events():
    return [e.get("event") for e in log.recent(80)]


# ── #16b: 09:15-09:30 is in-session but before the owner's entry window ──
def test_entry_window_blocks_0920_intraday():
    r, key = _runner(bar=dt.datetime(2026, 7, 3, 9, 0))       # completes 09:15 — fresh
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 9, 20)   # Friday, in-session
    r.process_entries()
    assert _open_intraday(r) == []
    assert "ENTRY_WINDOW_SKIP" in _events()


def test_entry_window_blocks_0920_options():
    r, key = _runner(product="options", bar=dt.datetime(2026, 7, 3, 9, 0))
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 9, 20)
    r.process_entries()
    assert r.broker.open_positions() == []
    assert "ENTRY_WINDOW_SKIP" in _events()


def test_entry_window_open_allows_the_entry():
    # Positive control: identical setup at 09:35 opens — the gate is the clock.
    # (affordable name so the ₹5–8k real-margin sizer buys ≥1 share; NIFTY at ₹24k can't)
    r, key = _runner(key="NATURALGAS", bar=dt.datetime(2026, 7, 3, 9, 15))  # completes 09:30 — fresh
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 9, 33)
    r.process_entries()
    assert _open_intraday(r) != []


# ── #9 extended: the Tuesday rule covers the OPTIONS branch as well ──
def test_tuesday_blocks_options_entries():
    r, key = _runner(product="options", bar=dt.datetime(2026, 6, 30, 10, 30),
                     block_weekday=1)
    r.provider.now = lambda: dt.datetime(2026, 6, 30, 10, 46)   # Tuesday, mid-session
    r.process_entries()
    assert r.broker.open_positions() == []
    assert "EXPIRY_DAY_SKIP" in _events()


def test_tuesday_blocks_intraday_entries():
    r, key = _runner(bar=dt.datetime(2026, 6, 30, 10, 30), block_weekday=1)
    r.provider.now = lambda: dt.datetime(2026, 6, 30, 10, 46)
    r.process_entries()
    assert _open_intraday(r) == []
    assert "EXPIRY_DAY_SKIP" in _events()


def test_wednesday_allows_entries_with_block_on():
    r, key = _runner(key="NATURALGAS", bar=dt.datetime(2026, 7, 1, 10, 30), block_weekday=1)
    r.provider.now = lambda: dt.datetime(2026, 7, 1, 10, 46)    # Wednesday
    r.process_entries()
    assert _open_intraday(r) != []
