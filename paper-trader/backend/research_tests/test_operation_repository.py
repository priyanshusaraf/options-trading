import datetime as dt
import time

import pytest
from sqlalchemy import inspect

from app.ir.hashing import content_address
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import (ExperimentRun, ExperimentSpec, Hypothesis,
                                    ResearchOperationEvent, ResearchProgram)
from research.domain.operations import (DurableOperationRecorder, ResearchOperationRepository,
                                        operation_item_keys)


@pytest.fixture
def repo(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as session:
        yield ResearchOperationRepository(session)
    engine.dispose()


def test_repository_hides_foreign_operation_and_fences_replaced_claim(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={"items": []}, build="b", provider_mode="mock", operation_id="shared", now=now)
    repo.enqueue(owner_id="owner-b", trigger="manual", plan={"items": []}, build="b", provider_mode="mock", operation_id="shared", now=now)
    assert repo.get("shared", owner_id="owner-c") is None

    first = repo.claim_next(owner_id="owner-a", worker_id="one", now=now, lease_seconds=1)
    second = repo.claim_next(owner_id="owner-a", worker_id="two", now=now + dt.timedelta(seconds=2), lease_seconds=30)
    assert first is not None and second is not None
    assert first.claim_token != second.claim_token
    assert not repo.transition("shared", owner_id="owner-a", token=first.claim_token, stage="planning", now=now + dt.timedelta(seconds=2))
    assert repo.transition("shared", owner_id="owner-a", token=second.claim_token, stage="planning", now=now + dt.timedelta(seconds=2))


def test_repository_cancels_pending_and_requires_owner_keywords(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={"items": []}, build="b", provider_mode="mock", operation_id="cancel", now=now)
    assert repo.request_cancel("cancel", owner_id="owner-a", now=now)
    assert repo.get("cancel", owner_id="owner-a").status == "cancelled"
    assert repo.reconcile_expired(owner_id="owner-a", now=now) == 0
    with pytest.raises(TypeError):
        repo.get("cancel")


def test_watchdog_marks_lost_claim_before_the_next_blocking_stage(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b", provider_mode="mock", operation_id="watch", now=now)
    claim = repo.claim_next(owner_id="owner-a", worker_id="worker", now=now)
    recorder = DurableOperationRecorder(repo, owner_id="owner-a", operation_id="watch", token=claim.claim_token)
    recorder.start_watchdog(lambda *_args: False, interval_seconds=0.01)
    time.sleep(0.03)
    with pytest.raises(RuntimeError, match="claim was lost"):
        recorder.transition("planning")
    recorder.close_watchdog()


def test_watchdog_exception_fails_closed_before_next_stage(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b", provider_mode="mock",
                 operation_id="watch-exception", now=now)
    claim = repo.claim_next(owner_id="owner-a", worker_id="worker", now=now)
    assert claim is not None and claim.claim_token
    recorder = DurableOperationRecorder(repo, owner_id="owner-a", operation_id="watch-exception",
                                        token=claim.claim_token)
    recorder.start_watchdog(lambda *_args: (_ for _ in ()).throw(OSError("db unavailable")),
                            interval_seconds=0.01)
    time.sleep(0.03)
    with pytest.raises(RuntimeError, match="claim was lost"):
        recorder.transition("planning")
    recorder.close_watchdog()


def test_recorder_claims_the_operation_it_enqueued_not_an_older_pending_one(repo):
    """Starting a new operation must never acquire write authority over another job."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                 provider_mode="mock", operation_id="older", now=now)

    recorder = DurableOperationRecorder.start(
        repo, owner_id="owner-a", trigger="manual", plan={}, build="b",
        provider_mode="mock", worker_id="worker", operation_id="newer",
    )

    assert recorder.operation_id == "newer"
    assert repo.get("older", owner_id="owner-a").status == "pending"
    assert repo.get("newer", owner_id="owner-a").status == "running"


def test_cancelled_claim_cannot_heartbeat_transition_append_or_complete(repo):
    """Cancellation is a terminal barrier for every fenced writer, not just reconcile."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                 provider_mode="mock", operation_id="cancelled", now=now)
    claim = repo.claim_next(owner_id="owner-a", worker_id="worker", now=now)
    assert claim is not None and claim.claim_token
    assert repo.request_cancel("cancelled", owner_id="owner-a", now=now)

    assert not repo.heartbeat("cancelled", owner_id="owner-a", token=claim.claim_token, now=now)
    assert not repo.transition("cancelled", owner_id="owner-a", token=claim.claim_token,
                               stage="planning", now=now)
    assert not repo.add_completed_run("cancelled", owner_id="owner-a", token=claim.claim_token,
                                      run_id=1, now=now)
    assert not repo.complete("cancelled", owner_id="owner-a", token=claim.claim_token, now=now)


def test_expired_cancelled_operation_is_terminalized_not_reclaimed(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b", provider_mode="mock",
                 operation_id="expired-cancel", now=now)
    claim = repo.claim_next(owner_id="owner-a", worker_id="first", now=now, lease_seconds=1)
    assert claim is not None
    assert repo.request_cancel("expired-cancel", owner_id="owner-a", now=now)
    assert repo.claim_next(owner_id="owner-a", worker_id="second",
                           now=now + dt.timedelta(seconds=2)) is None
    assert repo.reconcile_expired(owner_id="owner-a", now=now + dt.timedelta(seconds=2)) == 0
    assert repo.get("expired-cancel", owner_id="owner-a").status == "cancelled"


def test_cancelling_a_running_operation_releases_capacity_and_fences_the_old_worker(repo):
    """Cancellation is immediate; a lease holder must not occupy capacity until expiry."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for number in range(5):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b", provider_mode="mock",
                     operation_id=f"cancel-running-{number}", now=now)
    first = repo.claim_operation("cancel-running-0", owner_id="owner-a", worker_id="first", now=now)
    assert first is not None and first.claim_token
    assert repo.request_cancel("cancel-running-0", owner_id="owner-a", now=now)
    assert repo.get("cancel-running-0", owner_id="owner-a").status == "cancelled"
    assert repo.metrics(owner_id="owner-a", now=now)["active"] == 0
    assert not repo.transition("cancel-running-0", owner_id="owner-a", token=first.claim_token,
                               stage="planning", now=now)

    # The cancelled slot is no longer held by an expired-or-cancelled lease.
    claimed = [repo.claim_next(owner_id="owner-a", worker_id=f"worker-{number}", now=now)
               for number in range(4)]
    assert all(item is not None for item in claimed)


def test_trigger_filtered_claim_leaves_other_lane_pending(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b", provider_mode="mock",
                 operation_id="manual", now=now)
    repo.enqueue(owner_id="owner-a", trigger="nightly", plan={}, build="b", provider_mode="mock",
                 operation_id="nightly", now=now + dt.timedelta(seconds=1))
    claim = repo.claim_next(owner_id="owner-a", worker_id="nightly-worker", triggers=("nightly",), now=now)
    assert claim is not None and claim.operation_id == "nightly"
    assert repo.get("manual", owner_id="owner-a").status == "pending"


def test_active_and_terminal_reads_are_separate_bounded_owner_local_queries(repo):
    """Several active jobs must not hide the most recent terminal history entry."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for number in range(3):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id=f"op-{number}",
                     now=now + dt.timedelta(seconds=number))
    completed = repo.claim_operation("op-0", owner_id="owner-a", worker_id="worker", now=now)
    assert completed is not None and completed.claim_token
    assert repo.complete("op-0", owner_id="owner-a", token=completed.claim_token, now=now)

    assert repo.latest_active(owner_id="owner-a").operation_id == "op-2"
    assert repo.latest_terminal(owner_id="owner-a").operation_id == "op-0"


def test_operation_payloads_reject_nonfinite_and_unbounded_error_details(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    with pytest.raises(ValueError, match="plan payload"):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={"x": float("nan")},
                     build="b", provider_mode="mock", now=now)
    with pytest.raises(ValueError, match="content address"):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={
            "content_address": "0" * 64, "experiment_count": 0, "items": [],
        }, build="b", provider_mode="mock", now=now)
    with pytest.raises(ValueError, match="plan payload"):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={"secret": "never persist"},
                     build="b", provider_mode="mock", now=now)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                 provider_mode="mock", operation_id="error", now=now)
    claim = repo.claim_operation("error", owner_id="owner-a", worker_id="worker", now=now)
    assert claim is not None and claim.claim_token
    with pytest.raises(ValueError, match="error payload"):
        repo.fail("error", owner_id="owner-a", token=claim.claim_token,
                  error={"code": "x", "message": "m" * 4097}, now=now)


def test_failure_projection_records_the_stable_refusal_code(repo):
    """Hypothesis: a causal refusal is replaced by a generic failure in durable evidence."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                 provider_mode="mock", operation_id="receipt", now=now)
    claim = repo.claim_operation("receipt", owner_id="owner-a", worker_id="worker", now=now)
    assert claim is not None and claim.claim_token
    assert repo.fail("receipt", owner_id="owner-a", token=claim.claim_token,
                     error={"code": "RECEIPT_STALE", "message": "research operation refused"}, now=now)
    event = repo.session.get(ResearchOperationEvent, ("owner-a", "receipt", 2))
    assert event is not None
    assert __import__("json").loads(event.payload_json)["code"] == "RECEIPT_STALE"


def test_owner_admission_rejects_queue_capacity_before_creating_another_operation(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for number in range(16):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id=f"queued-{number}", now=now)
    with pytest.raises(RuntimeError, match="admission capacity"):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id="rejected", now=now)
    assert repo.get("rejected", owner_id="owner-a") is None
    assert repo.metrics(owner_id="owner-a", now=now)["admission_rejections"] >= 1


def test_owner_metrics_include_each_terminal_state_without_other_owner_rows(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for operation_id in ("completed", "failed", "cancelled"):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id=operation_id, now=now)
        claim = repo.claim_operation(operation_id, owner_id="owner-a", worker_id="worker", now=now)
        assert claim is not None and claim.claim_token
        if operation_id == "completed":
            assert repo.complete(operation_id, owner_id="owner-a", token=claim.claim_token, now=now)
        elif operation_id == "failed":
            assert repo.fail(operation_id, owner_id="owner-a", token=claim.claim_token,
                             error={"code": "TEST_FAILURE"}, now=now)
        else:
            assert repo.request_cancel(operation_id, owner_id="owner-a", now=now)
            assert repo.reconcile_expired(owner_id="owner-a", now=now + dt.timedelta(seconds=61)) == 0
    repo.enqueue(owner_id="owner-b", trigger="manual", plan={}, build="b", provider_mode="mock",
                 operation_id="foreign", now=now)
    metrics = repo.metrics(owner_id="owner-a", now=now)
    assert metrics == {
        "queued": 0, "active": 0, "expired_claims": 0,
        "completed": 1, "failed": 1, "cancelled": 1,
        "stage_age_seconds": 0, "claim_latency_seconds": 0,
        "heartbeat_age_seconds": 0, "takeovers": 0,
        "admission_rejections": metrics["admission_rejections"],
    }


def test_completed_plan_item_is_durable_owner_local_and_fenced(repo):
    """A recovered operation skips only the exact successfully checkpointed item."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    item = {
        "program": "program", "hypothesis": "hypothesis", "strategy_key": "strategy",
        "instrument_keys": ["NIFTY"], "interval": "day", "days": 10,
        "optimize_search": True,
        "params": {}, "seed": 0, "min_trades": 20, "n_folds": 4,
        "min_positive_fold_frac": 0.6, "capital": 100000.0,
    }
    plan = {"experiment_count": 1, "items": [item]}
    plan = {"content_address": content_address(plan), **plan}
    item_key = operation_item_keys(plan, trigger="manual")[0]
    repo.enqueue(owner_id="owner-a", trigger="manual", plan=plan, build="b",
                 provider_mode="mock", operation_id="replay", now=now)
    claim = repo.claim_operation("replay", owner_id="owner-a", worker_id="first", now=now,
                                 lease_seconds=1)
    assert claim is not None and claim.claim_token
    program = ResearchProgram(owner_id="owner-a", name="receipt", thesis="")
    repo.session.add(program); repo.session.flush()
    hyp = Hypothesis(owner_id="owner-a", program_id=program.id, statement="receipt")
    repo.session.add(hyp); repo.session.flush()
    spec = ExperimentSpec(owner_id="owner-a", id="receipt-spec", hypothesis_id=hyp.id)
    repo.session.add(spec); repo.session.flush()
    run = ExperimentRun(owner_id="owner-a", spec_id=spec.id, status="running")
    repo.session.add(run); repo.session.commit()
    assert repo.bind_item_run("replay", owner_id="owner-a", token=claim.claim_token,
                              item_key=item_key, run_id=run.id, now=now)
    assert repo.complete_item("replay", owner_id="owner-a", token=claim.claim_token,
                              item_key=item_key, run_id=run.id, now=now)
    assert repo.completed_item_run("replay", owner_id="owner-a", item_key=item_key) == run.id

    replacement = repo.claim_next(owner_id="owner-a", worker_id="second",
                                  now=now + dt.timedelta(seconds=2))
    assert replacement is not None and replacement.claim_token
    assert not repo.complete_item("replay", owner_id="owner-a", token=claim.claim_token,
                                  item_key=item_key, run_id=run.id,
                                  now=now + dt.timedelta(seconds=2))
    assert repo.completed_item_run("replay", owner_id="owner-b", item_key=item_key) is None


def test_complete_refuses_until_every_admitted_item_has_a_terminal_receipt(repo):
    """A claimed operation may not report success ahead of its durable workload."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    item = {
        "program": "program", "hypothesis": "hypothesis", "strategy_key": "strategy",
        "instrument_keys": ["NIFTY"], "interval": "day", "days": 10,
        "optimize_search": False, "params": {}, "seed": 0, "min_trades": 20,
        "n_folds": 4, "min_positive_fold_frac": 0.6, "capital": 100000.0,
    }
    payload = {"experiment_count": 1, "items": [item]}
    plan = {"content_address": content_address(payload), **payload}
    repo.enqueue(owner_id="owner-a", trigger="manual", plan=plan, build="b",
                 provider_mode="mock", operation_id="unfinished", now=now)
    claim = repo.claim_operation("unfinished", owner_id="owner-a", worker_id="worker", now=now)
    assert claim is not None and claim.claim_token

    assert not repo.complete("unfinished", owner_id="owner-a", token=claim.claim_token, now=now)
    assert repo.get("unfinished", owner_id="owner-a").status == "running"


def test_operation_event_history_is_owner_scoped_bounded_and_tracks_real_stage_age(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b", provider_mode="mock",
                 operation_id="events", now=now)
    claim = repo.claim_operation("events", owner_id="owner-a", worker_id="worker", now=now)
    assert claim is not None and claim.claim_token
    assert repo.transition("events", owner_id="owner-a", token=claim.claim_token,
                           stage="collection", now=now + dt.timedelta(seconds=5))
    assert repo.metrics(owner_id="owner-a", now=now + dt.timedelta(seconds=12))["stage_age_seconds"] == 7
    events = repo.events("events", owner_id="owner-a")
    assert [(event["type"], event["stage"], event["payload"]) for event in events] == [
        ("claimed", "startup", {}), ("stage", "collection", {}),
    ]
    assert repo.events("events", owner_id="owner-b") == []

    for _ in range(132):
        assert repo.heartbeat("events", owner_id="owner-a", token=claim.claim_token, now=now)
    retained = repo.events("events", owner_id="owner-a", limit=128)
    assert [(event["type"], event["stage"]) for event in retained] == [
        ("claimed", "startup"), ("stage", "collection"),
    ]
    assert repo.metrics(owner_id="owner-a", now=now + dt.timedelta(seconds=2000))["stage_age_seconds"] == 1995


def test_generated_manifest_items_are_admitted_and_receive_durable_checkpoints(repo):
    from research.orchestrator.generate import generated_descriptors

    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    # The descriptor is intentionally not derived again after enqueue.  The
    # operation table stores it with the normal immutable plan content address.
    class Instrument:
        key = "GOLDM"
    descriptors = generated_descriptors(repo.session, [Instrument()], "day",
                                        owner_id="owner-a", limit=2, seed=7,
                                        git_commit="build-a", provider_mode="mock")
    payload = {"experiment_count": 2, "items": [], "generated": descriptors}
    plan = {"content_address": content_address(payload), **payload}
    queued = repo.enqueue(owner_id="owner-a", trigger="generated", plan=plan,
                          build="build-a", provider_mode="mock", operation_id="generated", now=now)
    assert queued.plan == plan
    assert len(operation_item_keys(plan, trigger="generated")) == 2


def test_reclaim_bound_item_marks_old_run_failed_then_resets_checkpoint(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    item = {
        "program": "program", "hypothesis": "hypothesis", "strategy_key": "strategy",
        "instrument_keys": ["NIFTY"], "interval": "day", "days": 10,
        "optimize_search": False, "params": {}, "seed": 0, "min_trades": 20,
        "n_folds": 4, "min_positive_fold_frac": 0.6, "capital": 100000.0,
    }
    base = {"experiment_count": 1, "items": [item]}
    plan = {"content_address": content_address(base), **base}
    repo.enqueue(owner_id="owner-a", trigger="manual", plan=plan, build="b",
                 provider_mode="mock", operation_id="takeover", now=now)
    first = repo.claim_operation("takeover", owner_id="owner-a", worker_id="one", now=now,
                                 lease_seconds=1)
    program = ResearchProgram(owner_id="owner-a", name="takeover", thesis="")
    repo.session.add(program); repo.session.flush()
    hyp = Hypothesis(owner_id="owner-a", program_id=program.id, statement="takeover")
    repo.session.add(hyp); repo.session.flush()
    spec = ExperimentSpec(owner_id="owner-a", id="takeover-spec", hypothesis_id=hyp.id)
    repo.session.add(spec); repo.session.flush()
    run = ExperimentRun(owner_id="owner-a", spec_id=spec.id, status="running")
    repo.session.add(run); repo.session.commit()
    key = operation_item_keys(plan, trigger="manual")[0]
    assert repo.bind_item_run("takeover", owner_id="owner-a", token=first.claim_token,
                              item_key=key, run_id=run.id, now=now)
    second = repo.claim_next(owner_id="owner-a", worker_id="two",
                             now=now + dt.timedelta(seconds=2))
    assert second is not None and second.claim_token
    assert repo.reclaim_bound_item("takeover", owner_id="owner-a", token=second.claim_token,
                                   item_key=key, now=now + dt.timedelta(seconds=2)) == run.id
    repo.session.expire_all()
    assert repo.session.get(ExperimentRun, run.id).status == "failed"
    assert repo.bound_item_run("takeover", owner_id="owner-a", item_key=key) is None


def test_claim_enforces_the_active_operation_ceiling_not_just_enqueue(repo):
    """A queue is allowed to accumulate, but claiming must reserve active capacity."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for number in range(5):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id=f"claim-{number}", now=now)

    claimed = [repo.claim_next(owner_id="owner-a", worker_id=f"w-{number}", now=now)
               for number in range(5)]

    assert [item.operation_id for item in claimed if item is not None] == [
        "claim-0", "claim-1", "claim-2", "claim-3",
    ]
    assert claimed[-1] is None


def test_host_claim_cap_counts_same_operation_id_in_other_tenants(repo):
    """Owner-local ids must not let host admission undercount active workers."""
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for number in range(32):
        owner = f"owner-{number}"
        repo.enqueue(owner_id=owner, trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id="same-id", now=now)
        assert repo.claim_operation("same-id", owner_id=owner, worker_id=owner,
                                    now=now) is not None
    repo.enqueue(owner_id="overflow", trigger="manual", plan={}, build="b",
                 provider_mode="mock", operation_id="same-id", now=now)
    assert repo.claim_operation("same-id", owner_id="overflow", worker_id="overflow",
                                now=now) is None


def test_operation_item_schema_requires_one_owner_local_run_and_coherent_receipt(repo):
    """A receipt cannot point across tenants or claim completion without a run."""
    table = inspect(repo.session.bind).get_table_names()
    assert "research_operation_item" in table
    constraints = inspect(repo.session.bind).get_unique_constraints("research_operation_item")
    assert ("owner_id", "run_id") in {
        tuple(constraint["column_names"]) for constraint in constraints
    }
    foreign_keys = inspect(repo.session.bind).get_foreign_keys("research_operation_item")
    assert ("owner_id", "run_id") in {
        tuple(foreign_key["constrained_columns"]) for foreign_key in foreign_keys
    }
    sql = repo.session.connection().exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name='research_operation_item'"
    ).scalar_one().upper()
    assert "CHECK" in sql and "RUNNING" in sql and "COMPLETED" in sql
