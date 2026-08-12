"""Closing the generated-strategy loop on the execution side: a deployed generated
strategy is persisted as its composition JSON, and at engine startup it is reconstructed
(via the sandboxed builder) and registered so `get_strategy(key)` resolves to a REAL,
runnable strategy — not the silent default fallback. Without this, deploying a generated
strategy would run the wrong strategy."""
import json

import datetime as dt
import threading

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


def test_rehydrating_a_corrupt_current_row_evicts_the_previously_loaded_executable():
    init_db(reset=True)
    from app.strategy import registry
    from app.strategy.registry import StrategyNotFound, resolve_strategy
    try:
        with SessionLocal() as session:
            gs.save_generated(
                session, "gen_exec_test_v1", json.dumps(_COMP), owner_id="owner")
            session.commit()
            assert gs.register_all(session, owner_id="owner") == 1
            assert resolve_strategy("gen_exec_test_v1", owner_id="owner")
            session.get(gs.GeneratedStrategyRow, ("owner", "gen_exec_test_v1")).composition_json = "{}"
            session.commit()
            assert gs.register_all(session, owner_id="owner") == 0
        with pytest.raises(StrategyNotFound):
            resolve_strategy("gen_exec_test_v1", owner_id="owner")
    finally:
        registry._GENERATED_REGISTRY.pop(("owner", "gen_exec_test_v1"), None)


def test_owner_partition_publication_is_atomic_for_resolution_and_metadata():
    """A concurrent reader sees the complete old partition until one snapshot swap."""
    from app.strategy import registry

    class MarkerStrategy(registry.Strategy):
        def __init__(self, key, marker):
            self.key = key
            self.display_name = marker

    old = {
        "gen_atomic_a": MarkerStrategy("gen_atomic_a", "old-a"),
        "gen_atomic_b": MarkerStrategy("gen_atomic_b", "old-b"),
    }
    new = {
        "gen_atomic_a": MarkerStrategy("gen_atomic_a", "new-a"),
        "gen_atomic_b": MarkerStrategy("gen_atomic_b", "new-b"),
    }
    copy_started = threading.Event()
    allow_publication = threading.Event()

    class BlockingCompletePartition(dict):
        def items(self):
            copy_started.set()
            assert allow_publication.wait(timeout=5)
            return super().items()

    try:
        registry.replace_generated_partition("owner.atomic", old)
        publisher = threading.Thread(
            target=registry.replace_generated_partition,
            args=("owner.atomic", BlockingCompletePartition(new)),
            daemon=True,
        )
        publisher.start()
        assert copy_started.wait(timeout=5)

        resolved_during_copy = {
            key: registry.resolve_strategy(key, owner_id="owner.atomic").display_name
            for key in old
        }
        metadata_during_copy = {
            row["key"]: row["display_name"]
            for row in registry.strategy_meta(owner_id="owner.atomic")
            if row["key"] in old
        }
        assert resolved_during_copy == {"gen_atomic_a": "old-a", "gen_atomic_b": "old-b"}
        assert metadata_during_copy == resolved_during_copy

        allow_publication.set()
        publisher.join(timeout=5)
        assert not publisher.is_alive()
        resolved_after_swap = {
            key: registry.resolve_strategy(key, owner_id="owner.atomic").display_name
            for key in new
        }
        assert resolved_after_swap == {"gen_atomic_a": "new-a", "gen_atomic_b": "new-b"}
    finally:
        allow_publication.set()
        registry.replace_generated_partition("owner.atomic", {})


@pytest.mark.parametrize("key", ("trend_impulse_v3", "generated.bad", "gen_"))
def test_save_rejects_keys_outside_the_canonical_generated_namespace(key):
    init_db(reset=True)
    with SessionLocal() as session:
        composition = dict(_COMP, key=key)
        with pytest.raises(ValueError, match="generated strategy key"):
            gs.save_generated(session, key, json.dumps(composition), owner_id="owner")
        assert gs.list_generated(session, owner_id="owner") == []


def test_save_rejects_a_composition_whose_key_differs_from_the_persisted_identity():
    init_db(reset=True)
    with SessionLocal() as session:
        with pytest.raises(ValueError, match="composition key"):
            gs.save_generated(
                session, "gen_exec_test_v1", json.dumps(dict(_COMP, key="gen_sibling")),
                owner_id="owner")
        assert gs.list_generated(session, owner_id="owner") == []


def test_strategy_metadata_combines_builtins_with_only_the_requested_owner_partition():
    init_db(reset=True)
    from app.strategy import registry
    other = dict(_COMP, key="gen_owner_other")
    try:
        with SessionLocal() as session:
            session.execute(__import__("sqlalchemy").text(
                "INSERT INTO organizations VALUES "
                "('owner.other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            gs.save_generated(session, "gen_exec_test_v1", json.dumps(_COMP), owner_id="owner")
            gs.save_generated(session, "gen_owner_other", json.dumps(other), owner_id="owner.other")
            session.commit()
            gs.register_all(session, owner_id="owner")
            gs.register_all(session, owner_id="owner.other")
        owner_keys = {row["key"] for row in registry.strategy_meta(owner_id="owner")}
        other_keys = {row["key"] for row in registry.strategy_meta(owner_id="owner.other")}
        assert {"trend_impulse_v3", "expanding_z_v4", "gen_exec_test_v1"} <= owner_keys
        assert "gen_owner_other" not in owner_keys
        assert "gen_owner_other" in other_keys and "gen_exec_test_v1" not in other_keys
    finally:
        registry._GENERATED_REGISTRY.pop(("owner", "gen_exec_test_v1"), None)
        registry._GENERATED_REGISTRY.pop(("owner.other", "gen_owner_other"), None)


def test_strategy_metadata_routes_forward_the_composed_principal_owner(monkeypatch):
    from app.api import backtest_routes, routes
    from app.api.principal import Principal
    from app.strategy import registry

    seen = []
    monkeypatch.setattr(registry, "strategy_meta", lambda *, owner_id: seen.append(owner_id) or [])
    monkeypatch.setattr(routes, "owner_id_for", lambda _principal: "owner.route")
    monkeypatch.setattr(backtest_routes, "owner_id_for", lambda _principal: "owner.route")
    principal = Principal(id="caller", kind="owner", scopes=frozenset({"*"}))

    assert routes.strategies(principal) == {"strategies": []}
    response = backtest_routes.instruments("liquid", principal)
    assert response["strategies"] == []
    assert seen == ["owner.route", "owner.route"]
