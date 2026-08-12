"""Task 5B HTTP authorization boundaries, exercised with real tenant principals."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.api import principal as policy
from app.api.principal import Principal
from app.core.config import get_settings
from app.db import models
from app.db.session import SessionLocal, init_db


UTC = dt.timezone.utc


class _Owned:
    def __init__(self, owner_id: str):
        self.owner_id = owner_id


def _principal(*, organization_id: str, user_id: str, role: str,
               scopes: frozenset[str] = frozenset({"*"})) -> Principal:
    return Principal(id=user_id, kind="user", scopes=scopes, user_id=user_id,
                     organization_id=organization_id, role=role)


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_route_mounts_are_both_registered(prefix):
    """The versioned mount must expose the same protected resource families."""
    from app.main import app
    paths = {
        getattr(child, "path", "")
        for route in app.routes
        for child in getattr(getattr(route, "original_router", route), "routes", (route,))
    }
    assert f"{prefix}/ir/projects" in paths
    assert f"{prefix}/backtest/status" in paths


def test_policy_is_closed_and_requires_the_resource_owner_to_match_the_organization():
    """Removing either the action vocabulary or owner predicate makes this fail."""
    member_a = _principal(organization_id="org.a", user_id="same-name", role="member")
    assert policy.is_allowed(member_a, "read:project", _Owned("org.a")) is True
    assert policy.is_allowed(member_a, "read:project", _Owned("org.b")) is False
    assert policy.is_allowed(member_a, "invented:action", _Owned("org.a")) is False
    assert policy.is_allowed(member_a, "read:project", object()) is False


def test_role_baseline_and_explicit_scopes_intersect():
    """Role or scope mutation must remove the matching capability."""
    owned = _Owned("org.a")
    viewer = _principal(organization_id="org.a", user_id="viewer", role="viewer")
    member = _principal(organization_id="org.a", user_id="member", role="member")
    admin = _principal(organization_id="org.a", user_id="admin", role="admin")
    scoped_admin = _principal(organization_id="org.a", user_id="scoped", role="admin",
                              scopes=frozenset({"read:project"}))

    assert policy.is_allowed(viewer, "read:project", owned) is True
    assert policy.is_allowed(viewer, "write:graph", owned) is False
    assert policy.is_allowed(member, "write:graph", owned) is True
    assert policy.is_allowed(member, "archive:project", owned) is False
    assert policy.is_allowed(admin, "archive:project", owned) is True
    assert policy.is_allowed(scoped_admin, "archive:project", owned) is False


def test_sessions_preserve_role_and_tenant_when_resolved(monkeypatch):
    """Same display names and user keys do not permit cross-organization authority."""
    init_db(reset=True)
    with SessionLocal() as session:
        for organization_id in ("org.a", "org.b"):
            session.add(models.Organization(organization_id=organization_id, name="same"))
        for organization_id in ("org.a", "org.b"):
            user_id = f"same-user.{organization_id}"
            session.add(models.User(user_id=user_id, email_normalized=f"{organization_id}@test",
                                    display_name="same"))
        session.flush()
        for organization_id in ("org.a", "org.b"):
            user_id = f"same-user.{organization_id}"
            session.add(models.Membership(organization_id=organization_id, user_id=user_id,
                                          role="viewer" if organization_id == "org.a" else "admin"))
        session.commit()
        issued = policy.issue_user_session(
            session, user_id="same-user.org.a", organization_id="org.a",
            expires_at=dt.datetime.now(UTC) + dt.timedelta(hours=1),
        )
        session.commit()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    resolved = policy.resolve_principal(issued.token)
    assert resolved is not None
    assert (resolved.user_id, resolved.organization_id, resolved.role) == (
        "same-user.org.a", "org.a", "viewer")
    assert policy.is_allowed(resolved, "archive:project", _Owned("org.a")) is False
    assert policy.is_allowed(resolved, "read:project", _Owned("org.b")) is False


def _seed_http_principals(monkeypatch):
    """Two organizations, matching display names, and durable HTTP credentials."""
    init_db(reset=True)
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    with SessionLocal() as session:
        for org in ("org.a", "org.b"):
            session.add(models.Organization(organization_id=org, name="same"))
        session.add_all([
            models.User(user_id="user.a", email_normalized="same-a@test", display_name="same"),
            models.User(user_id="user.b", email_normalized="same-b@test", display_name="same"),
            models.User(user_id="viewer.a", email_normalized="viewer-a@test", display_name="same"),
        ])
        session.flush()
        session.add_all([
            models.Membership(organization_id="org.a", user_id="user.a", role="admin"),
            models.Membership(organization_id="org.b", user_id="user.b", role="admin"),
            models.Membership(organization_id="org.a", user_id="viewer.a", role="viewer"),
        ])
        session.flush()
        expiry = dt.datetime.now(UTC) + dt.timedelta(hours=1)
        issued = {
            user: policy.issue_user_session(session, user_id=user, organization_id=org,
                                            expires_at=expiry)
            for user, org in (("user.a", "org.a"), ("user.b", "org.b"),
                              ("viewer.a", "org.a"))
        }
        session.commit()
    return issued


def _headers(issued, user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {issued[user_id].token}"}


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_project_http_idor_is_sql_scoped_and_foreign_matches_absent(monkeypatch, prefix):
    """Removing Project.owner_id from the lookup leaks a foreign row into this response."""
    issued = _seed_http_principals(monkeypatch)
    with SessionLocal.begin() as session:
        project = models.Project(project_id="project.b", owner_id="org.b", name="same",
                                 description="B", status="active")
        session.add(project)
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        if "from graph_artifacts" in statement.lower():
            statements.append(" ".join(statement.lower().split()))

    from app.db.session import engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        client = TestClient(__import__("app.main", fromlist=["app"]).app)
        foreign = client.get(f"{prefix}/ir/projects/project.b/graphs/nope/draft",
                             headers=_headers(issued, "user.a"))
        absent = client.get(f"{prefix}/ir/projects/missing/graphs/nope/draft",
                            headers=_headers(issued, "user.a"))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert (foreign.status_code, foreign.content) == (absent.status_code, absent.content)
    assert foreign.status_code == 404
    assert statements and all("graph_artifacts.owner_id" in statement for statement in statements)


@pytest.mark.parametrize("prefix", ("/api", "/api/v1"))
def test_create_ignores_tenant_and_actor_input_and_viewer_write_is_forbidden(monkeypatch, prefix):
    """Scope/actor fields are forbidden input; principal tenant is the sole source of ownership."""
    issued = _seed_http_principals(monkeypatch)
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    forbidden = client.post(f"{prefix}/ir/projects", json={"name": "view"},
                            headers=_headers(issued, "viewer.a"))
    injected = client.post(f"{prefix}/ir/projects", json={"name": "bad", "owner_id": "org.b"},
                           headers=_headers(issued, "user.a"))
    created = client.post(f"{prefix}/ir/projects", json={"name": "good"},
                          headers=_headers(issued, "user.a"))
    assert forbidden.status_code == 403
    assert injected.status_code == 422
    assert created.status_code == 201
    with SessionLocal() as session:
        row = session.scalar(select(models.Project).where(models.Project.project_id == created.json()["project_id"]))
        assert row is not None and row.owner_id == "org.a"


def test_review_state_records_the_creator_user_id_without_rewriting_legacy_owner():
    """The old literal remains readable, while new principal-derived attribution is durable."""
    from app.core import review_state
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add(models.Organization(organization_id="org.a", name="A"))
        session.add(models.Project(project_id="project.a", owner_id="org.a", name="A",
                                   description="", status="active"))
    created = review_state.create_note(
        "project.a", owner_id="org.a", event_id="event.a",
        event_type="experiment_run", body="user attribution", created_by="user.a",
    )
    assert created.created_by == "user.a"


def test_review_state_refuses_another_same_organization_user_before_update(monkeypatch):
    """A member/admin role does not turn another user's review prose into shared state."""
    from app.core import review_state
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add(models.Organization(organization_id="org.a", name="A"))
        session.add(models.Project(project_id="project.a", owner_id="org.a", name="A",
                                   description="", status="active"))
    note = review_state.create_note("project.a", owner_id="org.a", event_id="event.a",
                                    event_type="experiment_run", body="original", created_by="user.a")
    with pytest.raises(review_state.ReviewStateNotFound):
        review_state.update_note("project.a", note.note_id, owner_id="org.a",
                                 base_revision=0, body="foreign", actor_id="admin.a",
                                 can_manage=False)
