"""
Trader risk controls (additive entry guards) + the per-position "let it run /
no take-profit" override. These guard real money once live: cap concurrent risk,
stop the chop re-entry trap, bound single-trade size, and let an overnight winner
run on news while the trailing stop still protects it.
"""
from __future__ import annotations

import datetime as dt

from app.engine.risk_controls import (
    slots_available, in_reentry_cooldown, over_per_trade_cap)
from app.engine.exit_monitor import evaluate_exit


def test_slots_available():
    assert slots_available(0, 0) is None       # cap off
    assert slots_available(3, 0) is None
    assert slots_available(0, 5) == 5
    assert slots_available(5, 5) == 0
    assert slots_available(7, 5) == 0          # never negative


def test_reentry_cooldown():
    now = dt.datetime(2026, 6, 19, 12, 0, 0)
    assert in_reentry_cooldown(None, now, 30) is False              # never stopped
    assert in_reentry_cooldown(now - dt.timedelta(minutes=10), now, 30) is True
    assert in_reentry_cooldown(now - dt.timedelta(minutes=40), now, 30) is False
    assert in_reentry_cooldown(now - dt.timedelta(minutes=1), now, 0) is False  # off


def test_per_trade_cap():
    assert over_per_trade_cap(10_000, 0) is False     # cap off
    assert over_per_trade_cap(10_000, 8_000) is True
    assert over_per_trade_cap(5_000, 8_000) is False


def test_evaluate_exit_target_disabled_suppresses_only_tp():
    # premium at/above target normally fires TARGET
    should, reason = evaluate_exit("LONG", 80.0, 120.0, 130.0, False, False)
    assert should and reason == "TARGET"
    # with the take-profit disabled, the SAME premium does NOT fire TARGET
    should2, reason2 = evaluate_exit("LONG", 80.0, 120.0, 130.0, False, False,
                                     target_disabled=True)
    assert not should2 and reason2 is None
    # ...but the protective stop still fires
    s3, r3 = evaluate_exit("LONG", 80.0, 120.0, 70.0, False, False, target_disabled=True)
    assert s3 and r3 == "STOP_LOSS"
    # ...and the strategy's own exit still fires
    s4, r4 = evaluate_exit("LONG", 80.0, 120.0, 100.0, True, False, target_disabled=True)
    assert s4 and r4 == "STRATEGY_EXIT"


def _client():
    from fastapi.testclient import TestClient
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.main import app
    init_db(reset=True)
    r = EngineRunner()
    for _ in range(160):
        r.tick(); r.provider.advance()
    app.state.runner = r
    return TestClient(app), r


def test_no_take_profit_route_toggles_flag():
    c, r = _client()
    op = c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()
    assert op.get("opened") is True, op
    res = c.post("/api/positions/NIFTY/no-take-profit", json={"enabled": True}).json()
    assert res.get("no_take_profit") is True, res
    assert r.broker.position_for("NIFTY").no_take_profit is True
    # restore
    res2 = c.post("/api/positions/NIFTY/no-take-profit", json={"enabled": False}).json()
    assert res2.get("no_take_profit") is False


def test_no_take_profit_refused_when_trailing_off():
    from app.core import runtime_config
    c, r = _client()
    c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"})
    runtime_config.set_override("trail_enabled", False)
    r.refresh_params()
    res = c.post("/api/positions/NIFTY/no-take-profit", json={"enabled": True}).json()
    assert "error" in res and "trailing" in res["error"].lower()
    assert r.broker.position_for("NIFTY").no_take_profit is False
    runtime_config.clear_override("trail_enabled")
