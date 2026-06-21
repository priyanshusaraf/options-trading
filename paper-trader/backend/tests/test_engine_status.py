"""
Authoritative engine status on the WS snapshot (C2). The operational screens must
be able to answer 'is the bot armed and allowed to trade?' from the snapshot alone:
armed / running / broker_mode and a PURE, side-effect-free halt block.

The halt block must mirror _entries_halted's math WITHOUT firing the once-per-day
notifier or mutating _halt_notified_date — snapshot_state runs on every WS push.
"""
from __future__ import annotations

import datetime as dt

from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_snapshot_carries_engine_status_keys():
    r = _runner()
    snap = r.snapshot_state()
    for k in ("armed", "running", "broker_mode", "halt"):
        assert k in snap, f"snapshot missing {k}"
    assert snap["armed"] is False          # disarmed on every process start
    assert snap["broker_mode"] == "paper"  # mock provider -> paper broker
    halt = snap["halt"]
    for k in ("halted", "reason", "realized", "open_unrealized",
              "max_daily_loss", "max_open_drawdown"):
        assert k in halt


def test_halt_status_reflects_realized_breaker():
    r = _runner()
    r.params = dict(r.params)
    r.params["max_daily_loss"] = 5000.0
    r.params["max_open_drawdown"] = 0.0
    # force a booked loss beyond the cap
    r._today_net_realized = lambda today: -6000.0
    halt = r.halt_status(r.provider.now())
    assert halt["halted"] is True
    assert halt["reason"] == "realized"
    assert halt["realized"] == -6000.0


def test_halt_status_is_pure_no_notifier_no_mutation():
    r = _runner()
    fired = []
    r.notifier.daily_halt = lambda amount, cap: fired.append((amount, cap))
    r.params = dict(r.params)
    r.params["max_daily_loss"] = 5000.0
    r.params["max_open_drawdown"] = 0.0
    r._today_net_realized = lambda today: -6000.0
    before = r._halt_notified_date

    # calling the snapshot path repeatedly must NOT notify or mutate halt state
    r.snapshot_state()
    r.snapshot_state()
    r.halt_status(r.provider.now())

    assert fired == [], "halt_status/snapshot must not fire the daily-halt notifier"
    assert r._halt_notified_date == before, "halt_status must not mutate _halt_notified_date"


def test_snapshot_carries_market_open_segments():
    """OPS-R2-1: the WS snapshot must carry per-segment market_open + a feed-wide
    any_market_open so EngineView/Monitor can render closed markets as a neutral
    'market closed' instead of an amber 'stale' alarm for every instrument."""
    r = _runner()
    r.enabled = {"NIFTY", "BANKNIFTY"}
    snap = r.snapshot_state()
    assert "market_open" in snap and isinstance(snap["market_open"], dict)
    assert "any_market_open" in snap
    # mock provider is always tradable
    assert snap["any_market_open"] is True
    assert all(snap["market_open"].values())


def test_snapshot_market_open_false_when_closed():
    """OPS-R2-1: when every enabled segment is closed, any_market_open is False so
    the UI can grey-out staleness rather than alarm on it overnight."""
    r = _runner()
    r.enabled = {"NIFTY"}
    # mock provider is a cached singleton — restore the bound method after the test.
    orig = r.provider.is_tradable_now
    r.provider.is_tradable_now = lambda inst: False
    try:
        snap = r.snapshot_state()
        assert snap["any_market_open"] is False
        assert all(v is False for v in snap["market_open"].values())
    finally:
        r.provider.is_tradable_now = orig


def test_halt_status_off_when_caps_disabled():
    r = _runner()
    r.params = dict(r.params)
    r.params["max_daily_loss"] = 0.0
    r.params["max_open_drawdown"] = 0.0
    halt = r.halt_status(r.provider.now())
    assert halt["halted"] is False
    assert halt["reason"] == ""
