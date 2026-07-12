"""Closing the generated-strategy loop on the execution side: a deployed generated
strategy is persisted as its composition JSON, and at engine startup it is reconstructed
(via the sandboxed builder) and registered so `get_strategy(key)` resolves to a REAL,
runnable strategy — not the silent default fallback. Without this, deploying a generated
strategy would run the wrong strategy."""
import json

import datetime as dt

import pandas as pd

from app.core import generated_strategies as gs
from app.db.session import SessionLocal, init_db
from app.strategy.registry import get_strategy

_COMP = {
    "key": "gen_exec_test_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def _df(n=120):
    base = dt.datetime(2024, 1, 1, 9, 15)
    return pd.DataFrame([
        {"date": base + dt.timedelta(minutes=15 * i), "open": 100 + i, "high": 101 + i,
         "low": 99 + i, "close": 100 + i} for i in range(n)])


def _cleanup():
    # keep the process-global registry from leaking the test strategy into other tests
    from app.strategy import registry
    registry._REGISTRY.pop("gen_exec_test_v1", None)


def test_save_and_register_makes_generated_strategy_resolvable():
    init_db(reset=True)
    try:
        with SessionLocal() as s:
            gs.save_generated(s, "gen_exec_test_v1", json.dumps(_COMP), source="def compute...")
            s.commit()
        with SessionLocal() as s:
            n = gs.register_all(s)
        assert n >= 1
        strat = get_strategy("gen_exec_test_v1")
        assert strat.key == "gen_exec_test_v1"
        out = strat.signals(_df())
        for col in ("longEntry", "shortEntry", "longExit", "shortExit"):
            assert col in out.columns
    finally:
        _cleanup()


def test_register_all_is_resilient_to_a_bad_row():
    init_db(reset=True)
    try:
        with SessionLocal() as s:
            gs.save_generated(s, "gen_bad", json.dumps({"key": "gen_bad"}))  # malformed comp
            gs.save_generated(s, "gen_exec_test_v1", json.dumps(_COMP))
            s.commit()
        with SessionLocal() as s:
            n = gs.register_all(s)                 # must not raise on the bad row
        assert get_strategy("gen_exec_test_v1").key == "gen_exec_test_v1"
        assert get_strategy("gen_bad").key == "trend_impulse_v3"   # bad row → not registered
    finally:
        _cleanup()
        from app.strategy import registry
        registry._REGISTRY.pop("gen_bad", None)


def test_unknown_key_still_falls_back_to_default():
    init_db(reset=True)
    assert get_strategy("never_generated").key == "trend_impulse_v3"
