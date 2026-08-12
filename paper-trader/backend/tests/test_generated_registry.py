"""Closing the generated-strategy loop on the execution side: a deployed generated
strategy is persisted as its composition JSON, and at engine startup it is reconstructed
(via the sandboxed builder) and registered so `get_strategy(key)` resolves to a REAL,
runnable strategy — not the silent default fallback. Without this, deploying a generated
strategy would run the wrong strategy."""
import json

import datetime as dt

import pandas as pd
import pytest

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
    registry._GENERATED_REGISTRY.pop(("owner", "gen_exec_test_v1"), None)


def test_save_and_register_makes_generated_strategy_resolvable():
    init_db(reset=True)
    try:
        with SessionLocal() as s:
            gs.save_generated(s, "gen_exec_test_v1", json.dumps(_COMP), owner_id="owner", source="def compute...")
            s.commit()
        with SessionLocal() as s:
            n = gs.register_all(s, owner_id="owner")
        assert n >= 1
        strat = get_strategy("gen_exec_test_v1", owner_id="owner")
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
            gs.save_generated(s, "gen_bad", json.dumps({"key": "gen_bad"}), owner_id="owner")
            gs.save_generated(s, "gen_exec_test_v1", json.dumps(_COMP), owner_id="owner")
            s.commit()
        with SessionLocal() as s:
            n = gs.register_all(s, owner_id="owner")
        assert get_strategy("gen_exec_test_v1", owner_id="owner").key == "gen_exec_test_v1"
        from app.strategy.registry import StrategyNotFound
        with pytest.raises(StrategyNotFound):
            get_strategy("gen_bad", owner_id="owner")
    finally:
        _cleanup()
        from app.strategy import registry
        registry._GENERATED_REGISTRY.pop(("owner", "gen_bad"), None)


def test_unknown_key_still_falls_back_to_default():
    init_db(reset=True)
    assert get_strategy("never_generated").key == "trend_impulse_v3"


def test_same_generated_key_is_registered_per_owner_and_foreign_resolution_fails_closed():
    init_db(reset=True)
    other = {**_COMP, "longExit": {"any": ["zscore_lt(50,0.5)"]}}
    try:
        with SessionLocal() as session:
            session.execute(__import__("sqlalchemy").text(
                "INSERT INTO organizations VALUES ('owner.other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            gs.save_generated(session, "gen_exec_test_v1", json.dumps(_COMP), owner_id="owner")
            gs.save_generated(session, "gen_exec_test_v1", json.dumps(other), owner_id="owner.other")
            session.commit()
        with SessionLocal() as session:
            assert gs.register_all(session, owner_id="owner") == 1
            assert gs.register_all(session, owner_id="owner.other") == 1
        first = get_strategy("gen_exec_test_v1", owner_id="owner")
        second = get_strategy("gen_exec_test_v1", owner_id="owner.other")
        assert first is not second and first.version != second.version
        from app.strategy.registry import StrategyNotFound
        with pytest.raises(StrategyNotFound):
            get_strategy("gen_exec_test_v1", owner_id="owner.missing")
    finally:
        from app.strategy import registry
        registry._GENERATED_REGISTRY.pop(("owner", "gen_exec_test_v1"), None)
        registry._GENERATED_REGISTRY.pop(("owner.other", "gen_exec_test_v1"), None)
