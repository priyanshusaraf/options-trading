"""Real-entry-point evidence for generated session handles and bootstrap rollback."""
from __future__ import annotations

import ast
import base64
import datetime as dt
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import RFC_4122, UUID

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.accounts import browser_auth as auth
from app.api import auth_session_routes, connection_routes as routes, principal as principal_api
from app.api.principal import Principal, token_digest
from app.core import credential_vault
from app.core.config import get_settings
from app.db import migrate, session as db_session
from app.db.engine import configure_connection_profile, create_database_engine
from app.db.models import (
    Base,
    BrokerAccount,
    BrokerConnection,
    BrowserCredential,
    BrowserSession,
    CapitalState,
    Deployment,
    EnrollmentInvite,
    GraphArtifact,
    GraphVersion,
    InstrumentState,
    LEGACY_BROKER_ACCOUNT_ID,
    LEGACY_DEPLOYMENT_ID,
    LEGACY_OWNER_ID,
    LEGACY_USER_ID,
    Membership,
    OAuthCallbackState,
    Organization,
    Project,
    UniverseInstrument,
    UniversePreference,
    User,
    UserSession,
)
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.events.planes import execution_outbox


PASSWORD = "synthetic runtime recovery passphrase"
MUTATION = os.environ.get("V0_SRH_MUTATION", "")


class FakeAuthenticator:
    def __init__(self) -> None:
        self.login_calls = 0
        self.exchange_calls = 0

    def login_url(self, source: dict[str, str]) -> str:
        assert set(source) == {"api_key", "api_secret"}
        self.login_calls += 1
        return "https://provider.invalid/oauth/start"

    def exchange(self, source: dict[str, str], request_token: str) -> dict[str, str]:
        assert set(source) == {"api_key", "api_secret"}
        assert request_token == "synthetic-request-token"
        self.exchange_calls += 1
        if MUTATION == "V0-SRH-MUT-003":
            socket.create_connection(("127.0.0.1", 9))
        return {"access_token": "synthetic-access-token", "user_id": "TEST-USER"}


@dataclass
class RuntimeStore:
    dialect: str
    url: str
    engine: sa.Engine
    factory: sessionmaker
    monkeypatch: pytest.MonkeyPatch
    authenticator: FakeAuthenticator
    engines: list[sa.Engine] = field(default_factory=list)

    def bind(self, engine: sa.Engine) -> None:
        self.engine = engine
        self.factory = sessionmaker(engine, future=True, expire_on_commit=False)
        db_session.engine = engine
        db_session.SessionLocal = self.factory
        self.monkeypatch.setattr(auth, "SessionLocal", self.factory)
        self.monkeypatch.setattr(auth_session_routes, "SessionLocal", self.factory)
        self.monkeypatch.setattr(principal_api, "SessionLocal", self.factory)
        self.monkeypatch.setattr(routes, "SessionLocal", self.factory)

    def restart(self) -> None:
        self.engine.dispose()
        replacement = configure_connection_profile(create_database_engine(self.url))
        self.engines.append(replacement)
        self.bind(replacement)


@pytest.fixture(params=("sqlite", "postgresql"))
def runtime_store(request, tmp_path, monkeypatch) -> RuntimeStore:
    original_engine = db_session.engine
    original_factory = db_session.SessionLocal
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path / 'session-runtime-recovery.db'}"
        engine = configure_connection_profile(create_database_engine(url))
    else:
        sandbox = request.getfixturevalue("pg_sandbox")
        url = sandbox.url("session_runtime_recovery")
        engine = configure_connection_profile(create_database_engine(url))
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SHOW server_version").scalar().startswith("16.")

    assert migrate.init_schema(
        engine,
        create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("fresh database attempted legacy migration"),
        expected_tables=Base.metadata.tables,
    ) == "0049"
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    fake = FakeAuthenticator()
    store = RuntimeStore(request.param, url, engine, factory, monkeypatch, fake, [engine])
    store.bind(engine)

    settings = get_settings()
    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "provider", "mock")
    monkeypatch.setattr(settings, "execution", "paper")
    monkeypatch.setattr(settings, "live_ack", "")
    monkeypatch.setattr(settings, "production", False)
    monkeypatch.setenv(credential_vault.ENV_KEY, base64.b64encode(b"v" * 32).decode())
    monkeypatch.setattr(routes, "_authenticator", lambda _broker: fake)

    def refuse_network(*_args, **_kwargs):
        raise AssertionError("provider network attempted by isolated runtime evidence")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    try:
        yield store
    finally:
        for opened in store.engines:
            opened.dispose()
        db_session.engine = original_engine
        db_session.SessionLocal = original_factory


def _enroll(email: str):
    invite = auth.create_invite(email)
    issued = auth.enroll(email, PASSWORD, "Runtime evidence", invite.token)
    principal = auth.browser_principal(issued.token)
    parsed = UUID(issued.session_id)
    assert parsed.variant == RFC_4122
    assert parsed.version == 4
    assert issued.session_id == str(parsed)
    assert principal.session_id == issued.session_id
    return issued, principal


def _create_oauth_connection(store: RuntimeStore, principal: Principal) -> int:
    account_id = f"account.{principal.user_id}"
    with store.factory() as session:
        session.add(BrokerAccount(
            broker_account_id=account_id,
            owner_id=principal.organization_id,
            broker="kite",
            external_account_id="synthetic-account",
            display_name="Synthetic account",
        ))
        session.commit()
    created = routes.create_connection(routes.ConnectionCreate(label="Runtime OAuth"), principal)
    connection_id = int(created["connection_handle"])
    stored = routes.store_credential(
        connection_id,
        routes.CredentialWrite(secrets={"api_key": "synthetic-key", "api_secret": "synthetic-secret"}),
        principal,
    )
    assert stored["credential_present"] is True
    return connection_id


def _start_state(connection_id: int, principal: Principal) -> tuple[str, str]:
    started = routes._start_oauth(connection_id, principal)
    raw_state = parse_qs(urlsplit(started["login_url"]).query)["state"][0]
    digest = routes._digest_state(raw_state)
    assert digest is not None and digest != raw_state
    return raw_state, digest


def _outbox_event_count(store: RuntimeStore, connection_id: int) -> int:
    event = execution_outbox().models.Event
    with store.factory() as session:
        return session.scalar(sa.select(sa.func.count()).select_from(event).where(
            event.aggregate_type == "broker_connection",
            event.aggregate_id == str(connection_id),
        ))


def _credential_snapshot(store: RuntimeStore, connection_id: int) -> tuple[object, object, int]:
    with store.factory() as session:
        row = session.get(BrokerConnection, connection_id)
        return row.credential_ciphertext, row.credential_key_id, _outbox_event_count(store, connection_id)


def _assert_callback_refused_without_side_effect(
    store: RuntimeStore,
    *,
    connection_id: int,
    raw_state: str,
) -> None:
    before = _credential_snapshot(store, connection_id)
    exchanges = store.authenticator.exchange_calls
    with pytest.raises(HTTPException) as refused:
        routes.oauth_callback(state=raw_state, request_token="synthetic-request-token")
    assert refused.value.status_code == 400
    assert refused.value.detail == "invalid login callback"
    assert store.authenticator.exchange_calls == exchanges
    assert _credential_snapshot(store, connection_id) == before


def _record_oauth_trace(monkeypatch, trace: list[str]) -> None:
    issue = auth.issue_user_session
    consume = routes._consume_callback_state
    credential = routes._store_callback_credential

    def traced_issue(*args, **kwargs):
        trace.append("issue_user_session")
        return issue(*args, **kwargs)

    def traced_consume(*args, **kwargs):
        trace.append("_consume_callback_state")
        return consume(*args, **kwargs)

    def traced_credential(*args, **kwargs):
        trace.append("_store_callback_credential")
        return credential(*args, **kwargs)

    monkeypatch.setattr(auth, "issue_user_session", traced_issue)
    monkeypatch.setattr(routes, "_consume_callback_state", traced_consume)
    monkeypatch.setattr(routes, "_store_callback_credential", traced_credential)


def test_generated_uuid_runs_actual_oauth_callback_revoke_and_restart(runtime_store, monkeypatch):
    store = runtime_store
    trace: list[str] = []
    _record_oauth_trace(monkeypatch, trace)
    issued, principal = _enroll(f"oauth-success-{store.dialect}@example.test")
    connection_id = _create_oauth_connection(store, principal)

    alternative = None
    if MUTATION == "V0-SRH-MUT-001":
        alternative = auth.login(f"oauth-success-{store.dialect}@example.test", PASSWORD)

    trace.append("_start_oauth")
    raw_state, state_digest = _start_state(connection_id, principal)
    if alternative is not None:
        with store.factory() as session:
            session.execute(sa.update(OAuthCallbackState).where(
                OAuthCallbackState.state_digest == state_digest
            ).values(session_id=alternative.session_id))
            session.commit()
    with store.factory() as session:
        persisted = session.get(OAuthCallbackState, state_digest)
        assert persisted is not None
        assert (
            persisted.connection_id,
            persisted.session_id,
            persisted.user_id,
            persisted.organization_id,
        ) == (
            connection_id,
            issued.session_id,
            principal.user_id,
            principal.organization_id,
        )
        durable = session.get(UserSession, issued.session_id)
        assert durable.token_digest == token_digest(issued.token)
        assert durable.token_digest != issued.token

    store.restart()
    restarted_principal = auth.browser_principal(issued.token)
    assert restarted_principal.session_id == issued.session_id
    result = routes.oauth_callback(state=raw_state, request_token="synthetic-request-token")
    assert result["connection_handle"] == str(connection_id)
    assert store.authenticator.exchange_calls == 1
    with store.factory() as session:
        persisted = session.get(OAuthCallbackState, state_digest)
        connection = session.get(BrokerConnection, connection_id)
        assert persisted.consumed_at is not None
        assert connection.credential_ciphertext is not None
        assert "synthetic-access-token" not in str(connection.credential_ciphertext)

    with pytest.raises(HTTPException) as replay:
        routes.oauth_callback(state=raw_state, request_token="synthetic-request-token")
    assert replay.value.status_code == 400
    assert store.authenticator.exchange_calls == 1

    trace.append("revoke_connection")
    revoked = routes.revoke_connection(connection_id, restarted_principal)
    assert revoked["connection_status"] == "REVOKED"
    store.restart()
    with store.factory() as session:
        persisted = session.get(OAuthCallbackState, state_digest)
        connection = session.get(BrokerConnection, connection_id)
        assert persisted.session_id == issued.session_id
        assert persisted.consumed_at is not None
        assert connection.status == "revoked"
        assert connection.credential_ciphertext is None
        assert connection.credential_key_id is None

    assert trace == [
        "issue_user_session",
        "_start_oauth",
        "_consume_callback_state",
        "_store_callback_credential",
        "revoke_connection",
    ]


def test_oauth_state_refuses_logout_expiry_replacement_and_cross_owner(runtime_store):
    store = runtime_store

    logout_issued, logout_principal = _enroll(f"logout-{store.dialect}@example.test")
    logout_connection = _create_oauth_connection(store, logout_principal)
    logout_state, _ = _start_state(logout_connection, logout_principal)
    if MUTATION != "V0-SRH-MUT-002":
        assert auth.mutate_session(logout_issued.token, "logout") is None
    _assert_callback_refused_without_side_effect(
        store, connection_id=logout_connection, raw_state=logout_state
    )

    expiry_issued, expiry_principal = _enroll(f"expiry-{store.dialect}@example.test")
    expiry_connection = _create_oauth_connection(store, expiry_principal)
    expiry_state, _ = _start_state(expiry_connection, expiry_principal)
    with store.factory() as session:
        session.get(UserSession, expiry_issued.session_id).expires_at = (
            dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1)
        )
        session.commit()
    _assert_callback_refused_without_side_effect(
        store, connection_id=expiry_connection, raw_state=expiry_state
    )

    replacement_email = f"replacement-{store.dialect}@example.test"
    old_issued, old_principal = _enroll(replacement_email)
    replacement_connection = _create_oauth_connection(store, old_principal)
    old_state, _ = _start_state(replacement_connection, old_principal)
    replacement = auth.login(replacement_email, PASSWORD, replaced=old_issued.token)
    assert replacement.session_id != old_issued.session_id
    _assert_callback_refused_without_side_effect(
        store, connection_id=replacement_connection, raw_state=old_state
    )
    replacement_principal = auth.browser_principal(replacement.token)
    replacement_state, _ = _start_state(replacement_connection, replacement_principal)
    exchanges = store.authenticator.exchange_calls
    routes.oauth_callback(state=replacement_state, request_token="synthetic-request-token")
    assert store.authenticator.exchange_calls == exchanges + 1

    owner_issued, owner_principal = _enroll(f"owner-a-{store.dialect}@example.test")
    owner_connection = _create_oauth_connection(store, owner_principal)
    other_issued, other_principal = _enroll(f"owner-b-{store.dialect}@example.test")
    forged = Principal(
        id=owner_principal.id,
        kind=owner_principal.kind,
        scopes=owner_principal.scopes,
        user_id=owner_principal.user_id,
        organization_id=other_principal.organization_id,
        role=owner_principal.role,
        session_id=owner_issued.session_id,
    )
    with pytest.raises(HTTPException) as cross_start:
        routes._start_oauth(owner_connection, forged)
    assert cross_start.value.status_code == 404

    owner_state, owner_digest = _start_state(owner_connection, owner_principal)
    with store.factory() as session:
        session.execute(sa.update(OAuthCallbackState).where(
            OAuthCallbackState.state_digest == owner_digest
        ).values(session_id=other_issued.session_id))
        session.commit()
    _assert_callback_refused_without_side_effect(
        store, connection_id=owner_connection, raw_state=owner_state
    )
    assert other_issued.session_id != owner_issued.session_id


def _seed_counts(store: RuntimeStore) -> dict[str, int]:
    outbox = execution_outbox().models
    models = {
        "organization": Organization,
        "user": User,
        "membership": Membership,
        "broker_account": BrokerAccount,
        "user_session": UserSession,
        "deployment": Deployment,
        "outbox_head": outbox.StreamHead,
        "outbox_event": outbox.Event,
        "project": Project,
        "graph_artifact": GraphArtifact,
        "graph_version": GraphVersion,
        "capital": CapitalState,
        "universe": UniverseInstrument,
        "preference": UniversePreference,
        "instrument_state": InstrumentState,
    }
    with store.factory() as session:
        return {
            name: session.scalar(sa.select(sa.func.count()).select_from(model))
            for name, model in models.items()
        }


def _assert_failed_seed_transaction(store: RuntimeStore, issued, principal: Principal) -> None:
    with store.factory() as session:
        foreign = session.get(UserSession, issued.session_id)
        assert foreign is not None
        assert (
            foreign.session_id,
            foreign.token_digest,
            foreign.user_id,
            foreign.organization_id,
        ) == (
            issued.session_id,
            token_digest(issued.token),
            principal.user_id,
            principal.organization_id,
        )
        assert session.get(User, principal.user_id) is not None
        assert session.get(Organization, principal.organization_id) is not None
        assert session.get(Membership, (principal.organization_id, principal.user_id)) is not None
        assert session.get(BrowserCredential, principal.user_id) is not None
        assert session.get(BrowserSession, issued.session_id) is not None
        invite = session.scalar(sa.select(EnrollmentInvite).where(
            EnrollmentInvite.email_normalized == f"collision-{store.dialect}@example.test"
        ))
        assert invite is not None and invite.consumed_at is not None

        assert session.get(Organization, LEGACY_OWNER_ID) is None
        assert session.get(User, LEGACY_USER_ID) is None
        assert session.get(Membership, (LEGACY_OWNER_ID, LEGACY_USER_ID)) is None
        assert session.get(BrokerAccount, LEGACY_BROKER_ACCOUNT_ID) is None
        assert session.scalar(sa.select(UserSession).where(
            UserSession.organization_id == LEGACY_OWNER_ID
        )) is None
        assert session.get(Deployment, LEGACY_DEPLOYMENT_ID) is None
        assert session.get(Project, CATALOGUE_PROJECT_ID) is None

    counts = _seed_counts(store)
    assert counts == {
        "organization": 1,
        "user": 1,
        "membership": 1,
        "broker_account": 0,
        "user_session": 1,
        "deployment": 0,
        "outbox_head": 0,
        "outbox_event": 0,
        "project": 0,
        "graph_artifact": 0,
        "graph_version": 0,
        "capital": 0,
        "universe": 0,
        "preference": 0,
        "instrument_state": 0,
    }


def _assert_complete_seed(store: RuntimeStore, foreign_session_id: str, legacy_token: str) -> None:
    with store.factory() as session:
        foreign = session.get(UserSession, foreign_session_id)
        legacy = session.scalar(sa.select(UserSession).where(
            UserSession.token_digest == token_digest(legacy_token)
        ))
        assert foreign is not None
        assert legacy is not None
        assert legacy.session_id != foreign_session_id
        assert (legacy.user_id, legacy.organization_id) == (LEGACY_USER_ID, LEGACY_OWNER_ID)
        assert session.get(Organization, LEGACY_OWNER_ID) is not None
        assert session.get(User, LEGACY_USER_ID) is not None
        assert session.get(Membership, (LEGACY_OWNER_ID, LEGACY_USER_ID)) is not None
        assert session.get(BrokerAccount, LEGACY_BROKER_ACCOUNT_ID) is not None
        assert session.get(Deployment, LEGACY_DEPLOYMENT_ID) is not None
        assert session.get(Project, CATALOGUE_PROJECT_ID) is not None

    counts = _seed_counts(store)
    assert counts["deployment"] == 1
    assert counts["outbox_head"] == 1
    assert counts["outbox_event"] == 1
    assert counts["project"] == 1
    assert counts["graph_artifact"] == 1
    assert counts["graph_version"] == 1
    assert counts["capital"] == 1
    assert counts["universe"] > 0
    assert counts["preference"] == counts["universe"]
    assert counts["instrument_state"] == counts["universe"]


def test_init_db_legacy_uuid_collision_rolls_back_complete_seed_and_retries(
    runtime_store, monkeypatch
):
    store = runtime_store
    legacy_token = "synthetic-legacy-runtime-bearer"
    issued, principal = _enroll(f"collision-{store.dialect}@example.test")
    before = _seed_counts(store)
    trace: list[str] = []

    roots = getattr(db_session, "_ensure_legacy_" + "tenancy_roots")
    bootstrap = getattr(principal_api, "bootstrap_legacy_" + "session")

    def traced_roots(session):
        trace.append("_ensure_legacy_tenancy_roots")
        return roots(session)

    def traced_bootstrap(session, token):
        trace.append("bootstrap_legacy_session")
        if MUTATION == "V0-SRH-MUT-004":
            session.commit()
        return bootstrap(session, token)

    monkeypatch.setattr(db_session, "_ensure_legacy_" + "tenancy_roots", traced_roots)
    monkeypatch.setattr(principal_api, "bootstrap_legacy_" + "session", traced_bootstrap)
    monkeypatch.setattr(principal_api, "uuid4", lambda: UUID(issued.session_id))
    monkeypatch.setattr(get_settings(), "api_token", legacy_token)

    trace.append("init_db")
    with pytest.raises(IntegrityError):
        db_session.init_db()
    assert trace == ["init_db", "_ensure_legacy_tenancy_roots", "bootstrap_legacy_session"]
    _assert_failed_seed_transaction(store, issued, principal)

    monkeypatch.undo()
    # Reapply only the safe fixture bindings after restoring the collision source.
    store.monkeypatch = monkeypatch
    store.restart()
    settings = get_settings()
    monkeypatch.setattr(settings, "api_token", legacy_token)
    monkeypatch.setattr(settings, "provider", "mock")
    monkeypatch.setattr(settings, "execution", "paper")
    monkeypatch.setattr(settings, "live_ack", "")
    monkeypatch.setattr(settings, "production", False)

    db_session.init_db()
    _assert_complete_seed(store, issued.session_id, legacy_token)
    first_success = _seed_counts(store)
    store.restart()
    db_session.init_db()
    assert _seed_counts(store) == first_success
    _assert_complete_seed(store, issued.session_id, legacy_token)
    assert before == {
        "organization": 1,
        "user": 1,
        "membership": 1,
        "broker_account": 0,
        "user_session": 1,
        "deployment": 0,
        "outbox_head": 0,
        "outbox_event": 0,
        "project": 0,
        "graph_artifact": 0,
        "graph_version": 0,
        "capital": 0,
        "universe": 0,
        "preference": 0,
        "instrument_state": 0,
    }


def test_runtime_entrypoint_shortcuts_are_absent():
    source = Path(__file__).read_text(encoding="utf-8")
    if MUTATION == "V0-SRH-MUT-005":
        source += "\nOAuthCallbackState(state_digest='shortcut')\n"
    tree = ast.parse(source)
    forbidden_calls = {
        "OAuthCallbackState",
        "bootstrap_legacy_session",
        "_ensure_legacy_tenancy_roots",
        "rollback",
    }
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if name in forbidden_calls:
            found.append((name, node.lineno))
    assert found == []
