from __future__ import annotations

import ast
from dataclasses import replace
import functools
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest
from sqlalchemy import create_engine, event, text

from app.backtest.artifacts import (
    BoundedResearchArtifactStore,
    ResearchArtifactRefusal,
    research_cache_identity_document,
)
from app.backtest.worker import (
    BoundedLocalResearchQueue,
    BoundedWorkerObservationStore,
    ResearchWorkerDependencies,
    ResearchWorkerLimits,
    ResearchWorkerRefusal,
    ResearchWorkerRuntime,
    WORKER_ROLES,
    admit_durable_queue_slot,
    research_worker_build_address,
    submit_durable_research_request,
    verify_locked_environment,
)
from app.ir.hashing import content_address


BACKEND = Path(__file__).resolve().parents[1]
LOCK = BACKEND / "requirements.lock"
SCRIPT = BACKEND / "scripts/run_research_worker.py"


def _limits(**overrides):
    values = dict(
        queue_depth=2, concurrency=1, maximum_attempts=2,
        cache_bytes=1024, artifact_bytes=512, database_connections=2,
        memory_bytes=1024, disk_bytes=2048, retention_entries=4,
    )
    values.update(overrides)
    return ResearchWorkerLimits(**values)


def _address(name):
    return content_address({"phase5-worker-test": name})


def _artifact_identity_document(*, owner_id="owner", suffix="a"):
    return dict(research_cache_identity_document(
        owner_id=owner_id, licence_scope="OWNER_PRIVATE",
        semantic_nodes=[{"component_id": "analytical.sma", "component_version": 1}],
        parameters_address=_address(f"parameters-{suffix}"),
        instrument_addresses=[_address(f"instrument-{suffix}")],
        registry_snapshot_address=_address(f"registry-{suffix}"),
        dataset_manifest_address=_address(f"dataset-{suffix}"),
        provider_evidence_addresses=[_address(f"provider-{suffix}")],
        event_start="2026-01-01T00:00:00+00:00",
        event_end="2026-01-02T00:00:00+00:00",
        segment_addresses=[_address(f"segment-{suffix}")],
        adjustment_policy_address=_address(f"adjustment-{suffix}"),
        session_policy_address=_address(f"session-{suffix}"),
        resampling_policy_address=_address(f"resampling-{suffix}"),
        missing_data_policy_address=_address(f"missing-{suffix}"),
        alignment_policy_address=_address(f"alignment-{suffix}"),
        implementation_closure_address=_address(f"implementation-{suffix}"),
        resolved_graph_address=_address(f"graph-{suffix}"),
        resource_plan_address=_address(f"resource-{suffix}"),
        evaluation_policy_address=_address(f"evaluation-{suffix}"),
        node_context_resolver_address=_address(f"resolver-{suffix}"),
        run_authority_address=_address(f"run-{suffix}"),
    ))


def _runtime(queue=None):
    lock = verify_locked_environment(LOCK)
    build = research_worker_build_address(lock, source_paths=(
        BACKEND / "app/backtest/worker.py", SCRIPT,
    ))
    return ResearchWorkerRuntime(
        worker_id="worker-a",
        queue=queue or BoundedLocalResearchQueue(
            depth_upper_bound=2, maximum_attempts=2,
        ),
        limits=_limits(), build_address=build,
    )


def _bounded_engine(path, *, connections=2):
    engine = create_engine(
        f"sqlite:///{path}", future=True,
        connect_args={"check_same_thread": False},
        pool_size=connections, max_overflow=0, pool_timeout=1,
    )

    @event.listens_for(engine, "connect")
    def configure(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    return engine


@pytest.fixture()
def topology_runtime(tmp_path, monkeypatch):
    from app.backtest import sweep
    from app.db.migrate import head_revision, stamp
    from app.db.models import Base
    from research.domain.base import init_research_db

    execution = _bounded_engine(tmp_path / "execution.db")
    research = _bounded_engine(tmp_path / "research.db")
    Base.metadata.create_all(execution)
    stamp(execution, head_revision())
    init_research_db(research)
    limits = _limits(cache_bytes=128 * 1024, artifact_bytes=64 * 1024)
    monkeypatch.setenv("PT_DISABLE_DOTENV", "1")
    monkeypatch.setenv("PT_WORKER_MEMORY_LIMIT_BYTES", str(limits.memory_bytes))
    monkeypatch.setenv("PT_WORKER_SUPERVISOR_PID", str(os.getppid()))
    artifact_store = BoundedResearchArtifactStore(
        owner_id="owner", licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=limits.cache_bytes,
        artifact_bytes_upper_bound=limits.artifact_bytes,
        entry_upper_bound=limits.retention_entries,
        concurrency_upper_bound=limits.concurrency,
        queue_depth_upper_bound=limits.queue_depth,
    )
    observations = BoundedWorkerObservationStore(
        root=tmp_path / "observations",
        disk_bytes_upper_bound=limits.disk_bytes,
        retention_upper_bound=limits.retention_entries,
    )
    worker = ResearchWorkerRuntime(
        worker_id="worker-a",
        queue=BoundedLocalResearchQueue(
            depth_upper_bound=limits.queue_depth,
            maximum_attempts=limits.maximum_attempts,
        ),
        limits=limits,
        build_address=content_address({"build": "test"}),
        dependencies=ResearchWorkerDependencies(
            execution_engine=execution, research_engine=research,
                artifact_store=artifact_store,
                durable_dispatch=sweep.dispatch_all_reclaimable,
                durable_wait=sweep._join,
                api_submit=submit_durable_research_request,
        ),
        observations=observations,
    )
    yield worker
    execution.dispose(); research.dispose()


def test_complete_lock_matches_environment_and_contains_no_mutable_requirement():
    lock = verify_locked_environment(LOCK)
    assert len(lock.requirements) == 59
    assert lock.lock_address.startswith("sha256:")
    for line in LOCK.read_text().splitlines():
        value = line.split("#", 1)[0].strip()
        if value: assert value.count("==") == 1


def test_mutable_duplicate_missing_and_wrong_lock_entries_refuse(tmp_path):
    for text in (
        "pandas>=3\n", "pandas==3.0.5\npandas==3.0.5\n",
        "not-a-real-package==1.0\n", "pandas==0.0.1\n",
    ):
        path = tmp_path / (content_address({"text": text})[-8:] + ".lock")
        path.write_text(text)
        with pytest.raises(ResearchWorkerRefusal): verify_locked_environment(path)


def test_build_identity_binds_lock_and_every_source(tmp_path):
    lock = verify_locked_environment(LOCK)
    first = tmp_path / "a.py"; second = tmp_path / "b.py"
    first.write_text("x=1\n"); second.write_text("y=2\n")
    baseline = research_worker_build_address(lock, source_paths=(first, second))
    assert baseline == research_worker_build_address(lock, source_paths=(second, first))
    second.write_text("y=3\n")
    assert research_worker_build_address(lock, source_paths=(first, second)) != baseline


def test_queue_depth_duplicate_identity_and_owner_are_exact():
    queue = BoundedLocalResearchQueue(depth_upper_bound=2, maximum_attempts=2)
    first = queue.enqueue(owner_id="owner-a", payload={"value": 1})
    assert queue.enqueue(owner_id="owner-a", payload={"value": 1}) == first
    queue.enqueue(owner_id="owner-b", payload={"value": 1})
    with pytest.raises(ResearchWorkerRefusal, match="depth"):
        queue.enqueue(owner_id="owner-a", payload={"value": 2})
    assert queue.counts()["PENDING"] == 2


def test_claim_completion_is_fenced_and_duplicate_delivery_is_exactly_once():
    queue = BoundedLocalResearchQueue(depth_upper_bound=2, maximum_attempts=2)
    address = queue.enqueue(owner_id="owner-a", payload={"value": 1})
    claim = queue.claim(worker_id="worker-a")
    result = content_address({"result": 1})
    assert claim.job_address == address and queue.complete(claim, result_address=result)
    with pytest.raises(ResearchWorkerRefusal, match="stale"):
        queue.complete(claim, result_address=result)
    assert queue.enqueue(owner_id="owner-a", payload={"value": 1}) == address
    assert queue.claim(worker_id="worker-b") is None
    assert queue.counts()["COMPLETED"] == 1


def test_forced_death_reclaims_and_fences_old_claim():
    queue = BoundedLocalResearchQueue(depth_upper_bound=1, maximum_attempts=2)
    queue.enqueue(owner_id="owner-a", payload={"value": 1})
    old = queue.claim(worker_id="worker-a")
    assert queue.expire_claims() == 1
    replacement = queue.claim(worker_id="worker-b")
    assert replacement.attempt == 2 and replacement.claim_token != old.claim_token
    with pytest.raises(ResearchWorkerRefusal, match="stale"):
        queue.complete(old, result_address=content_address({"old": True}))
    assert queue.expire_claims() == 1
    assert queue.claim(worker_id="worker-c") is None
    assert queue.counts()["FAILED"] == 1
    with pytest.raises(ResearchWorkerRefusal, match="stale"):
        queue.complete(replacement, result_address=content_address({"new": True}))


def test_failure_retry_is_bounded_and_cancel_never_requeues():
    queue = BoundedLocalResearchQueue(depth_upper_bound=2, maximum_attempts=2)
    retry_job = queue.enqueue(owner_id="owner-a", payload={"value": 1})
    first = queue.claim(worker_id="worker")
    assert queue.fail(first, retry=True)
    second = queue.claim(worker_id="worker")
    assert second.job_address == retry_job and second.attempt == 2
    assert queue.fail(second, retry=True)
    assert queue.counts()["FAILED"] == 1
    cancelled = queue.enqueue(owner_id="owner-a", payload={"value": 2})
    assert queue.cancel(owner_id="owner-a", job_address=cancelled)
    assert queue.counts()["CANCELLED"] == 1


def test_snapshot_restart_requires_no_active_claim_and_preserves_terminal_rows():
    queue = BoundedLocalResearchQueue(depth_upper_bound=2, maximum_attempts=2)
    queue.enqueue(owner_id="owner-a", payload={"value": 1})
    claimed = queue.claim(worker_id="worker")
    with pytest.raises(ResearchWorkerRefusal, match="CLAIMED|stale"):
        BoundedLocalResearchQueue.from_snapshot(queue.snapshot())
    queue.expire_claims()
    restored = BoundedLocalResearchQueue.from_snapshot(queue.snapshot())
    replacement = restored.claim(worker_id="replacement")
    assert replacement.attempt == claimed.attempt + 1
    assert restored.complete(replacement, result_address=content_address({"ok": True}))
    terminal = BoundedLocalResearchQueue.from_snapshot(restored.snapshot())
    assert terminal.counts()["COMPLETED"] == 1


def test_worker_run_once_graceful_stop_and_handler_failure_are_safe():
    queue = BoundedLocalResearchQueue(depth_upper_bound=3, maximum_attempts=2)
    queue.enqueue(owner_id="owner", payload={"value": 1})
    worker = _runtime(queue)
    assert worker.run_once(lambda payload: content_address({"payload": dict(payload)}))
    queue.enqueue(owner_id="owner", payload={"value": 2})
    with pytest.raises(RuntimeError, match="boom"):
        worker.run_once(lambda _payload: (_ for _ in ()).throw(RuntimeError("boom")))
    assert queue.counts()["PENDING"] == 1
    assert worker.run_once(lambda payload: content_address({"payload": dict(payload)}))
    queue.enqueue(owner_id="owner", payload={"value": 3})
    worker.stop()
    assert not worker.run_once(lambda _payload: content_address({"never": True}))
    assert queue.counts()["PENDING"] == 1


def test_concurrency_one_admits_exactly_one_simultaneous_handler():
    queue = BoundedLocalResearchQueue(depth_upper_bound=2, maximum_attempts=2)
    queue.enqueue(owner_id="owner", payload={"value": 1})
    queue.enqueue(owner_id="owner", payload={"value": 2})
    worker = _runtime(queue)
    entered = threading.Event()
    release = threading.Event()
    outcomes = []

    def handler(payload):
        entered.set()
        release.wait(timeout=5)
        return content_address({"payload": dict(payload)})

    first = threading.Thread(target=lambda: outcomes.append(worker.run_once(handler)))
    first.start()
    assert entered.wait(timeout=5)
    second = threading.Thread(target=lambda: outcomes.append(worker.run_once(handler)))
    second.start(); second.join(timeout=5)
    assert outcomes == [False]
    assert worker._active == 1
    release.set(); first.join(timeout=5)
    assert sorted(outcomes) == [False, True]
    assert queue.counts()["PENDING"] == 1 and worker._active == 0


def test_memory_disk_and_retention_refuse_first_above_bound(tmp_path):
    queue = BoundedLocalResearchQueue(depth_upper_bound=1, maximum_attempts=1)
    queue.enqueue(owner_id="owner", payload={"value": "x" * 2000})
    worker = _runtime(queue)
    with pytest.raises(ResearchWorkerRefusal, match="memory"):
        worker.run_once(lambda _payload: content_address({"never": True}))
    observations = BoundedWorkerObservationStore(
        root=tmp_path / "bounded", disk_bytes_upper_bound=120,
        retention_upper_bound=1,
    )
    observations.record({"schema": "observation/1", "value": 1})
    with pytest.raises(ResearchWorkerRefusal, match="retention"):
        observations.record({"schema": "observation/1", "value": 2})
    too_small = BoundedWorkerObservationStore(
        root=tmp_path / "small", disk_bytes_upper_bound=1,
        retention_upper_bound=1,
    )
    with pytest.raises(ResearchWorkerRefusal, match="disk"):
        too_small.record({"schema": "observation/1", "value": 1})


def test_health_is_never_false_green_for_stale_execution_head(topology_runtime):
    worker = topology_runtime
    with worker.dependencies.execution_engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='bogus-exec'"))
    health = worker.health()
    assert health["status"] == "DEGRADED"
    assert "execution_database" in health["degraded_reasons"]
    assert health["roles"] == WORKER_ROLES
    assert health["execution_head"] == "bogus-exec"
    assert health["health_address"].startswith("sha256:")
    with pytest.raises(ResearchWorkerRefusal, match="execution_database"):
        worker.run_durable_once()


def test_health_is_never_false_green_for_stale_research_head(topology_runtime):
    worker = topology_runtime
    with worker.dependencies.research_engine.begin() as connection:
        connection.execute(text(
            "UPDATE research_schema_version SET version='bogus-research'",
        ))
    health = worker.health()
    assert health["status"] == "DEGRADED"
    assert health["research_head"] == "bogus-research"
    assert "research_database" in health["degraded_reasons"]


def test_ready_health_binds_real_heads_capacity_roles_and_dependencies(topology_runtime):
    worker = topology_runtime
    health = worker.health()
    assert health["status"] == "READY" and health["active"] == 0
    assert health["capacity"] == 1 and health["queue_counts"]["PENDING"] == 0
    assert health["execution_head"] == health["probes"]["execution_database"]["expected"]
    assert health["research_head"] == health["probes"]["research_database"]["expected"]
    assert all(health["role_readiness"].values())
    assert health["probes"]["durable_dispatch"]["binding"] == (
        "app.backtest.sweep.dispatch_all_reclaimable"
    )
    assert health["probes"]["api"]["binding"] == (
        "app.backtest.worker.submit_durable_research_request"
    )


def _terminal_durable_run(worker, identity_document, *, suffix, trades_json="[]"):
    from sqlalchemy.orm import Session
    from app.db.models import BacktestResult, BacktestRun, Organization

    with Session(worker.dependencies.execution_engine, future=True) as session:
        if session.get(Organization, "owner") is None:
            session.add(Organization(organization_id="owner", name="Owner"))
            session.flush()
        run = BacktestRun(
            owner_id="owner", status="done", scope="liquid", intervals="day",
            capital=1.0, total=1, done=1,
            request_json=json.dumps({
                "research_cache_identity": identity_document,
            }, sort_keys=True, separators=(",", ":")),
        )
        session.add(run); session.flush()
        session.add(BacktestResult(
            owner_id="owner", run_id=run.id, cell_key=f"cell-{suffix}",
            instrument_key="NIFTY", name="NIFTY", segment="nse_delivery",
            strategy_key="strategy", strategy_version="v1", interval="day",
            attribution_state="NON_GRAPH", bars=1, params_hash="params",
            trades_json=trades_json,
        ))
        session.commit()
        return run.id


def test_durable_terminal_results_materialize_cold_then_warm_through_store(
        topology_runtime):
    identity = _artifact_identity_document()
    first_id = _terminal_durable_run(topology_runtime, identity, suffix="same")
    first = topology_runtime._materialize_durable_run(first_id)
    second_id = _terminal_durable_run(topology_runtime, identity, suffix="same")
    second = topology_runtime._materialize_durable_run(second_id)
    assert not first.from_cache and second.from_cache
    assert first.identity_address == second.identity_address
    assert first.artifact_address == second.artifact_address
    assert first.payload_address == second.payload_address
    assert topology_runtime.dependencies.artifact_store.metrics()["cold_computes"] == 1
    assert topology_runtime.dependencies.artifact_store.metrics()["cache_hits"] == 1


def test_warm_artifact_cannot_hide_changed_durable_result_bytes(topology_runtime):
    identity = _artifact_identity_document(suffix="warm-mismatch")
    first_id = _terminal_durable_run(topology_runtime, identity, suffix="first")
    topology_runtime._materialize_durable_run(first_id)
    changed_id = _terminal_durable_run(topology_runtime, identity, suffix="changed")
    with pytest.raises(ResearchArtifactRefusal, match="differs"):
        topology_runtime._materialize_durable_run(changed_id)


def test_durable_artifact_corruption_and_first_over_are_visible(topology_runtime):
    identity = _artifact_identity_document(suffix="corrupt")
    first_id = _terminal_durable_run(topology_runtime, identity, suffix="corrupt")
    receipt = topology_runtime._materialize_durable_run(first_id)
    store = topology_runtime.dependencies.artifact_store
    store._entries[receipt.identity_address].payload_bytes = b'{"corrupt":true}'
    second_id = _terminal_durable_run(topology_runtime, identity, suffix="corrupt")
    with pytest.raises(ResearchArtifactRefusal, match="corrupt"):
        topology_runtime._materialize_durable_run(second_id)
    large_identity = _artifact_identity_document(suffix="large")
    large_id = _terminal_durable_run(
        topology_runtime, large_identity, suffix="large", trades_json="x" * (70 * 1024),
    )
    with pytest.raises(ResearchArtifactRefusal, match="artifact exceeds"):
        topology_runtime._materialize_durable_run(large_id)
    assert store.metrics()["failures"] >= 1
    assert store.metrics()["corruption_refusals"] == 1


def test_durable_dispatch_artifact_failure_degrades_worker_health(topology_runtime):
    identity = _artifact_identity_document(suffix="dispatch-large")
    run_id = _terminal_durable_run(
        topology_runtime, identity, suffix="dispatch-large",
        trades_json="x" * (70 * 1024),
    )
    from app.backtest import sweep

    @functools.wraps(sweep.dispatch_all_reclaimable)
    def dispatch(**_kwargs):
        return [run_id]

    worker = ResearchWorkerRuntime(
        worker_id="artifact-failure-worker",
        queue=BoundedLocalResearchQueue(depth_upper_bound=2, maximum_attempts=2),
        limits=topology_runtime.limits,
        build_address=content_address({"build": "artifact-failure"}),
        dependencies=replace(
            topology_runtime.dependencies,
            durable_dispatch=dispatch, durable_wait=lambda: None,
        ),
        observations=topology_runtime.observations,
    )
    with pytest.raises(ResearchWorkerRefusal, match="artifact materialization"):
        worker.run_durable_once()
    health = worker.health()
    assert health["status"] == "DEGRADED"
    assert "artifact" in health["degraded_reasons"]
    assert health["last_artifact_error"]


def test_database_pool_saturation_degrades_health(topology_runtime):
    first = topology_runtime.dependencies.execution_engine.connect()
    second = topology_runtime.dependencies.execution_engine.connect()
    try:
        health = topology_runtime.health()
        assert health["status"] == "DEGRADED"
        assert "execution_database" in health["degraded_reasons"]
    finally:
        second.close(); first.close()


def test_durable_queue_slot_is_transactionally_exact_under_concurrency(
        topology_runtime):
    from sqlalchemy.orm import Session
    from app.db.models import BacktestRun, Organization

    engine = topology_runtime.dependencies.execution_engine
    with Session(engine, future=True) as session:
        session.add(Organization(organization_id="owner", name="Owner"))
        session.commit()
    start = threading.Barrier(2)
    outcomes = []

    def admit():
        with Session(engine, future=True) as session:
            start.wait(timeout=5)
            try:
                depth = admit_durable_queue_slot(session, upper_bound=1)
                session.add(BacktestRun(
                    owner_id="owner", status="pending", scope="liquid",
                    intervals="day", capital=1.0, total=1,
                ))
                session.commit()
                outcomes.append(("PASS", depth))
            except ResearchWorkerRefusal:
                session.rollback(); outcomes.append(("REFUSED", None))

    first = threading.Thread(target=admit); second = threading.Thread(target=admit)
    first.start(); second.start(); first.join(timeout=10); second.join(timeout=10)
    assert sorted(outcomes) == [("PASS", 0), ("REFUSED", None)]


def test_worker_limits_pass_at_limit_and_refuse_invalid_values():
    assert _limits(queue_depth=0, cache_bytes=0, artifact_bytes=0).queue_depth == 0
    for field in (
        "queue_depth", "concurrency", "maximum_attempts", "cache_bytes",
        "artifact_bytes", "database_connections", "memory_bytes", "disk_bytes",
        "retention_entries",
    ):
        with pytest.raises(ResearchWorkerRefusal): _limits(**{field: -1})


def test_entrypoint_health_and_one_shot_are_local_mock_only():
    env = {**os.environ, "PYTHONPATH": str(BACKEND), "PT_PROVIDER": "mock",
           "PT_LIVE_TRADING": ""}
    health = subprocess.run(
        [sys.executable, str(SCRIPT), "--health"], cwd=BACKEND,
        env=env, text=True, capture_output=True, check=True,
    )
    document = json.loads(health.stdout)
    assert document["status"] == "READY" and document["roles"] == list(WORKER_ROLES)
    assert document["execution_head"] == document["probes"]["execution_database"]["expected"]
    assert document["research_head"] == document["probes"]["research_database"]["expected"]
    configuration = document["probes"]["configuration"]
    assert configuration["ready"] and configuration["dotenv_disabled"]
    assert configuration["env_file"] is None and configuration["credentials_empty"]
    once = subprocess.run(
        [sys.executable, str(SCRIPT), "--health", "--once"],
        cwd=BACKEND, env=env, text=True, capture_output=True, check=True,
    )
    assert json.loads(once.stdout)["launched_run_ids"] == []
    for extra_env in (
        {"PT_PROVIDER": "kite", "PT_LIVE_TRADING": ""},
        {"PT_PROVIDER": "mock", "PT_LIVE_TRADING": "true"},
        {"PT_PROVIDER": "mock", "PT_PRODUCTION": "true"},
    ):
        refused = subprocess.run(
            [sys.executable, str(SCRIPT), "--health"], cwd=BACKEND,
            env={**env, **extra_env}, text=True, capture_output=True,
        )
        assert refused.returncode != 0
    mixed = subprocess.run(
        [sys.executable, str(SCRIPT), "--once", "--submit-json", "{}"],
        cwd=BACKEND, env=env, text=True, capture_output=True,
    )
    assert mixed.returncode != 0 and "separate processes" in mixed.stderr


def test_entrypoint_cannot_stamp_or_report_ready_over_a_stale_database(tmp_path):
    stale = tmp_path / "stale-execution.db"
    engine = create_engine(f"sqlite:///{stale}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)",
        ))
        connection.execute(text(
            "INSERT INTO alembic_version(version_num) VALUES ('bogus-exec')",
        ))
    engine.dispose()
    env = {
        **os.environ, "PYTHONPATH": str(BACKEND), "PT_PROVIDER": "mock",
        "PT_LIVE_TRADING": "", "PT_PRODUCTION": "0",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--health",
         "--state-dir", str(tmp_path / "worker-state"),
         "--execution-database", str(stale)],
        cwd=BACKEND, env=env, text=True, capture_output=True,
    )
    assert result.returncode == 1
    document = json.loads(result.stdout)
    assert document["status"] == "DEGRADED"
    assert "execution_database" in document["degraded_reasons"]
    with create_engine(f"sqlite:///{stale}").connect() as connection:
        assert connection.execute(text(
            "SELECT version_num FROM alembic_version",
        )).scalar_one() == "bogus-exec"


def test_aggregate_process_memory_supervisor_passes_and_kills_first_over():
    env = {
        **os.environ, "PYTHONPATH": str(BACKEND), "PT_PROVIDER": "mock",
        "PT_LIVE_TRADING": "", "PT_PRODUCTION": "0",
    }
    bound = 256 * 1024 * 1024
    passing = subprocess.run(
        [sys.executable, str(SCRIPT), "--health", "--memory-bytes", str(bound)],
        cwd=BACKEND, env=env, text=True, capture_output=True, check=True,
    )
    healthy = json.loads(passing.stdout)
    assert healthy["probes"]["process_memory"]["ready"]
    assert healthy["probes"]["process_memory"]["limit_bytes"] == bound
    refused = subprocess.run(
        [sys.executable, str(SCRIPT), "--memory-bytes", str(bound),
         "--memory-probe-bytes", str(bound)],
        cwd=BACKEND, env=env, text=True, capture_output=True,
    )
    assert refused.returncode == 75
    document = json.loads(refused.stdout)
    assert document["status"] == "MEMORY_REFUSED"
    assert document["observed_bytes"] > document["limit_bytes"] == bound


def test_durable_api_submission_is_consumed_by_a_separate_canonical_worker_process(
        tmp_path, admitted_backtest_receipt):
    from sqlalchemy.engine import make_url
    from app.backtest import repository, sweep
    from app.db.models import BacktestRun
    from app.db.session import SessionLocal, engine, init_db

    init_db(reset=True)
    with SessionLocal() as session:
        identity = admitted_backtest_receipt(session, owner_id="owner")
        admitted = repository.load_verified_admission(
            session, owner_id="owner",
            admission_address=identity["admission_address"],
        )
        descriptor = {
            "scope": "liquid", "intervals": ["day"], "capital": 1.0,
            "instruments": ["NIFTY"], "lookback_days": 1,
            "start_date": None, "end_date": None,
            "strategies": [sweep._strategy_descriptor(
                admitted.strategy, owner_id="owner",
            )],
            "attribution": sweep._admission_attribution(admitted),
            "admission_address": admitted.admission_address,
            "pinned_datasets": {}, "workers": 1,
            "research_cache_identity": _artifact_identity_document(owner_id="owner"),
        }
        session.commit()
    execution_path = make_url(str(engine.url)).database
    assert execution_path and Path(execution_path).is_file()
    env = {
        **os.environ, "PYTHONPATH": str(BACKEND), "PT_PROVIDER": "mock",
        "PT_LIVE_TRADING": "", "PT_PRODUCTION": "0",
    }
    state = tmp_path / "worker-state"
    api = subprocess.run(
        [sys.executable, str(SCRIPT), "--health",
         "--state-dir", str(state), "--execution-database", execution_path,
         "--owner-id", "owner", "--submit-json",
         json.dumps(descriptor, sort_keys=True, separators=(",", ":"))],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90,
    )
    assert api.returncode == 0, api.stderr
    api_document = json.loads(api.stdout)
    run_id = api_document["submitted_run_id"]
    assert type(run_id) is int and api_document["launched_run_ids"] == []
    child = subprocess.run(
        [sys.executable, str(SCRIPT), "--health", "--once",
         "--state-dir", str(state),
         "--execution-database", execution_path, "--owner-id", "owner"],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90,
    )
    assert child.returncode == 0, child.stderr
    document = json.loads(child.stdout)
    assert document["launched_run_ids"] == [run_id]
    assert document["probes"]["durable_dispatch"]["binding"] == (
        "app.backtest.sweep.dispatch_all_reclaimable"
    )
    assert len(document["materializations"]) == 1
    materialized = document["materializations"][0]
    assert materialized["run_id"] == run_id and not materialized["from_cache"]
    assert materialized["artifact_address"].startswith("sha256:")
    assert materialized["payload_address"].startswith("sha256:")
    with SessionLocal() as session:
        persisted = session.get(BacktestRun, run_id)
        assert persisted.status in {"done", "error"}
        assert persisted.claim_token and persisted.claimed_by.startswith("dispatcher:")
        assert persisted.status == "done" or persisted.note


def _prepare_process_lifecycle_job(tmp_path, admitted_backtest_receipt, *, suffix):
    from sqlalchemy.engine import make_url
    from app.backtest import repository, sweep
    from app.db.session import SessionLocal, engine, init_db

    init_db(reset=True)
    with SessionLocal() as session:
        identity = admitted_backtest_receipt(session, owner_id="owner")
        admitted = repository.load_verified_admission(
            session, owner_id="owner",
            admission_address=identity["admission_address"],
        )
        descriptor = {
            "scope": "liquid", "intervals": ["day"], "capital": 1.0,
            "instruments": ["NIFTY"], "lookback_days": 1,
            "start_date": None, "end_date": None,
            "strategies": [sweep._strategy_descriptor(
                admitted.strategy, owner_id="owner",
            )],
            "attribution": sweep._admission_attribution(admitted),
            "admission_address": admitted.admission_address,
            "pinned_datasets": {}, "workers": 1,
            "research_cache_identity": _artifact_identity_document(
                owner_id="owner", suffix=suffix,
            ),
        }
        session.commit()
    execution_path = make_url(str(engine.url)).database
    state = tmp_path / f"worker-state-{suffix}"
    env = {
        **os.environ, "PYTHONPATH": str(BACKEND), "PT_PROVIDER": "mock",
        "PT_LIVE_TRADING": "", "PT_PRODUCTION": "0",
        "PT_BACKTEST_CLAIM_LEASE_SECONDS": "5",
    }
    api = subprocess.run(
        [sys.executable, str(SCRIPT), "--health",
         "--state-dir", str(state), "--execution-database", execution_path,
         "--owner-id", "owner", "--submit-json",
         json.dumps(descriptor, sort_keys=True, separators=(",", ":"))],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=120,
    )
    assert api.returncode == 0, api.stderr
    run_id = json.loads(api.stdout)["submitted_run_id"]
    command = [
        sys.executable, str(SCRIPT), "--health", "--once",
        "--state-dir", str(state), "--execution-database", execution_path,
        "--owner-id", "owner",
    ]
    return env, command, run_id


def _wait_for_active_claim(run_id, *, timeout=20):
    from app.db.models import BacktestRun
    from app.db.session import SessionLocal

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with SessionLocal() as session:
            run = session.get(BacktestRun, run_id)
            if run is not None and run.status == "running" and run.claim_token:
                return run.claim_token
        time.sleep(0.05)
    raise AssertionError("worker process did not publish an active durable claim")


def _direct_children(parent_pid):
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,command="], text=True,
        capture_output=True, check=True,
    )
    children = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=2)
        if len(fields) == 3 and int(fields[1]) == parent_pid \
                and "--supervised-child" in fields[2]:
            children.append(int(fields[0]))
    return children


def test_sigkill_active_worker_is_reclaimed_once_by_fresh_process(
        tmp_path, admitted_backtest_receipt):
    from sqlalchemy import func, select
    from app.db.models import BacktestResult, BacktestRun
    from app.db.session import SessionLocal

    env, command, run_id = _prepare_process_lifecycle_job(
        tmp_path, admitted_backtest_receipt, suffix="sigkill",
    )
    first = subprocess.Popen(
        command, cwd=BACKEND, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        old_token = _wait_for_active_claim(run_id)
        deadline = time.monotonic() + 5
        children = []
        while time.monotonic() < deadline and not children:
            children = _direct_children(first.pid)
            time.sleep(0.02)
        assert len(children) == 1
        os.kill(children[0], signal.SIGKILL)
        first.communicate(timeout=20)
        assert first.returncode != 0
    finally:
        if first.poll() is None:
            for child_pid in _direct_children(first.pid):
                os.kill(child_pid, signal.SIGKILL)
            first.kill(); first.communicate(timeout=10)
    time.sleep(5.2)
    replacement = subprocess.run(
        command, cwd=BACKEND, env=env, text=True,
        capture_output=True, timeout=120,
    )
    assert replacement.returncode == 0, replacement.stderr
    document = json.loads(replacement.stdout)
    assert document["launched_run_ids"] == [run_id]
    assert len(document["materializations"]) == 1
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        count = session.scalar(select(func.count()).select_from(BacktestResult).where(
            BacktestResult.owner_id == "owner", BacktestResult.run_id == run_id,
        ))
        assert run.status in {"done", "error"}
        assert run.claim_token != old_token and run.attempt_count == 2
        assert count == run.done and count <= run.total


def test_sigterm_stops_new_work_and_finishes_active_claim_safely(
        tmp_path, admitted_backtest_receipt):
    from app.db.models import BacktestRun
    from app.db.session import SessionLocal

    env, command, run_id = _prepare_process_lifecycle_job(
        tmp_path, admitted_backtest_receipt, suffix="sigterm",
    )
    process = subprocess.Popen(
        command, cwd=BACKEND, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _wait_for_active_claim(run_id)
    process.send_signal(signal.SIGTERM)
    stdout, stderr = process.communicate(timeout=120)
    assert process.returncode == 0, stderr
    document = json.loads(stdout)
    assert document["termination_requested"]
    assert document["termination_signal"] == signal.SIGTERM
    assert document["status"] == "STOPPING"
    assert len(document["materializations"]) == 1
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        assert run.status in {"done", "error"} and run.attempt_count == 1


def test_entrypoint_imports_no_provider_broker_order_live_or_deployment_path():
    tree = ast.parse(SCRIPT.read_text())
    forbidden = {
        "app.providers", "app.engine", "app.execution", "app.ledger",
        "paper-trader.scripts.deploy",
    }
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    }
    assert not any(any(name.startswith(prefix) for prefix in forbidden) for name in imports)
