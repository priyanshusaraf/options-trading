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


def quota_plan(count):
    """A bounded synthetic plan; no instrument or provider work is admitted."""
    from research.operations import safe_plan_summary
    return safe_plan_summary([{
        "program": "quota-recovery", "hypothesis": f"item-{i}",
        "strategy_key": "trend_impulse_v3", "instruments": [],
        "interval": "day", "days": 10, "seed": 17,
    } for i in range(count)])


@pytest.fixture(params=["sqlite", "postgresql"])
def repo(tmp_path, request):
    authority = (request.getfixturevalue("pg_sandbox").research_url
                 if request.param == "postgresql" else str(tmp_path / "research.db"))
    engine = make_engine(authority)
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
    import copy
    from research.domain.operations import _plan_payload
    for field in ("composition_identity", "graph_content_address", "admission_address"):
        changed = copy.deepcopy(payload)
        changed["generated"][0][field] = "invalid" if field == "admission_address" else "sha256:" + "f" * 64
        with pytest.raises(ValueError, match="generated descriptor is invalid"):
            _plan_payload({"content_address": content_address(changed), **changed})
    changed = copy.deepcopy(payload)
    changed["generated"][0]["graph"]["unexpected"] = True
    changed["generated"][0]["graph_content_address"] = content_address(changed["generated"][0]["graph"])
    with pytest.raises(ValueError, match="generated descriptor is invalid"):
        _plan_payload({"content_address": content_address(changed), **changed})
    with pytest.raises(ValueError, match="content address is invalid"):
        _plan_payload({**plan, "content_address": "sha256:" + "f" * 64})


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
    checks = inspect(repo.session.bind).get_check_constraints("research_operation_item")
    sql = " ".join(check["sqltext"] for check in checks).upper()
    assert "RUNNING" in sql and "COMPLETED" in sql


@pytest.mark.parametrize("boundary", ["host_queue", "owner_pending_items", "host_pending_items",
                                      "owner_active_items", "host_active_items"])
def test_real_quota_boundaries_refuse_then_release_exact_capacity(repo, boundary):
    """Exercise shipped caps through admission/claim, without lowering policy."""
    import json
    import resource
    from sqlalchemy import func, select
    from research.domain.models import ResearchOperation

    started = time.monotonic()
    now = dt.datetime.now(dt.UTC)
    active = "active" in boundary
    if boundary == "host_queue":
        count, width = 256, 0
        owner_for = lambda i: f"owner-{i // 16}"
        overflow_owner, overflow_width = "overflow", 0
    elif boundary == "owner_pending_items":
        count, width = 2, 64
        owner_for = lambda i: "owner"
        overflow_owner, overflow_width = "owner", 1
    elif boundary == "host_pending_items":
        count, width = 8, 64
        owner_for = lambda i: f"owner-{i}"
        overflow_owner, overflow_width = "overflow", 1
    elif boundary == "owner_active_items":
        count, width = 1, 32
        owner_for = lambda i: "owner"
        overflow_owner, overflow_width = "owner", 1
    else:
        count, width = 4, 32
        owner_for = lambda i: f"owner-{i}"
        overflow_owner, overflow_width = "overflow", 1
    for i in range(count):
        repo.enqueue(owner_id=owner_for(i), operation_id=f"op-{i}", trigger="manual",
                     plan=quota_plan(width), build="quota-build", provider_mode="mock", now=now)
        if active:
            assert repo.claim_operation(f"op-{i}", owner_id=owner_for(i), worker_id="worker", now=now)
    enqueue = lambda: repo.enqueue(owner_id=overflow_owner, operation_id="overflow", trigger="manual",
                                    plan=quota_plan(overflow_width), build="quota-build",
                                    provider_mode="mock", now=now)
    if active:
        enqueue()
        assert repo.claim_operation("overflow", owner_id=overflow_owner, worker_id="extra", now=now) is None
    else:
        with pytest.raises(RuntimeError, match="admission capacity"):
            enqueue()
        assert repo.get("overflow", owner_id=overflow_owner) is None
    assert repo.request_cancel("op-0", owner_id=owner_for(0), now=now)
    if not active:
        enqueue()
    else:
        assert repo.claim_operation("overflow", owner_id=overflow_owner, worker_id="extra", now=now)
    rows = repo.session.scalar(select(func.count()).select_from(ResearchOperation))
    assert rows == count + 1
    print(json.dumps({"boundary": boundary, "dialect": repo.session.bind.dialect.name,
                      "operations": rows, "elapsed_seconds": time.monotonic() - started,
                      "process_peak_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


def test_terminal_receipt_rollback_never_publishes_success(repo, monkeypatch):
    from research.orchestrator.run import run_nightly
    from research.domain.operations import reconstruct_plan

    plan = quota_plan(1)
    recorder = DurableOperationRecorder.start(repo, owner_id="owner", operation_id="atomic",
        trigger="manual", plan=plan, build="atomic-build", provider_mode="mock", worker_id="worker")
    key = operation_item_keys(plan, trigger="manual")[0]
    original = repo._append_event

    def fail_receipt(*args, **kwargs):
        original(*args, **kwargs)
        if kwargs["event_type"] == "item_completed":
            raise RuntimeError("injected receipt interruption")

    with monkeypatch.context() as patch:
        patch.setattr(repo, "_append_event", fail_receipt)
        with pytest.raises(RuntimeError, match="injected receipt interruption"):
            run_nightly(repo.session, None, reconstruct_plan(plan, instrument_for_key=lambda _: None),
                owner_id="owner", git_commit="atomic-build", item_keys=[key],
                bind_item_run=recorder.bind_item_run_in_transaction,
                finalize_item=recorder.finalize_item_in_transaction)
        repo.session.rollback()
    run_id = recorder.bound_item_run(key)
    assert run_id is not None
    # The actual consumer rolls back terminal success, then records a failed
    # run in its exception handler. This differs from abrupt process death.
    assert repo.session.get(ExperimentRun, run_id).status == "failed"
    assert recorder.completed_item_run(key) is None
    assert repo.get("atomic", owner_id="owner").completed_run_ids == []
    assert all(event["type"] != "item_completed" for event in repo.events("atomic", owner_id="owner"))
    assert recorder.reclaim_bound_item(key) is None
    assert repo.request_cancel("atomic", owner_id="owner")
    assert repo.get("atomic", owner_id="owner").status == "cancelled"


def test_expired_token_refuses_all_terminal_and_progress_writes(repo):
    now = dt.datetime.now(dt.UTC)
    repo.enqueue(owner_id="owner", operation_id="expired", trigger="manual", plan={},
                 build="b", provider_mode="mock", now=now)
    claim = repo.claim_operation("expired", owner_id="owner", worker_id="first", now=now, lease_seconds=1)
    late = now + dt.timedelta(seconds=2)
    assert not repo.heartbeat("expired", owner_id="owner", token=claim.claim_token, now=late)
    assert not repo.transition("expired", owner_id="owner", token=claim.claim_token, stage="reports", now=late)
    assert not repo.add_completed_run("expired", owner_id="owner", token=claim.claim_token, run_id=1, now=late)
    assert not repo.fail("expired", owner_id="owner", token=claim.claim_token, error={"code": "STALE"}, now=late)
    assert not repo.complete("expired", owner_id="owner", token=claim.claim_token, now=late)
    replacement = repo.claim_next(owner_id="owner", worker_id="second", now=late)
    assert replacement.claim_token != claim.claim_token
    assert replacement.attempt_count == 2
    assert not repo.complete("expired", owner_id="owner", token=claim.claim_token, now=late)
    assert repo.complete("expired", owner_id="owner", token=replacement.claim_token, now=late)
    assert not repo.complete("expired", owner_id="owner", token=replacement.claim_token, now=late)


def test_real_watchdog_observes_cancellation_and_refuses_next_stage(repo):
    import threading
    recorder = DurableOperationRecorder.start(repo, owner_id="owner", operation_id="watchdog-real",
        trigger="manual", plan={}, build="b", provider_mode="mock", worker_id="worker")
    sessions = make_sessionmaker(repo.session.bind)
    observed = threading.Event()

    def heartbeat(operation_id, owner_id, token):
        with sessions() as session:
            alive = ResearchOperationRepository(session).heartbeat(operation_id, owner_id=owner_id, token=token)
        if not alive:
            observed.set()
        return alive

    repo.request_cancel("watchdog-real", owner_id="owner")
    started = time.monotonic()
    recorder.start_watchdog(heartbeat, interval_seconds=0.01)
    try:
        assert observed.wait(timeout=5)
        assert recorder._claim_lost.wait(timeout=5)
        with pytest.raises(RuntimeError, match="claim was lost"):
            recorder.transition("collection")
        assert repo.events("watchdog-real", owner_id="owner")[-1]["type"] == "cancelled"
        print({"dialect": repo.session.bind.dialect.name,
               "local_cancellation_observation_seconds": time.monotonic() - started})
    finally:
        recorder.close_watchdog()


def test_cancellation_terminalizes_bound_run_and_fences_item_writes(repo):
    plan = quota_plan(1)
    recorder = DurableOperationRecorder.start(repo, owner_id="owner", operation_id="bound-cancel",
        trigger="manual", plan=plan, build="b", provider_mode="mock", worker_id="worker")
    program = ResearchProgram(owner_id="owner", name="cancel", thesis="")
    repo.session.add(program); repo.session.flush()
    hypothesis = Hypothesis(owner_id="owner", program_id=program.id, statement="cancel")
    repo.session.add(hypothesis); repo.session.flush()
    spec = ExperimentSpec(owner_id="owner", id="cancel-spec", hypothesis_id=hypothesis.id)
    repo.session.add(spec); repo.session.flush()
    run = ExperimentRun(owner_id="owner", spec_id=spec.id, status="running")
    repo.session.add(run); repo.session.flush()
    run_id = run.id
    key = operation_item_keys(plan, trigger="manual")[0]
    assert recorder.bind_item_run_in_transaction(key, run_id)
    repo.session.commit()
    assert not repo.request_cancel("bound-cancel", owner_id="foreign")
    assert repo.request_cancel("bound-cancel", owner_id="owner")
    repo.session.expire_all()
    assert repo.session.get(ExperimentRun, run_id).status == "failed"
    assert repo.session.get(ExperimentRun, run_id).error == "RESEARCH_OPERATION_CANCELLED"
    assert not recorder.finalize_item_in_transaction(key, run_id)
    repo.session.rollback()
    assert not repo.complete_item("bound-cancel", owner_id="owner", token=recorder.token,
                                  item_key=key, run_id=run_id)
    assert not repo.bind_item_run("bound-cancel", owner_id="owner", token=recorder.token,
                                  item_key=key, run_id=run_id)
    assert recorder.reclaim_bound_item(key) is None
    assert repo.get("bound-cancel", owner_id="owner").completed_run_ids == []
    assert repo.completed_item_run("bound-cancel", owner_id="owner", item_key=key) is None
    assert repo.claim_next(owner_id="owner", worker_id="replacement") is None


@pytest.mark.parametrize("field,value,accepted", [
    ("program", "", False), ("program", "p" * 80, True), ("program", "p" * 81, False),
    ("hypothesis", "h" * 4001, False), ("strategy_key", "s" * 81, False),
    ("interval", "i" * 25, False), ("instrument_keys", [], True),
    ("instrument_keys", [""], False), ("instrument_keys", ["i" * 49], False),
    ("instrument_keys", ["i"] * 65, False), ("instrument_keys", [1], False),
    ("days", False, False), ("days", 0, True), ("days", 10000, True), ("days", 10001, False),
    ("optimize_search", 0, False), ("params", [], False), ("params", {"": None}, True),
    ("params", {"p" * 65: 1}, False), ("params", {"p": []}, False),
    ("seed", None, False), ("seed", False, False), ("seed", 2147483647, True),
    ("seed", 2147483648, False), ("min_trades", 0, False), ("min_trades", 100001, False),
    ("n_folds", 1, False), ("n_folds", 32, True), ("n_folds", 33, False),
    ("min_positive_fold_frac", False, False), ("min_positive_fold_frac", 1.0, True),
    ("min_positive_fold_frac", 1.01, False), ("capital", False, False),
    ("capital", 0, False), ("capital", 1000000000.0, True), ("capital", 1000000000.01, False),
])
def test_handwritten_plan_boundaries_keep_the_closed_public_contract(field, value, accepted):
    from research.domain.operations import _plan_payload
    plan = quota_plan(1)
    plan["items"][0][field] = value
    plan["content_address"] = content_address({"experiment_count": 1, "items": plan["items"]})
    if accepted:
        assert _plan_payload(plan) == plan
    else:
        with pytest.raises(ValueError, match="operation plan payload is invalid"):
            _plan_payload(plan)


def test_pending_capacity_counts_only_the_requesting_owner(repo):
    repo.enqueue(owner_id="other", trigger="manual", plan=quota_plan(64), build="b", provider_mode="mock", operation_id="other-1")
    repo.enqueue(owner_id="other", trigger="manual", plan=quota_plan(64), build="b", provider_mode="mock", operation_id="other-2")
    queued = repo.enqueue(owner_id="owner", trigger="manual", plan=quota_plan(1), build="b", provider_mode="mock", operation_id="owner-1")
    assert queued.operation_id == "owner-1"
    assert repo._pending_capacity_counts("owner") == (1, 3, 1, 129)


def test_manual_duplicate_keeps_the_existing_operation(repo):
    original = repo.enqueue(owner_id="owner", trigger="manual", plan=quota_plan(1), build="b", provider_mode="mock", operation_id="same")
    with pytest.raises(ValueError, match="operation_id already exists"):
        repo.enqueue(owner_id="owner", trigger="manual", plan=quota_plan(1), build="b", provider_mode="mock", operation_id="same")
    assert repo.get("same", owner_id="owner").plan == original.plan


@pytest.mark.parametrize('count,complete', [(0, True), (20, True), (21, False), (25, False)])
def test_active_recovery_is_owner_scoped_complete_or_explicitly_truncated(repo, count, complete):
    from research.domain.models import ResearchOperation

    now = dt.datetime(2026, 9, 5, tzinfo=dt.UTC)
    # Insert an over-cap historical state to prove the reader fails closed too.
    for number in range(count):
        repo.session.add(ResearchOperation(owner_id='owner-a', operation_id=f'active-{number:02}',
            trigger='v2_graph', plan_json='{}', status='running' if number < 4 else 'pending',
            queued_at=now + dt.timedelta(seconds=number)))
    repo.session.add_all([
        ResearchOperation(owner_id='owner-b', operation_id='foreign', trigger='v2_graph',
                          plan_json='{}', status='running', queued_at=now + dt.timedelta(days=1)),
        ResearchOperation(owner_id='owner-a', operation_id='terminal', trigger='v2_graph',
                          plan_json='{}', status='completed', queued_at=now + dt.timedelta(days=1)),
    ])
    repo.session.commit()
    operations, is_complete = repo.active_for_recovery(owner_id='owner-a')
    assert is_complete is complete
    assert [item.operation_id for item in operations] == [
        f'active-{number:02}' for number in reversed(range(count))][:21]
    assert repo.active_for_recovery(owner_id='absent') == ([], True)


@pytest.mark.parametrize("change", [
    {"extra": True}, {"content_address": None}, {"experiment_count": False},
    {"experiment_count": -1}, {"experiment_count": 65}, {"items": {}},
    {"generated": {}}, {"experiment_count": 1},
])
def test_legacy_operation_plan_refuses_open_or_inconsistent_workload_shape(change):
    from research.domain.operations import _plan_payload
    payload = {"content_address": "sha256:" + "a" * 64, "experiment_count": 0, "items": []}
    payload.update(change)
    with pytest.raises(ValueError, match="operation plan payload is invalid"):
        _plan_payload(payload)


@pytest.mark.parametrize("field,value", [
    ("limit", 0), ("limit", 65), ("owner_universe", []), ("owner_universe", [""]),
    ("seed", False), ("seed", -1), ("min_trades", 0), ("n_folds", 1),
    ("min_positive_fold_frac", 1.1),
])
def test_generated_workload_bounds_refuse_before_composition_loading(field, value):
    from research.domain.operations import _generated_bounds
    descriptor = {"limit": 1, "owner_universe": ["GOLDM"], "seed": None,
                  "min_trades": 1, "n_folds": 2, "min_positive_fold_frac": 0.5}
    descriptor[field] = value
    with pytest.raises(ValueError, match="generated descriptor is invalid"):
        _generated_bounds(descriptor)


def test_running_v2_count_keeps_pending_findings_and_heartbeat_writable(repo):
    from research.domain.models import Finding

    now = dt.datetime.now(dt.UTC)
    repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                 provider_mode="mock", operation_id="finding-heartbeat", now=now)
    claim = repo.claim_operation("finding-heartbeat", owner_id="owner-a",
                                 worker_id="worker", now=now)
    program = ResearchProgram(owner_id="owner-a", name="pending-finding", thesis="")
    repo.session.add(program)
    repo.session.flush()
    hypothesis = Hypothesis(owner_id="owner-a", program_id=program.id, statement="pending")
    repo.session.add(hypothesis)
    repo.session.commit()
    finding = Finding(owner_id="owner-a", hypothesis_id=hypothesis.id,
                      statement="Uncommitted validation evidence", polarity="negative")
    repo.session.add(finding)
    assert repo.running_v2_count(owner_id="owner-a") == 0
    Session = make_sessionmaker(repo.session.get_bind())
    with Session() as other:
        if other.bind.dialect.name == "sqlite":
            other.connection().exec_driver_sql("PRAGMA busy_timeout=50")
        assert ResearchOperationRepository(other).heartbeat(
            "finding-heartbeat", owner_id="owner-a", token=claim.claim_token, now=now)
    assert finding in repo.session.new
    repo.session.rollback()


@pytest.mark.parametrize("value", [None, [], "plan", True])
def test_operation_plan_refuses_non_object_before_dispatch(value):
    from research.domain.operations import _plan_payload
    with pytest.raises(ValueError, match="payload is invalid"):
        _plan_payload(value)
