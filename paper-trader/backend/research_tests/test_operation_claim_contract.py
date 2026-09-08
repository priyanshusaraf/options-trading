import datetime as dt
import sqlite3

import pytest

from research.domain.base import init_research_db, make_engine


def test_only_one_worker_can_claim_the_same_owner_operation(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    try:
        now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO research_operation (owner_id, operation_id, trigger, plan_json, status, stage, build, provider_mode, completed_run_ids_json, created_at, queued_at, attempt_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("owner-a", "operation-a", "manual", "{}", "pending", "startup", "test", "mock", "[]", now, now, 0),
            )
            first = connection.exec_driver_sql(
                "UPDATE research_operation SET status='running', claim_token='worker-one' WHERE owner_id=? AND operation_id=? AND status='pending'",
                ("owner-a", "operation-a"),
            )
            second = connection.exec_driver_sql(
                "UPDATE research_operation SET status='running', claim_token='worker-two' WHERE owner_id=? AND operation_id=? AND status='pending'",
                ("owner-a", "operation-a"),
            )
        assert first.rowcount == 1
        assert second.rowcount == 0
    finally:
        engine.dispose()


def test_same_operation_id_can_exist_per_owner_without_cross_owner_read(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO research_operation (owner_id, operation_id, trigger, plan_json, status, stage, build, provider_mode, completed_run_ids_json, created_at, queued_at, attempt_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
                ("owner-a", "same", "manual", '{"private":"a"}', "pending", "startup", "test", "mock", "[]", 0),
            )
            connection.exec_driver_sql(
                "INSERT INTO research_operation (owner_id, operation_id, trigger, plan_json, status, stage, build, provider_mode, completed_run_ids_json, created_at, queued_at, attempt_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
                ("owner-b", "same", "manual", '{"private":"b"}', "pending", "startup", "test", "mock", "[]", 0),
            )
            foreign = connection.exec_driver_sql(
                "SELECT plan_json FROM research_operation WHERE owner_id=? AND operation_id=?", ("owner-c", "same")
            ).first()
        assert foreign is None
    finally:
        engine.dispose()


# Reuse the migrated real-database fixture for both dialects. PostgreSQL uses
# the existing disposable-cluster sandbox; no fake connection earns this proof.
from research_tests.test_operation_repository import repo


def recovery_inputs():
    from research_tests.conftest import FakeInst, make_series
    from research.data.store import StaticDataSource
    from research.operations import safe_plan_summary
    plan = safe_plan_summary([{
        "program": "Recovery", "hypothesis": "Synthetic checkpoint recovery",
        "strategy_key": "trend_impulse_v3", "instruments": [FakeInst("AAA")],
        "interval": "day", "days": 400, "seed": 17, "min_trades": 1,
        "n_folds": 4, "min_positive_fold_frac": 0.0,
    }])
    return plan, StaticDataSource({("AAA", "day"): make_series(400)}), FakeInst


def _checkpoint_process(authority, ready_path, phase, report_dir):
    """Run the existing synthetic consumer until the parent kills this process."""
    import json
    import sys
    from pathlib import Path
    from research.domain.base import make_sessionmaker
    from research.domain.operations import (DurableOperationRecorder, ResearchOperationRepository,
                                            operation_item_keys, reconstruct_plan)
    from research.orchestrator.run import run_nightly

    _, source, instrument = recovery_inputs()
    engine = make_engine(authority)
    with make_sessionmaker(engine)() as session:
        repository = ResearchOperationRepository(session)
        recorder = DurableOperationRecorder.claim_next(repository, owner_id="owner", worker_id="doomed")
        assert recorder is not None
        view = repository.get("recover", owner_id="owner")
        keys = operation_item_keys(view.plan, trigger=view.trigger)

        def pause(run_id):
            Path(ready_path).write_text(json.dumps({"run_id": run_id, "token": recorder.token}))
            sys.stdin.read()
            raise AssertionError("parent must kill the child at its checkpoint")

        def finalize(key, run_id):
            result = recorder.finalize_item_in_transaction(key, run_id)
            assert result
            if phase == "before_commit":
                pause(run_id)
            return result

        run_nightly(session, source, reconstruct_plan(view.plan, instrument_for_key=instrument),
            owner_id="owner", git_commit=view.build, report_dir=report_dir,
            item_keys=keys, completed_item_run=recorder.completed_item_run,
            bound_item_run=recorder.bound_item_run, reclaim_bound_item=recorder.reclaim_bound_item,
            bind_item_run=recorder.bind_item_run_in_transaction, finalize_item=finalize,
            progress=pause if phase == "after_commit" else None)
    raise AssertionError("checkpoint was not reached")


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_killed_consumer_recovers_only_durable_checkpoint(repo, tmp_path, phase):
    import json
    import os
    import signal
    import subprocess
    import sys
    import time
    from pathlib import Path
    from sqlalchemy import select
    from research.domain.models import ExperimentRun, RESEARCH_OUTBOX_MODELS
    from research.domain.operations import (DurableOperationRecorder, ResearchOperationRepository,
                                            operation_item_keys, reconstruct_plan)
    from research.orchestrator.run import run_nightly

    plan, source, instrument = recovery_inputs()
    repo.enqueue(owner_id="owner", operation_id="recover", trigger="manual", plan=plan,
                 build="recovery-build", provider_mode="mock")
    # A same-id foreign job must survive the crash and takeover unchanged.
    repo.enqueue(owner_id="foreign", operation_id="recover", trigger="manual", plan={},
                 build="foreign-build", provider_mode="mock")
    ready = tmp_path / "ready.json"
    command = [sys.executable, "-c",
               "import sys; from research_tests.test_operation_claim_contract import _checkpoint_process; "
               "_checkpoint_process(*sys.argv[1:])",
               str(repo.session.bind.url), str(ready), phase, str(tmp_path)]
    repo.session.rollback()
    with (tmp_path / "child.log").open("w") as log:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                 cwd=Path(__file__).parents[1], env=dict(os.environ))
        try:
            deadline = time.monotonic() + 45
            while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert ready.exists(), (tmp_path / "child.log").read_text()
            checkpoint = json.loads(ready.read_text())
            child.kill()
            assert child.wait(timeout=10) == -signal.SIGKILL
        finally:
            if child.poll() is None:
                child.kill(); child.wait(timeout=10)
            child.stdin.close()
    repo.session.expire_all()
    key = operation_item_keys(plan, trigger="manual")[0]
    old_run = checkpoint["run_id"]
    assert repo.session.get(ExperimentRun, old_run).status == (
        "running" if phase == "before_commit" else "completed")
    assert repo.completed_item_run("recover", owner_id="owner", item_key=key) == (
        None if phase == "before_commit" else old_run)
    view = repo.get("recover", owner_id="owner")
    assert view.plan == plan and view.build == "recovery-build" and view.provider_mode == "mock"
    takeover_time = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=61)
    claim = repo.claim_next(owner_id="owner", worker_id="replacement", now=takeover_time)
    assert claim is not None and claim.claim_token != checkpoint["token"]
    assert not repo.complete("recover", owner_id="owner", token=checkpoint["token"], now=takeover_time)
    recorder = DurableOperationRecorder(repo, owner_id="owner", operation_id="recover", token=claim.claim_token)
    if phase == "after_commit":
        class NoReplaySource:
            def candles(self, *args, **kwargs):
                raise AssertionError("checkpointed data must not be read again")
        source = NoReplaySource()
    reports = run_nightly(repo.session, source, reconstruct_plan(plan, instrument_for_key=instrument),
        owner_id="owner", git_commit=view.build, report_dir=str(tmp_path), item_keys=[key],
        completed_item_run=recorder.completed_item_run, bound_item_run=recorder.bound_item_run,
        reclaim_bound_item=recorder.reclaim_bound_item,
        bind_item_run=recorder.bind_item_run_in_transaction, finalize_item=recorder.finalize_item_in_transaction)
    assert len(reports) == int(phase == "before_commit")
    completed = recorder.completed_item_run(key)
    assert completed is not None
    events_before = repo.events("recover", owner_id="owner")
    recorder.complete_item(key, completed)  # repeated delivery is a no-op
    assert repo.events("recover", owner_id="owner") == events_before
    assert repo.get("recover", owner_id="owner").completed_run_ids == [completed]
    recorder.complete()
    assert repo.get("recover", owner_id="owner").status == "completed"
    assert repo.get("recover", owner_id="foreign").status == "pending"
    assert repo.events("recover", owner_id="foreign") == []
    runs = repo.session.scalars(select(ExperimentRun).where(ExperimentRun.owner_id == "owner")
                                .order_by(ExperimentRun.id)).all()
    assert [r.status for r in runs] == (["failed", "completed"] if phase == "before_commit" else ["completed"])
    from research.domain.models import ExperimentSpec
    specs = repo.session.scalars(select(ExperimentSpec).where(ExperimentSpec.owner_id == "owner")).all()
    assert len(specs) == 1
    assert specs[0].rng_seed == 17 and specs[0].git_commit == "recovery-build"
    outbox = RESEARCH_OUTBOX_MODELS.Event
    rows = repo.session.scalars(select(outbox).where(outbox.aggregate_type == "research_operation")).all()
    assert all(row.owner_id in {"owner", "foreign"} for row in rows)
    foreign = [json.loads(row.payload_json) for row in rows if row.owner_id == "foreign"]
    assert len(foreign) == 1 and foreign[0]["state"] == "queued"
