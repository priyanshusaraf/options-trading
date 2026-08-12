import datetime as dt
import time

import pytest

from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.operations import DurableOperationRecorder, ResearchOperationRepository


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


def test_owner_admission_rejects_queue_capacity_before_creating_another_operation(repo):
    now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
    for number in range(16):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id=f"queued-{number}", now=now)
    with pytest.raises(RuntimeError, match="admission capacity"):
        repo.enqueue(owner_id="owner-a", trigger="manual", plan={}, build="b",
                     provider_mode="mock", operation_id="rejected", now=now)
    assert repo.get("rejected", owner_id="owner-a") is None


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
            assert repo.reconcile_expired(owner_id="owner-a", now=now + dt.timedelta(seconds=61)) == 1
    repo.enqueue(owner_id="owner-b", trigger="manual", plan={}, build="b", provider_mode="mock",
                 operation_id="foreign", now=now)
    assert repo.metrics(owner_id="owner-a", now=now) == {
        "queued": 0, "active": 0, "expired_claims": 0,
        "completed": 1, "failed": 1, "cancelled": 1,
    }
