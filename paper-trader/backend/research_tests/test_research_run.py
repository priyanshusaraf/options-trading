"""The research-run driver's plan must sweep BOTH 15m and 30m so each strategy is
evaluated on both of its native timeframes (the strategy is invalid on anything
slower or faster). The dev-blacklist filtering must still apply on every interval."""
import dataclasses
import importlib
import contextlib
import datetime as dt
import hashlib
import json
import math
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.engine.charges import (
    CORRECTED_RESEARCH_CHARGE_SCHEDULE,
    ROUNDING_POLICY_V2,
    charge_schedule_address,
)
from app.ir.hashing import canonical_json
from app.ir.validity import valid
from app.core.market_hours import ist_epoch
from app.market_data.observations import (
    load_normalized_observation,
    load_provider_observation,
    load_raw_segment,
)
from research.domain.base import init_research_db
from research.data.store import StaticDataSource, materialize
from research.domain.models import ExperimentRun, ExperimentSpec
from research.evaluation import kernels
from research.orchestrator.run import run_experiment
from research.operations import OperationAlreadyRunning
from research_tests import test_canonical_dataset as canonical_fixture


def _load():
    import scripts.research_run as rr
    return importlib.reload(rr)


@pytest.mark.parametrize("mutation", ["descending", "duplicate"])
def test_experiment_refuses_noncanonical_dataset_order_or_identity(
        research_session, inst_factory, candles_factory, mutation):
    instrument = inst_factory("ORDER")
    candles = candles_factory(20)
    if mutation == "descending":
        candles = list(reversed(candles))
    else:
        candles = candles + [candles[-1]]
    dataset = materialize(
        StaticDataSource({("ORDER", "day"): candles}), instrument, "day",
    )
    strategy = kernels.get_strategy("trend_impulse_v3")
    with pytest.raises(ValueError, match="canonical candle sequence"):
        run_experiment(
            research_session, owner_id="canonical-order-owner",
            program_name="Canonical order", hypothesis_statement="Order is frozen",
            strategy=strategy, datasets=[(instrument, dataset)], min_trades=10_000,
        )
    assert research_session.query(ExperimentRun).count() == 0


def test_research_spec_binds_the_resolved_v2_charge_schedule(
        research_session, inst_factory, candles_factory):
    source = StaticDataSource({("AAA", "day"): candles_factory(400)})
    instrument = inst_factory("AAA")
    dataset = materialize(source, instrument, "day")
    strategy = kernels.get_strategy("trend_impulse_v3")
    report = run_experiment(
        research_session,
        owner_id="charge-binding-owner",
        program_name="Charge binding",
        hypothesis_statement="Charge schedule identity is immutable",
        strategy=strategy,
        datasets=[(instrument, dataset)],
        params=dict(strategy.default_params),
        git_commit="charge-binding",
        min_trades=10_000,
        n_folds=2,
    )
    spec = research_session.get(
        ExperimentSpec, ("charge-binding-owner", report["spec_id"])
    )
    recipe = json.loads(spec.recipe_json)
    binding = recipe["resolved_charge_schedule"]
    assert binding["id"] == CORRECTED_RESEARCH_CHARGE_SCHEDULE
    assert binding["address"] == charge_schedule_address(
        CORRECTED_RESEARCH_CHARGE_SCHEDULE
    )
    assert binding["rounding_policy"]["id"] == ROUNDING_POLICY_V2
    assert binding["application_mode"] == (
        "current_public_schedule_counterfactual_as_of_2026_08_29"
    )


def test_partition_changes_identity_and_preserves_optional_robustness_shape(
        research_session, inst_factory, candles_factory):
    source = StaticDataSource({("COMPAT", "day"): candles_factory(12)})
    instrument = inst_factory("COMPAT")
    dataset = materialize(source, instrument, "day")
    strategy = kernels.get_strategy("trend_impulse_v3")
    shared = dict(
        owner_id="compat-owner", program_name="Compatibility",
        hypothesis_statement="Historical recipe bytes remain stable",
        strategy=strategy, datasets=[(instrument, dataset)],
        params=dict(strategy.default_params), git_commit="compat-build",
        min_trades=10_000, n_folds=2,
    )
    absent = run_experiment(research_session, **shared)
    stationary = run_experiment(research_session, **shared, robustness={
        "enabled": True, "iterations": 100, "restart_probability_ppm": 250_000,
    })
    absent_recipe = json.loads(research_session.get(
        ExperimentSpec, ("compat-owner", absent["spec_id"]),
    ).recipe_json)
    stationary_recipe = json.loads(research_session.get(
        ExperimentSpec, ("compat-owner", stationary["spec_id"]),
    ).recipe_json)
    assert "robustness" not in absent_recipe
    assert set(stationary_recipe["robustness"]) == {"stationary_bootstrap"}
    stripped = dict(stationary_recipe)
    del stripped["robustness"]
    assert stripped == absent_recipe
    partition = absent_recipe["research_partition"]
    assert partition["development_fraction"] == 0.7
    assert partition["validation_use"] == "locked_holdout"
    assert partition["datasets"]["COMPAT"] == {
        "development_bars": 8,
        "development_end_ts": ist_epoch(dataset.candles[7].ts),
        "validation_bars": 4,
        "validation_start_ts": ist_epoch(dataset.candles[8].ts),
        "validation_end_ts": ist_epoch(dataset.candles[-1].ts),
    }
    facts = {
        "absent_recipe_bytes": canonical_json(absent_recipe),
        "absent_recipe_sha256": hashlib.sha256(
            canonical_json(absent_recipe).encode()
        ).hexdigest(),
        "absent_spec_id": absent["spec_id"],
        "stationary_recipe_bytes": canonical_json(stationary_recipe),
        "stationary_recipe_sha256": hashlib.sha256(
            canonical_json(stationary_recipe).encode()
        ).hexdigest(),
        "stationary_spec_id": stationary["spec_id"],
    }
    assert facts["absent_recipe_sha256"] \
        == "ab7ce90695e73846cfa7421581990c9e0082b40dc047d8eb8b7693dd4a0a8a42"
    assert facts["absent_spec_id"] == "ab7ce90695e73846cfa7421581990c9e"
    assert facts["stationary_recipe_sha256"] \
        == "eb788c449cdfb1be11431984ae983092564a5b36e2f5eae88fd2e87208d4298c"
    assert facts["stationary_spec_id"] == "eb788c449cdfb1be11431984ae983092"
    print(json.dumps(facts, sort_keys=True))


def _signed_zero_dataset(instrument, zero):
    candle = SimpleNamespace(
        ts=dt.datetime(2026, 8, 30, 9, 15),
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=zero,
    )
    return materialize(
        StaticDataSource({(instrument.key, "day"): [candle]}),
        instrument,
        "day",
    )


def test_signed_zero_reuses_current_spec_and_refuses_stale_dataset_identity(
        research_session, inst_factory):
    instrument = inst_factory("SIGNED_ZERO")
    strategy = kernels.get_strategy("trend_impulse_v3")
    positive = _signed_zero_dataset(instrument, 0.0)
    negative = _signed_zero_dataset(instrument, -0.0)
    legacy_hash = "0" * 32
    legacy = dataclasses.replace(negative, content_hash=legacy_hash)
    shared = dict(
        owner_id="signed-zero-owner",
        program_name="Signed zero identity",
        hypothesis_statement="Equivalent market zero has one current research identity",
        strategy=strategy,
        params=dict(strategy.default_params),
        git_commit="signed-zero-correction",
        min_trades=10_000,
        n_folds=2,
    )

    with pytest.raises(ValueError, match="content identity"):
        run_experiment(research_session, datasets=[(instrument, legacy)], **shared)
    positive_report = run_experiment(
        research_session, datasets=[(instrument, positive)], **shared
    )
    negative_report = run_experiment(
        research_session, datasets=[(instrument, negative)], **shared
    )

    assert legacy_hash != positive.content_hash
    assert positive.content_hash == negative.content_hash
    assert positive_report["spec_id"] == negative_report["spec_id"]
    assert research_session.get(
        ExperimentSpec, ("signed-zero-owner", positive_report["spec_id"])
    ) is not None
    assert research_session.query(ExperimentSpec).filter_by(
        owner_id="signed-zero-owner"
    ).count() == 1
    assert research_session.query(ExperimentRun).filter_by(
        owner_id="signed-zero-owner",
        spec_id=positive_report["spec_id"],
    ).count() == 2
    print(json.dumps({
        "current_dataset_hash": positive.content_hash,
        "current_negative_spec_id": negative_report["spec_id"],
        "current_positive_spec_id": positive_report["spec_id"],
        "current_spec_run_count": 2,
        "legacy_dataset_hash": legacy_hash,
        "stored_spec_count": 1,
    }, sort_keys=True))


def _authority_zero_pipeline(tmp_path, monkeypatch, *, negative: bool):
    label = "negative" if negative else "positive"
    root = tmp_path / label
    root.mkdir()
    execution = create_engine(f"sqlite:///{root / 'execution.db'}")
    research = create_engine(f"sqlite:///{root / 'research.db'}")
    Base.metadata.create_all(execution)
    init_research_db(research)
    signed_zero = -0.0 if negative else 0.0

    def signed_raw_payload(value):
        if type(value) is dict and set(value) == {
                "open", "high", "low", "close", "volume"}:
            value = dict(value)
            value["volume"] = signed_zero
        return canonical_json(value)

    def signed_normalized_volume(_index, field, observation):
        if field == "VOLUME":
            return dataclasses.replace(observation, numeric=valid(signed_zero))
        return observation

    try:
        with Session(execution) as execution_session, Session(research) as research_session:
            with monkeypatch.context() as signed:
                signed.setattr(canonical_fixture, "canonical_json", signed_raw_payload)
                manifest = canonical_fixture.seed_canonical(
                    execution_session,
                    research_session,
                    count=1,
                    flat=True,
                    mutate_observation=signed_normalized_volume,
                )
            [(instrument, canonical)] = canonical_fixture.load(
                execution_session, research_session, manifest
            )
            volume_observation = next(
                observation
                for address in manifest.normalized_observation_addresses
                if (observation := load_normalized_observation(
                    execution_session, address
                )).field == "VOLUME"
            )
            provider_address = volume_observation.provider_observation_addresses[0]
            provider = load_provider_observation(execution_session, provider_address)
            raw = load_raw_segment(execution_session, provider.raw_segment_address)
            active = materialize(
                StaticDataSource({
                    (instrument.key, canonical.interval): list(canonical.candles)
                }),
                instrument,
                canonical.interval,
            )
            receipt = {
                "active_dataset_content_hash": active.content_hash,
                "canonical_research_content_hash": canonical.content_hash,
                "canonical_volume_negative": math.copysign(
                    1.0, canonical.candles[0].volume
                ) < 0,
                "manifest_address": manifest.manifest_address,
                "normalized_address": volume_observation.address,
                "normalized_volume_negative": math.copysign(
                    1.0, volume_observation.numeric.value
                ) < 0,
                "provider_address": provider.address,
                "raw_address": raw.address,
                "raw_volume_negative": math.copysign(
                    1.0, json.loads(raw.payload)["volume"]
                ) < 0,
                "segment_address": manifest.segment_addresses[0],
            }
            return receipt
    finally:
        execution.dispose()
        research.dispose()


def test_provider_to_manifest_to_research_preserves_evidence_and_converges_zero(
        tmp_path, monkeypatch):
    positive = _authority_zero_pipeline(
        tmp_path, monkeypatch, negative=False
    )
    negative = _authority_zero_pipeline(
        tmp_path, monkeypatch, negative=True
    )

    assert positive["raw_volume_negative"] is False
    assert negative["raw_volume_negative"] is True
    for identity in (
            "raw_address", "provider_address", "normalized_address",
            "segment_address", "manifest_address",
            "canonical_research_content_hash"):
        assert positive[identity] != negative[identity]
    assert positive["normalized_volume_negative"] is False
    assert negative["normalized_volume_negative"] is False
    assert positive["canonical_volume_negative"] is False
    assert negative["canonical_volume_negative"] is False
    assert (
        positive["active_dataset_content_hash"]
        == negative["active_dataset_content_hash"]
    )
    print(json.dumps({
        "negative": negative,
        "positive": positive,
    }, sort_keys=True))


def test_plan_sweeps_both_15m_and_30m(monkeypatch):
    monkeypatch.delenv("PT_WATCHLIST_SNAPSHOT", raising=False)
    rr = _load()
    plan = rr._plan(lambda k: k)          # identity instrument factory
    assert {item["interval"] for item in plan} == {"15minute", "30minute"}


def test_plan_runs_every_strategy_on_every_interval(monkeypatch):
    monkeypatch.delenv("PT_WATCHLIST_SNAPSHOT", raising=False)
    rr = _load()
    plan = rr._plan(lambda k: k)
    pairs = {(item["strategy_key"], item["interval"]) for item in plan}
    assert len(pairs) == len(plan)        # no duplicate (strategy, interval) cell
    for sk in ("trend_impulse_v3", "expanding_z_v4"):
        for iv in ("15minute", "30minute"):
            assert (sk, iv) in pairs


def test_plan_respects_dev_blacklist_on_every_interval(monkeypatch, tmp_path):
    import json
    snap = tmp_path / "wl.json"
    snap.write_text(json.dumps({"in_watchlists": ["NIFTY", "BANKNIFTY"]}))
    monkeypatch.setenv("PT_WATCHLIST_SNAPSHOT", str(snap))
    rr = _load()
    plan = rr._plan(lambda k: k)
    # NIFTY/BANKNIFTY are committed (and not in the always-allowed sandbox) -> excluded
    for item in plan:
        assert "NIFTY" not in item["instruments"]
        assert "BANKNIFTY" not in item["instruments"]
    # every interval is still represented after filtering
    assert {item["interval"] for item in plan} == {"15minute", "30minute"}


def test_manual_entry_point_reports_shared_lock_conflict(monkeypatch):
    rr = _load()
    monkeypatch.setattr(rr, "_enforce_isolation", lambda: "research.db")
    monkeypatch.setattr(rr, "_research_enabled", lambda: True)
    monkeypatch.setattr(
        rr,
        "_run_enabled_operation",
        lambda _research_db: (_ for _ in ()).throw(OperationAlreadyRunning()),
    )

    assert rr.main() == 2


def test_manual_entry_point_enforces_isolation_before_operation(monkeypatch):
    import pytest

    rr = _load()
    calls = []
    monkeypatch.setattr(
        rr, "_enforce_isolation",
        lambda: (_ for _ in ()).throw(RuntimeError("isolation failed")),
    )
    monkeypatch.setattr(rr, "_run_enabled_operation", lambda _db: calls.append(_db))

    with pytest.raises(RuntimeError, match="isolation failed"):
        rr.main()
    assert calls == []


def test_manual_entry_point_freeze_precedes_operation_receipt(monkeypatch):
    rr = _load()
    calls = []
    monkeypatch.setattr(rr, "_enforce_isolation", lambda: "research.db")
    monkeypatch.setattr(rr, "_research_enabled", lambda: False)
    monkeypatch.setattr(rr, "_run_enabled_operation", lambda _db: calls.append(_db))

    assert rr.main() == 0
    assert calls == []


def test_manual_operation_forwards_the_required_owner_to_every_research_call(monkeypatch):
    """The CLI has no compatibility owner: both manual paths receive the env owner."""
    rr = _load()
    monkeypatch.setenv("PT_RESEARCH_OWNER_ID", "manual-owner")
    monkeypatch.setattr(rr, "_plan", lambda _instrument: [])
    monkeypatch.setattr(rr, "_dump_db", lambda _session: None)
    monkeypatch.setattr(rr, "UNIVERSE", ("NIFTY",))
    monkeypatch.setattr(rr, "INTERVALS", ("day",))
    seen = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Engine:
        def dispose(self):
            pass

    class Recorder:
        @staticmethod
        def claim_next(*_args, **_kwargs):
            return None

        @staticmethod
        def start(*_args, **_kwargs):
            return Recorder()

        def transition(self, *_args):
            pass

        def start_watchdog(self, *_args, **_kwargs):
            pass

        def set_plan(self, *_args):
            pass

        def add_completed_run(self, *_args):
            pass

        def completed_item_run(self, *_args):
            return None

        def bound_item_run(self, *_args):
            return None

        def reclaim_bound_item(self, *_args):
            return None

        def bind_item_run_in_transaction(self, *_args):
            return True

        def finalize_item_in_transaction(self, *_args):
            return True

        def complete(self, **_kwargs):
            pass

        def fail(self, *_args, **_kwargs):
            pass

    import app.core.config as config
    import app.core.instruments as instruments
    import app.providers.factory as providers
    import research.data.store as data_store
    import research.domain.base as domain_base
    import research.domain.operations as domain_operations
    import research.operations as operations
    import research.orchestrator.generate as generate
    import research.orchestrator.run as run
    import research.universe as universe

    class Repository:
        def reconcile_expired(self, **_kwargs):
            return 0

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(provider="mock"))
    monkeypatch.setattr(instruments, "get_instrument", lambda key: SimpleNamespace(key=key))
    monkeypatch.setattr(providers, "get_provider", lambda: SimpleNamespace(name="mock"))
    monkeypatch.setattr(data_store, "KiteDataSource", lambda provider: provider)
    monkeypatch.setattr(domain_base, "make_engine", lambda _path: Engine())
    monkeypatch.setattr(domain_base, "init_research_db", lambda _engine: None)
    monkeypatch.setattr(domain_base, "make_sessionmaker", lambda _engine: Session)
    monkeypatch.setattr(domain_operations, "DurableOperationRecorder", Recorder)
    monkeypatch.setattr(domain_operations, "ResearchOperationRepository", lambda _session: Repository())
    monkeypatch.setattr(domain_operations, "operation_item_keys", lambda _plan, **_kwargs: ["generated:0"])
    monkeypatch.setattr(operations, "safe_plan_summary", lambda _plan: {
        "content_address": "sha256:plan", "experiment_count": 0, "items": [],
    })
    monkeypatch.setattr(universe, "ALWAYS_ALLOWED", frozenset({"NIFTY"}))
    monkeypatch.setattr(run, "run_nightly", lambda *_args, **kwargs: seen.append(("nightly", kwargs["owner_id"])) or [])
    monkeypatch.setattr(generate, "generated_descriptors", lambda *_args, **_kwargs: [{
        "interval": "day", "owner_universe": ["NIFTY"],
    }])
    monkeypatch.setattr(generate, "run_generated", lambda *_args, **kwargs: seen.append(("generated", kwargs["owner_id"])) or [])

    reports, provider = rr._run_enabled_operation("research.db")

    assert reports == []
    assert provider == "mock"
    assert seen == [("nightly", "manual-owner"), ("generated", "manual-owner")]


def test_dispatcher_claims_v2_graph_without_constructing_provider(monkeypatch):
    rr = _load()
    monkeypatch.setenv("PT_RESEARCH_OWNER_ID", "owner-v2")
    monkeypatch.setattr(rr, "_git_commit", lambda: "build-v2")
    seen = []

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    class Engine:
        def dispose(self): pass

    operation = SimpleNamespace(
        operation_id="operation-v2", trigger="v2_graph", build="build-v2",
        provider_mode="persisted-dataset", plan={"closed": True},
    )

    class Repository:
        def __init__(self, _session): pass
        def reconcile_expired(self, **_kwargs): return 0
        def get(self, *_args, **_kwargs): return operation

    class Recorder:
        operation_id = operation.operation_id
        token = "claim-v2"

        @classmethod
        def claim_next(cls, *_args, **kwargs):
            assert kwargs["triggers"] == ("v2_graph", "manual")
            return cls()

        def start_watchdog(self, *_args, **_kwargs): pass
        def transition(self, stage): seen.append(("stage", stage))
        def complete(self): raise AssertionError("V2 dispatcher used split completion")
        def close_watchdog(self): seen.append(("watchdog_closed", None))
        def fail(self, error): raise AssertionError(error)

    import app.core.config as config
    import app.db.session as execution_db
    import app.providers.factory as providers
    import research.domain.base as domain_base
    import research.domain.operations as domain_operations
    import research.orchestrator.graph_experiment as graph_experiment

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(provider="forbidden"))
    monkeypatch.setattr(domain_base, "make_engine", lambda _path: Engine())
    monkeypatch.setattr(domain_base, "init_research_db", lambda _engine: None)
    monkeypatch.setattr(domain_base, "make_sessionmaker", lambda _engine: Session)
    monkeypatch.setattr(domain_operations, "DurableOperationRecorder", Recorder)
    monkeypatch.setattr(domain_operations, "ResearchOperationRepository", Repository)
    monkeypatch.setattr(execution_db, "SessionLocal", Session)
    monkeypatch.setattr(
        providers, "get_provider",
        lambda: (_ for _ in ()).throw(AssertionError("V2 branch constructed provider")),
    )
    monkeypatch.setattr(
        graph_experiment, "run_saved_v2_graph_experiment",
        lambda **kwargs: seen.append(("run", kwargs["operation"].operation_id))
        or {"run_id": 41},
    )

    reports, mode = rr._run_enabled_operation("research.db")
    assert reports == [{"run_id": 41}]
    assert mode == "persisted-dataset"
    assert seen == [("stage", "planning"), ("run", "operation-v2"),
                    ("watchdog_closed", None)]


@pytest.mark.parametrize("trigger,build,provider", [
    ("v2_graph", "old-build", "persisted-dataset"),
    ("v2_graph", "current-build", "mock"),
    ("manual", "current-build", "wrong-provider"),
])
def test_dispatcher_refuses_changed_replay_provenance_before_execution(monkeypatch, trigger, build, provider):
    from types import SimpleNamespace
    import scripts.research_run as runner
    from app.core.config import get_settings
    failures = []
    claimed = SimpleNamespace(trigger=trigger, build=build, provider_mode=provider)
    repository = SimpleNamespace(get=lambda *_args, **_kwargs: claimed)
    recorder = SimpleNamespace(operation_id="op", fail=failures.append)
    monkeypatch.setattr(runner, "_git_commit", lambda: "current-build")
    monkeypatch.setattr(get_settings(), "provider", "mock")
    with pytest.raises(RuntimeError, match="replay provenance mismatch"):
        runner._verified_claim(repository, recorder, "owner")
    assert failures[0]["code"] == "RESEARCH_OPERATION_PROVENANCE_MISMATCH"


def test_dispatcher_refuses_a_disappeared_claim():
    from types import SimpleNamespace
    import scripts.research_run as runner
    repository = SimpleNamespace(get=lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match="disappeared"):
        runner._verified_claim(repository, SimpleNamespace(operation_id="op"), "owner")


@pytest.mark.parametrize("stamp,expected", [("commit=release-build\n", "release-build"), ("", "unknown")])
def test_dispatcher_uses_the_same_process_build_as_api_enqueue(monkeypatch, tmp_path, stamp, expected):
    import scripts.research_run as runner
    from app.core import version
    path = tmp_path / "VERSION"
    path.write_text(stamp)
    monkeypatch.setattr(version, "_VERSION_PATH", path)
    monkeypatch.setattr(version, "_cache", None)
    # API enqueue uses this getter, including the explicit local unknown state.
    claimed = SimpleNamespace(trigger="v2_graph", build=version.get_build_sha(), provider_mode="persisted-dataset")
    assert claimed.build == expected
    repository = SimpleNamespace(get=lambda *_args, **_kwargs: claimed)
    failures = []
    recorder = SimpleNamespace(operation_id="same-api-job", fail=failures.append)
    assert runner._verified_claim(repository, recorder, "owner") is claimed
    assert failures == []


def test_v2_dispatcher_starts_heartbeat_before_cold_component_imports(monkeypatch):
    import builtins
    import scripts.research_run as runner
    seen = []
    original_import = builtins.__import__
    @contextlib.contextmanager
    def execution_session():
        yield "synthetic-execution-session"
    def imported(name, *args, **kwargs):
        if name == "app.db.session":
            assert "heartbeat" in seen
            return SimpleNamespace(SessionLocal=execution_session)
        if name == "research.orchestrator.graph_experiment":
            assert "heartbeat" in seen
            return SimpleNamespace(run_saved_v2_graph_experiment=lambda **_kwargs: {"run_id": 91})
        return original_import(name, *args, **kwargs)
    recorder = SimpleNamespace(start_watchdog=lambda _callback: seen.append("heartbeat"),
        transition=lambda stage: seen.append(stage), close_watchdog=lambda: seen.append("closed"))
    monkeypatch.setattr(builtins, "__import__", imported)
    assert runner._run_claimed_v2("claimed", recorder, "repository", "session", "research.db") == ([{"run_id": 91}], "persisted-dataset")
    assert seen == ["heartbeat", "planning", "closed"]
