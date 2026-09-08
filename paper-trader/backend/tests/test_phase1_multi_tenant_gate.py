"""Phase 1 closure proof across the load-bearing private boundaries.

The detailed Task 1--6 suites own each resource family.  This file deliberately
joins their highest-risk contracts with two matching tenants: an untrusted
principal cannot choose an organization, repository calls cannot omit scope,
money state requires both organization and account, private cache rows cannot
be reused by another owner, and a private WebSocket frame cannot cross either
channel dimension.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.api import principal as policy
from app.api.principal import Principal
from app.backtest import cache
from app.core import deployments
from app.db.models import BacktestResult, BacktestRun, BrokerAccount, Organization
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts
from app.ledger import db as ledger_db
from app.ledger import routes as ledger_routes
from app.ledger import service as ledger_service
from app.ws.manager import WSManager
from tests.admitted_entry import persist_admitted_entry


OWNER_A = "org.gate.a"
OWNER_B = "org.gate.b"
ACCOUNT_A = "account.gate.a"
ACCOUNT_B = "account.gate.b"


@dataclass(frozen=True)
class _Owned:
    owner_id: str


class _Socket:
    def __init__(self) -> None:
        self.sent_text: list[str] = []

    async def accept(self) -> None:
        return None

    async def send_text(self, text: str) -> None:
        self.sent_text.append(text)

    async def close(self, code: int = 1000) -> None:
        return None

    @property
    def frames(self) -> list[dict]:
        return [json.loads(text) for text in self.sent_text]


def _principal(owner_id: str, role: str) -> Principal:
    return Principal(
        id=f"user.{owner_id}.{role}", kind="user", scopes=frozenset({"*"}),
        user_id=f"user.{owner_id}.{role}", organization_id=owner_id, role=role,
    )


def _seed_two_tenants() -> None:
    init_db(reset=True)
    with SessionLocal.begin() as session:
        for owner_id, account_id in ((OWNER_A, ACCOUNT_A), (OWNER_B, ACCOUNT_B)):
            session.add(Organization(organization_id=owner_id, name="same display name"))
            session.add(BrokerAccount(
                broker_account_id=account_id, owner_id=owner_id, broker="mock",
                external_account_id="same external account", display_name="same account",
                status="active",
            ))


def test_policy_role_matrix_rejects_foreign_resources_and_unknown_actions() -> None:
    """A policy mutation that accepts a foreign owner or unknown action reddens here."""
    own = _Owned(OWNER_A)
    foreign = _Owned(OWNER_B)
    viewer = _principal(OWNER_A, "viewer")
    member = _principal(OWNER_A, "member")
    admin = _principal(OWNER_A, "admin")
    owner = _principal(OWNER_A, "owner")

    assert policy.is_allowed(viewer, "read:project", own)
    assert not policy.is_allowed(viewer, "write:graph", own)
    assert policy.is_allowed(member, "write:graph", own)
    assert not policy.is_allowed(member, "archive:project", own)
    assert policy.is_allowed(admin, "archive:project", own)
    assert policy.is_allowed(owner, "authoritative:execution", own)
    assert not policy.is_allowed(owner, "invented:action", own)
    assert not policy.is_allowed(owner, "read:project", foreign)


def test_direct_repositories_require_scope_and_keep_matching_project_names_private() -> None:
    """Removing required scope or an owner predicate exposes this same-name fixture."""
    _seed_two_tenants()
    for boundary, required_scope in (
        (graph_artifacts.list_projects, ("owner_id",)),
        (deployments.get_deployment, ("owner_id", "broker_account_id")),
        (deployments.set_armed, ("owner_id", "broker_account_id")),
        (cache.find_reusable, ("owner_id",)),
    ):
        parameters = inspect.signature(boundary).parameters
        for name in required_scope:
            assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
            assert parameters[name].default is inspect.Parameter.empty

    project_a = graph_artifacts.create_project("same project", owner_id=OWNER_A)
    project_b = graph_artifacts.create_project("same project", owner_id=OWNER_B)
    assert project_a.project_id != project_b.project_id
    assert graph_artifacts.list_projects(owner_id=OWNER_A) == (project_a,)
    assert graph_artifacts.list_projects(owner_id=OWNER_B) == (project_b,)


def test_account_bound_execution_and_private_cache_reject_foreign_probes() -> None:
    """Removing either owner/account SQL predicate leaks money state or cache evidence."""
    _seed_two_tenants()
    with SessionLocal() as session:
        receipt_a = persist_admitted_entry(session, owner_id=OWNER_A)
        receipt_b = persist_admitted_entry(session, owner_id=OWNER_B)
        deployment_a = deployments.create_deployment(
            session, "same deployment", owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
            strategy_key=receipt_a["strategy_key"], strategy_version=receipt_a["strategy_version"],
            graph_address=receipt_a["graph_address"],
            attribution_state=receipt_a["attribution_state"],
            admission_address=receipt_a["admission_address"], status=deployments.ACTIVE,
        )
        deployment_b = deployments.create_deployment(
            session, "same deployment", owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
            strategy_key=receipt_b["strategy_key"], strategy_version=receipt_b["strategy_version"],
            graph_address=receipt_b["graph_address"],
            attribution_state=receipt_b["attribution_state"],
            admission_address=receipt_b["admission_address"], status=deployments.ACTIVE,
        )
        run_a = BacktestRun(owner_id=OWNER_A, scope="liquid", intervals="day", capital=1, total=1)
        session.add(run_a)
        session.flush()
        session.add(BacktestResult(
            owner_id=OWNER_A, run_id=run_a.id, instrument_key="NIFTY", interval="day",
            params_hash="same", last_candle_ts=100, schema_version=cache.SCHEMA_VERSION,
            error="", trades=1,
        ))
        deployments.set_armed(
            session, deployment_a.id, True, owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
        )
        with pytest.raises(ValueError, match="no deployment"):
            deployments.set_armed(
                session, deployment_a.id, False,
                owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
            )
        assert deployments.get_deployment(
            session, deployment_a.id, owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
        ).armed is True
        assert deployments.get_deployment(
            session, deployment_a.id, owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
        ) is None
        assert deployments.get_deployment(
            session, deployment_a.id, owner_id=OWNER_A, broker_account_id=ACCOUNT_B,
        ) is None
        assert deployments.get_deployment(
            session, deployment_a.id, owner_id=OWNER_B, broker_account_id=ACCOUNT_A,
        ) is None
        assert deployments.get_by_name(
            session, "same deployment", owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
        ).id == deployment_a.id
        assert deployments.get_by_name(
            session, "same deployment", owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
        ).id == deployment_b.id
        assert cache.find_reusable(
            session, "NIFTY", "day", "same", 100, owner_id=OWNER_B,
        ) is None
        assert cache.find_reusable(
            session, "NIFTY", "day", "same", 100, owner_id=OWNER_A,
        ).run_id == run_a.id


def test_private_websocket_event_cannot_cross_organization_or_account() -> None:
    """A global or one-dimensional channel mapping delivers a foreign private frame."""
    async def exercise() -> tuple[list[dict], list[dict], list[dict]]:
        manager = WSManager()
        manager.bind(asyncio.get_running_loop())
        a1, a2, b1 = _Socket(), _Socket(), _Socket()
        await manager.connect(a1, channel=(OWNER_A, ACCOUNT_A))
        await manager.connect(a2, channel=(OWNER_A, ACCOUNT_B))
        await manager.connect(b1, channel=(OWNER_B, ACCOUNT_A))
        await manager.broadcast((OWNER_A, ACCOUNT_A), {"type": "state", "data": {"private": "a1"}})
        await asyncio.sleep(0.02)
        return a1.frames, a2.frames, b1.frames

    a1, a2, b1 = asyncio.run(exercise())
    assert [frame["data"]["private"] for frame in a1] == ["a1"]
    assert a2 == []
    assert b1 == []


def test_private_ledger_artifacts_never_cache_across_tenant_credential_switches(
        tmp_path, monkeypatch) -> None:
    """A long-lived artifact cache at the same URL would replay A's bytes to B."""
    ledger_db._sessionmaker = None
    monkeypatch.setenv("PT_LEDGER_DB_PATH", str(tmp_path / "ledger.db"))
    account_by_owner = {OWNER_A: ACCOUNT_A, OWNER_B: ACCOUNT_B}
    for owner_id, body in ((OWNER_A, b"owner-a-private"), (OWNER_B, b"owner-b-private")):
        ledger_service.put_artifact(
            ledger_db.get_sessionmaker(), "same-artifact-id", "image/png", body,
            owner_id=owner_id, broker_account_id=account_by_owner[owner_id],
        )

    monkeypatch.setattr(
        ledger_routes, "_scope",
        lambda _request, principal, mutation=False: (
            principal.organization_id, account_by_owner[principal.organization_id],
        ),
    )
    from app.main import app
    principal_a = _principal(OWNER_A, "owner")
    principal_b = _principal(OWNER_B, "owner")
    try:
        client = TestClient(app)
        for prefix in ("/api", "/api/v1"):
            app.dependency_overrides[policy.get_principal] = lambda: principal_a
            first = client.get(f"{prefix}/ledger/artifacts/same-artifact-id")
            app.dependency_overrides[policy.get_principal] = lambda: principal_b
            second = client.get(f"{prefix}/ledger/artifacts/same-artifact-id")
            assert first.content == b"owner-a-private"
            assert second.content == b"owner-b-private"
            assert first.headers["cache-control"] == "private, no-store"
            assert second.headers["cache-control"] == "private, no-store"
    finally:
        app.dependency_overrides.clear()
        ledger_db._sessionmaker = None
