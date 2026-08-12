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
    assert repo.reconcile_expired(owner_id="owner-a", now=now) == 1
    assert repo.get("cancel", owner_id="owner-a").status == "cancelled"
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
