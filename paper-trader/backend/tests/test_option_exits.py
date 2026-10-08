"""Per-strategy option-exit policy: the live entry params, the trail gate, and the
premium backtest all honour Strategy.option_exits; strategies without it keep the
global Settings exactly."""
import datetime as dt
from dataclasses import dataclass

import pytest

from app.backtest.premium import simulate_premium
from app.engine.runner import option_entry_params, trail_allowed
from app.strategy.registry import get_strategy
from app.strategy.registry.base import Strategy

GLOBAL = {"stop_loss_pct": 0.35, "target_pct": 0.60, "trail_enabled": True}


class Plain(Strategy):
    key = "plain_stub"
    default_params = {}


def test_no_policy_keeps_global_settings():
    p, no_tp = option_entry_params(GLOBAL, Plain())
    assert p == GLOBAL and no_tp is False
    assert trail_allowed(GLOBAL, Plain()) and trail_allowed(GLOBAL, None)


@pytest.mark.parametrize("key,stop", [("shock_reversal", 0.65), ("spike_fade", 0.65),
                                      ("vwap_band_reversion", 0.95), ("gold_month_turn", 0.95)])
def test_declared_policies(key, stop):
    s = get_strategy(key)
    p, no_tp = option_entry_params(GLOBAL, s)
    assert p["stop_loss_pct"] == stop and no_tp is True
    assert p["target_pct"] == 0.60                   # untouched; the flag disables it
    assert trail_allowed(GLOBAL, s) is False
    assert GLOBAL["stop_loss_pct"] == 0.35           # caller's dict not mutated


def test_global_trail_off_still_wins():
    assert trail_allowed({**GLOBAL, "trail_enabled": False}, Plain()) is False


@dataclass
class C:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 1.0


class Inst:
    segment = "MCX"
    lot_size = 10
    strike_step = 1.0
    has_options = True


ENTRY_BAR = 30 * 8


class EnterOnce(Strategy):
    """Long once (after the vol warmup), never exits on its own: only the premium
    stop/target/expiry or end-of-data can close it."""
    key = "enter_once_stub"
    default_params = {}
    warmup_columns = ("close",)

    def compute(self, df, **p):
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i == ENTRY_BAR for i in range(n)]
        out["shortEntry"] = [False] * n
        out["longExit"] = [False] * n
        out["shortExit"] = [False] * n
        return out


def _tape():
    """8 hourly bars a day for 34 days: calm wiggle (vol warmup), the entry, then a
    3% drop over 10 bars that flattens out."""
    import math
    t0 = dt.datetime(2026, 1, 1, 10, 0)
    cs = []
    for i in range(34 * 8):
        day, hour = divmod(i, 8)
        if i <= ENTRY_BAR + 1:
            px = 100.0 + 1.5 * math.sin(i / 2.0)
        else:
            px = (100.0 + 1.5 * math.sin((ENTRY_BAR + 1) / 2.0)) * (1 - 0.003 * min(i - ENTRY_BAR - 1, 10))
        cs.append(C(t0 + dt.timedelta(days=day, hours=hour), px, px * 1.002, px * 0.998, px))
    return cs


def test_premium_path_honours_policy():
    plain = EnterOnce()
    wide = EnterOnce()
    wide.option_exits = {"stop_loss_pct": 0.95, "target_pct": None, "trail_enabled": False}
    a, _ = simulate_premium(_tape(), Inst(), "60minute", strategy=plain)
    b, _ = simulate_premium(_tape(), Inst(), "60minute", strategy=wide)
    assert len(a) == 1 and a[0].reason == "STOP_LOSS"   # the global −35% stop fires
    assert len(b) == 1 and b[0].reason == "OPEN_AT_END"  # the −95% policy rides it out
    assert b[0].bars_held > a[0].bars_held


# ── wiring: the LIVE entry path applies the policy (not just the pure helper) ──
def _armed_runner(strategy_key=None):
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()
    r.params["entry_min_days_to_expiry"] = 0     # mock NIFTY chain is ~1-DTE
    if strategy_key:
        r.strategy_keys["NIFTY"] = strategy_key
    r.arm(True)
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                        "close": 100.0, "long_exit": False, "short_exit": False}
    return r


def test_live_entry_applies_strategy_option_exits():
    r = _armed_runner("spike_fade")
    r.process_entries()
    pos = r.broker.position_for("NIFTY")
    assert pos is not None
    assert pos.stop_price == pytest.approx(pos.entry_premium * (1 - 0.65))
    assert pos.no_take_profit is True and pos.strategy_key == "spike_fade"
    # the percent-of-premium trail must not move this position's stop
    before = pos.stop_price
    pos.high_water_premium = pos.entry_premium * 3
    pos.last_premium = pos.entry_premium * 3
    r._apply_trailing(pos)
    assert pos.stop_price == before


def test_live_entry_default_strategy_unchanged():
    r = _armed_runner()
    r.process_entries()
    pos = r.broker.position_for("NIFTY")
    assert pos is not None
    assert pos.stop_price == pytest.approx(pos.entry_premium * (1 - r.params["stop_loss_pct"]))
    assert pos.no_take_profit is False
    before = pos.stop_price
    pos.high_water_premium = pos.entry_premium * 3
    pos.last_premium = pos.entry_premium * 3
    r._apply_trailing(pos)
    assert pos.stop_price > before                    # global trail still ratchets
