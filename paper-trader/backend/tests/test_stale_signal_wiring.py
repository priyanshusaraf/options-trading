"""#15 WIRING: process_entries must DROP a signal whose candle is old news — after a
(re)start the latest completed candle can be hours stale (pre-open it is the PREVIOUS
session's last bar) and its crossover is history, not a live signal (LODHA 2026-07-03:
a prior-session crossover fired at 09:00 and the entry chased a move ~5% gone by noon).
The pure guard is covered in test_entry_guards.py; this proves the guard is wired into
the live entry path for BOTH the intraday and the options branches (the #15 lesson:
a pure test passed while the live wiring stayed broken)."""
import datetime as dt

from app.core.logging import log
from app.core.market_hours import ist_epoch
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner(key="NIFTY", product="equity_intraday", bar: dt.datetime | None = None,
            signal="LONG_ENTRY"):
    init_db(reset=True)
    r = EngineRunner()
    r.enabled = {key}
    r.products[key] = product
    r.params = {**r.params, "intraday_enabled": True,
                "intraday_block_weekday": -1}   # isolate: no weekday block here
    r.armed = True
    r.state[key] = {"signal": signal, "z": 2.5, "slope": 1.0, "close": 100.0,
                    "time": ist_epoch(bar) if bar else None}
    return r, key


def _open_intraday(r):
    return [p for p in r.broker.open_positions() if p.segment == "equity_intraday"]


def _events():
    return [e.get("event") for e in log.recent(80)]


def test_stale_bar_blocks_intraday_entry():
    # bar completed 10:45; it is 12:00 — the crossover is 75 minutes old, not live.
    r, key = _runner(bar=dt.datetime(2026, 7, 3, 10, 30))
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 12, 0)   # Friday, mid-session
    r.process_entries()
    assert _open_intraday(r) == []
    assert "SIGNAL_STALE_SKIP" in _events()


def test_prior_session_bar_blocks_at_open():
    # the 2026-07-03 shape: yesterday's last candle is still 'latest' after a restart.
    r, key = _runner(bar=dt.datetime(2026, 7, 2, 15, 15))
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 10, 0)
    r.process_entries()
    assert _open_intraday(r) == []
    assert "SIGNAL_STALE_SKIP" in _events()


def test_fresh_bar_opens_the_intraday_entry():
    # Positive control: same setup with a just-completed candle opens the position —
    # proving the guard gates on age, not everything.
    r, key = _runner(bar=dt.datetime(2026, 7, 3, 10, 45))     # completes 11:00
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 11, 1)
    r.process_entries()
    assert _open_intraday(r) != []


def test_stale_bar_blocks_the_options_branch_too():
    # options-product key: the guard sits ABOVE the branch split, so the stale skip
    # must fire before any chain fetch / picker work.
    r, key = _runner(product="options", bar=dt.datetime(2026, 7, 3, 9, 30))
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 13, 0)
    r.process_entries()
    assert r.broker.open_positions() == []
    assert "SIGNAL_STALE_SKIP" in _events()
