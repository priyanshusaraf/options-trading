"""#16 WIRING: process_entries must not open an intraday entry outside continuous
trading (the 09:01:25 LODHA pre-open protected-limit that rested and never filled,
2026-07-03 live incident). The pure-guard logic is covered in test_entry_guards.py;
this proves the guard is actually wired into the live entry path — not just defined
(the #15 lesson: a pure test passed while the live wiring stayed broken)."""
import datetime as dt
from dataclasses import replace

import pytest

from app.core import execution_binding
from app.core.logging import log
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _intraday_runner(key="NIFTY", bar=None):
    """A runner with `key` set to the intraday segment and a ready LONG entry signal.
    `bar` is the signal candle's OPEN time — keep it fresh relative to the test's
    `now` or the #15 signal-age guard (correctly) drops the entry first."""
    from app.core.market_hours import ist_epoch
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.enabled = {key}
    r.products[key] = "equity_intraday"
    r.params = {**r.params, "intraday_enabled": True}
    r.armed = True
    r.publish_signal(
        key, r._binding_for(key), {"signal": "LONG_ENTRY", "z": 2.5, "slope": 1.0,
                                   "close": 100.0, "time": ist_epoch(bar) if bar else None})
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
    # (affordable name so the ₹5–8k real-margin sizer buys ≥1 share; NIFTY at ₹24k can't)
    r, key = _intraday_runner(key="NATURALGAS")
    # Session wiring is the subject here.  Supply an otherwise admitted binding and
    # isolate its independently tested owner-local broker verifier.
    admitted = replace(r._binding_for(key), admission_address="sha256:" + "a" * 64)
    r.publish_signal(
        key, admitted, {"signal": "LONG_ENTRY", "z": 2.5, "slope": 1.0,
                        "close": 100.0, "time": None})
    r._require_entry_receipt = lambda _binding: object()
    r.broker._require_current_entry_receipt = lambda **_: None
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 11, 0)   # Friday, mid-session
    r.process_entries()
    assert _open_intraday(r) != []


def test_final_entry_receipt_check_blocks_an_already_published_signal(monkeypatch):
    """The order seam rechecks receipt after scan/publish; an earlier scan cannot mask it."""
    r, key = _intraday_runner(key="NATURALGAS", bar=dt.datetime(2026, 7, 3, 9, 15))
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 9, 33)
    opened = []
    receipt_checks = []

    def stale_at_order_time(binding):
        receipt_checks.append(binding)
        raise execution_binding.AuthorityNotGranted(binding.strategy_key, "RECEIPT_STALE")

    monkeypatch.setattr(r, "_require_entry_receipt", stale_at_order_time)
    monkeypatch.setattr(r.broker, "open_equity_position",
                        lambda *args, **kwargs: opened.append((args, kwargs)))

    r.process_entries()

    # The guard was reached after the published signal, session, route and sizing paths.
    # Thus deleting this local call makes the broker spy fire; an earlier scan check cannot
    # make this mutant pass.
    assert len(receipt_checks) == 1
    assert opened == []
