"""Task 6 HTTP resume boundary: durable auth, exact scope and fail-closed cursors."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.api.principal import action_for_request, token_digest
from app.core.config import BootConfigError, Settings, assert_boot_config, get_settings
from app.db.models import BrokerAccount, Membership, Organization, User, UserSession
from app.db.session import SessionLocal, init_db
from app.events.delivery import ResumeCursorCodec
from app.events.outbox import PrincipalScope
from app.events.planes import execution_outbox
from app.main import app


TOKEN = "task6-resume-user-token"
OWNER = "task6-resume-owner"
ACCOUNT = "task6-resume-account"


def _seed_durable_user(monkeypatch) -> TestClient:
    monkeypatch.setattr(get_settings(), "api_token", "auth-is-enabled")
    init_db(reset=True)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    with SessionLocal() as session, session.begin():
        session.add(Organization(organization_id=OWNER, name="Resume owner"))
        session.add(User(user_id="task6-resume-user", email_normalized="resume@example.test",
                         display_name="Resume user"))
        session.flush()
        session.add(Membership(organization_id=OWNER, user_id="task6-resume-user",
                               role="viewer"))
        session.add(UserSession(
            session_id="task6-resume-session", token_digest=token_digest(TOKEN),
            user_id="task6-resume-user", organization_id=OWNER,
            issued_at=now, expires_at=now + dt.timedelta(hours=1)))
        session.add(BrokerAccount(
            owner_id=OWNER, broker_account_id=ACCOUNT, broker="mock",
            external_account_id=ACCOUNT, display_name=ACCOUNT, status="active"))
    app.state.event_cursor_codec = ResumeCursorCodec(b"r" * 32)
    return TestClient(app)


@pytest.mark.parametrize("path", [
    "/api/execution/events", "/api/v1/execution/events",
])
def test_durable_user_can_reach_resume_surface_through_auth_middleware(monkeypatch, path):
    client = _seed_durable_user(monkeypatch)
    response = client.get(path, headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.parametrize("path", [
    "/api/execution/events", "/api/v1/execution/events",
])
@pytest.mark.parametrize("cursor", ["malformed", "foreign"])
def test_supplied_invalid_or_foreign_cursor_is_rejected_before_event_read(
        monkeypatch, path, cursor):
    client = _seed_durable_user(monkeypatch)
    if cursor == "foreign":
        cursor = app.state.event_cursor_codec.encode(
            plane="execution", scope=PrincipalScope("other-owner", ACCOUNT), offset=1)

    class NoReadRepository:
        def read_scoped_after(self, *_args, **_kwargs):
            raise AssertionError("invalid cursor reached scoped outbox read")

    monkeypatch.setattr("app.events.planes.execution_outbox", lambda: NoReadRepository())
    response = client.get(
        path, params={"cursor": cursor},
        headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid resume cursor"}


def test_resume_route_has_one_closed_read_capability():
    assert action_for_request("GET", "/api/execution/events") == "read:execution"


@pytest.mark.parametrize("api_token", ["", "legacy-token"])
def test_production_requires_a_shared_resume_cursor_secret(api_token):
    with pytest.raises(BootConfigError, match="EVENT_CURSOR_SECRET"):
        assert_boot_config(
            Settings(service_role="production", auth_disabled=False,
                     api_token=api_token, event_cursor_secret=""),
            env_file=".env", under_test=False, warn=lambda _message: None)
    assert_boot_config(
        Settings(service_role="production", auth_disabled=False, api_token="",
                 event_cursor_secret="s" * 32),
        env_file=".env", under_test=False, warn=lambda _message: None)


def test_shared_cursor_secret_survives_restart_and_foreign_secret_refuses():
    first = ResumeCursorCodec(b"shared-replica-resume-secret-12345")
    restarted = ResumeCursorCodec(b"shared-replica-resume-secret-12345")
    foreign = ResumeCursorCodec(b"different-replica-secret-value-123")
    scope = PrincipalScope(OWNER, ACCOUNT)
    cursor = first.encode(plane="execution", scope=scope, offset=41)
    assert restarted.decode(cursor, plane="execution", scope=scope) == 41
    assert foreign.decode(cursor, plane="execution", scope=scope) is None


def test_fully_pruned_resume_advances_the_returned_cursor(monkeypatch):
    client = _seed_durable_user(monkeypatch)
    repo = execution_outbox()
    old = dt.datetime(2026, 7, 1)
    now = dt.datetime(2026, 8, 13)
    with SessionLocal() as session, repo.writer(session):
        identity = repo.append(
            session, classification="private", owner_id=OWNER,
            broker_account_id=ACCOUNT, aggregate_type="lease",
            aggregate_id=ACCOUNT, event_type="execution.lease.changed",
            schema_version=1, payload={"projection": "execution_lease", "version": 1},
            producer_key="resume-pruned:1")
        session.get(repo.models.Event, identity.plane_offset).created_at = old
    with SessionLocal() as session, session.begin():
        assert repo.cleanup(
            session, older_than=now - dt.timedelta(days=7), now=now,
            abandoned_after_seconds=60, limit=100) == 1
    initial = app.state.event_cursor_codec.encode(
        plane="execution", scope=PrincipalScope(OWNER, ACCOUNT), offset=0)
    response = client.get(
        "/api/execution/events", params={"cursor": initial},
        headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["resync_required"] is True
    assert app.state.event_cursor_codec.decode(
        response.json()["cursor"], plane="execution",
        scope=PrincipalScope(OWNER, ACCOUNT)) == identity.plane_offset


def test_paginated_resume_cursor_never_skips_unreturned_events(monkeypatch):
    client = _seed_durable_user(monkeypatch)
    repo = execution_outbox()
    identities = []
    with SessionLocal() as session, repo.writer(session):
        for index in (1, 2):
            identities.append(repo.append(
                session, classification="private", owner_id=OWNER,
                broker_account_id=ACCOUNT, aggregate_type="lease",
                aggregate_id=f"lease-{index}", event_type="execution.lease.changed",
                schema_version=1,
                payload={"projection": "execution_lease", "version": index},
                producer_key=f"resume-page:{index}"))
    response = client.get(
        "/api/execution/events", params={"limit": 1},
        headers={"Authorization": f"Bearer {TOKEN}"})
    assert [event["offset"] for event in response.json()["events"]] == [
        identities[0].plane_offset]
    assert app.state.event_cursor_codec.decode(
        response.json()["cursor"], plane="execution",
        scope=PrincipalScope(OWNER, ACCOUNT)) == identities[0].plane_offset
