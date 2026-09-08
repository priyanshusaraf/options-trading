"""Direct-V1 fake-only data-provider onboarding contract."""
from __future__ import annotations

import base64
import concurrent.futures
import datetime as dt
import json
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.principal import Principal, get_principal, token_digest
from app.core import credential_vault
from app.core import deployments
from app.core.config import get_settings
from app.core.instruments import get_instrument
from app.db.models import (
    BrokerAccount,
    BrokerConnection,
    AccountExecutionLease,
    CapitalState,
    Deployment,
    ExecutionIntent,
    Membership,
    OAuthCallbackState,
    OrderJournal,
    Organization,
    Position,
    User,
    UserSession,
)
from app.db.session import SessionLocal, init_db
from app.main import app
from app.providers import data_connection_service
from app.providers.connection_store import (
    DATA_CAPABILITIES,
    DATA_ONLY_ACCOUNT_NAME,
    DATA_ONLY_ACCOUNT_STATUS,
    DATA_ONLY_EXTERNAL_ACCOUNT_ID,
    DataConnectionUnavailable,
    DataOperationUnavailable,
    OwnedConnectionStore,
)
from app.api.execution_access import durable_execution_account
from app.engine.broker import PaperBroker
from app.execution.leases import LeaseRepository, LeaseUnavailable


OWNER = "provider-owner-a"
USER = "provider-user-a"
SESSION = "provider-session-a"
KEY = base64.b64encode(b"p" * 32).decode()


class FakeAuthenticator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.login_calls = 0
        self.exchange_calls = 0

    def login_url(self, stable_keys: dict[str, str]) -> str:
        self.login_calls += 1
        assert stable_keys == {"api_key": "app-key-a", "api_secret": "app-secret-a"}
        return "https://fake-provider.invalid/login"

    def exchange(self, stable_keys: dict[str, str], request_token: str) -> dict[str, str]:
        self.exchange_calls += 1
        assert stable_keys == {"api_key": "app-key-a", "api_secret": "app-secret-a"}
        assert request_token == "synthetic-request-token"
        if self.fail:
            raise RuntimeError("synthetic failure with no secret")
        return {"access_token": "synthetic-access-token"}


class BlockingFakeAuthenticator(FakeAuthenticator):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def exchange(self, stable_keys: dict[str, str], request_token: str) -> dict[str, str]:
        self.entered.set()
        assert self.release.wait(timeout=5)
        return super().exchange(stable_keys, request_token)


def _principal(owner: str = OWNER, user: str = USER, session_id: str = SESSION) -> Principal:
    return Principal(
        id=user, kind="user", scopes=frozenset({"*"}), user_id=user,
        organization_id=owner, role="owner", session_id=session_id,
    )


def _seed_identity(owner: str = OWNER, user: str = USER,
                   session_id: str = SESSION, *, with_account: bool = True) -> None:
    now = dt.datetime.now()
    with SessionLocal() as session:
        if session.get(Organization, owner) is None:
            session.add(Organization(organization_id=owner, name=owner))
        if session.get(User, user) is None:
            session.add(User(
                user_id=user, email_normalized=f"{user}@example.test", display_name=user))
        session.flush()
        session.add(Membership(
            organization_id=owner, user_id=user, role="owner", status="active"))
        session.add(UserSession(
            session_id=session_id, token_digest=token_digest(f"token-{session_id}"),
            user_id=user, organization_id=owner, issued_at=now,
            expires_at=now + dt.timedelta(hours=2)))
        if with_account and session.get(BrokerAccount, f"account-{owner}") is None:
            session.add(BrokerAccount(
                broker_account_id=f"account-{owner}", owner_id=owner, broker="kite",
                external_account_id=f"external-{owner}", display_name="Synthetic account"))
        session.commit()


@pytest.fixture()
def direct_client(monkeypatch):
    init_db(reset=True)
    _seed_identity()
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    fake = FakeAuthenticator()
    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[data_connection_service.production_data_authenticator] = lambda: fake
    try:
        yield TestClient(app), fake
    finally:
        app.dependency_overrides.clear()


def _setup_keys(client: TestClient) -> None:
    created = client.post("/api/v1/data-connections", json={})
    assert created.status_code == 201, created.text
    stored = client.post("/api/v1/data-connections/app-keys", json={
        "api_key": "app-key-a", "api_secret": "app-secret-a",
    })
    assert stored.status_code == 200, stored.text


def _setup_foreign_owner(client: TestClient) -> tuple[str, str]:
    owner, user, session_id = "provider-owner-b", "provider-user-b", "provider-session-b"
    _seed_identity(owner, user, session_id)
    app.dependency_overrides[get_principal] = lambda: _principal(owner, user, session_id)
    _setup_keys(client)
    with SessionLocal() as session:
        ciphertext = session.scalar(select(BrokerConnection.credential_ciphertext).where(
            BrokerConnection.owner_id == owner))
    assert ciphertext
    return owner, ciphertext


def _seed_foreign_owner_row() -> tuple[str, str]:
    owner, user, session_id = "provider-owner-b", "provider-user-b", "provider-session-b"
    _seed_identity(owner, user, session_id)
    ciphertext, key_id = credential_vault.seal({
        "api_key": "foreign-key", "api_secret": "foreign-secret"})
    with SessionLocal() as session:
        session.add(BrokerConnection(
            owner_id=owner,
            broker_account_id=f"account-{owner}",
            broker="kite",
            scope="strategy-os-v0:data:1",
            label="",
            capabilities_json=json.dumps(sorted(DATA_CAPABILITIES)),
            credential_ciphertext=ciphertext,
            credential_key_id=key_id,
            status="active",
            created_at=dt.datetime.now(),
            updated_at=dt.datetime.now(),
        ))
        session.commit()
    return owner, ciphertext


def _initiate(client: TestClient) -> str:
    response = client.post("/api/v1/data-connections/oauth/initiate", json={})
    assert response.status_code == 200, response.text
    return parse_qs(urlsplit(response.json()["login_url"]).query)["state"][0]


def _provider_callback_state(login_url: str) -> str:
    query = parse_qs(urlsplit(login_url).query)
    assert "state" not in query
    redirect_params = parse_qs(query["redirect_params"][0])
    assert set(redirect_params) == {"state"}
    return redirect_params["state"][0]


def _assert_closed(status: dict, expected: str) -> None:
    assert status["schema"] == "strategy-os-data-connection-status/1"
    assert status["state"] == expected
    assert status["provider"] == "ZERODHA" and status["role"] == "DATA"
    assert status["ready"] is False
    assert status["credential_expiry"] == "UNVERIFIED"
    assert status["rate_quota"] == "UNVERIFIED"
    assert set(status) == {
        "schema", "state", "provider", "role", "ready",
        "credential_expiry", "rate_quota", "actions",
    }


def test_only_seven_direct_v1_routes_exist_without_unversioned_mirror():
    from app.api import data_connection_routes

    actual = {
        (method, route.path)
        for route in data_connection_routes.router.routes
        for method in (getattr(route, "methods", set()) or set())
    }
    assert actual == {
        ("GET", "/api/v1/data-connections/status"),
        ("GET", "/api/v1/data-connections/instruments"),
        ("POST", "/api/v1/data-connections"),
        ("POST", "/api/v1/data-connections/app-keys"),
        ("POST", "/api/v1/data-connections/app-keys/rotate"),
        ("POST", "/api/v1/data-connections/oauth/initiate"),
        ("GET", "/api/v1/data-connections/oauth/callback"),
        ("DELETE", "/api/v1/data-connections"),
    }
    assert not any(path.startswith("/api/data-connections") for _, path in actual)


def test_new_owner_bootstraps_one_data_only_account_without_execution_authority(
        monkeypatch):
    init_db(reset=True)
    _seed_identity(with_account=False)
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    app.dependency_overrides[get_principal] = _principal
    try:
        client = TestClient(app)
        before = client.get("/api/v1/data-connections/status")
        assert before.status_code == 200
        _assert_closed(before.json(), "CONNECTION_REQUIRED")
        with SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(BrokerAccount).where(
                BrokerAccount.owner_id == OWNER)) == 0

        created = client.post("/api/v1/data-connections", json={})
        assert created.status_code == 201, created.text
        _assert_closed(created.json(), "APP_KEYS_REQUIRED")
        assert client.post("/api/v1/data-connections", json={}).status_code == 409

        with SessionLocal() as session:
            accounts = session.scalars(select(BrokerAccount).where(
                BrokerAccount.owner_id == OWNER)).all()
            connections = session.scalars(select(BrokerConnection).where(
                BrokerConnection.owner_id == OWNER)).all()
            assert len(accounts) == 1 and len(connections) == 1
            account, connection = accounts[0], connections[0]
            assert account.broker_account_id.startswith("zerodha-data-")
            assert account.broker == "kite"
            assert account.external_account_id == DATA_ONLY_EXTERNAL_ACCOUNT_ID
            assert account.display_name == DATA_ONLY_ACCOUNT_NAME
            assert account.status == DATA_ONLY_ACCOUNT_STATUS
            assert connection.broker_account_id == account.broker_account_id
            assert connection.scope == "strategy-os-v0:data:1"
            assert json.loads(connection.capabilities_json) == sorted(DATA_CAPABILITIES)
            assert connection.credential_ciphertext is None
            for model in (AccountExecutionLease, Deployment, ExecutionIntent,
                          CapitalState, Position, OrderJournal):
                assert session.scalar(select(func.count()).select_from(model).where(
                    model.broker_account_id == account.broker_account_id)) == 0
            data_account_id = account.broker_account_id
            with pytest.raises(ValueError, match="not available"):
                OwnedConnectionStore(
                    session, owner_id=OWNER, broker_account_id=data_account_id)
            data_store = OwnedConnectionStore.for_data_role(
                session, owner_id=OWNER, broker_account_id=data_account_id)
            with pytest.raises(DataConnectionUnavailable, match="no execution"):
                data_store.live_connection(connection.id)
            with pytest.raises(DataConnectionUnavailable, match="general credential"):
                data_store.store_credential(connection.id, {"access_token": "synthetic"})
            with pytest.raises(DataConnectionUnavailable, match="general connection"):
                data_store.create(broker="kite", scope="execution")

        monkeypatch.setattr(get_settings(), "release_profile", "standard")
        with pytest.raises(HTTPException) as refused:
            durable_execution_account(_principal(), data_account_id)
        assert refused.value.status_code == 404
        with pytest.raises(LeaseUnavailable, match="unavailable"):
            LeaseRepository(SessionLocal).claim(
                owner_id=OWNER, broker_account_id=data_account_id,
                cell_id="data-cell", worker_id="data-worker")
        with SessionLocal() as session:
            assert deployments._account_belongs_to_owner(
                session, owner_id=OWNER,
                broker_account_id=data_account_id) is False
        with pytest.raises(ValueError, match="not available"):
            PaperBroker(object(), owner_id=OWNER, broker_account_id=data_account_id)

        control_id = "execution-control-account"
        with SessionLocal() as session:
            session.add(BrokerAccount(
                broker_account_id=control_id, owner_id=OWNER, broker="mock",
                external_account_id="synthetic-execution-control",
                display_name="Execution control", status="active"))
            session.commit()
        assert durable_execution_account(_principal(), control_id) == control_id
        control_token = LeaseRepository(SessionLocal).claim(
            owner_id=OWNER, broker_account_id=control_id,
            cell_id="control-cell", worker_id="control-worker")
        assert control_token.broker_account_id == control_id
        with SessionLocal() as session:
            assert deployments._account_belongs_to_owner(
                session, owner_id=OWNER, broker_account_id=control_id) is True
        control_broker = PaperBroker(
            object(), owner_id=OWNER, broker_account_id=control_id)
        control_broker.s.close()
        with SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(AccountExecutionLease).where(
                AccountExecutionLease.broker_account_id == data_account_id)) == 0
            assert session.scalar(select(func.count()).select_from(CapitalState).where(
                CapitalState.broker_account_id == data_account_id)) == 0
    finally:
        app.dependency_overrides.clear()


def test_data_only_account_bootstrap_is_tenant_distinct_and_ambiguous_state_closes(
        monkeypatch):
    init_db(reset=True)
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    owner_b, user_b, session_b = "provider-owner-b", "provider-user-b", "provider-session-b"
    _seed_identity(with_account=False)
    _seed_identity(owner_b, user_b, session_b, with_account=False)
    client = TestClient(app)
    try:
        app.dependency_overrides[get_principal] = _principal
        assert client.post("/api/v1/data-connections", json={}).status_code == 201
        app.dependency_overrides[get_principal] = lambda: _principal(owner_b, user_b, session_b)
        assert client.get("/api/v1/data-connections/status").json()["state"] == "CONNECTION_REQUIRED"
        assert client.post("/api/v1/data-connections", json={}).status_code == 201
        with SessionLocal() as session:
            rows = session.scalars(select(BrokerAccount).where(
                BrokerAccount.owner_id.in_([OWNER, owner_b])).order_by(BrokerAccount.owner_id)).all()
            assert len(rows) == 2
            assert rows[0].owner_id != rows[1].owner_id
            assert rows[0].broker_account_id != rows[1].broker_account_id
            assert session.scalar(select(func.count()).select_from(BrokerConnection).where(
                BrokerConnection.owner_id == OWNER)) == 1
            assert session.scalar(select(func.count()).select_from(BrokerConnection).where(
                BrokerConnection.owner_id == owner_b)) == 1

        app.dependency_overrides[get_principal] = _principal
        _assert_closed(client.get("/api/v1/data-connections/status").json(), "APP_KEYS_REQUIRED")

        ambiguous_owner = "provider-owner-ambiguous"
        ambiguous_user = "provider-user-ambiguous"
        ambiguous_session = "provider-session-ambiguous"
        _seed_identity(ambiguous_owner, ambiguous_user, ambiguous_session, with_account=False)
        with SessionLocal() as session:
            for suffix, status in (("disabled", "disabled"), ("active", "active")):
                session.add(BrokerAccount(
                    broker_account_id=f"account-{ambiguous_owner}-{suffix}",
                    owner_id=ambiguous_owner, broker="kite",
                    external_account_id=f"external-{suffix}",
                    display_name=f"Synthetic {suffix}", status=status))
            session.commit()
        app.dependency_overrides[get_principal] = lambda: _principal(
            ambiguous_owner, ambiguous_user, ambiguous_session)
        _assert_closed(client.get("/api/v1/data-connections/status").json(), "UNAVAILABLE")
        assert client.post("/api/v1/data-connections", json={}).status_code == 409
        with SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(BrokerConnection).where(
                BrokerConnection.owner_id == ambiguous_owner)) == 0
    finally:
        app.dependency_overrides.clear()


def test_unrecognized_disabled_account_does_not_become_a_data_anchor(monkeypatch):
    init_db(reset=True)
    _seed_identity(with_account=False)
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    with SessionLocal() as session:
        session.add(BrokerAccount(
            broker_account_id="disabled-unrecognized", owner_id=OWNER, broker="kite",
            external_account_id="disabled-execution-account",
            display_name="Disabled account", status="disabled"))
        session.commit()
    app.dependency_overrides[get_principal] = _principal
    try:
        client = TestClient(app)
        _assert_closed(client.get("/api/v1/data-connections/status").json(), "UNAVAILABLE")
        assert client.post("/api/v1/data-connections", json={}).status_code == 409
        with SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(BrokerConnection).where(
                BrokerConnection.owner_id == OWNER)) == 0
    finally:
        app.dependency_overrides.clear()


def test_foreign_derived_id_collision_is_generic_and_preserves_foreign_row(monkeypatch):
    init_db(reset=True)
    _seed_identity(with_account=False)
    foreign_owner, foreign_user, foreign_session = (
        "provider-owner-foreign", "provider-user-foreign", "provider-session-foreign")
    _seed_identity(foreign_owner, foreign_user, foreign_session, with_account=False)
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    occupied_id = data_connection_service._data_only_account_id(OWNER)
    with SessionLocal() as session:
        session.add(BrokerAccount(
            broker_account_id=occupied_id, owner_id=foreign_owner, broker="kite",
            external_account_id="foreign-existing-account",
            display_name="Foreign existing account", status="active"))
        session.commit()
    app.dependency_overrides[get_principal] = _principal
    try:
        client = TestClient(app)
        _assert_closed(client.get("/api/v1/data-connections/status").json(), "CONNECTION_REQUIRED")
        response = client.post("/api/v1/data-connections", json={})
        assert response.status_code == 409
        assert response.json() == {"detail": "data connection unavailable"}
        assert foreign_owner not in response.text and occupied_id not in response.text
        with SessionLocal() as session:
            occupied = session.get(BrokerAccount, occupied_id)
            assert occupied.owner_id == foreign_owner
            assert occupied.external_account_id == "foreign-existing-account"
            assert session.scalar(select(func.count()).select_from(BrokerAccount).where(
                BrokerAccount.owner_id == OWNER)) == 0
            assert session.scalar(select(func.count()).select_from(BrokerConnection)) == 0
    finally:
        app.dependency_overrides.clear()


def test_downstream_connection_failure_rolls_back_new_data_account(monkeypatch):
    init_db(reset=True)
    _seed_identity(with_account=False)
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    app.dependency_overrides[get_principal] = _principal
    monkeypatch.setattr(
        OwnedConnectionStore, "create_data_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            DataConnectionUnavailable("synthetic downstream refusal")),
    )
    try:
        client = TestClient(app)
        response = client.post("/api/v1/data-connections", json={})
        assert response.status_code == 409
        assert response.json() == {"detail": "data connection unavailable"}
        with SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(BrokerAccount).where(
                BrokerAccount.owner_id == OWNER)) == 0
            assert session.scalar(select(func.count()).select_from(BrokerConnection).where(
                BrokerConnection.owner_id == OWNER)) == 0
    finally:
        app.dependency_overrides.clear()


def test_concurrent_first_create_leaves_one_data_account_and_connection(monkeypatch):
    init_db(reset=True)
    _seed_identity(with_account=False)
    monkeypatch.setenv(credential_vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(get_settings(), "release_service_role", "api")
    app.dependency_overrides[get_principal] = _principal
    barrier = threading.Barrier(2)

    def create_one():
        barrier.wait(timeout=5)
        return TestClient(app).post("/api/v1/data-connections", json={})

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _index: create_one(), range(2)))
        assert sorted(response.status_code for response in responses) == [201, 409]
        assert all("owner" not in response.text.lower() for response in responses)
        with SessionLocal() as session:
            accounts = session.scalars(select(BrokerAccount).where(
                BrokerAccount.owner_id == OWNER)).all()
            connections = session.scalars(select(BrokerConnection).where(
                BrokerConnection.owner_id == OWNER)).all()
            assert len(accounts) == 1 and len(connections) == 1
            assert accounts[0].status == DATA_ONLY_ACCOUNT_STATUS
            assert connections[0].broker_account_id == accounts[0].broker_account_id
    finally:
        app.dependency_overrides.clear()


def test_complete_fake_lifecycle_preserves_stable_keys_and_never_becomes_ready(direct_client):
    client, fake = direct_client
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "CONNECTION_REQUIRED")
    _assert_closed(client.post("/api/v1/data-connections", json={}).json(), "APP_KEYS_REQUIRED")
    assert client.post("/api/v1/data-connections", json={}).status_code == 409
    rejected_identity = client.post(
        "/api/v1/data-connections", json={"owner_id": "other"})
    assert rejected_identity.status_code == 422
    assert rejected_identity.headers["cache-control"] == "no-store"

    initial = client.post("/api/v1/data-connections/app-keys", json={
        "api_key": "app-key-a", "api_secret": "app-secret-a",
    })
    _assert_closed(initial.json(), "REAUTH_REQUIRED")
    assert "app-key-a" not in initial.text and "app-secret-a" not in initial.text
    assert client.post("/api/v1/data-connections/app-keys", json={
        "api_key": "again", "api_secret": "again",
    }).status_code == 409

    state = _initiate(client)
    with SessionLocal() as session:
        callback = session.scalar(select(OAuthCallbackState))
        assert callback is not None
        assert callback.expires_at - callback.created_at == dt.timedelta(minutes=10)
        assert callback.consumed_at is None and callback.credential_stored_at is None
    completed = client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    )
    assert completed.status_code == 303
    assert completed.headers["location"] == "/account/provider"
    assert "synthetic" not in completed.text and "synthetic" not in completed.headers["location"]
    _assert_closed(
        client.get("/api/v1/data-connections/status").json(),
        "SESSION_PRESENT_UNVERIFIED",
    )
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        callback = session.scalar(select(OAuthCallbackState))
        assert callback.credential_stored_at == row.last_authenticated_at
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "app-key-a", "api_secret": "app-secret-a",
            "access_token": "synthetic-access-token",
        }

    rotated = client.post("/api/v1/data-connections/app-keys/rotate", json={
        "api_key": "rotated-key", "api_secret": "rotated-secret",
    })
    _assert_closed(rotated.json(), "REAUTH_REQUIRED")
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        callback = session.scalar(select(OAuthCallbackState))
        assert row.last_authenticated_at is None
        assert callback.revoked_at is not None
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "rotated-key", "api_secret": "rotated-secret"}

    revoked = client.delete("/api/v1/data-connections")
    _assert_closed(revoked.json(), "REVOKED")
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        assert row.status == "revoked" and row.credential_ciphertext is None
        assert row.credential_key_id is None
    assert fake.login_calls == 1 and fake.exchange_calls == 1


def test_consumed_but_failed_callback_stays_reauth_required(direct_client):
    client, _ = direct_client
    failing = FakeAuthenticator(fail=True)
    app.dependency_overrides[data_connection_service.production_data_authenticator] = lambda: failing
    _setup_keys(client)
    state = _initiate(client)
    response = client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
    )
    assert response.status_code == 400
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    with SessionLocal() as session:
        callback = session.scalar(select(OAuthCallbackState))
        row = session.scalar(select(BrokerConnection))
        assert callback.consumed_at is not None
        assert callback.credential_stored_at is None
        assert row.last_authenticated_at is None
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "app-key-a", "api_secret": "app-secret-a"}


def test_production_authenticator_builds_provider_login_without_network_or_dependency_override(
        direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    app.dependency_overrides.pop(data_connection_service.production_data_authenticator)
    touched = []
    monkeypatch.setattr(
        "app.providers.zerodha_data_runtime.ZerodhaDataKite._request",
        lambda *_args, **_kwargs: touched.append(True),
    )
    response = client.post("/api/v1/data-connections/oauth/initiate", json={})
    assert response.status_code == 200
    login_url = response.json()["login_url"]
    assert login_url.startswith(
        "https://kite.zerodha.com/connect/login?api_key=app-key-a"
    )
    raw_state = _provider_callback_state(login_url)
    assert len(raw_state) >= 32
    assert touched == []
    with SessionLocal() as session:
        state = session.scalar(select(OAuthCallbackState))
        assert state is not None and len(state.state_digest) == 64


def test_production_callback_keeps_provider_account_fields_out_of_the_vault(
        direct_client, monkeypatch):
    from app.providers.broker_auth import KiteAuthenticator

    class OfflineKite:
        def login_url(self):
            return "https://kite.zerodha.com/connect/login?api_key=app-key-a"

        def generate_session(self, request_token, api_secret):
            assert request_token == "synthetic-request-token"
            assert api_secret == "app-secret-a"
            return {
                "access_token": "production-shaped-token",
                "public_token": "must-not-persist",
                "user_id": "must-not-persist",
                "email": "must-not-persist@example.test",
                "login_time": dt.datetime(2026, 9, 4, 9, 0),
            }

    client, _ = direct_client
    _setup_keys(client)
    app.dependency_overrides.pop(data_connection_service.production_data_authenticator)
    monkeypatch.setattr(KiteAuthenticator, "_client", lambda _self, _key: OfflineKite())
    initiated = client.post("/api/v1/data-connections/oauth/initiate", json={})
    assert initiated.status_code == 200
    state = _provider_callback_state(initiated.json()["login_url"])
    callback = client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert "must-not-persist" not in callback.text
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "app-key-a",
            "api_secret": "app-secret-a",
            "access_token": "production-shaped-token",
        }


def test_provider_redirect_params_passthrough_completes_once_and_keeps_owner_session_binding(
        direct_client, monkeypatch):
    from app.providers.broker_auth import KiteAuthenticator

    class OfflineKite:
        def login_url(self):
            return "https://kite.zerodha.com/connect/login?api_key=app-key-a&v=3"

        def generate_session(self, request_token, api_secret):
            assert request_token == "provider-passthrough-token"
            assert api_secret == "app-secret-a"
            return {"access_token": "provider-passthrough-access"}

    client, _ = direct_client
    _setup_keys(client)
    app.dependency_overrides.pop(data_connection_service.production_data_authenticator)
    monkeypatch.setattr(KiteAuthenticator, "_client", lambda _self, _key: OfflineKite())
    initiated = client.post("/api/v1/data-connections/oauth/initiate", json={})
    assert initiated.status_code == 200
    state = _provider_callback_state(initiated.json()["login_url"])
    callback_params = {
        "request_token": "provider-passthrough-token",
        "status": "success",
        "action": "login",
        "state": state,
    }
    first = client.get(
        "/api/v1/data-connections/oauth/callback",
        params=callback_params,
        follow_redirects=False,
    )
    assert first.status_code == 303
    duplicate = client.get(
        "/api/v1/data-connections/oauth/callback",
        params=callback_params,
        follow_redirects=False,
    )
    assert duplicate.status_code == 400
    _assert_closed(
        client.get("/api/v1/data-connections/status").json(),
        "SESSION_PRESENT_UNVERIFIED",
    )


def test_completion_is_current_session_bound_and_other_owner_sees_only_own_state(direct_client):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    assert client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    ).status_code == 303

    _seed_identity(OWNER, "provider-user-b", "provider-session-b")
    app.dependency_overrides[get_principal] = lambda: _principal(
        OWNER, "provider-user-b", "provider-session-b")
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")

    _seed_identity("provider-owner-b", "provider-user-c", "provider-session-c")
    app.dependency_overrides[get_principal] = lambda: _principal(
        "provider-owner-b", "provider-user-c", "provider-session-c")
    foreign = client.get("/api/v1/data-connections/status").json()
    _assert_closed(foreign, "CONNECTION_REQUIRED")
    assert client.post("/api/v1/data-connections", json={"connection_id": 1}).status_code == 422
    with SessionLocal() as session:
        assert session.scalar(select(BrokerConnection).where(
            BrokerConnection.owner_id == OWNER)).credential_ciphertext is not None


def test_foreign_owner_account_cannot_change_same_owner_status(direct_client):
    client, _ = direct_client
    _setup_keys(client)
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    foreign_owner, foreign_ciphertext = _seed_foreign_owner_row()
    with SessionLocal() as session:
        assert session.scalar(select(BrokerConnection.id).where(
            BrokerConnection.owner_id == OWNER)) is not None
        assert session.scalar(select(BrokerConnection.id).where(
            BrokerConnection.owner_id == foreign_owner)) is not None
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    with SessionLocal() as session:
        assert session.scalar(select(BrokerConnection.credential_ciphertext).where(
            BrokerConnection.owner_id == foreign_owner)) == foreign_ciphertext


@pytest.mark.parametrize("withdrawal", [
    "membership_removed", "session_expired", "session_revoked", "user_disabled",
    "organization_disabled", "broker_account_disabled",
])
def test_direct_service_revalidates_every_authority_and_callback_writes_nothing(
        direct_client, withdrawal):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    foreign_owner, foreign_ciphertext = _setup_foreign_owner(client)
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    app.dependency_overrides[get_principal] = _principal
    with SessionLocal() as session:
        if withdrawal == "membership_removed":
            session.get(Membership, (OWNER, USER)).status = "revoked"
        elif withdrawal == "session_expired":
            session.get(UserSession, SESSION).expires_at = dt.datetime(2000, 1, 1)
        elif withdrawal == "session_revoked":
            session.get(UserSession, SESSION).revoked_at = dt.datetime.now()
        elif withdrawal == "user_disabled":
            session.get(User, USER).status = "disabled"
        elif withdrawal == "organization_disabled":
            session.get(Organization, OWNER).status = "disabled"
        else:
            session.get(BrokerAccount, f"account-{OWNER}").status = "disabled"
        session.commit()
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "UNAVAILABLE")
    callback = client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    )
    assert callback.status_code == 400
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        receipt = session.scalar(select(OAuthCallbackState).where(
            OAuthCallbackState.organization_id == OWNER))
        foreign = session.scalar(select(BrokerConnection).where(
            BrokerConnection.owner_id == foreign_owner))
        assert row.last_authenticated_at is None
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "app-key-a", "api_secret": "app-secret-a"}
        assert receipt.credential_stored_at is None
        assert foreign.credential_ciphertext == foreign_ciphertext


@pytest.mark.parametrize(("field", "value"), [
    ("broker", "mock"),
    ("scope", "strategy-os-v0:data-forged:1"),
    ("capabilities_json", "[]"),
])
def test_direct_service_rejects_malformed_data_identity_without_cross_owner_effect(
        direct_client, field, value):
    client, _ = direct_client
    _setup_keys(client)
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    foreign_owner, foreign_ciphertext = _setup_foreign_owner(client)
    app.dependency_overrides[get_principal] = _principal
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        setattr(row, field, value)
        session.commit()
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "UNAVAILABLE")
    assert client.post("/api/v1/data-connections/oauth/initiate", json={}).status_code == 409
    with SessionLocal() as session:
        foreign = session.scalar(select(BrokerConnection).where(
            BrokerConnection.owner_id == foreign_owner))
        assert foreign.credential_ciphertext == foreign_ciphertext


def test_duplicate_direct_callback_is_refused_without_replacing_the_first_completion(
        direct_client):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    first = client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    )
    assert first.status_code == 303
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        first_ciphertext = row.credential_ciphertext
        first_authenticated = row.last_authenticated_at
    duplicate = client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    )
    assert duplicate.status_code == 400
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        assert row.credential_ciphertext == first_ciphertext
        assert row.last_authenticated_at == first_authenticated


def test_callback_event_failure_rolls_back_credential_and_completion_without_cross_owner_effect(
        direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    foreign_owner, foreign_ciphertext = _setup_foreign_owner(client)
    app.dependency_overrides[get_principal] = _principal
    monkeypatch.setattr(
        "app.events.producers.append_execution_change",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic callback transaction failure")),
    )
    with pytest.raises(RuntimeError, match="synthetic callback transaction failure"):
        client.get(
            "/api/v1/data-connections/oauth/callback",
            params={"state": state, "request_token": "synthetic-request-token"},
            follow_redirects=False,
        )
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        receipt = session.scalar(select(OAuthCallbackState).where(
            OAuthCallbackState.organization_id == OWNER))
        foreign = session.scalar(select(BrokerConnection).where(
            BrokerConnection.owner_id == foreign_owner))
        assert row.last_authenticated_at is None
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "app-key-a", "api_secret": "app-secret-a"}
        assert receipt.consumed_at is not None and receipt.credential_stored_at is None
        assert foreign.credential_ciphertext == foreign_ciphertext


def test_malformed_or_wrong_vault_state_is_unavailable_without_secret_echo(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    monkeypatch.setenv(credential_vault.ENV_KEY, base64.b64encode(b"q" * 32).decode())
    response = client.get("/api/v1/data-connections/status")
    _assert_closed(response.json(), "UNAVAILABLE")
    assert "app-key-a" not in response.text and "ciphertext" not in response.text


def test_event_failure_rolls_back_app_keys_without_partial_success(direct_client, monkeypatch):
    client, _ = direct_client
    assert client.post("/api/v1/data-connections", json={}).status_code == 201
    monkeypatch.setattr(
        "app.events.producers.append_execution_change",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic event failure")),
    )
    with pytest.raises(RuntimeError, match="synthetic event failure"):
        client.post("/api/v1/data-connections/app-keys", json={
            "api_key": "app-key-a", "api_secret": "app-secret-a",
        })
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        assert row.credential_ciphertext is None and row.last_authenticated_at is None


def test_concurrent_initiations_leave_one_live_bounded_state(direct_client):
    client, _ = direct_client
    _setup_keys(client)

    def start_one():
        return client.post("/api/v1/data-connections/oauth/initiate", json={})

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _index: start_one(), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    states = [parse_qs(urlsplit(response.json()["login_url"]).query)["state"][0]
              for response in responses]
    with SessionLocal() as session:
        rows = session.scalars(select(OAuthCallbackState)).all()
        assert len(rows) <= 2
        assert sum(row.revoked_at is None for row in rows) == 1
    results = [client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    ).status_code for state in states]
    assert sorted(results) == [303, 400]


def test_callback_racing_revoke_cannot_resurrect_ciphertext(direct_client):
    client, _ = direct_client
    blocking = BlockingFakeAuthenticator()
    app.dependency_overrides[data_connection_service.production_data_authenticator] = lambda: blocking
    _setup_keys(client)
    state = _initiate(client)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        callback = pool.submit(
            client.get,
            "/api/v1/data-connections/oauth/callback",
            params={"state": state, "request_token": "synthetic-request-token"},
            follow_redirects=False,
        )
        assert blocking.entered.wait(timeout=5)
        revoked = client.delete("/api/v1/data-connections")
        blocking.release.set()
        callback_result = callback.result(timeout=5)
    assert revoked.status_code == 200
    assert callback_result.status_code == 400
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REVOKED")
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        assert row.status == "revoked" and row.credential_ciphertext is None


def test_callback_racing_rotation_cannot_restore_old_keys_or_session(direct_client):
    client, _ = direct_client
    blocking = BlockingFakeAuthenticator()
    app.dependency_overrides[data_connection_service.production_data_authenticator] = lambda: blocking
    _setup_keys(client)
    state = _initiate(client)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        callback = pool.submit(
            client.get,
            "/api/v1/data-connections/oauth/callback",
            params={"state": state, "request_token": "synthetic-request-token"},
            follow_redirects=False,
        )
        assert blocking.entered.wait(timeout=5)
        rotated = client.post("/api/v1/data-connections/app-keys/rotate", json={
            "api_key": "new-key", "api_secret": "new-secret",
        })
        blocking.release.set()
        callback_result = callback.result(timeout=5)
    assert rotated.status_code == 200
    assert callback_result.status_code == 400
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection))
        assert row.last_authenticated_at is None
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "new-key", "api_secret": "new-secret"}


def test_digest_state_and_fake_callback_survive_client_restart(direct_client):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    client.close()
    restarted = TestClient(app)
    try:
        result = restarted.get(
            "/api/v1/data-connections/oauth/callback",
            params={"state": state, "request_token": "synthetic-request-token"},
            follow_redirects=False,
        )
        assert result.status_code == 303
        _assert_closed(
            restarted.get("/api/v1/data-connections/status").json(),
            "SESSION_PRESENT_UNVERIFIED",
        )
    finally:
        restarted.close()


def test_expired_access_token_is_removed_but_stable_app_keys_remain(direct_client):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    assert client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    ).status_code == 303
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        store = OwnedConnectionStore(
            session, owner_id=OWNER, broker_account_id=f"account-{OWNER}")
        assert store.invalidate_data_access_token(row.id, "synthetic-access-token") is True
        session.commit()
        assert credential_vault.unseal(row.credential_ciphertext) == {
            "api_key": "app-key-a", "api_secret": "app-secret-a",
        }
        assert row.last_authenticated_at is None
    _assert_closed(client.get("/api/v1/data-connections/status").json(), "REAUTH_REQUIRED")


def test_delayed_expiry_cannot_erase_a_newer_callback_token(direct_client):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    assert client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    ).status_code == 303
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        row.credential_ciphertext, row.credential_key_id = credential_vault.seal({
            "api_key": "app-key-a", "api_secret": "app-secret-a",
            "access_token": "newer-access-token",
        })
        session.commit()
        store = OwnedConnectionStore(
            session, owner_id=OWNER, broker_account_id=f"account-{OWNER}")
        assert store.invalidate_data_access_token(row.id, "synthetic-access-token") is False
        session.commit()
        assert credential_vault.unseal(row.credential_ciphertext)["access_token"] == (
            "newer-access-token"
        )


def test_data_facade_uses_only_the_strict_runtime_and_keeps_unproven_operations_closed(
        direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    assert client.get(
        "/api/v1/data-connections/oauth/callback",
        params={"state": state, "request_token": "synthetic-request-token"},
        follow_redirects=False,
    ).status_code == 303
    monkeypatch.setattr(
        "app.providers.kite.KiteProvider.__init__",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("broad provider constructed")
        ),
    )
    calls = []

    def offline_request(_self, route, method, **_kwargs):
        calls.append((route, method))
        if route == "market.instruments":
            return (
                b"instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,"
                b"strike,tick_size,lot_size,instrument_type,segment,exchange\n"
                b"256265,1001,NIFTY 50,NIFTY 50,0,,0,0.05,1,EQ,INDICES,NSE\n"
            )
        return {"NSE:NIFTY 50": {"instrument_token": 256265, "last_price": 100.0}}

    monkeypatch.setattr(
        "app.providers.zerodha_data_runtime.ZerodhaDataKite._request",
        offline_request,
    )
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        facade = OwnedConnectionStore(
            session, owner_id=OWNER, broker_account_id=f"account-{OWNER}")
        facade = facade.data_connection(row.id)
        assert facade.get_ltp(get_instrument("NIFTY")) == 100.0
        with pytest.raises(DataOperationUnavailable) as option_refusal:
            facade.get_option_chain("NIFTY")
        assert option_refusal.value.reason_code == "CURRENT_OPTION_CHAIN_UNPROVEN"
        with pytest.raises(DataOperationUnavailable) as futures_refusal:
            facade.get_futures_ltp("NIFTY")
        assert futures_refusal.value.reason_code == "CURRENT_FUTURES_LTP_UNPROVEN"
    assert calls == [("market.instruments", "GET"), ("market.quote.ltp", "GET")]


def test_service_sources_import_no_execution_or_broad_provider_runtime():
    root = Path(__file__).parents[1]
    sources = "\n".join((root / path).read_text() for path in (
        "app/api/data_connection_routes.py", "app/providers/data_connection_service.py"))
    for forbidden in (
        "app.engine", "app.execution", "load_venue", "SafePaperKite",
        "KiteProvider", "place_order", "positions", "margin", "funds",
    ):
        assert forbidden not in sources
    assert "KiteAuthenticator" in sources
    assert "ready\": True" not in sources and "\"ready\": true" not in sources


def _search_row(token=256265, symbol="NIFTY 50", name="NIFTY 50", **changes):
    return {"instrument_token": token, "tradingsymbol": symbol, "name": name,
            "exchange": "NSE", "segment": "INDICES", "instrument_type": "EQ",
            "expiry": "", **changes}


def _search_runtime(monkeypatch, rows):
    from types import SimpleNamespace
    calls = []

    def construct(store, connection_id):
        store.require_data_connection(connection_id)
        calls.append((store.owner_id, store.broker_account_id, connection_id))
        return SimpleNamespace(instruments=lambda exchange: rows)

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", construct)
    return calls


def _resolve_index(client, **changes):
    return client.post("/api/v1/data-connections/instruments/resolve", json={
        "token": 256265, "symbol": "NIFTY 50", "exchange": "NSE", **changes})


@pytest.mark.parametrize("operation", ["search", "select"])
def test_instrument_missing_app_keys_is_a_connection_prerequisite(direct_client, monkeypatch, operation):
    client, _ = direct_client
    assert client.post("/api/v1/data-connections", json={}).status_code == 201
    calls = []

    def forbidden(*args):
        calls.append(True)
        raise AssertionError("missing app keys must refuse before runtime construction")

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", forbidden)
    result = (_resolve_index(client) if operation == "select" else client.get(
        "/api/v1/data-connections/instruments", params={"query": "NIFTY"}))
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "DATA_CONNECTION_UNAVAILABLE"
    assert calls == []


def test_index_selection_registers_only_the_source_defined_root(direct_client, monkeypatch):
    from app.ir.hashing import content_address
    from app.market_truth.identity import load_canonical_instrument
    client, _ = direct_client
    _setup_keys(client)
    calls = _search_runtime(monkeypatch, [_search_row()])
    response = _resolve_index(client)
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    result = response.json()
    assert result["schema"] == "strategy-os-provider-instrument-selection/1"
    assert result["reference_type"] == "CURRENT_PROVIDER_REFERENCE"
    assert result["historical_mapping"] == "UNVERIFIED"
    assert result["selection"] == {"token": 256265, "symbol": "NIFTY 50", "name": "NIFTY 50",
                                   "exchange": "NSE", "kind": "INDEX"}
    with SessionLocal() as session:
        root = load_canonical_instrument(session, result["instrument"]["address"])
    assert result["instrument"]["definition"] == root.fact()
    assert (root.authority_namespace, root.authority_version, root.venue_code,
            root.asset_class, root.contract_kind, root.currency) == (
        "strategy-os:index:nifty-50:inr:price-return", "1", "XNSE", "INDEX", "SPOT", "INR")
    assert root.economic_underlier_address is None and root.series_terms == ()
    evidence = result["definition_evidence"]
    assert evidence["address"] == content_address(evidence["document"])
    assert evidence["document"]["representation"] == "TRANSFORMED_REFERENCE"
    assert evidence["document"]["instrument_address"] == root.address
    assert evidence["document"]["interpretation"] == {
        "name": "Nifty 50", "currency": "INR", "return_type": "PRICE_RETURN"}
    # Token migration cannot create a second index identity. Neither selection
    # establishes a historical alias; that requires retained acquisition facts.
    _search_runtime(monkeypatch, [_search_row(token=12345)])
    second = _resolve_index(client, token=12345)
    assert second.status_code == 200 and second.json()["instrument"] == result["instrument"]
    assert len(calls) == 1


@pytest.mark.parametrize("provider_name", ["INFOSYS", "INFOSYS LIMITED", ""])
def test_equity_selection_registers_isin_root_without_borrowing_provider_name(direct_client, monkeypatch, provider_name):
    from app.ir.hashing import content_address
    from app.market_truth.identity import load_canonical_instrument
    from app.market_truth.cash_reference import source_reference_for_address, source_reference_for_symbol
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [_search_row(token=77, symbol="INFY", name=provider_name, segment="NSE")])
    response = _resolve_index(client, token=77, symbol="INFY")
    assert response.status_code == 200, response.text
    body = response.json()
    with SessionLocal() as session:
        root = load_canonical_instrument(session, body["instrument"]["address"])
    assert root.fact() == {
        "authority_namespace": "strategy-os:security:isin:INE009A01021", "authority_version": "1",
        "venue_code": "XNSE", "asset_class": "EQUITY", "contract_kind": "SPOT", "currency": "INR",
        "economic_underlier_address": None, "expiry": None, "strike": None, "option_right": None,
        "multiplier": None, "series_terms": [],
    }
    assert body["selection"] == {"symbol": "INFY", "token": 77, "name": provider_name, "exchange": "NSE", "kind": "EQUITY"}
    assert body["historical_mapping"] == "UNVERIFIED"
    evidence = body["definition_evidence"]
    assert evidence["address"] == content_address(evidence["document"])
    assert evidence["document"]["schema"] == "strategy-os-equity-definition-reference/1"
    assert evidence["document"]["interpretation"] == {
        "name": "Infosys Limited", "symbol": "INFY", "isin": "INE009A01021",
        "security_class": "INDIAN_EQUITY", "exchange": "NSE", "series": "EQ", "currency": "INR",
    }
    assert evidence["document"]["sources"][0]["document_date"] == "2026-05-29"
    assert "ISIN* INE009A01021" in evidence["document"]["sources"][0]["excerpts"]
    assert source_reference_for_symbol("INFY", "NSE") == source_reference_for_address(root.address)
    _search_runtime(monkeypatch, [_search_row(token=88, symbol="INFY", name="INFOSYS", segment="NSE")])
    migrated = _resolve_index(client, token=88, symbol="INFY")
    assert migrated.status_code == 200
    assert migrated.json()["instrument"] == body["instrument"]
    assert migrated.json()["definition_evidence"] == evidence


@pytest.mark.parametrize("rows", [
    [], [_search_row(token=77, symbol="INFY", name="INFOSYS")],
    [_search_row(token=77, symbol="INFY", name="INFOSYS", segment="NSE", exchange="BSE")],
    [_search_row(token=77, symbol="INFY", name="INFOSYS", segment="NFO", instrument_type="FUT", expiry="2026-09-30")],
    [_search_row(token=78, symbol="INFY", name="INFOSYS", segment="NSE")],
    [_search_row(token=77, symbol="OTHER", name="INFOSYS", segment="NSE")],
    [_search_row(token=77, symbol="INFY", name="INFOSYS", segment="NSE"), _search_row(token=78, symbol="INFY", name="INFOSYS", segment="NSE")],
])
def test_equity_selection_refuses_wrong_kind_venue_symbol_token_or_ambiguity(direct_client, monkeypatch, rows):
    from app.db.models import AuthorityCanonicalInstrument
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, rows)
    result = _resolve_index(client, token=77, symbol="INFY")
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "INSTRUMENT_SELECTION_UNAVAILABLE"
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AuthorityCanonicalInstrument)) == 0


def test_source_cash_lookup_is_exact_and_does_not_invent_an_unknown_root():
    from app.market_truth.cash_reference import source_reference_for_address, source_reference_for_symbol, source_reference_label
    from app.market_truth.index_reference import nifty_50_price_return_reference
    assert source_reference_for_symbol("NIFTY 50", "NSE") == nifty_50_price_return_reference()
    assert source_reference_for_symbol("INFY", "BSE") is None
    assert source_reference_for_symbol("INFY", "NYSE") is None
    assert source_reference_for_symbol("OTHER", "NSE") is None
    assert source_reference_for_address("sha256:" + "0" * 64) is None
    assert source_reference_label("sha256:" + "0" * 64) is None


@pytest.mark.parametrize("changes,status", [
    ({"token": True}, 422), ({"token": "256265"}, 422), ({"token": 0}, 422),
    ({"token": 4_294_967_296}, 422), ({"owner_id": "other"}, 422),
    ({"symbol": "NIFTY 50 TR"}, 409), ({"symbol": "NIFTY50 USD"}, 409),
    ({"symbol": "NSE_E_60"}, 409), ({"symbol": "NIFTY BANK"}, 409),
    ({"exchange": "BSE"}, 409),
])
def test_index_selection_rejects_unsupported_or_open_requests(direct_client, monkeypatch, changes, status):
    client, _ = direct_client
    _setup_keys(client)
    calls = _search_runtime(monkeypatch, [_search_row()])
    result = _resolve_index(client, **changes)
    assert result.status_code == status, result.text
    assert calls == []


@pytest.mark.parametrize("rows", [
    None, {}, [], [_search_row(token=999)], [_search_row(name="NIFTY 50 TR")],
    [_search_row(segment="NSE")], [_search_row(exchange="BSE")],
    [_search_row(expiry="2026-09-30")], [_search_row(), _search_row()],
    [_search_row(), _search_row(symbol="OTHER")],
    [_search_row(), _search_row(token=999)],
    [None] * (data_connection_service.MAX_INSTRUMENT_ROWS + 1),
])
def test_index_selection_refuses_changed_ambiguous_or_invalid_reference(direct_client, monkeypatch, rows):
    from app.db.models import AuthorityCanonicalInstrument
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, rows)
    response = _resolve_index(client)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "INSTRUMENT_SELECTION_UNAVAILABLE"
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AuthorityCanonicalInstrument)) == 0


def test_index_selection_revalidates_identity_before_registration(direct_client, monkeypatch):
    from types import SimpleNamespace
    from app.db.models import AuthorityCanonicalInstrument
    client, _ = direct_client
    _setup_keys(client)

    def fetch(exchange):
        with SessionLocal() as session:
            session.get(UserSession, SESSION).revoked_at = dt.datetime.now()
            session.commit()
        return [_search_row()]

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime",
                        lambda *args: SimpleNamespace(instruments=fetch))
    response = _resolve_index(client)
    assert response.status_code == 409, response.text
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AuthorityCanonicalInstrument)) == 0


@pytest.mark.parametrize("failure,status", [
    (RuntimeError("synthetic-provider-secret"), 502),
    (DataConnectionUnavailable("synthetic-provider-secret"), 409),
])
def test_index_selection_provider_failures_are_closed(direct_client, monkeypatch, failure, status):
    from types import SimpleNamespace
    client, _ = direct_client
    _setup_keys(client)

    def fetch(exchange):
        raise failure

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime",
                        lambda *args: SimpleNamespace(instruments=fetch))
    response = _resolve_index(client)
    assert response.status_code == status, response.text
    assert "synthetic-provider-secret" not in response.text


def test_index_selection_requires_exact_owner_action_and_v0(direct_client, monkeypatch):
    from dataclasses import replace
    from app.api.request_actions import classify_request
    client, _ = direct_client
    _setup_keys(client)
    calls = _search_runtime(monkeypatch, [_search_row()])
    assert classify_request("POST", "/api/data-connections/instruments/resolve") == "create:connection"
    assert classify_request("GET", "/api/data-connections/instruments/resolve") is None
    assert classify_request("POST", "/api/data-connections/instruments/resolve/extra") is None
    app.dependency_overrides[get_principal] = lambda: replace(_principal(), role="member")
    assert _resolve_index(client).status_code == 403
    app.dependency_overrides[get_principal] = _principal
    monkeypatch.setattr(get_settings(), "release_profile", "standard")
    assert _resolve_index(client).status_code == 409
    assert calls == []


def test_index_selection_refuses_replaced_connection_before_registration(direct_client, monkeypatch):
    from types import SimpleNamespace
    from app.db.models import AuthorityCanonicalInstrument
    client, _ = direct_client
    _setup_keys(client)

    def fetch(exchange):
        with SessionLocal() as session:
            row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
            row.status = "revoked"
            session.commit()
            data_connection_service.create(session, _principal())
            session.commit()
        return [_search_row()]

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime",
                        lambda *args: SimpleNamespace(instruments=fetch))
    response = _resolve_index(client)
    assert response.status_code == 409, response.text
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AuthorityCanonicalInstrument)) == 0


def test_index_selection_does_not_borrow_another_owner_connection(direct_client, monkeypatch):
    client, _ = direct_client
    _seed_foreign_owner_row()
    calls = _search_runtime(monkeypatch, [_search_row()])
    assert _resolve_index(client).status_code == 409
    assert calls == []


@pytest.mark.parametrize("token", [True, 0, "256265"])
def test_index_selection_service_refuses_invalid_token_before_io(monkeypatch, token):
    def forbidden():
        raise AssertionError("invalid input must not open a session")
    with pytest.raises(data_connection_service.InstrumentSelectionUnavailable):
        data_connection_service.resolve_instrument(forbidden, _principal(),
            token=token, symbol="NIFTY 50", exchange="NSE")


def test_index_selection_concurrent_owners_register_one_root(direct_client, monkeypatch):
    import time
    from sqlalchemy import event
    from types import SimpleNamespace
    from app.db.models import AuthorityCanonicalInstrument
    client, _ = direct_client
    _setup_keys(client)
    owner_b, _ = _setup_foreign_owner(client)
    barrier = threading.Barrier(2)

    def fetch(exchange):
        barrier.wait(timeout=5)
        return [_search_row()]

    def delay_insert(*args):
        # Hold the winning insertion long enough to expose a second check-then-
        # insert if the cross-owner registration reservation is removed.
        time.sleep(0.1)

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime",
                        lambda *args: SimpleNamespace(instruments=fetch))
    event.listen(AuthorityCanonicalInstrument, "before_insert", delay_insert)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(data_connection_service.resolve_instrument, SessionLocal, principal,
                token=256265, symbol="NIFTY 50", exchange="NSE") for principal in (
                _principal(), _principal(owner_b, "provider-user-b", "provider-session-b"))]
            results = [future.result(timeout=10) for future in futures]
    finally:
        event.remove(AuthorityCanonicalInstrument, "before_insert", delay_insert)
    assert results[0]["instrument"] == results[1]["instrument"]
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AuthorityCanonicalInstrument)) == 1


def test_instrument_search_is_current_only_closed_bounded_and_deterministic(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    rows = [_search_row(3, "NIFTY Z", "Z index"), _search_row(1, "NIFTY A", "A index"),
            _search_row(2, "NIFTY B", "B index", raw_secret="never-return"),
            _search_row(1, "NIFTY A", "A index")]
    calls = _search_runtime(monkeypatch, rows)
    response = client.get("/api/v1/data-connections/instruments", params={"query": " nifty ", "limit": 2})
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "schema": "strategy-os-provider-instrument-search/2", "provider": "ZERODHA",
        "reference_type": "CURRENT_PROVIDER_REFERENCE", "available_exchanges": ["NSE"],
        "exchange": "ALL", "query": "NIFTY",
        "has_more": True, "items": [
            {"token": 1, "symbol": "NIFTY A", "name": "A index", "exchange": "NSE", "segment": "INDICES", "instrument_type": "EQ", "expiry": None, "strike": None, "lot_size": None, "tick_size": None},
            {"token": 2, "symbol": "NIFTY B", "name": "B index", "exchange": "NSE", "segment": "INDICES", "instrument_type": "EQ", "expiry": None, "strike": None, "lot_size": None, "tick_size": None},
        ],
    }
    rows.reverse()
    assert client.get("/api/v1/data-connections/instruments", params={"query": "nifty", "limit": 2}).json() == response.json()
    assert len(calls) == 2 and all(call[:2] == (OWNER, f"account-{OWNER}") for call in calls)


@pytest.mark.parametrize("params", [
    {}, {"query": "a"}, {"query": " " * 5}, {"query": "x" * 65}, {"query": "ab\ncd"},
    {"query": "ab\x7f"}, {"query": "ab", "exchange": "bad exchange"},
    {"query": "ab", "limit": 0}, {"query": "ab", "limit": 51},
    {"query": "ab", "limit": "broken"}, {"query": "ab", "owner_id": "foreign"},
])
def test_instrument_search_invalid_input_never_constructs_runtime(direct_client, monkeypatch, params):
    client, _ = direct_client
    calls = _search_runtime(monkeypatch, [])
    response = client.get("/api/v1/data-connections/instruments", params=params)
    assert response.status_code == 422, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert calls == []


@pytest.mark.parametrize("changes", [
    {"instrument_token": True}, {"instrument_token": "256265"}, {"instrument_token": 0},
    {"instrument_token": 4_294_967_296}, {"tradingsymbol": ""}, {"tradingsymbol": " NIFTY"},
    {"tradingsymbol": " "}, {"tradingsymbol": "NIFTY\n"}, {"tradingsymbol": "x" * 65},
    {"name": None}, {"name": "x" * 129},
    {"exchange": "bad exchange"}, {"segment": []},
    {"instrument_type": ""}, {"expiry": "2026-02-30"},
])
def test_instrument_search_excludes_malformed_rows(direct_client, monkeypatch, changes):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [None, [], _search_row(**changes)])
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert response.json()["has_more"] is False


def test_instrument_search_supports_bse_equity_and_name_matching(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [
        _search_row(4_294_967_295, "EXAMPLE", "Example company", exchange="BSE", segment="BSE"),
        _search_row(2, "EXAMPLE2", "", exchange="BSE", segment="BSE"),
    ])
    response = client.get("/api/v1/data-connections/instruments", params={"query": "company", "exchange": "BSE", "limit": 1})
    assert response.status_code == 200, response.text
    assert response.json()["items"] == [{"token": 4_294_967_295, "symbol": "EXAMPLE",
        "name": "Example company", "exchange": "BSE", "segment": "BSE", "instrument_type": "EQ", "expiry": None, "strike": None, "lot_size": None, "tick_size": None}]
    assert response.json()["has_more"] is False


@pytest.mark.parametrize("change", ["session_revoked", "session_expired", "member_removed", "member_downgraded", "user_disabled", "org_disabled"])
def test_instrument_search_revalidates_durable_identity(direct_client, monkeypatch, change):
    client, _ = direct_client
    _setup_keys(client)
    calls = _search_runtime(monkeypatch, [])
    with SessionLocal() as session:
        if change == "session_revoked":
            session.get(UserSession, SESSION).revoked_at = dt.datetime.now()
        elif change == "session_expired":
            session.get(UserSession, SESSION).expires_at = dt.datetime(2000, 1, 1)
        elif change.startswith("member"):
            member = session.scalar(select(Membership).where(Membership.user_id == USER))
            member.status = "revoked" if change == "member_removed" else "active"
            member.role = "viewer" if change == "member_downgraded" else "owner"
        elif change == "user_disabled":
            session.get(User, USER).status = "disabled"
        else:
            session.get(Organization, OWNER).status = "disabled"
        session.commit()
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "DATA_CONNECTION_UNAVAILABLE"
    assert calls == []


def test_instrument_search_never_uses_foreign_or_revoked_connection(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    _seed_foreign_owner_row()
    calls = _search_runtime(monkeypatch, [_search_row()])
    assert client.delete("/api/v1/data-connections").status_code == 200
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409
    assert calls == []


def test_instrument_search_rechecks_identity_after_provider_call(direct_client, monkeypatch):
    from types import SimpleNamespace
    client, _ = direct_client
    _setup_keys(client)

    def instruments(exchange):
        with SessionLocal() as session:
            session.get(UserSession, SESSION).revoked_at = dt.datetime.now()
            session.commit()
        return [_search_row()]

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", lambda *_: SimpleNamespace(instruments=instruments))
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409
    assert "items" not in response.json()


@pytest.mark.parametrize("failure,status,code", [
    ("ZerodhaReauthRequired", 409, "DATA_REAUTH_REQUIRED"),
    ("ZerodhaTransientError", 503, "DATA_PROVIDER_BUSY"),
    ("ZerodhaDataUnavailable", 502, "INSTRUMENT_SEARCH_UNAVAILABLE"),
    ("RuntimeError", 502, "INSTRUMENT_SEARCH_UNAVAILABLE"),
])
def test_instrument_search_provider_failure_is_redacted(direct_client, monkeypatch, failure, status, code):
    from types import SimpleNamespace
    from app.providers import zerodha_data_runtime
    client, _ = direct_client
    _setup_keys(client)

    def instruments(exchange):
        exception = RuntimeError if failure == "RuntimeError" else getattr(zerodha_data_runtime, failure)
        raise exception("synthetic-access-token app-secret-a provider-private-payload")

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", lambda *_: SimpleNamespace(instruments=instruments))
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetic-access-token" not in response.text and "app-secret-a" not in response.text


@pytest.mark.parametrize("rows", [{"items": []}, [None] * 100_001])
def test_instrument_search_refuses_unbounded_or_invalid_dump(direct_client, monkeypatch, rows):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, rows)
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 502


def test_instrument_search_exact_read_permission_and_release_gate(direct_client, monkeypatch):
    from app.api.request_actions import classify_request
    client, _ = direct_client
    _setup_keys(client)
    calls = _search_runtime(monkeypatch, [_search_row()])
    assert classify_request("GET", "/api/data-connections/instruments") == "read:connections"
    assert classify_request("POST", "/api/data-connections/instruments") is None
    assert classify_request("GET", "/api/data-connections/instruments/anything") is None
    principal = _principal()
    from dataclasses import replace
    app.dependency_overrides[get_principal] = lambda: replace(principal, role="viewer")
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 403
    app.dependency_overrides[get_principal] = _principal
    monkeypatch.setattr(get_settings(), "release_profile", "standard")
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409
    assert response.json()["detail"] == "data onboarding is unavailable"
    assert calls == []


@pytest.mark.parametrize("field,value", [("status", "revoked"), ("broker", "mock"),
    ("scope", "strategy-os-v0:data-forged:1"), ("capabilities_json", "[]"),
    ("owner_id", "provider-owner-b")])
def test_instrument_search_closed_data_row_identity(direct_client, monkeypatch, field, value):
    client, _ = direct_client
    _setup_keys(client)
    _seed_foreign_owner_row()
    calls = _search_runtime(monkeypatch, [_search_row()])
    with SessionLocal() as session:
        row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        setattr(row, field, value)
        session.commit()
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409
    assert calls == []


def test_instrument_search_real_runtime_reads_only_owner_credentials_and_handles_token_expiry(direct_client, monkeypatch):
    from kiteconnect.exceptions import TokenException
    client, _ = direct_client
    _setup_keys(client)
    state = _initiate(client)
    assert client.get("/api/v1/data-connections/oauth/callback", params={
        "state": state, "request_token": "synthetic-request-token"}, follow_redirects=False).status_code == 303
    foreign_owner, foreign_ciphertext = _seed_foreign_owner_row()
    calls = []

    def offline_request(wire, route, method, **kwargs):
        calls.append((route, method, kwargs.get("url_args")))
        assert wire.api_key == "app-key-a" and wire.access_token == "synthetic-access-token"
        if len(calls) > 1:
            raise TokenException("synthetic-access-token must never escape")
        return (b"instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,"
                b"strike,tick_size,lot_size,instrument_type,segment,exchange\n"
                b"256265,1001,NIFTY 50,NIFTY 50,0,,0,0.05,1,EQ,INDICES,NSE\n")

    monkeypatch.setattr("app.providers.zerodha_data_runtime.ZerodhaDataKite._request", offline_request)
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 200, response.text
    assert response.json()["items"] == [{"token": 256265, "symbol": "NIFTY 50", "name": "NIFTY 50", "exchange": "NSE", "segment": "INDICES", "instrument_type": "EQ",
        "expiry": None, "strike": "0", "lot_size": "1", "tick_size": "0.05"}]
    expired = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert expired.status_code == 409, expired.text
    assert expired.json()["detail"]["code"] == "DATA_REAUTH_REQUIRED"
    assert "synthetic-access-token" not in expired.text
    assert calls == [("market.instruments.all", "GET", None)] * 2
    with SessionLocal() as session:
        owner_row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
        assert credential_vault.unseal(owner_row.credential_ciphertext) == {"api_key": "app-key-a", "api_secret": "app-secret-a"}
        foreign = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == foreign_owner))
        assert foreign.credential_ciphertext == foreign_ciphertext


@pytest.mark.parametrize("change", ["replacement", "capabilities"])
def test_instrument_search_refuses_connection_change_during_request(direct_client, monkeypatch, change):
    from types import SimpleNamespace
    client, _ = direct_client
    _setup_keys(client)

    def instruments(exchange):
        with SessionLocal() as session:
            row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
            if change == "replacement":
                row.status = "revoked"
                session.commit()
                data_connection_service.create(session, _principal())
            else:
                row.capabilities_json = "[]"
            session.commit()
        return [_search_row()]

    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", lambda *_: SimpleNamespace(instruments=instruments))
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409, response.text
    assert "items" not in response.json()


def test_instrument_search_two_owners_remain_separate(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    foreign_owner, _ = _seed_foreign_owner_row()
    calls = _search_runtime(monkeypatch, [_search_row()])
    first = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert first.status_code == 200
    app.dependency_overrides[get_principal] = lambda: _principal(foreign_owner, "provider-user-b", "provider-session-b")
    second = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert second.status_code == 200
    assert [call[:2] for call in calls] == [(OWNER, f"account-{OWNER}"), (foreign_owner, f"account-{foreign_owner}")]
    assert calls[0][2] != calls[1][2]


def test_instrument_search_refuses_multiple_active_data_rows(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    calls = _search_runtime(monkeypatch, [_search_row()])
    with SessionLocal() as session:
        session.add(BrokerConnection(owner_id=OWNER, broker_account_id=f"account-{OWNER}",
            broker="kite", scope="strategy-os-v0:data:99", label="",
            capabilities_json=json.dumps(sorted(DATA_CAPABILITIES)), status="active",
            created_at=dt.datetime.now(), updated_at=dt.datetime.now()))
        session.commit()
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409
    assert calls == []


def test_instrument_search_foreign_session_cannot_borrow_owner_identity(direct_client, monkeypatch):
    from dataclasses import replace
    client, _ = direct_client
    _setup_keys(client)
    _seed_foreign_owner_row()
    calls = _search_runtime(monkeypatch, [_search_row()])
    app.dependency_overrides[get_principal] = lambda: replace(_principal(), session_id="provider-session-b")
    response = client.get("/api/v1/data-connections/instruments", params={"query": "nifty"})
    assert response.status_code == 409
    assert calls == []


def test_instrument_search_accepts_exact_dump_and_result_limits(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    rows = [_search_row(i, f"SEARCH{i:03}") for i in range(1, 52)] + [None] * (100_000 - 51)
    _search_runtime(monkeypatch, rows)
    response = client.get("/api/v1/data-connections/instruments", params={"query": "search", "limit": 50})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 50
    assert response.json()["items"][-1]["token"] == 50
    assert response.json()["has_more"] is True


@pytest.mark.parametrize("instrument_type,exchange,segment,expiry", [
    ("EQ", "NSE", "NSE", ""), ("FUT", "NFO", "NFO-FUT", "2026-10-29"),
    ("CE", "BFO", "BFO-OPT", "2026-10-29"), ("PE", "NFO", "NFO-OPT", "2026-10-29"),
    ("PROVIDER_NEW_TYPE", "NEW", "NEW-SEGMENT", ""),
])
def test_generic_provider_search_preserves_all_catalogue_types(direct_client, monkeypatch,
        instrument_type, exchange, segment, expiry):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [_search_row(721, "UNKNOWN SMALLCAP", "Small company",
        instrument_type=instrument_type, exchange=exchange, segment=segment, expiry=expiry,
        strike=125.50, lot_size=25, tick_size=0.05, last_price=99.75)])
    result = client.get("/api/v1/data-connections/instruments", params={"query": "small"})
    assert result.status_code == 200, result.text
    assert result.json()["available_exchanges"] == [exchange]
    assert result.json()["items"] == [{"token": 721, "symbol": "UNKNOWN SMALLCAP",
        "name": "Small company", "exchange": exchange, "segment": segment,
        "instrument_type": instrument_type, "expiry": expiry or None,
        "strike": "125.5", "lot_size": "25", "tick_size": "0.05"}]
    assert "last_price" not in result.text


def test_generic_provider_search_filters_discovered_exchanges(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [_search_row(1, "SEARCH1", exchange="NSE"),
        _search_row(2, "SEARCH2", exchange="BFO", instrument_type="CE", segment="BFO-OPT")])
    result = client.get("/api/v1/data-connections/instruments", params={"query": "search", "exchange": "BFO"})
    assert result.status_code == 200, result.text
    assert result.json()["available_exchanges"] == ["BFO", "NSE"]
    assert [item["token"] for item in result.json()["items"]] == [2]



def _generic_reference(**changes):
    return {"token": 721, "symbol": "UNKNOWN SMALLCAP", "name": "Small company",
            "exchange": "NSE", "segment": "NSE", "instrument_type": "EQ", "expiry": None,
            "strike": "0", "lot_size": "1", "tick_size": "0.05", **changes}


def _generic_row(**changes):
    return _search_row(721, "UNKNOWN SMALLCAP", "Small company", segment="NSE",
                       strike=0, lot_size=1, tick_size=0.05, **changes)


def test_generic_provider_selection_saves_unknown_symbol_and_reuses_receipt(direct_client, monkeypatch):
    from app.db.models import OwnerProviderInstrumentSelection, AuthorityCanonicalInstrument
    from app.ir.hashing import content_address
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [_generic_row(last_price=91)])
    response = client.post("/api/v1/data-connections/instrument-selections", json={"reference": _generic_reference()})
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    saved = response.json()
    assert set(saved) == {"schema", "selection_address", "selection", "research_resolution"}
    assert saved["schema"] == "strategy-os-provider-selection/1"
    assert saved["research_resolution"] == "UNRESOLVED"
    assert saved["selection"]["reference"] == _generic_reference()
    assert saved["selection"]["owner_id"] == OWNER
    assert saved["selection_address"] == content_address(saved["selection"])
    _search_runtime(monkeypatch, [_generic_row(last_price=99)])
    assert client.post("/api/v1/data-connections/instrument-selections", json={"reference": _generic_reference()}).json() == saved
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(OwnerProviderInstrumentSelection)) == 1
        assert session.scalar(select(func.count()).select_from(AuthorityCanonicalInstrument)) == 0


@pytest.mark.parametrize("changes", [
    {"token": True}, {"extra": "untrusted"}, {"strike": "0.00"}, {"tick_size": float("inf")},
    {"expiry": "2026-02-30"}, {"lot_size": "NaN"}, {"name": None},
])
def test_generic_provider_selection_invalid_reference_before_io(direct_client, monkeypatch, changes):
    client, _ = direct_client
    calls = _search_runtime(monkeypatch, [])
    # Infinity is not JSON; its string form exercises the same normalized-decimal refusal.
    if changes.get("tick_size") == float("inf"):
        changes = {"tick_size": "Infinity"}
    response = client.post("/api/v1/data-connections/instrument-selections", json={"reference": _generic_reference(**changes)})
    assert response.status_code == 422, response.text
    assert calls == []


@pytest.mark.parametrize("rows", [[], [_generic_row(expiry="2026-10-29")],
    [_generic_row(), _generic_row()], [_generic_row(), {"instrument_token": 721}],
    [_generic_row(), {"tradingsymbol": "UNKNOWN SMALLCAP", "exchange": "NSE"}],
    [{**_generic_row(), "name": None}]])
def test_generic_provider_selection_refuses_stale_or_ambiguous_catalogue(direct_client, monkeypatch, rows):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, rows)
    response = client.post("/api/v1/data-connections/instrument-selections", json={"reference": _generic_reference()})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "INSTRUMENT_SELECTION_UNAVAILABLE"


@pytest.mark.parametrize("change", ["session", "connection", "replacement"])
def test_generic_provider_selection_rechecks_authority_after_io(direct_client, monkeypatch, change):
    from types import SimpleNamespace
    from app.db.models import OwnerProviderInstrumentSelection
    client, _ = direct_client
    _setup_keys(client)
    def instruments(exchange):
        with SessionLocal() as session:
            if change == "session":
                session.get(UserSession, SESSION).revoked_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            else:
                row = session.scalar(select(BrokerConnection).where(BrokerConnection.owner_id == OWNER))
                row.status = "revoked"
                if change == "replacement":
                    session.commit()
                    data_connection_service.create(session, _principal())
                    session.commit()
                    data_connection_service.write_app_keys(session, _principal(),
                        {"api_key": "replacement-key", "api_secret": "replacement-secret"}, rotate=False)
            session.commit()
        return [_generic_row()]
    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", lambda *args: SimpleNamespace(instruments=instruments))
    response = client.post("/api/v1/data-connections/instrument-selections", json={"reference": _generic_reference()})
    assert response.status_code == 409, response.text
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(OwnerProviderInstrumentSelection)) == 0


@pytest.mark.parametrize("value", [True, [], "NaN", "Infinity", "-1", "1e25", "1e-25", "x", "1" * 65])
def test_generic_provider_catalogue_excludes_invalid_financial_terms(value):
    rows = [{**_generic_row(), "strike": value}]
    result = data_connection_service._instrument_matches(rows, "SMALL", "ALL", 20)
    assert result["items"] == []


def test_generic_provider_catalogue_decimal_terms_are_exact_and_stable():
    from decimal import Decimal
    rows = [{**_generic_row(), "expiry": dt.date(2026, 10, 29),
             "strike": Decimal("12345678901234567890.123456789012345"), "lot_size": 1000,
             "tick_size": "0.05000", "last_price": 123.45}]
    result = data_connection_service._instrument_matches(rows, "SMALL", "ALL", 20)
    reference = result["items"][0]
    assert reference["strike"] == "12345678901234567890.123456789012345"
    assert reference["lot_size"] == "1000"
    assert reference["tick_size"] == "0.05"
    assert reference["expiry"] == "2026-10-29"
    assert "last_price" not in reference


@pytest.mark.parametrize("field,value", [("expiry", 42), ("expiry", "20261029"), ("expiry", "2026-W01-1"),
    ("symbol", "e\u0301"), ("name", "line\x7fbreak"), ("segment", ""), ("lot_size", 1)])
def test_generic_provider_reference_requires_canonical_request_terms(field, value):
    from app.providers.provider_instrument_reference import ProviderReferenceInvalid, validate_reference
    with pytest.raises(ProviderReferenceInvalid):
        validate_reference(_generic_reference(**{field: value}))


def test_generic_provider_unicode_search_is_literal_text():
    query = data_connection_service._instrument_query(" sociétés <fonds> ", "ALL", 20)
    rows = [{**_generic_row(), "name": "Sociétés <fonds>"}]
    assert data_connection_service._instrument_matches(rows, query, "ALL", 20)["items"][0]["token"] == 721



def test_generic_provider_selection_action_and_release_gates(direct_client, monkeypatch):
    from dataclasses import replace
    from app.api.request_actions import classify_request
    client, _ = direct_client
    calls = _search_runtime(monkeypatch, [_generic_row()])
    path = "/api/v1/data-connections/instrument-selections"
    assert classify_request("POST", "/api/data-connections/instrument-selections") == "create:connection"
    assert classify_request("GET", "/api/data-connections/instrument-selections") is None
    assert classify_request("POST", "/api/data-connections/instrument-selections/extra") is None
    app.dependency_overrides[get_principal] = lambda: replace(_principal(), role="member")
    assert client.post(path, json={"reference": _generic_reference()}).status_code == 403
    app.dependency_overrides[get_principal] = _principal
    monkeypatch.setattr(get_settings(), "release_profile", "standard")
    assert client.post(path, json={"reference": _generic_reference()}).status_code == 409
    assert calls == []


def test_generic_provider_api_search_save_watchlist_reopen_without_connection_or_datasets(direct_client, monkeypatch):
    client, _ = direct_client
    _setup_keys(client)
    _search_runtime(monkeypatch, [_generic_row()])
    search = client.get('/api/v1/data-connections/instruments', params={'query': 'small'})
    assert search.status_code == 200, search.text
    selected = client.post('/api/v1/data-connections/instrument-selections',
        json={'reference': search.json()['items'][0]})
    assert selected.status_code == 200, selected.text
    created_project = client.post('/api/v1/ir/projects', json={'name': 'Provider selection research'})
    assert created_project.status_code == 201, created_project.text
    path = f"/api/v1/ir/projects/{created_project.json()['project_id']}/static-scopes"
    pointer = {'kind': 'PROVIDER_REFERENCE', 'selection_address': selected.json()['selection_address']}
    saved = client.post(path, json={'name': 'Small companies', 'members': [pointer]})
    assert saved.status_code == 201, saved.text
    document = saved.json()
    assert document['snapshot']['schema'] == 'static-instrument-scope/2'
    assert document['snapshot']['members'] == [pointer]
    assert document['member_labels'][0]['provider_reference'] == _generic_reference()
    assert client.delete('/api/v1/data-connections').status_code == 200
    reopened = client.get(f"{path}/{document['scope_id']}")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == document
    assert client.get(path).json()['items'] == [document]
    owner_b, _ = _setup_foreign_owner(client)
    foreign_project = client.post('/api/v1/ir/projects', json={'name': 'Other workspace'})
    assert foreign_project.status_code == 201, foreign_project.text
    foreign_path = f"/api/v1/ir/projects/{foreign_project.json()['project_id']}/static-scopes"
    refused = client.post(foreign_path, json={'name': 'Cannot borrow selection', 'members': [pointer]})
    assert refused.status_code == 422, refused.text
    assert client.get(f"{path}/{document['scope_id']}").status_code == 404


def _history_fetch_setup(client, monkeypatch, *, symbol="INFY", grant=True, product_version="3", dated_clock=False):
    from app.core.provider_selections import persist_provider_selection
    from app.db.models import Project
    from app.ir.hashing import content_address
    from app.market_truth.identity import ProviderEntity, ProviderProduct, ProviderContract, persist_provider_identity
    from research.data import provider_history_fetch as fetch
    _setup_keys(client)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=123456)
    monkeypatch.setattr(fetch, "_now", lambda: now + dt.timedelta(seconds=1))
    reference = _generic_reference(token=408065, symbol=symbol, name="INFOSYS")
    entity = ProviderEntity("synthetic", "kite", "Synthetic provider authority") if dated_clock else (
        ProviderEntity("history-fetch-test", "kite", "Synthetic provider"))
    product = ProviderProduct(entity.address, "kite-connect-v3", "kite-connect", product_version)
    contract = ProviderContract(OWNER, product.address, "RESEARCH", ("HISTORICAL",),
        now-dt.timedelta(days=2), None, content_address({"synthetic": "existing-grant"}))
    with SessionLocal() as session:
        from app.db.concurrency import begin_reservation
        begin_reservation(session, scope="synthetic-history-fetch")
        session.add(Project(project_id="fetch-project", owner_id=OWNER, name="History", status="active"))
        session.flush()
        store, connection_id = data_connection_service._instrument_connection(session, _principal(), SessionLocal)
        saved = persist_provider_selection(session, owner_id=OWNER, data_account_id=store.broker_account_id,
            connection_id=connection_id, provider="ZERODHA", reference=reference, observed_at=now)
        if grant:
            persist_provider_identity(session, entity, product, contract)
        session.commit()
    return dict(project_id="fetch-project", selection_address=saved["selection_address"],
        from_date="2019-01-01", to_date="2025-01-01"), reference, (entity, product, contract), connection_id, now


class _HistoryFetchRuntime:
    def __init__(self, reference, now, *, empty=(), malformed=False, changed_csv=False,
                 missing_callback=False, after_history=None):
        self.reference, self.now = reference, now
        self.empty, self.malformed, self.changed_csv = empty, malformed, changed_csv
        self.after_history, self.missing_callback = after_history, missing_callback
        self.calls, self.responses = [], []

    def instruments(self, exchange, *, capture_response):
        self.calls.append(("instruments", exchange))
        row = {**_generic_row(), "instrument_token": self.reference["token"],
               "tradingsymbol": self.reference["symbol"], "name": self.reference["name"]}
        raw = ("instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"
            f'{self.reference["token"]},1,{self.reference["symbol"]},{self.reference["name"]},0,,0,0.05,1,EQ,NSE,NSE\n').encode()
        if self.changed_csv:
            raw = raw.replace(b"0.05", b"0.10")
        capture_response(raw, self.now, exchange)
        return [row]

    def historical_data(self, token, start, end, interval, *, continuous, oi, capture_response):
        from app.providers.zerodha_data_runtime import _history_windows
        self.calls.append(("history", token, start, end, interval, continuous, oi))
        for index, (first, last) in enumerate(_history_windows(start, end, interval)):
            rows = [] if index in self.empty else [[first.isoformat(), 100, 102, 99, 101, 1000]]
            raw = json.dumps({"status": "success", "data": {"candles": rows}}, indent=1).encode()
            if self.malformed:
                raw = b'{"status":"success","data":{"candles":false}}'
            self.responses.append(raw)
            if not (self.missing_callback and index == 0):
                capture_response(raw, self.now, first, last, interval)
        if self.after_history is not None:
            self.after_history()
        return []


def _install_history_fetch_runtime(monkeypatch, runtime):
    constructions = []
    def construct(store, connection_id):
        store.require_data_connection(connection_id)
        constructions.append((store.owner_id, store.broker_account_id, connection_id))
        return runtime
    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", construct)
    return constructions


def _history_fetch_clock(identity, now, seconds):
    from app.ir.hashing import canonical_json
    from app.market_data.dated_session_clock import SCHEMA, COMPLETION_SCHEMA, prepare_session_clock
    from app.market_data.observations import RawObservationSegment, persist_raw_segment
    from app.market_truth.cash_reference import source_reference_for_symbol
    from app.market_truth.dated_sessions import parse_dated_sessions
    entity, product, contract = identity
    instrument, _ = source_reference_for_symbol('INFY', 'NSE')
    recorded = now-dt.timedelta(days=1)
    start = recorded.replace(hour=4, minute=0, second=0, microsecond=0)
    end = start+dt.timedelta(minutes=45)
    doc = dict(schema=SCHEMA, instrument_address=instrument.address, venue_code='XNSE', timezone='UTC',
        provenance='SYNTHETIC', source_reference='Synthetic DATA acquisition test', recorded_at=recorded.isoformat(),
        rows=[dict(date=start.date().isoformat(), status='OPEN', opens_at=start.isoformat(), closes_at=end.isoformat())])
    raw = RawObservationSegment(OWNER, product.address, contract.address, 'application/json', SCHEMA,
        canonical_json(doc).encode(), recorded)
    calendar = parse_dated_sessions(raw.payload, instrument_address=instrument.address,
        venue_code='XNSE', timezone='UTC', as_of=now, allow_synthetic=True)
    completion = dict(schema=COMPLETION_SCHEMA, calendar_address=calendar.address, product_address=product.address,
        contract_address=contract.address, resolution_seconds=seconds, completion_rule='SESSION_OPEN_CLIP_CLOSE_V1',
        provenance='SYNTHETIC')
    completion_raw = RawObservationSegment(OWNER, product.address, contract.address, 'application/json',
        COMPLETION_SCHEMA, canonical_json(completion).encode(), recorded)
    clock = prepare_session_clock(owner_id=OWNER, entity=entity, product=product, contract=contract,
        instrument=instrument, resolution_seconds=seconds, calendar_source=raw, completion_source=completion_raw, as_of=now)
    with SessionLocal() as session:
        persist_raw_segment(session, raw); persist_raw_segment(session, completion_raw); session.commit()
    return clock, start, end


class _DatedHistoryFetchRuntime(_HistoryFetchRuntime):
    def __init__(self, reference, now, clock):
        super().__init__(reference, now)
        self.clock = clock

    def historical_data(self, token, start, end, interval, *, continuous, oi, capture_response):
        from app.market_truth.dated_sessions import expected_bars
        self.calls.append(('history',token,start,end,interval,continuous,oi))
        bars = expected_bars(self.clock.calendar, requested_start=start.astimezone(dt.timezone.utc),
            requested_end=end.astimezone(dt.timezone.utc), resolution_seconds=self.clock.resolution_seconds, cutoff_at=self.now)
        rows = [[opened.isoformat(),100,102,99,101,1000] for opened,_ in bars]
        raw = json.dumps({'status':'success','data':{'candles':rows}}).encode()
        self.responses.append(raw)
        capture_response(raw,self.now,start,end,interval)
        return []


@pytest.mark.parametrize('seconds', [900,1800,3600])
def test_monitoring_history_fetch_uses_retained_clock_and_data_only_runtime(direct_client, monkeypatch, seconds):
    from research.data.provider_history_fetch import fetch_monitoring_history
    client, _ = direct_client
    request, reference, identity, connection_id, now = _history_fetch_setup(client, monkeypatch, dated_clock=True)
    clock, start, end = _history_fetch_clock(identity, now, seconds)
    runtime = _DatedHistoryFetchRuntime(reference, now, clock)
    constructions = _install_history_fetch_runtime(monkeypatch, runtime)
    interval = {900:'15minute',1800:'30minute',3600:'60minute'}[seconds]
    result = fetch_monitoring_history(SessionLocal, _principal(), **{**request,'from_date':start,'to_date':end},
        interval=interval, clock_binding_addresses=clock.receipt_binding())
    assert len(constructions) == 1 and result.connection_id == connection_id
    assert result.requested_end == start+dt.timedelta(seconds=((2700-1)//seconds)*seconds)
    assert result.captures[0].row_count == len(range(0,2700,seconds))
    assert result.captures[0].current_reference == result.current_reference
    assert result.sources[0].clock_binding == clock
    assert result.sources[0].historical_response.payload == runtime.responses[0]
    assert runtime.calls[-1][-3:] == (interval,False,False)


def test_history_fetch_returns_all_original_chunks_without_publishing(direct_client, monkeypatch):
    from dataclasses import FrozenInstanceError
    from app.db.models import AuthorityRawSegment, AuthorityProviderAlias, AuthorityCanonicalInstrument
    from research.data.provider_history_fetch import fetch_provider_history
    client, _ = direct_client
    request, reference, _, connection_id, now = _history_fetch_setup(client, monkeypatch)
    runtime = _HistoryFetchRuntime(reference, now, empty=(0,))
    constructions = _install_history_fetch_runtime(monkeypatch, runtime)
    result = fetch_provider_history(SessionLocal, _principal(), **request)
    assert len(result.captures) == 2 and [item.row_count for item in result.captures] == [0, 1]
    assert len(result.sources) == 1
    assert [item.payload for item in result.captures] == runtime.responses
    assert result.sources[0].historical_response.payload == runtime.responses[1]
    assert result.sources[0].context.provider_contract_address == result.sources[0].mapping.provider_contract_address
    assert result.current_reference.received_at == now
    assert result.sources[0].current_reference.payload == result.current_reference.payload
    assert result.sources[0].context.owner_id == OWNER and result.connection_id == connection_id
    assert result.requested_start.utcoffset() == result.requested_end.utcoffset() == dt.timedelta(0)
    assert all(item.interval == "day" and item.received_at == now and item.recorded_at > now for item in result.captures)
    assert len(constructions) == 1 and runtime.calls[0] == ("instruments", "NSE")
    assert runtime.calls[1][-2:] == (False, False)
    assert json.loads(result.definition_evidence)["document"]["instrument_address"] == result.instrument.address
    with pytest.raises(FrozenInstanceError):
        result.connection_id = 9
    with SessionLocal() as session:
        assert [session.scalar(select(func.count()).select_from(model)) for model in
                (AuthorityRawSegment, AuthorityProviderAlias, AuthorityCanonicalInstrument)] == [0, 0, 0]


@pytest.mark.parametrize("condition,code", [("unknown_root", "HISTORICAL_FETCH_ROOT_UNAVAILABLE"),
    ("missing_grant", "HISTORICAL_FETCH_GRANT_UNAVAILABLE"), ("ambiguous_grant", "HISTORICAL_FETCH_GRANT_UNAVAILABLE"),
    ("wrong_product", "HISTORICAL_FETCH_GRANT_UNAVAILABLE"),
    ("project", "HISTORICAL_FETCH_PROJECT_UNAVAILABLE"), ("foreign_project", "HISTORICAL_FETCH_PROJECT_UNAVAILABLE"),
    ("incomplete_today", "HISTORICAL_FETCH_INCOMPLETE_DAY"), ("range", "HISTORICAL_FETCH_RANGE_INVALID")])
def test_history_fetch_prerequisites_refuse_before_runtime(direct_client, monkeypatch, condition, code):
    from dataclasses import replace
    from app.market_truth.identity import persist_provider_identity
    from research.data.provider_history_fetch import fetch_provider_history, HistoricalFetchRefused
    client, _ = direct_client
    request, reference, identities, _, now = _history_fetch_setup(client, monkeypatch,
        symbol="UNKNOWN" if condition == "unknown_root" else "INFY", grant=condition != "missing_grant",
        product_version="4" if condition == "wrong_product" else "3")
    if condition == "ambiguous_grant":
        entity, product, contract = identities
        with SessionLocal() as session:
            persist_provider_identity(session, entity, product, replace(contract, effective_from=contract.effective_from-dt.timedelta(seconds=1)))
            session.commit()
    if condition == "project":
        request["project_id"] = "other-project"
    if condition == "foreign_project":
        from app.db.models import Project
        _seed_identity("fetch-foreign-owner", "fetch-foreign-user", "fetch-foreign-session", with_account=False)
        with SessionLocal() as session:
            session.add(Project(project_id="foreign-fetch-project", owner_id="fetch-foreign-owner", name="Foreign", status="active"))
            session.commit()
        request["project_id"] = "foreign-fetch-project"
    if condition == "incomplete_today":
        from research.data import provider_history_fetch as fetch
        request["to_date"] = fetch._now().astimezone(fetch.EXCHANGE_TIME).date().isoformat()
    if condition == "range":
        request["from_date"] = "2026-09-06"  # After the requested end.
    runtime = _HistoryFetchRuntime(reference, now)
    constructions = _install_history_fetch_runtime(monkeypatch, runtime)
    with pytest.raises(HistoricalFetchRefused) as refused:
        fetch_provider_history(SessionLocal, _principal(), **request)
    assert refused.value.code == code
    assert constructions == runtime.calls == []


@pytest.mark.parametrize("condition,code", [("all_empty", "HISTORICAL_FETCH_EMPTY"),
    ("malformed", "HISTORICAL_FETCH_CAPTURE_INVALID"), ("missing_callback", "HISTORICAL_FETCH_CAPTURE_INVALID"),
    ("changed_csv", "HISTORICAL_FETCH_SELECTION_UNAVAILABLE")])
def test_history_fetch_refuses_empty_malformed_or_changed_raw_reference(direct_client, monkeypatch, condition, code):
    from research.data.provider_history_fetch import fetch_provider_history, HistoricalFetchRefused
    client, _ = direct_client
    request, reference, _, _, now = _history_fetch_setup(client, monkeypatch)
    runtime = _HistoryFetchRuntime(reference, now, empty=(0, 1) if condition == "all_empty" else (),
        malformed=condition == "malformed", changed_csv=condition == "changed_csv", missing_callback=condition == "missing_callback")
    _install_history_fetch_runtime(monkeypatch, runtime)
    with pytest.raises(HistoricalFetchRefused) as refused:
        fetch_provider_history(SessionLocal, _principal(), **request)
    assert refused.value.code == code
    if condition == "changed_csv":
        assert len(runtime.calls) == 1  # Refuse before requesting historical data.


@pytest.mark.parametrize("change", ["connection", "replacement", "project", "membership", "grant"])
def test_history_fetch_rechecks_durable_access_after_all_calls(direct_client, monkeypatch, change):
    from dataclasses import replace
    from app.db.models import Project
    from app.market_truth.identity import persist_provider_identity
    from research.data.provider_history_fetch import fetch_provider_history, HistoricalFetchRefused
    client, _ = direct_client
    request, reference, identities, connection_id, now = _history_fetch_setup(client, monkeypatch)
    def revoke():
        with SessionLocal() as session:
            if change == "connection":
                session.get(BrokerConnection, connection_id).status = "revoked"
            elif change == "replacement":
                row = session.get(BrokerConnection, connection_id)
                row.status = "revoked"
                session.flush()
                store = OwnedConnectionStore.for_data_role(session, owner_id=OWNER, broker_account_id=row.broker_account_id)
                new = store.create_data_connection()
                new.credential_ciphertext = row.credential_ciphertext
            elif change == "project":
                session.get(Project, request["project_id"]).status = "archived"
            elif change == "membership":
                session.scalar(select(Membership).where(Membership.organization_id == OWNER)).status = "revoked"
            else:
                entity, product, contract = identities
                persist_provider_identity(session, entity, product, replace(contract, effective_from=contract.effective_from-dt.timedelta(seconds=1)))
            session.commit()
    runtime = _HistoryFetchRuntime(reference, now, after_history=revoke)
    _install_history_fetch_runtime(monkeypatch, runtime)
    with pytest.raises(HistoricalFetchRefused):
        fetch_provider_history(SessionLocal, _principal(), **request)
    assert len(runtime.responses) == 2


@pytest.mark.parametrize("failure,code", [
    ("ConnectionNotFound", "DATA_CONNECTION_UNAVAILABLE"),
    ("DataConnectionUnavailable", "DATA_CONNECTION_UNAVAILABLE"),
    ("ZerodhaDataUnavailable", "DATA_CONNECTION_UNAVAILABLE"),
    ("ZerodhaReauthRequired", "DATA_REAUTH_REQUIRED"),
    ("ZerodhaTransientError", "DATA_PROVIDER_BUSY"),
    ("CredentialVaultUnavailable", "DATA_VAULT_UNAVAILABLE"),
    ("CredentialDecryptionFailed", "DATA_VAULT_UNAVAILABLE"),
    ("unexpected", "HISTORICAL_FETCH_UNAVAILABLE"),
])
def test_history_fetch_preserves_safe_connection_and_provider_failure_categories(direct_client, monkeypatch, failure, code):
    from research.data import provider_history_fetch as fetch
    client, _ = direct_client
    request, _, _, _, _ = _history_fetch_setup(client, monkeypatch)
    error_type = RuntimeError if failure == "unexpected" else getattr(fetch, failure)
    def fail(*_args):
        raise error_type("sensitive-provider-detail")
    monkeypatch.setattr(OwnedConnectionStore, "zerodha_data_runtime", fail)
    with pytest.raises(fetch.HistoricalFetchRefused) as refused:
        fetch.fetch_provider_history(SessionLocal, _principal(), **request)
    assert refused.value.code == code
    assert "sensitive-provider-detail" not in str(refused.value)
