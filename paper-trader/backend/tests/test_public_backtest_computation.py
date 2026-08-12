"""Public computation reuse never turns private evidence into a shared row."""
from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.backtest import public_computation
from app.backtest import dataset_store
from app.backtest import sweep
from app.db.models import BacktestComputation
from app.db.session import SessionLocal, init_db


def _payload() -> dict:
    return {
        "instrument_key": "NIFTY", "interval": "15minute",
        "strategy_key": "trend_impulse_v3", "strategy_version": "v1",
        "params_hash": "a" * 64, "last_candle_ts": 123,
        "net_pnl": 42.0, "curve_json": "[]", "trades_json": "[]",
        "from_cache": False, "computed_at": "also-private",
    }


def test_public_artifact_is_immutable_neutral_payload_and_materializes_locally():
    """Two owners receive independent local values from one public artifact."""
    init_db(reset=True)
    address = "b" * 64
    with SessionLocal() as session:
        first = public_computation.put_immutable(
            session, execution_address=address, dataset_address="c" * 64,
            strategy_key="trend_impulse_v3", strategy_version="v1",
            policy_address="d" * 64, payload=_payload())
        session.commit()
        assert first.execution_address == address
    with SessionLocal() as session:
        stored = session.get(BacktestComputation, address)
        assert stored is not None
        raw = json.loads(stored.payload_json)
        assert "owner_id" not in raw and "run_id" not in raw
        assert "computed_at" not in raw and "from_cache" not in raw
        a = public_computation.materialize(session, execution_address=address)
        b = public_computation.materialize(session, execution_address=address)
        assert a == b
        assert a["from_cache"] is True


def test_conflicting_public_bytes_refuse_without_overwriting_artifact():
    init_db(reset=True)
    address = "e" * 64
    with SessionLocal() as session:
        public_computation.put_immutable(
            session, execution_address=address, dataset_address="c" * 64,
            strategy_key="trend_impulse_v3", strategy_version="v1",
            policy_address="d" * 64, payload=_payload())
        session.commit()
    with SessionLocal() as session:
        changed = _payload() | {"net_pnl": 99.0}
        with pytest.raises(public_computation.PublicComputationIntegrityError):
            public_computation.put_immutable(
                session, execution_address=address, dataset_address="c" * 64,
                strategy_key="trend_impulse_v3", strategy_version="v1",
                policy_address="d" * 64, payload=changed)
        session.rollback()
        assert public_computation.materialize(session, execution_address=address)["net_pnl"] == 42.0


def test_public_payload_rejects_owner_or_run_provenance():
    init_db(reset=True)
    with SessionLocal() as session:
        with pytest.raises(public_computation.PublicComputationIntegrityError, match="source identity"):
            public_computation.put_immutable(
                session, execution_address="f" * 64, dataset_address="c" * 64,
                strategy_key="trend_impulse_v3", strategy_version="v1",
                policy_address="d" * 64, payload=_payload() | {"owner_id": "a"})


def test_concurrent_identical_public_writers_converge_to_one_immutable_payload():
    init_db(reset=True)
    barrier = threading.Barrier(2)
    errors = []
    def writer():
        try:
            barrier.wait()
            with SessionLocal() as session:
                public_computation.put_immutable(
                    session, execution_address="9" * 64, dataset_address="c" * 64,
                    strategy_key="trend_impulse_v3", strategy_version="v1",
                    policy_address="d" * 64, payload=_payload())
                session.commit()
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=writer) for _ in range(2)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert errors == []
    with SessionLocal() as session:
        assert len(list(session.scalars(select(BacktestComputation)))) == 1


def test_ineligible_or_private_input_never_queries_public_artifact(monkeypatch):
    """Deny by default: private classifications cannot use the global table."""
    calls = []
    monkeypatch.setattr(public_computation, "_lookup", lambda *a, **k: calls.append(a))
    assert public_computation.is_eligible(
        dataset_classification="BYOD_PRIVATE", strategy_key="trend_impulse_v3",
        strategy_module="app.strategy.registry.trend_impulse_v3",
        execution_manifest={"dataset_address": "a" * 64, "dataset_verified": True}) is False
    assert public_computation.maybe_materialize(
        object(), execution_address="a" * 64, dataset_classification="BYOD_PRIVATE",
        strategy_key="trend_impulse_v3", strategy_module="app.strategy.registry.trend_impulse_v3",
        execution_manifest={"dataset_address": "a" * 64, "dataset_verified": True}) is None
    assert calls == []


def test_public_dataset_port_refuses_private_classification_before_blob_or_index_io(tmp_path):
    store = dataset_store.DatasetStore(tmp_path)
    try:
        with pytest.raises(dataset_store.DatasetStoreError, match="public"):
            store.get("a" * 64, classification="BYOD_PRIVATE")
        with pytest.raises(dataset_store.DatasetStoreError, match="public"):
            store.lookup(provider={"key": "p"}, instrument={"key": "i"}, interval="day",
                         requested_window={}, classification="BYOD_PRIVATE")
    finally:
        store.close()


def test_two_owners_share_only_neutral_public_computation_not_a_result_row():
    """Warm B is pure bytes from MARKET, never an A result source row."""
    from app.core.instruments import get_instrument
    from app.providers.mock import MockProvider
    init_db(reset=True)
    provider, inst = MockProvider(), get_instrument("NIFTY")
    win = {"lookback_days": 30, "start": None, "end": None}
    strategy = __import__("app.strategy.registry", fromlist=["get_strategy"]).get_strategy(None)
    prepared = sweep._prepare_dataset(provider, inst, "15minute", win)
    cold = sweep._one(provider, inst, "15minute", 50_000, win, strategy,
                      owner_id="owner-a", prepared=prepared)
    warm = sweep._one(provider, inst, "15minute", 50_000, win, strategy,
                      owner_id="owner-b", prepared=prepared)
    assert cold["from_cache"] is False and warm["from_cache"] is True
    assert {k: v for k, v in warm.items() if k not in {"from_cache", "computed_at"}} == {
        k: v for k, v in cold.items() if k not in {"from_cache", "computed_at"}}
    with SessionLocal() as session:
        assert len(list(session.scalars(select(BacktestComputation)))) == 1


def test_generated_or_ir_strategy_is_rejected_before_shared_lookup(monkeypatch):
    calls = []
    monkeypatch.setattr(public_computation, "_lookup", lambda *a, **k: calls.append(a))
    prepared = sweep._PreparedDataset(dataset_address="a" * 64, last_ts=1,
                                      dataset_classification=dataset_store.MARKET_PUBLIC,
                                      dataset_verified=True)
    for key, module in (("gen_same_hash", "app.core.generated_strategies"),
                        ("ir.graph", "app.strategy.ir_adapter")):
        strategy_type = type("PrivateStrategy", (), {"__module__": module,
                                                       "key": key, "version": "v"})
        assert sweep._public_reusable_values(prepared, strategy_type(), "b" * 64) is None
    assert calls == []


def test_unverified_dataset_address_is_rejected_before_public_lookup(monkeypatch):
    calls = []
    monkeypatch.setattr(public_computation, "_lookup", lambda *a, **k: calls.append(a))
    assert public_computation.maybe_materialize(
        object(), execution_address="b" * 64, dataset_classification=dataset_store.MARKET_PUBLIC,
        strategy_key="trend_impulse_v3", strategy_module="app.strategy.registry.trend_impulse_v3",
        execution_manifest={"dataset_address": "a" * 64, "dataset_verified": False}) is None
    assert calls == []
