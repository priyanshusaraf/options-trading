import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.operations import ResearchOperationRepository
from research.operations import ResearchOperationRecorder, safe_plan_summary


@pytest.fixture(autouse=True)
def _operation_path(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PT_RESEARCH_OPERATION_RECEIPT", str(tmp_path / "operations.json")
    )
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", str(tmp_path / "research.db"))
    monkeypatch.setattr(get_settings(), "research_enabled", True)


@pytest.fixture
def client():
    return TestClient(app)


def test_never_run_status_is_explicit_and_versioned(client):
    expected = {"state": "never_run", "active": None, "last": None, "events": [],
                "active_operations": [], "active_complete": True}

    assert client.get("/api/research/operations/status").json() == expected
    assert client.get("/api/v1/research/operations/status").json() == expected


def test_status_returns_only_persisted_current_and_last_receipts(client, monkeypatch):
    engine = make_engine(os.environ["PT_RESEARCH_DB_PATH"])
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as session:
        ResearchOperationRepository(session).enqueue(
            owner_id=get_settings().owner_id or "legacy", trigger="nightly", build="abc123", provider_mode="historical",
            operation_id="operation-1", plan=safe_plan_summary([]),
        )
    engine.dispose()

    response = client.get("/api/research/operations/status")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "available"
    assert body["active"]["operation_id"] == "operation-1"
    assert body["active"]["plan"]["items"] == []
    assert body["last"] is None


def test_global_receipt_cannot_authorize_or_supply_operation_status(client):
    """A mutable host file cannot become another tenant's status authority."""
    recorder = ResearchOperationRecorder.start(
        Path(os.environ["PT_RESEARCH_OPERATION_RECEIPT"]),
        trigger="nightly",
        build="foreign-build",
        provider_mode="historical",
        operation_id="foreign-operation",
        now=lambda: "2026-08-03T01:00:00Z",
    )
    recorder.set_plan(safe_plan_summary([]))

    body = client.get("/api/research/operations/status").json()

    assert body == {"state": "never_run", "active": None, "last": None, "events": [],
                "active_operations": [], "active_complete": True}


def test_status_read_never_calls_research_execution(monkeypatch, client):
    from research.orchestrator import run

    monkeypatch.setattr(
        run,
        "run_nightly",
        lambda *args, **kwargs: pytest.fail("status read executed research"),
    )

    assert client.get("/api/research/operations/status").status_code == 200


def test_corrupt_global_receipt_does_not_change_durable_status(client, monkeypatch):
    receipt = Path(os.environ["PT_RESEARCH_OPERATION_RECEIPT"])
    receipt.write_text('{"not":"canonical state"}', encoding="utf-8")

    response = client.get("/api/research/operations/status")

    assert response.status_code == 200
    assert response.json() == {"state": "never_run", "active": None, "last": None, "events": [],
                "active_operations": [], "active_complete": True}


def test_status_surface_is_read_only_and_research_gated(client, monkeypatch):
    path = "/api/research/operations/status"
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(path).status_code == 405

    monkeypatch.setattr(get_settings(), "research_enabled", False)
    assert client.get(path).status_code == 403


def test_owner_local_detail_events_and_cancel_are_private_and_terminal(client):
    engine = make_engine(os.environ["PT_RESEARCH_DB_PATH"])
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    owner = get_settings().owner_id or "legacy"
    with Session() as session:
        repository = ResearchOperationRepository(session)
        repository.enqueue(
            owner_id=owner, trigger="manual", build="build", provider_mode="mock",
            operation_id="owned-operation", plan={},
        )
        repository.enqueue(
            owner_id="foreign-owner", trigger="manual", build="build",
            provider_mode="mock", operation_id="foreign-operation", plan={},
        )
    engine.dispose()

    detail = client.get("/api/research/operations/owned-operation")
    assert detail.status_code == 200
    assert detail.json()["operation_id"] == "owned-operation"
    assert detail.json()["status"] == "pending"
    assert detail.json()["events"] == []
    cancelled = client.post("/api/research/operations/owned-operation/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["events"][-1]["type"] == "cancelled"

    absent = client.get("/api/research/operations/missing-operation")
    foreign = client.get("/api/research/operations/foreign-operation")
    assert absent.status_code == foreign.status_code == 404
    assert absent.json() == foreign.json()
    assert client.post("/api/research/operations/foreign-operation/cancel").json() \
        == foreign.json()


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_recovery_status_keeps_older_active_jobs_and_hides_foreign_jobs(client, prefix):
    import datetime as dt

    engine = make_engine(os.environ['PT_RESEARCH_DB_PATH'])
    init_research_db(engine)
    owner = get_settings().owner_id or 'legacy'
    now = dt.datetime(2026, 9, 5, tzinfo=dt.UTC)
    with make_sessionmaker(engine)() as session:
        repository = ResearchOperationRepository(session)
        for index, (job_owner, identifier) in enumerate([
            (owner, 'older-strategy'), (owner, 'newer-strategy'), ('foreign-owner', 'foreign-job'),
        ]):
            repository.enqueue(owner_id=job_owner, operation_id=identifier, trigger='manual',
                plan={}, build='test', provider_mode='mock', now=now + dt.timedelta(seconds=index))
    engine.dispose()
    response = client.get(prefix + '/research/operations/status')
    assert response.status_code == 200
    body = response.json()
    assert body['active_complete'] is True
    assert [item['operation_id'] for item in body['active_operations']] == ['newer-strategy', 'older-strategy']
    assert body['active'] == body['active_operations'][0]
    assert all(item['status'] == 'pending' for item in body['active_operations'])


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_recovery_status_never_claims_a_truncated_active_list_is_complete(client, prefix):
    from research.domain.models import ResearchOperation

    engine = make_engine(os.environ['PT_RESEARCH_DB_PATH'])
    init_research_db(engine)
    owner = get_settings().owner_id or 'legacy'
    with make_sessionmaker(engine)() as session:
        session.add_all([ResearchOperation(owner_id=owner, operation_id=f'old-{index:02}',
            trigger='manual', plan_json='{}', status='pending') for index in range(25)])
        session.commit()
    engine.dispose()
    response = client.get(prefix + '/research/operations/status')
    assert response.status_code == 200
    body = response.json()
    assert body['active_complete'] is False
    assert len(body['active_operations']) == 21
    assert body['active'] == body['active_operations'][0]
