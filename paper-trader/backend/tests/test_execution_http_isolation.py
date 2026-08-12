"""HTTP proof that the singleton local runner never becomes another tenant's cell."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.principal import Principal, get_principal
from app.core import deployments
from app.core.config import get_settings
from app.db.models import BrokerAccount, Membership, Organization, User
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.execution.leases import LeaseRepository
from app.main import app


OWNER_A = "org.execution.a"
OWNER_B = "org.execution.b"
ACCOUNT_A = "account.execution.a"
ACCOUNT_B = "account.execution.b"


def _principal(owner_id: str, role: str) -> Principal:
    return Principal(id=f"user.{owner_id}", kind="user", scopes=frozenset({"*"}),
                     user_id=f"user.{owner_id}", organization_id=owner_id, role=role)


def _client(monkeypatch, principal: Principal) -> tuple[TestClient, EngineRunner]:
    monkeypatch.setattr(get_settings(), "api_token", "")
    init_db(reset=True)
    with SessionLocal() as session:
        for owner_id, account_id in ((OWNER_A, ACCOUNT_A), (OWNER_B, ACCOUNT_B)):
            user_id = f"user.{owner_id}"
            session.add_all([
                Organization(organization_id=owner_id, name=owner_id),
                User(user_id=user_id, email_normalized=f"{user_id}@example.test",
                     display_name=user_id),
            ])
        session.flush()
        for owner_id, account_id in ((OWNER_A, ACCOUNT_A), (OWNER_B, ACCOUNT_B)):
            user_id = f"user.{owner_id}"
            session.add_all([
                Membership(organization_id=owner_id, user_id=user_id, role="owner"),
                BrokerAccount(broker_account_id=account_id, owner_id=owner_id, broker="mock",
                              external_account_id=account_id, display_name=account_id),
            ])
        session.flush()
        deployment = deployments.create_deployment(session, "local", owner_id=OWNER_A,
                                                   broker_account_id=ACCOUNT_A)
        session.commit()
    runner = EngineRunner(owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
                          deployment_id=deployment.id)
    leases = LeaseRepository(SessionLocal)
    token = leases.claim(owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
                         cell_id="test-cell", worker_id="test-boot")
    leases.activate(token, reconciliation_evidence="test fixture reconciled")
    runner.broker.execution_lease_token = token
    app.state.runner = runner
    app.dependency_overrides[get_principal] = lambda: principal
    return TestClient(app), runner


def test_foreign_or_missing_execution_cells_are_indistinguishable_and_cannot_arm(monkeypatch):
    """Removing the owner/account predicate would expose or mutate A's runner for B."""
    client, runner = _client(monkeypatch, _principal(OWNER_B, "owner"))
    try:
        foreign = client.get("/api/status")
        missing = client.get("/api/v1/status")
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json() == {"detail": "execution unavailable"}
        assert client.post("/api/execution/arm", json={"armed": True}).status_code == 404
        assert runner.armed is False
    finally:
        app.dependency_overrides.clear()
        runner.broker.close()


def test_viewer_can_read_local_cell_but_cannot_mutate_it_on_either_prefix(monkeypatch):
    """Changing the role gate from owner-only to any member must fail this test."""
    client, runner = _client(monkeypatch, _principal(OWNER_A, "viewer"))
    try:
        assert client.get("/api/status").status_code == 200
        assert client.get("/api/v1/status").status_code == 200
        assert client.post("/api/execution/arm", json={"armed": True}).status_code == 403
        assert client.post("/api/v1/execution/arm", json={"armed": True}).status_code == 403
        assert runner.armed is False
    finally:
        app.dependency_overrides.clear()
        runner.broker.close()


def test_local_owner_can_arm_only_the_local_execution_cell(monkeypatch):
    """Removing the local-cell equality check would make this authorization meaningless."""
    client, runner = _client(monkeypatch, _principal(OWNER_A, "owner"))
    try:
        response = client.post("/api/v1/execution/arm", json={"armed": True})
        assert response.status_code == 202
        assert response.json()["armed"] is False
        assert response.json()["desired_state"] == "armed"
        assert response.json()["effective_state"] == "disabled"
        assert response.json()["status"] == "accepted"
        # The API records shared desired state; it never pretends another process's
        # in-memory runner has already executed the command.
        assert runner.armed is False
    finally:
        app.dependency_overrides.clear()
        runner.broker.close()
