from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

from sqlalchemy.orm import Session

from app.backtest.artifacts import BoundedResearchArtifactStore
from app.backtest.worker import (
    BoundedLocalResearchQueue,
    BoundedWorkerObservationStore,
    ResearchWorkerDependencies,
    ResearchWorkerLimits,
    ResearchWorkerRefusal,
    ResearchWorkerRuntime,
    admit_durable_queue_slot,
    submit_durable_research_request,
)
from app.ir.hashing import content_address


BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts/run_research_worker.py"


def _limits():
    return ResearchWorkerLimits(
        queue_depth=2, concurrency=1, maximum_attempts=2,
        cache_bytes=128 * 1024, artifact_bytes=64 * 1024,
        database_connections=2, memory_bytes=4 * 1024 * 1024 * 1024,
        disk_bytes=128 * 1024, retention_entries=8,
    )


def _initialize_execution(engine):
    from app.db import migrate
    from app.db.models import Base

    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
        expected_tables=Base.metadata.tables,
    )


def test_disposable_postgresql_entrypoint_reports_actual_heads_and_exact_pools(
        pg_sandbox, tmp_path):
    env = {
        **os.environ, "PYTHONPATH": str(BACKEND), "PT_PROVIDER": "mock",
        "PT_LIVE_TRADING": "", "PT_PRODUCTION": "0",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--health",
         "--state-dir", str(tmp_path / "state"),
         "--execution-database-url", pg_sandbox.execution_url,
         "--research-database-url", pg_sandbox.research_url,
         "--database-connections", "1"],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["status"] == "READY"
    assert document["execution_head"] == document["probes"]["execution_database"]["expected"]
    assert document["research_head"] == document["probes"]["research_database"]["expected"]
    assert document["probes"]["execution_database"]["maximum_connections"] == 1
    assert document["probes"]["research_database"]["maximum_connections"] == 1


def test_disposable_postgresql_pool_saturation_and_queue_admission_are_exact(
        pg_sandbox, tmp_path, monkeypatch):
    from app.backtest import sweep
    from app.db.models import BacktestRun, Organization
    from research.domain.base import init_research_db

    execution = pg_sandbox.engine(
        "execution", pool_size=2, max_overflow=0, pool_timeout=0.2,
    )
    research = pg_sandbox.engine(
        "research", pool_size=2, max_overflow=0, pool_timeout=0.2,
    )
    _initialize_execution(execution); init_research_db(research)
    limits = _limits()
    monkeypatch.setenv("PT_DISABLE_DOTENV", "1")
    monkeypatch.setenv("PT_WORKER_MEMORY_LIMIT_BYTES", str(limits.memory_bytes))
    monkeypatch.setenv("PT_WORKER_SUPERVISOR_PID", str(os.getppid()))
    store = BoundedResearchArtifactStore(
        owner_id="owner", licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=limits.cache_bytes,
        artifact_bytes_upper_bound=limits.artifact_bytes,
        entry_upper_bound=limits.retention_entries,
        concurrency_upper_bound=limits.concurrency,
        queue_depth_upper_bound=limits.queue_depth,
    )
    worker = ResearchWorkerRuntime(
        worker_id="postgres-worker",
        queue=BoundedLocalResearchQueue(
            depth_upper_bound=limits.queue_depth,
            maximum_attempts=limits.maximum_attempts,
        ),
        limits=limits, build_address=content_address({"build": "postgres-test"}),
        dependencies=ResearchWorkerDependencies(
            execution_engine=execution, research_engine=research,
            artifact_store=store,
            durable_dispatch=sweep.dispatch_all_reclaimable,
            durable_wait=sweep._join,
            api_submit=submit_durable_research_request,
        ),
        observations=BoundedWorkerObservationStore(
            root=tmp_path / "observations",
            disk_bytes_upper_bound=limits.disk_bytes,
            retention_upper_bound=limits.retention_entries,
        ),
    )
    first, second = execution.connect(), execution.connect()
    try:
        health = worker.health()
        assert health["status"] == "DEGRADED"
        assert "execution_database" in health["degraded_reasons"]
    finally:
        second.close(); first.close()

    with Session(execution, future=True) as session:
        session.add(Organization(organization_id="owner", name="Owner"))
        session.commit()
    barrier = threading.Barrier(2)
    outcomes = []

    def admit():
        with Session(execution, future=True) as session:
            barrier.wait(timeout=5)
            try:
                depth = admit_durable_queue_slot(session, upper_bound=1)
                session.add(BacktestRun(
                    owner_id="owner", status="pending", scope="liquid",
                    intervals="day", capital=1.0, total=1,
                ))
                session.commit(); outcomes.append(("PASS", depth))
            except ResearchWorkerRefusal:
                session.rollback(); outcomes.append(("REFUSED", None))

    left, right = threading.Thread(target=admit), threading.Thread(target=admit)
    left.start(); right.start(); left.join(timeout=10); right.join(timeout=10)
    assert sorted(outcomes) == [("PASS", 0), ("REFUSED", None)]
