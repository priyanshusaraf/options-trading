"""#16 WIRING: process_entries must not open an intraday entry outside continuous
trading (the 09:01:25 LODHA pre-open protected-limit that rested and never filled,
2026-07-03 live incident). The pure-guard logic is covered in test_entry_guards.py;
this proves the guard is actually wired into the live entry path — not just defined
(the #15 lesson: a pure test passed while the live wiring stayed broken)."""
import datetime as dt

from app.core.logging import log
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _intraday_runner(key="NIFTY", bar=None):
    """A runner with `key` set to the intraday segment and a ready LONG entry signal.
    `bar` is the signal candle's OPEN time — keep it fresh relative to the test's
    `now` or the #15 signal-age guard (correctly) drops the entry first."""
    from app.core.market_hours import ist_epoch
    init_db(reset=True)
    r = EngineRunner()
    r.enabled = {key}
    r.products[key] = "equity_intraday"
    r.params = {**r.params, "intraday_enabled": True}
    r.armed = True
    r.state[key] = {"signal": "LONG_ENTRY", "z": 2.5, "slope": 1.0,
                    "close": 100.0, "time": ist_epoch(bar) if bar else None}
    return r, key


def _open_intraday(r):
    return [p for p in r.broker.open_positions() if p.segment == "equity_intraday"]


def test_preopen_intraday_entry_is_skipped():
    r, key = _intraday_runner()
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 9, 1)   # Friday, pre-open (before 09:15)
    r.process_entries()
    assert _open_intraday(r) == []                            # nothing opened pre-open
    assert "SESSION_SKIP" in [e.get("event") for e in log.recent(80)]


def test_continuous_session_allows_the_intraday_entry():
    # Positive control: the SAME setup that is blocked pre-open opens a position once the
    # continuous session is live — proving the guard gates on the session, not everything.
    r, key = _intraday_runner()
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 11, 0)   # Friday, mid-session
    r.process_entries()
    assert _open_intraday(r) != []
