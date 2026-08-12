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


def _payload(address: str = "a" * 64) -> dict:
    payload = {field: 0 for field in public_computation.PUBLIC_RESULT_FIELDS}
    payload.update({
        "instrument_key": "NIFTY", "interval": "15minute",
        "strategy_key": "trend_impulse_v3",
        "strategy_version": public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
        "params_hash": address, "last_candle_ts": 123,
        "net_pnl": 42.0, "curve_json": "[]", "trades_json": "[]",
    })
    return payload


def _expected(address: str) -> dict:
    catalog = public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]
    return dict(execution_address=address, dataset_classification=dataset_store.MARKET_PUBLIC,
                strategy_key="trend_impulse_v3", strategy_module=catalog["module"],
                strategy_version=catalog["version"], policy_address=address,
                execution_manifest={"dataset_address": "c" * 64, "dataset_verified": True})


def test_public_artifact_is_immutable_neutral_payload_and_materializes_locally():
    """Two owners receive independent local values from one public artifact."""
    init_db(reset=True)
    address = "b" * 64
    with SessionLocal() as session:
        first = public_computation.put_immutable(
            session, execution_address=address, dataset_address="c" * 64,
            strategy_key="trend_impulse_v3", strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
            policy_address=address, payload=_payload(address))
        session.commit()
        assert first.execution_address == address
    with SessionLocal() as session:
        stored = session.get(BacktestComputation, address)
        assert stored is not None
        raw = json.loads(stored.payload_json)["result"]
        assert "owner_id" not in raw and "run_id" not in raw
        assert "computed_at" not in raw and "from_cache" not in raw
        a = public_computation.maybe_materialize(session, **_expected(address))
        b = public_computation.maybe_materialize(session, **_expected(address))
        assert a == b
        assert a["from_cache"] is True


def test_conflicting_public_bytes_refuse_without_overwriting_artifact():
    init_db(reset=True)
    address = "e" * 64
    with SessionLocal() as session:
        public_computation.put_immutable(
            session, execution_address=address, dataset_address="c" * 64,
            strategy_key="trend_impulse_v3", strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
                policy_address=address, payload=_payload(address))
        session.commit()
    with SessionLocal() as session:
        changed = _payload(address) | {"net_pnl": 99.0}
        with pytest.raises(public_computation.PublicComputationIntegrityError):
            public_computation.put_immutable(
                session, execution_address=address, dataset_address="c" * 64,
                strategy_key="trend_impulse_v3", strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
                policy_address=address, payload=changed)
        session.rollback()
        assert public_computation.maybe_materialize(session, **_expected(address))["net_pnl"] == 42.0


def test_public_payload_rejects_owner_or_run_provenance():
    init_db(reset=True)
    with SessionLocal() as session:
        with pytest.raises(public_computation.PublicComputationIntegrityError, match="exact v1"):
            public_computation.put_immutable(
                session, execution_address="f" * 64, dataset_address="c" * 64,
                strategy_key="trend_impulse_v3", strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
            policy_address="f" * 64, payload=_payload("f" * 64) | {"owner_id": "a"})


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
                    strategy_key="trend_impulse_v3", strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
                    policy_address="9" * 64, payload=_payload("9" * 64))
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
        strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
        policy_address="a" * 64,
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
        strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
        policy_address="b" * 64,
        execution_manifest={"dataset_address": "a" * 64, "dataset_verified": False}) is None
    assert calls == []


def test_public_payload_is_a_versioned_exact_allowlist_and_never_copies_local_metadata():
    """A public artifact is a closed pure-result format, not a filtered ORM row."""
    assert public_computation.PUBLIC_PAYLOAD_VERSION >= 1
    allowed = set(public_computation.PUBLIC_RESULT_FIELDS)
    assert allowed
    with pytest.raises(public_computation.PublicComputationIntegrityError, match="exact v1"):
        public_computation.canonical_public_payload(
            {next(iter(allowed)): 1, "owner_id": "private"})
    with pytest.raises(public_computation.PublicComputationIntegrityError, match="exact v1"):
        public_computation.canonical_public_payload({next(iter(allowed)): 1})


def test_public_payload_requires_the_complete_v1_schema():
    payload = {field: 0 for field in public_computation.PUBLIC_RESULT_FIELDS}
    with pytest.raises(public_computation.PublicComputationIntegrityError, match="exact v1"):
        public_computation.canonical_public_payload(
            {key: value for key, value in payload.items() if key != "params_hash"})


def test_public_payload_semantics_must_match_the_artifact_identity():
    init_db(reset=True)
    address = "a" * 64
    payload = {field: 0 for field in public_computation.PUBLIC_RESULT_FIELDS}
    payload.update(strategy_key="trend_impulse_v3", strategy_version="wrong",
                   params_hash=address)
    with SessionLocal() as session:
        with pytest.raises(public_computation.PublicComputationIntegrityError, match="semantic"):
            public_computation.put_immutable(
                session, execution_address=address, dataset_address="b" * 64,
                strategy_key="trend_impulse_v3",
                strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
                policy_address=address, payload=payload)


def test_manifest_private_or_extra_key_never_queries_shared_artifact(monkeypatch):
    calls = []
    monkeypatch.setattr(public_computation, "_lookup", lambda *args, **kwargs: calls.append(args))
    manifest = {"dataset_address": "a" * 64, "dataset_verified": True,
                "owner_id": "private"}
    assert public_computation.maybe_materialize(
        object(), execution_address="b" * 64, dataset_classification=dataset_store.MARKET_PUBLIC,
        strategy_key="trend_impulse_v3", strategy_module="app.strategy.registry.trend_impulse_v3",
        strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG["trend_impulse_v3"]["version"],
        policy_address="b" * 64, execution_manifest=manifest) is None
    assert calls == []


def test_poisoned_stored_payload_identity_refuses_materialization():
    init_db(reset=True)
    address = "a" * 64
    expected = _expected(address)
    payload = {field: 0 for field in public_computation.PUBLIC_RESULT_FIELDS}
    payload.update(strategy_key="trend_impulse_v3", strategy_version=expected["strategy_version"],
                   params_hash=address)
    with SessionLocal() as session:
        public_computation.put_immutable(session, execution_address=address,
            dataset_address="c" * 64, strategy_key="trend_impulse_v3",
            strategy_version=expected["strategy_version"], policy_address=address,
            payload=payload)
        row = session.get(BacktestComputation, address)
        envelope = json.loads(row.payload_json)
        envelope["result"]["strategy_key"] = "poisoned"
        row.payload_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        row.payload_digest = __import__("hashlib").sha256(row.payload_json.encode()).hexdigest()
        session.commit()
    with SessionLocal() as session:
        with pytest.raises(public_computation.PublicComputationIntegrityError, match="semantic"):
            public_computation.maybe_materialize(session, **expected)


def test_shared_lookup_requires_exact_expected_artifact_metadata_before_query(monkeypatch):
    calls = []
    monkeypatch.setattr(public_computation, "_lookup", lambda *a, **k: calls.append(a))
    manifest = {"dataset_address": "a" * 64, "dataset_verified": True}
    assert public_computation.maybe_materialize(
        object(), execution_address="b" * 64, dataset_classification=dataset_store.MARKET_PUBLIC,
        strategy_key="trend_impulse_v3", strategy_module="app.strategy.registry.trend_impulse_v3",
        strategy_version="not-in-the-public-catalog", policy_address="b" * 64,
        execution_manifest=manifest) is None
    assert calls == []


def test_runtime_registry_mutation_cannot_become_platform_public():
    from app.strategy.registry.base import Strategy
    class RuntimeStrategy(Strategy):
        key = "trend_impulse_v3"
        default_params = {"ema_length": 50}
    assert public_computation.strategy_is_platform_public(RuntimeStrategy()) is False


def test_public_catalog_refuses_checked_in_strategy_when_its_source_digest_changes(monkeypatch):
    from app.strategy.registry import resolve_strategy
    strategy = resolve_strategy("trend_impulse_v3")
    monkeypatch.setattr(public_computation, "_module_source_digest", lambda _strategy: "0" * 64)
    assert public_computation.strategy_is_platform_public(strategy) is False


def test_checked_in_public_catalog_matches_only_checked_in_registry_modules():
    """Catalog drift disables sharing until a source-review updates its constants."""
    from app.strategy.registry import resolve_strategy
    for key, expected in public_computation.PUBLIC_STRATEGY_CATALOG.items():
        strategy = resolve_strategy(key)
        assert type(strategy).__module__ == expected["module"]
        assert strategy.version == expected["version"]
        assert strategy.default_params == expected["defaults"]
        assert public_computation._module_source_digest(strategy) == expected["source_digest"]


def test_parallel_shared_hit_is_planned_in_parent_and_cold_worker_publishes():
    """Parallel paths have the same public cache contract as serial execution."""
    from app.providers.mock import MockProvider
    from app.db.models import Organization
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="parallel-a", name="Parallel A"),
                         Organization(organization_id="parallel-b", name="Parallel B")])
        session.commit()
    provider = MockProvider()
    first = sweep.start_sweep(owner_id="parallel-a", scope="liquid", intervals=["15minute"],
                              instruments=["NIFTY"], capital=50_000, provider=provider,
                              workers=2)
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(select(BacktestComputation)))
        assert len(rows) == 1
    second = sweep.start_sweep(owner_id="parallel-b", scope="liquid", intervals=["15minute"],
                               instruments=["NIFTY"], capital=50_000, provider=provider,
                               workers=2)
    sweep._join()
    from app.db.models import BacktestResult
    with SessionLocal() as session:
        rows = list(session.scalars(select(BacktestResult).where(BacktestResult.run_id == second)))
        assert len(rows) == 1 and rows[0].from_cache is True
