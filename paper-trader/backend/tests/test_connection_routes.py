"""The HTTP surface for broker connections.

`tests/test_connection_store.py` proves the store. This file proves the *route* — which is a
separate claim, because every way this goes wrong is a way the route re-introduces something the
store was careful about:

  * the owner arriving from the request instead of the principal,
  * a credential coming back out in a response,
  * a missing vault key being swallowed into a 200 with the credential dropped,
  * a `planned` broker being accepted and discovered at 09:15.

The anonymous-owner mapping gets its own test because it is the trap: auth disabled is the
shipped default and the current production posture, and `ANONYMOUS_OWNER.id` is not the owner id
the engine reads.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import credential_vault as vault
from app.core.config import get_settings
from app.db.models import BrokerAccount, LEGACY_OWNER_ID, BrokerConnection
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app
from app.api.principal import Principal, get_principal, token_digest
from app.providers.connection_store import ConnectionNotFound, OwnedConnectionStore
from app.events.planes import execution_outbox

KEY = base64.b64encode(b"r" * 32).decode()

#: Deliberately NOT `LEGACY_OWNER_ID`. Three independent mechanisms produce the string `"owner"`
#: — the model column default, `Settings.owner_id`'s default, and `LEGACY_OWNER_ID` itself — so
#: an assertion against it cannot tell which one answered, and the owner test passed under a
#: hardcoded `return "owner"`. A distinct value makes the assertion discriminating. Found by an
#: independent security review, 2026-08-11.
OWNER = "acct-7"


def _store(session, owner_id: str):
    account_id = f"account.{owner_id}"
    if session.get(BrokerAccount, account_id) is None:
        session.add(BrokerAccount(
            broker_account_id=account_id, owner_id=owner_id, broker="kite",
            external_account_id=owner_id, display_name=owner_id))
        session.flush()
    return OwnedConnectionStore(
        session, owner_id=owner_id, broker_account_id=account_id)


@pytest.fixture()
def client(monkeypatch):
    init_db(reset=True)
    with SessionLocal() as session:
        _store(session, OWNER)
        session.commit()
    monkeypatch.setattr(get_settings(), "owner_id", OWNER)
    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


@pytest.fixture()
def vault_key(monkeypatch):
    monkeypatch.setenv(vault.ENV_KEY, KEY)
    return KEY


def _rows(owner: str = OWNER) -> list[BrokerConnection]:
    with SessionLocal() as s:
        return _store(s, owner).list(include_revoked=True)


def _create(client, **kw) -> dict:
    body = {"broker": "kite", "scope": "kite:main", "label": "primary",
            "broker_account_id": f"account.{OWNER}"} | kw
    res = client.post("/api/connections", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ── the registry, as the operator sees it ─────────────────────────────────

def test_broker_list_reports_planned_brokers_as_planned_with_their_documentation(client):
    """Hiding the planned rows would make "not yet" indistinguishable from "never heard of it"."""
    body = client.get("/api/brokers").json()["brokers"]
    by_key = {b["key"]: b for b in body}
    assert by_key["kite"]["status"] == "supported"
    assert by_key["angelone"]["status"] == "planned"
    assert by_key["angelone"]["docs_url"].startswith("https://")


def test_broker_list_separates_the_data_and_execution_roles(client):
    """"Supported" does not mean "can execute". Upstox is supported and serves data only, and a
    caller choosing an execution broker needs to see that before it creates the connection."""
    by_key = {b["key"]: b for b in client.get("/api/brokers").json()["brokers"]}
    assert by_key["kite"]["roles"] == {"data": True, "execution": True}
    assert by_key["upstox"]["roles"]["data"] is True
    assert by_key["upstox"]["roles"]["execution"] is False


# ── create ────────────────────────────────────────────────────────────────

def test_a_created_connection_is_persisted_under_the_owner_the_engine_reads(client):
    """The trap this pins: with auth off the principal id is `anonymous-owner`, and keying the
    row on it would file it under an owner `configured_execution_connection` never queries — a
    connection that exists, looks right in the API, and is invisible to the engine."""
    assert get_settings().api_token == ""          # auth off: the default posture
    created = _create(client)
    assert created["owner_id"] == OWNER
    assert created["owner_id"] != LEGACY_OWNER_ID, (
        "the fixture must configure a NON-default owner, or this assertion cannot distinguish "
        "`owner_id_for` from the model's column default")
    assert [r.id for r in _rows()] == [created["id"]]


def test_connection_creation_uses_the_explicit_owned_account_not_an_exact_one_heuristic(client):
    """Adding a second owned account must not make the selected account ambiguous."""
    second = f"account.{OWNER}.second"
    with SessionLocal() as s:
        s.add(BrokerAccount(broker_account_id=second, owner_id=OWNER, broker="kite",
                            external_account_id="second", display_name="Second"))
        s.commit()

    created = _create(client, broker_account_id=second)
    assert created["broker_account_id"] == second

    # A caller cannot bind a connection to somebody else's account merely by
    # knowing its durable account id.
    with SessionLocal() as s:
        s.add(BrokerAccount(broker_account_id="account.alice", owner_id="alice", broker="kite",
                            external_account_id="alice", display_name="Alice"))
        s.commit()
    refused = client.post("/api/connections", json={
        "broker": "kite", "scope": "kite:foreign", "broker_account_id": "account.alice"})
    assert refused.status_code == 404


def test_connection_creation_refuses_an_owned_account_for_a_different_broker(client):
    """An account id is not sufficient: the connection adapter must match it."""
    with SessionLocal() as s:
        s.add(BrokerAccount(broker_account_id="account.dhan", owner_id=OWNER, broker="dhan",
                            external_account_id="dhan", display_name="Dhan"))
        s.commit()
    response = client.post("/api/connections", json={
        "broker": "kite", "scope": "kite:wrong-account", "broker_account_id": "account.dhan"})
    assert response.status_code == 404


def test_a_new_connection_holds_no_credential(client):
    assert _create(client)["has_credential"] is False


def test_a_planned_broker_is_refused_at_create_naming_its_documentation(client):
    """A row naming a broker with no adapter looks configured and can never work."""
    res = client.post("/api/connections",
                      json={"broker": "angelone", "scope": "angel:main",
                            "broker_account_id": f"account.{OWNER}"})
    assert res.status_code == 400
    assert "planned" in res.json()["detail"]
    assert _rows() == []


def test_an_unknown_broker_is_refused_at_create(client):
    res = client.post("/api/connections",
                      json={"broker": "not-a-broker", "scope": "x:main",
                            "broker_account_id": f"account.{OWNER}"})
    assert res.status_code == 400
    assert _rows() == []


def test_a_duplicate_scope_for_one_owner_is_a_conflict_not_a_server_error(client):
    """Two connections sharing a scope make `ExecutionIntent.connection_scope` ambiguous, and
    that column is what restart recovery matches on."""
    _create(client)
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main",
                            "broker_account_id": f"account.{OWNER}"})
    assert res.status_code == 409


def test_a_capability_outside_the_vocabulary_is_refused(client):
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main",
                            "broker_account_id": f"account.{OWNER}",
                            "capabilities": ["teleportation"]})
    assert res.status_code == 400


def test_an_unknown_field_is_refused_rather_than_ignored(client):
    """An ignored field means the row is not what the caller asked for. `owner_id` is the one
    that matters: a caller supplying it must be refused, not quietly overridden."""
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main", "owner_id": "alice"})
    assert res.status_code == 422


# ── the credential ────────────────────────────────────────────────────────

def test_a_stored_credential_is_encrypted_and_never_comes_back_out(client, vault_key):
    created = _create(client)
    token = "live-access-token-abcdef"
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {"access_token": token}})
    assert res.status_code == 200
    assert res.json()["has_credential"] is True
    assert token not in res.text

    with SessionLocal() as s:
        row = s.get(BrokerConnection, created["id"])
        assert row.credential_ciphertext and token not in row.credential_ciphertext
        assert vault.unseal(row.credential_ciphertext) == {"access_token": token}

    # There is no route that reads it back, and the listing does not carry it either.
    assert token not in client.get("/api/connections").text
    assert token not in client.get(f"/api/connections/{created['id']}").text


def test_no_response_ever_carries_the_ciphertext_field(client, vault_key):
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"access_token": "t"}})
    for res in (client.get("/api/connections"),
                client.get(f"/api/connections/{created['id']}")):
        assert "credential_ciphertext" not in res.text
        assert "credential_key_id" not in res.text


def test_a_missing_vault_key_refuses_rather_than_reporting_a_success(client, monkeypatch):
    """The failure shape this file exists to prevent: a 200 with the credential silently
    dropped, and an operator who believes the connection is authenticated."""
    monkeypatch.delenv(vault.ENV_KEY, raising=False)
    monkeypatch.setattr(get_settings(), "credential_key", "", raising=False)
    created = _create(client)
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {"access_token": "t"}})
    assert res.status_code == 503
    with SessionLocal() as s:
        assert s.get(BrokerConnection, created["id"]).credential_ciphertext is None


def test_an_oversized_credential_bundle_is_refused(client, vault_key):
    created = _create(client)
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {f"k{i}": "v" for i in range(30)}})
    assert res.status_code == 422
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {"access_token": "x" * 5000}})
    assert res.status_code == 422


def test_an_empty_credential_bundle_is_refused(client, vault_key):
    created = _create(client)
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {}})
    assert res.status_code == 422


# ── revoke ────────────────────────────────────────────────────────────────

def test_revoke_keeps_the_row_and_destroys_the_credential(client, vault_key):
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"access_token": "t"}})

    body = client.delete(f"/api/connections/{created['id']}").json()
    assert body["status"] == "revoked" and body["revoked_at"]
    assert body["has_credential"] is False

    with SessionLocal() as s:
        row = s.get(BrokerConnection, created["id"])
        assert row is not None, "revocation must not delete the audit fact"
        assert row.credential_ciphertext is None

    # Gone from the default listing, still visible when asked for.
    assert client.get("/api/connections").json()["connections"] == []
    assert len(client.get("/api/connections",
                          params={"include_revoked": True}).json()["connections"]) == 1


# ── cross-owner isolation ─────────────────────────────────────────────────

def _foreign_connection() -> int:
    with SessionLocal() as s:
        row = _store(s, "alice").create(broker="kite", scope="kite:alice")
        s.commit()
        return row.id


@pytest.mark.parametrize("call", [
    lambda c, i: c.get(f"/api/connections/{i}"),
    lambda c, i: c.post(f"/api/connections/{i}/credential",
                        json={"secrets": {"access_token": "t"}}),
    lambda c, i: c.delete(f"/api/connections/{i}"),
])
def test_another_owners_connection_is_not_found_on_every_route(client, vault_key, call):
    """404, not 403: a 403 confirms the id exists, and an id is guessable."""
    foreign = _foreign_connection()
    assert call(client, foreign).status_code == 404
    with SessionLocal() as s:
        row = s.get(BrokerConnection, foreign)
        assert row.owner_id == "alice" and row.status == "active"
        assert row.credential_ciphertext is None


def test_the_listing_shows_only_this_owners_connections(client):
    _foreign_connection()
    mine = _create(client)
    listed = client.get("/api/connections").json()["connections"]
    assert [r["id"] for r in listed] == [mine["id"]]


# ── auth ──────────────────────────────────────────────────────────────────

def test_the_connection_surface_requires_the_token_when_auth_is_enabled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    assert client.get("/api/connections").status_code == 401
    assert client.post("/api/connections",
                       json={"broker": "kite", "scope": "kite:main"}).status_code == 401
    assert client.get("/api/brokers").status_code == 401
    ok = client.get("/api/connections",
                    headers={"Authorization": "Bearer secret-token"})
    assert ok.status_code == 200


def test_an_authenticated_owner_and_an_anonymous_one_are_the_same_owner(client, monkeypatch):
    """Both principals are the same human. If they resolved to different `owner_id` values, the
    connections an operator created on the tailnet box would vanish the day auth was switched on."""
    created = _create(client)
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    listed = client.get("/api/connections",
                        headers={"Authorization": "Bearer secret-token"}).json()
    assert [r["id"] for r in listed["connections"]] == [created["id"]]


def test_a_non_owner_principal_has_no_owner_identity_to_fall_back_to():
    """There is no second principal kind today, and this is the guard for the day there is: a
    service or a customer principal must not acquire the owner's connections by falling through
    a default. `owner_id_for` refuses rather than returning the configured owner."""
    from app.api.principal import Forbidden, Principal, owner_id_for

    service = Principal(id="ingest", kind="service", scopes=frozenset({"read:status"}))
    with pytest.raises(Forbidden):
        owner_id_for(service)
    with pytest.raises(Forbidden):
        owner_id_for(None)


# ── the engine reads what the API wrote ───────────────────────────────────

def test_a_connection_created_over_http_is_the_one_the_engine_resolves(client, vault_key):
    """The whole point of the route. `configured_execution_connection` reads this table on every
    engine start; before this module there was no way to write a row into it."""
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"access_token": "morning-token"}})
    with SessionLocal() as s:
        conn = _store(s, OWNER).live_connection(created["id"])
    assert conn.broker == "kite" and conn.scope == "kite:main"
    assert conn.token_source() == "morning-token"


def test_a_revoked_connection_stops_producing_a_token(client, vault_key):
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"access_token": "morning-token"}})
    with SessionLocal() as s:
        conn = _store(s, OWNER).live_connection(created["id"])
    assert conn.token_source() == "morning-token"

    client.delete(f"/api/connections/{created['id']}")
    # The Connection outlives the request that revoked it; the late read is what makes the
    # revocation take effect at the next order rather than at the next restart.
    assert conn.token_source() is None


def test_declared_capabilities_round_trip(client):
    created = _create(client, capabilities=["historical_data", "live_quotes"])
    assert sorted(created["capabilities"]) == ["historical_data", "live_quotes"]
    with SessionLocal() as s:
        row = s.get(BrokerConnection, created["id"])
        assert sorted(json.loads(row.capabilities_json)) == ["historical_data", "live_quotes"]


# ── findings from the independent security review, 2026-08-11 ─────────────

def test_a_revoked_connection_cannot_be_re_credentialed(client, vault_key):
    """Revocation must stay revoked. Before this guard one POST undid it: the row kept its
    `revoked` status while acquiring fresh ciphertext, so `revoke`'s promise that a revoked
    connection is not a credential at rest lasted exactly until the next request — on a database
    that `deploy.sh` rsyncs to a laptop — and `last_authenticated_at` ended up later than
    `revoked_at`, which is an audit record contradicting itself."""
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"access_token": "first"}})
    client.delete(f"/api/connections/{created['id']}")

    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {"access_token": "resurrected"}})
    assert res.status_code == 404
    with SessionLocal() as s:
        row = s.get(BrokerConnection, created["id"])
        assert row.status == "revoked"
        assert row.credential_ciphertext is None
        assert row.last_authenticated_at <= row.revoked_at


def test_an_oversized_credential_field_NAME_is_refused(client, vault_key):
    """The bound checked `.values()` only, so field names were unbounded — a single
    two-million-character key stored a 2.6 MB ciphertext on a 1 GB droplet."""
    created = _create(client)
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {"k" * 5000: "v"}})
    assert res.status_code == 422
    with SessionLocal() as s:
        assert s.get(BrokerConnection, created["id"]).credential_ciphertext is None


def test_a_rejected_credential_is_not_echoed_back_in_the_validation_body(client, vault_key):
    """FastAPI's default 422 envelope carries pydantic's `input` — the value that failed. On this
    one route that value is a live broker token, and the body reaches browser network logs, proxy
    error logs and client-side error reporters. `loc` and `msg` survive; the value does not."""
    created = _create(client)
    secret = "SUPERSECRETTOKEN-zzz"
    res = client.post(f"/api/connections/{created['id']}/credential",
                      json={"secrets": {"access_token": [secret]}})   # wrong type on purpose
    assert res.status_code == 422
    assert secret not in res.text
    assert "input" not in res.text
    # The caller must still learn WHICH field was wrong — a 422 that says nothing is not a fix.
    assert "access_token" in res.text

    # The versioned mirror normalises through `unversioned_path`, so it must strip too.
    v1 = client.post(f"/api/v1/connections/{created['id']}/credential",
                     json={"secrets": {"access_token": [secret]}})
    assert v1.status_code == 422 and secret not in v1.text


def test_other_routes_keep_the_default_validation_envelope(client):
    """The strip is scoped to the credential route. Everywhere else the echo is a helpful
    diagnostic, and silently changing 45 routes' error shape is not what this fix is for."""
    res = client.post("/api/connections", json={"broker": "kite", "scope": 12345})
    assert res.status_code == 422
    assert "input" in res.text


def test_a_whitespace_padded_scope_is_refused(client):
    """`"kite:main "` and `"kite:main"` are different strings to the unique constraint, so the
    409 never fires and the owner ends up holding two visually identical scopes — worse than two
    literally identical ones, because `ExecutionIntent.connection_scope` is what restart recovery
    matches on. Refused rather than stripped, so the stored record is what the caller asked for."""
    _create(client)
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main "})
    assert res.status_code == 422
    assert len(_rows()) == 1


def test_the_capabilities_list_is_bounded(client):
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main",
                            "capabilities": ["historical_data"] * 5000})
    assert res.status_code == 422


def test_the_policy_refuses_a_foreign_row_even_if_the_store_filter_hands_one_over():
    """The second layer, proven independently of the first.

    `_authorized` exists because the store's owner filter and `is_allowed` are two different
    checks on the same fact: one is data scoping, one is policy. Through the HTTP surface the
    store's filter always wins the race, so no request can distinguish them — which means the
    policy layer was untestable and, by this repo's own standard, unproven. A mutation sweep
    found exactly that: replacing the loaded row with `None` broke nothing.

    So the second layer is tested where it can actually be observed — with a store that hands
    back a row belonging to someone else, which is what a dropped owner filter would do.
    """
    from app.api.connection_routes import _authorized
    from app.api.principal import OWNER

    class LeakyStore:
        """A store whose owner filter has been lost in a refactor."""
        def get(self, connection_id):
            row = BrokerConnection(owner_id='owner', broker_account_id='account.default', id=connection_id, broker="kite", scope="kite:x")
            row.owner_id = "someone-else"
            return row

    with pytest.raises(ConnectionNotFound):
        _authorized(LeakyStore(), OWNER, "read:connection", 1)


def test_a_non_owner_principal_is_refused_by_the_policy_itself():
    """Rule 1 of `is_allowed`, guarded directly.

    `owner_id_for` has its own refusal and it is tested, but `is_allowed` now checks
    `is_owner` BEFORE ever reaching it — so the two guards are independent and only one of them
    was pinned. A mutation that removed `is_allowed`'s check stayed green.
    """
    from app.api.principal import Principal, is_allowed

    service = Principal(id="ingest", kind="service", scopes=frozenset({"read:status"}))
    assert is_allowed(service, "read:connections") is False
    assert is_allowed(service, "read:connections", None) is False


# ── acquiring a credential, per connection (2026-08-11) ───────────────────

def _kite_with_app_keys(client, vault_key) -> dict:
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"api_key": "ak-123", "api_secret": "as-456"}})
    return created


def test_the_login_url_is_built_from_THIS_connections_app_keys(client, vault_key, monkeypatch):
    """No fallback to the process-wide `KITE_API_KEY`. A default that reaches for the owner's
    own Zerodha app registration is a cross-tenant credential path wearing a convenience."""
    monkeypatch.setattr(get_settings(), "kite_api_key", "PROCESS-WIDE-KEY")
    created = _kite_with_app_keys(client, vault_key)
    res = client.get(f"/api/connections/{created['id']}/login")
    assert res.status_code == 200
    url = res.json()["login_url"]
    assert "ak-123" in url
    assert "PROCESS-WIDE-KEY" not in url


def test_a_connection_with_no_app_keys_is_told_to_store_them(client, vault_key):
    created = _create(client)                       # no credential stored at all
    res = client.get(f"/api/connections/{created['id']}/login")
    assert res.status_code == 400
    assert "api_key" in res.json()["detail"]


def test_a_long_lived_key_broker_refuses_a_login_url_instead_of_inventing_one(client, vault_key):
    """Dhan issues its token in a dashboard. Returning a URL would send the user to a 404 with
    no way to distinguish that from a broker outage."""
    with SessionLocal() as s:
        account = "account.acct-7.dhan"
        s.add(BrokerAccount(broker_account_id=account, owner_id=OWNER, broker="dhan",
                            external_account_id="dhan", display_name="Dhan"))
        s.flush()
        row = OwnedConnectionStore(s, owner_id=OWNER, broker_account_id=account).create(
            broker="dhan", scope="dhan:main")
        s.commit()
        dhan_id = row.id
    res = client.get(f"/api/connections/{dhan_id}/login")
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "dashboard" in detail and "/credential" in detail


def test_the_legacy_connection_session_endpoint_is_retired(client, vault_key, monkeypatch):
    """Dropping the app keys would work until tomorrow morning, when the re-login has nothing to
    authenticate with — a failure that appears once a day and looks like an expired token."""
    import app.providers.broker_auth as ba

    monkeypatch.setattr(ba.KiteAuthenticator, "_client",
                        lambda self, api_key: _FakeKite(api_key))
    created = _kite_with_app_keys(client, vault_key)
    res = client.post(f"/api/connections/{created['id']}/session",
                      json={"request_token": "one-time-rt"})
    assert res.status_code == 404


class _FakeKite:
    def __init__(self, api_key):
        self.api_key = api_key

    def login_url(self):
        return f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"

    def generate_session(self, request_token, api_secret):
        assert request_token == "one-time-rt" and api_secret == "as-456"
        return {"access_token": "exchanged-access-token", "user_id": "AB1234"}


def _oauth_principal(user_id: str, session_id: str, bearer: str) -> Principal:
    from app.db.models import Membership, Organization, User, UserSession

    with SessionLocal() as session:
        if session.get(Organization, OWNER) is None:
            session.add(Organization(organization_id=OWNER, name=OWNER))
        session.add(User(
            user_id=user_id, email_normalized=f"{user_id}@example.test",
            display_name=user_id,
        ))
        session.flush()
        session.add_all([
            Membership(organization_id=OWNER, user_id=user_id, role="owner"),
            UserSession(
                session_id=session_id, token_digest=token_digest(bearer),
                user_id=user_id, organization_id=OWNER, issued_at=dt.datetime.now(),
                expires_at=dt.datetime.now() + dt.timedelta(hours=1),
            ),
        ])
        session.commit()
    return Principal(
        id=user_id, kind="user", scopes=frozenset({"*"}), user_id=user_id,
        organization_id=OWNER, role="owner", session_id=session_id,
    )


def _connection_change_events(connection_id: int):
    event = execution_outbox().models.Event
    with SessionLocal() as session:
        return list(session.scalars(select(event).where(
            event.event_type == "execution.connection.changed",
            event.aggregate_type == "broker_connection",
            event.aggregate_id == str(connection_id),
        ).order_by(event.plane_offset)))


def test_durable_user_gets_closed_data_only_lifecycle_on_both_mounts(
        client, vault_key):
    principal = _oauth_principal("data-user", "data-session", "data-bearer")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        created = client.post("/api/connections", json={"label": "Research feed"})
        assert created.status_code == 201, created.text
        body = created.json()
        handle = body["connection_handle"]
        assert body == {
            "connection_handle": handle,
            "provider": "kite",
            "role": "DATA",
            "label": "Research feed",
            "capabilities": ["historical_data", "live_quotes"],
            "connection_status": "CREDENTIAL_REQUIRED",
            "credential_present": False,
            "auth_method": "DAILY_OAUTH",
            "last_credential_replaced_at": None,
            "credential_expiry": "UNVERIFIED",
            "rate_quota": "UNVERIFIED",
        }
        forbidden = {
            "owner_id", "broker_account_id", "scope", "id", "ciphertext", "credential_key_id",
            "live_execution", "account_funds", "account_positions", "account_equity", "order_margin",
        }
        assert forbidden.isdisjoint(body)
        assert client.post("/api/v1/connections", json={"label": "duplicate"}).status_code == 409
        assert client.get(f"/api/v1/connections/{handle}").json() == body
        assert client.get("/api/connections").json() == {"connections": [body]}

        rejected = client.post(f"/api/connections/{handle}/credential", json={
            "secrets": {"access_token": "must-not-enter-headlessly"}})
        assert rejected.status_code == 422
        stored = client.post(f"/api/v1/connections/{handle}/credential", json={
            "secrets": {"api_key": "ak-123", "api_secret": "as-456"}})
        assert stored.status_code == 200
        assert stored.json()["connection_status"] == "PRESENT_UNVERIFIED"
        assert "ak-123" not in stored.text and "as-456" not in stored.text
        assert client.get(f"/api/connections/{handle}/login").status_code == 409

        revoked = client.delete(f"/api/v1/connections/{handle}")
        assert revoked.status_code == 200
        assert revoked.json()["connection_status"] == "REVOKED"
        assert revoked.json()["credential_present"] is False
        assert client.get(f"/api/connections/{handle}").status_code == 404
        assert client.post(f"/api/connections/{handle}/credential", json={
            "secrets": {"api_key": "x", "api_secret": "y"}}).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_data_only_oauth_is_session_bound_single_use_and_returns_closed_projection(
        client, vault_key, monkeypatch):
    import app.providers.broker_auth as ba

    principal = _oauth_principal("data-oauth-user", "data-oauth-session", "data-oauth-bearer")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        monkeypatch.setattr(ba.KiteAuthenticator, "_client", lambda self, key: _FakeKite(key))
        created = client.post("/api/connections", json={"label": "OAuth feed"}).json()
        handle = created["connection_handle"]
        keys = client.post(f"/api/connections/{handle}/credential", json={
            "secrets": {"api_key": "ak-123", "api_secret": "as-456"}})
        assert keys.status_code == 200
        started = client.post(f"/api/v1/connections/{handle}/oauth/initiate")
        assert started.status_code == 200, started.text
        state = parse_qs(urlsplit(started.json()["login_url"]).query)["state"][0]
        from app.db.models import OAuthCallbackState
        with SessionLocal() as session:
            persisted = session.scalars(select(OAuthCallbackState).where(
                OAuthCallbackState.connection_id == int(handle))).one()
            assert persisted.expires_at - persisted.created_at == dt.timedelta(minutes=10)
        callback = client.get("/api/oauth/callback", params={
            "state": state, "request_token": "one-time-rt"})
        assert callback.status_code == 200, callback.text
        assert callback.json()["role"] == "DATA"
        assert callback.json()["connection_status"] == "PRESENT_UNVERIFIED"
        assert "user_id" not in callback.json() and "access_token" not in callback.text
        assert client.get("/api/v1/oauth/callback", params={
            "state": state, "request_token": "one-time-rt"}).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_data_only_connection_is_organization_local_and_request_cannot_select_authority(client):
    principal = _oauth_principal("data-authority-user", "data-authority-session", "data-authority")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        for field, value in {
            "owner_id": "other", "organization_id": "other", "user_id": "other", "role": "execution",
        }.items():
            response = client.post("/api/connections", json={"label": "x", field: value})
            assert response.status_code == 422
        created = client.post("/api/connections", json={"label": "local"}).json()
        foreign = _foreign_connection()
        assert client.get(f"/api/connections/{foreign}").status_code == 404
        assert client.delete(f"/api/connections/{foreign}").status_code == 404
        assert client.get(f"/api/connections/{created['connection_handle']}").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_concurrent_data_creates_converge_to_one_row(client):
    import concurrent.futures

    principal = _oauth_principal("data-race-user", "data-race-session", "data-race")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        def create_one(label):
            return client.post("/api/connections", json={"label": label}).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(create_one, ("one", "two")))
        assert statuses == [201, 409]
        with SessionLocal() as session:
            rows = session.scalars(select(BrokerConnection).where(
                BrokerConnection.owner_id == OWNER,
                BrokerConnection.scope.like("strategy-os-v0:data:%"),
                BrokerConnection.status == "active",
            )).all()
        assert len(rows) == 1
    finally:
        app.dependency_overrides.clear()


def test_data_oauth_state_and_connection_resources_remain_bounded(client, vault_key):
    from app.db.models import OAuthCallbackState

    principal = _oauth_principal("data-bound-user", "data-bound-session", "data-bound")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        created = client.post("/api/connections", json={"label": "bounded"}).json()
        handle = created["connection_handle"]
        client.post(f"/api/connections/{handle}/credential", json={
            "secrets": {"api_key": "ak-123", "api_secret": "as-456"}})
        states = []
        for _ in range(6):
            response = client.post(f"/api/connections/{handle}/oauth/initiate")
            assert response.status_code == 200
            states.append(parse_qs(urlsplit(response.json()["login_url"]).query)["state"][0])
        with SessionLocal() as session:
            rows = session.scalars(select(OAuthCallbackState).where(
                OAuthCallbackState.connection_id == int(handle))).all()
            active = [row for row in rows if row.revoked_at is None and row.consumed_at is None]
        assert len(rows) <= 2 and len(active) == 1
        assert client.get("/api/connections").json()["connections"] == [
            client.get(f"/api/connections/{handle}").json()]
        assert client.get("/api/oauth/callback", params={
            "state": states[0], "request_token": "never-exchanged"}).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_concurrent_data_oauth_initiation_converges_to_one_usable_state(
        client, vault_key, monkeypatch):
    import concurrent.futures
    import app.providers.broker_auth as ba
    from app.db.models import OAuthCallbackState

    principal = _oauth_principal("init-race-user", "init-race-session", "init-race")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        monkeypatch.setattr(ba.KiteAuthenticator, "_client", lambda self, key: _FakeKite(key))
        created = client.post("/api/connections", json={"label": "race"}).json()
        handle = created["connection_handle"]
        client.post(f"/api/connections/{handle}/credential", json={
            "secrets": {"api_key": "ak-123", "api_secret": "as-456"}})

        def initiate(_):
            return client.post(f"/api/connections/{handle}/oauth/initiate")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(initiate, range(2)))
        assert all(response.status_code == 200 for response in responses)
        states = [parse_qs(urlsplit(response.json()["login_url"]).query)["state"][0]
                  for response in responses]
        with SessionLocal() as session:
            rows = session.scalars(select(OAuthCallbackState).where(
                OAuthCallbackState.connection_id == int(handle))).all()
        assert len([row for row in rows if row.revoked_at is None and row.consumed_at is None]) == 1
        callbacks = [client.get("/api/oauth/callback", params={
            "state": state, "request_token": "one-time-rt"}) for state in states]
        assert sorted(response.status_code for response in callbacks) == [200, 400]
    finally:
        app.dependency_overrides.clear()


def test_data_callback_racing_connection_revoke_never_restores_a_credential(
        client, vault_key, monkeypatch):
    import threading
    import app.api.connection_routes as routes

    principal = _oauth_principal("revoke-race-user", "revoke-race-session", "revoke-race")
    app.dependency_overrides[get_principal] = lambda: principal
    entered, release = threading.Event(), threading.Event()

    class BlockingAuthenticator:
        def login_url(self, secrets):
            assert secrets["api_key"] == "ak-123"
            return "https://kite.example.test/login"
        def exchange(self, secrets, request_token):
            assert secrets["api_secret"] == "as-456" and request_token == "one-time-rt"
            entered.set()
            assert release.wait(timeout=5)
            return {**secrets, "access_token": "must-not-survive"}

    try:
        created = client.post("/api/connections", json={"label": "revoke race"}).json()
        handle = created["connection_handle"]
        client.post(f"/api/connections/{handle}/credential", json={
            "secrets": {"api_key": "ak-123", "api_secret": "as-456"}})
        monkeypatch.setattr(routes, "_authenticator", lambda _broker: BlockingAuthenticator())
        started = client.post(f"/api/connections/{handle}/oauth/initiate")
        state = parse_qs(urlsplit(started.json()["login_url"]).query)["state"][0]
        result = {}
        worker = threading.Thread(target=lambda: result.setdefault("response", client.get(
            "/api/oauth/callback", params={"state": state, "request_token": "one-time-rt"})))
        worker.start()
        assert entered.wait(timeout=3)
        revoked = client.delete(f"/api/connections/{handle}")
        assert revoked.status_code == 200
        release.set()
        worker.join(timeout=5)
        assert not worker.is_alive() and result["response"].status_code == 400
        with SessionLocal() as session:
            row = session.get(BrokerConnection, int(handle))
            assert row.status == "revoked" and row.credential_ciphertext is None
    finally:
        release.set()
        app.dependency_overrides.clear()


def test_data_route_query_memory_and_response_ceilings_are_measured(client):
    import tracemalloc
    from sqlalchemy import event
    from app.db.session import engine

    principal = _oauth_principal("resource-user", "resource-session", "resource")
    app.dependency_overrides[get_principal] = lambda: principal
    queries = []
    def count_query(*_args):
        queries.append(1)
    try:
        created = client.post("/api/connections", json={"label": "measured"})
        event.listen(engine, "before_cursor_execute", count_query)
        tracemalloc.start()
        listed = client.get("/api/connections")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        event.remove(engine, "before_cursor_execute", count_query)
        assert listed.status_code == 200
        assert len(queries) <= 2
        assert peak <= 8 * 1024 * 1024
        assert len(listed.content) <= 1024 and len(created.content) <= 1024
        assert client.post("/api/connections", json={"label": "x" * 81}).status_code == 422
        print({"list_queries": len(queries), "peak_bytes": peak,
               "list_response_bytes": len(listed.content)})
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        if event.contains(engine, "before_cursor_execute", count_query):
            event.remove(engine, "before_cursor_execute", count_query)
        app.dependency_overrides.clear()


def test_removed_membership_cannot_read_or_mutate_its_data_connection(
        client, monkeypatch):
    from app.db.models import Membership

    bearer = "removed-data-bearer"
    principal = _oauth_principal("removed-data-user", "removed-data-session", bearer)
    app.dependency_overrides[get_principal] = lambda: principal
    created = client.post("/api/connections", json={"label": "withdrawn"}).json()
    handle = created["connection_handle"]
    app.dependency_overrides.clear()
    monkeypatch.setattr(get_settings(), "api_token", "legacy-header-token")
    with SessionLocal() as session:
        session.get(Membership, (OWNER, principal.user_id)).status = "revoked"
        session.commit()
    headers = {"Authorization": f"Bearer {bearer}"}
    assert client.get(f"/api/connections/{handle}", headers=headers).status_code == 401
    assert client.delete(f"/api/connections/{handle}", headers=headers).status_code == 401
    with SessionLocal() as session:
        row = session.get(BrokerConnection, int(handle))
        assert row.status == "active" and row.credential_ciphertext is None


def test_real_browser_cookie_origin_and_csrf_gate_the_data_routes(monkeypatch):
    """Exercise Q01's actual cookie resolver and middleware, not a dependency override."""
    from app.accounts import browser_auth
    import app.main as main_module

    origin = "https://testserver"
    settings = get_settings()
    for name, value in {
        "browser_auth_enabled": True,
        "browser_auth_origin": origin,
        "browser_auth_counter_secret": "b2" * 32,
        "auth_disabled": False,
        "api_token": "",
        "release_profile": "v0_research_signal",
        "release_service_role": "api",
    }.items():
        monkeypatch.setattr(settings, name, value)
    init_db(reset=True)
    # Capability remains BLOCKED in product truth. This test-only bypass reaches
    # the route solely to prove the already-accepted cookie Origin/CSRF boundary.
    monkeypatch.setattr(main_module, "denied_route", lambda *_args, **_kwargs: None)
    invite = browser_auth.create_invite("cookie-data@example.test")
    browser = TestClient(app, base_url=origin)
    try:
        enrolled = browser.post("/api/v1/auth/enroll", headers={"Origin": origin}, json={
            "email": "cookie-data@example.test",
            "password": "a synthetic sufficiently long password",
            "display_name": "Cookie Data",
            "invitation": invite.token,
        })
        assert enrolled.status_code == 200
        bootstrap = browser.get("/api/v1/auth/session")
        assert bootstrap.status_code == 200
        state = bootstrap.json()
        organization_id = state["memberships"][0]["organization_id"]
        with SessionLocal() as session:
            session.add(BrokerAccount(
                broker_account_id=f"account.{organization_id}", owner_id=organization_id,
                broker="kite", external_account_id="cookie-data", display_name="Cookie Data"))
            session.commit()

        assert browser.post("/api/connections", json={"label": "missing origin"}).status_code == 403
        assert browser.post("/api/connections", headers={"Origin": "https://evil.test"},
                            json={"label": "wrong origin"}).status_code == 403
        assert browser.post("/api/connections", headers={"Origin": origin},
                            json={"label": "missing csrf"}).status_code == 403
        created = browser.post("/api/connections", headers={
            "Origin": origin, "x-strategy-csrf": state["csrf"]},
            json={"label": "cookie data"})
        assert created.status_code == 201, created.text
        handle = created.json()["connection_handle"]
        same_owner = browser.get(f"/api/v1/connections/{handle}")
        assert same_owner.status_code == 200 and same_owner.json()["role"] == "DATA"
    finally:
        browser.close()


def test_the_retired_exchange_endpoint_never_reaches_the_provider(client, vault_key, monkeypatch):
    """Kite's exception messages have been observed to echo request parameters, and this one
    reaches an API response and the /api/logs ring buffer. Only the type name crosses."""
    import app.providers.broker_auth as ba

    class _Angry:
        def __init__(self, api_key): pass
        def login_url(self): return "x"
        def generate_session(self, request_token, api_secret):
            raise ValueError(f"bad checksum for api_secret={api_secret} rt={request_token}")

    monkeypatch.setattr(ba.KiteAuthenticator, "_client", lambda self, k: _Angry(k))
    created = _kite_with_app_keys(client, vault_key)
    res = client.post(f"/api/connections/{created['id']}/session",
                      json={"request_token": "one-time-rt"})
    assert res.status_code == 404
    assert "as-456" not in res.text and "one-time-rt" not in res.text


def test_the_legacy_session_exchange_route_is_absent(client, monkeypatch):
    """`/api/session` is an auth-exempt GET because Zerodha redirects to it directly. That is
    acceptable for one hard-coded account and not here, where the request names WHICH connection
    to write a credential into — an unauthenticated GET taking an id would let anyone who could
    reach the port bind a credential to another owner's connection."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    assert client.post("/api/connections/1/session",
                       json={"request_token": "x"}).status_code == 401
    assert client.get("/api/connections/1/session",
                      headers={"Authorization": "Bearer secret-token"}).status_code == 404


def test_another_owners_connection_cannot_be_logged_in_or_exchanged(client, vault_key):
    foreign = _foreign_connection()
    assert client.get(f"/api/connections/{foreign}/login").status_code == 404
    assert client.post(f"/api/connections/{foreign}/session",
                       json={"request_token": "x"}).status_code == 404


def test_a_broker_with_no_registered_login_flow_refuses_with_its_docs_url(client, vault_key):
    """Upstox is SUPPORTED and DAILY_OAUTH and has a working data adapter — and deliberately no
    authenticator, because writing its token exchange without reading its current documentation
    is how a flow that looks right fails at 06:00. It must refuse and name the documentation,
    not fall through to an AttributeError 500 that reads as a server fault."""
    with SessionLocal() as s:
        account = "account.acct-7.upstox"
        s.add(BrokerAccount(broker_account_id=account, owner_id=OWNER, broker="upstox",
                            external_account_id="upstox", display_name="Upstox"))
        s.flush()
        row = OwnedConnectionStore(s, owner_id=OWNER, broker_account_id=account).create(
            broker="upstox", scope="upstox:data")
        s.commit()
        upstox_id = row.id
    res = client.get(f"/api/connections/{upstox_id}/login")
    assert res.status_code == 501
    detail = res.json()["detail"]
    assert "upstox.com" in detail

    exchange = client.post(f"/api/connections/{upstox_id}/session",
                           json={"request_token": "x"})
    assert exchange.status_code == 404


def test_oauth_callback_binds_one_durable_session_connection_and_is_single_use(
        client, vault_key, monkeypatch):
    """A callback needs opaque state, not a connection id or bearer header."""
    import app.providers.broker_auth as ba

    user_id, session_id = "oauth-user", "oauth-session"
    principal = _oauth_principal(user_id, session_id, "oauth-bearer")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        monkeypatch.setattr(ba.KiteAuthenticator, "_client", lambda self, key: _FakeKite(key))
        created = _kite_with_app_keys(client, vault_key)
        started = client.post(f"/api/connections/{created['id']}/oauth/initiate")
        assert started.status_code == 200, started.text
        state = parse_qs(urlsplit(started.json()["login_url"]).query)["state"][0]
        before = {event.event_id for event in _connection_change_events(created["id"])}
        callback = client.get("/api/oauth/callback", params={
            "state": state, "request_token": "one-time-rt"})
        assert callback.status_code == 200, callback.text
        assert callback.json()["id"] == created["id"]
        appended = [event for event in _connection_change_events(created["id"])
                    if event.event_id not in before]
        assert len(appended) == 1
        assert (appended[0].owner_id, appended[0].broker_account_id) == (
            OWNER, created["broker_account_id"])
        assert json.loads(appended[0].payload_json) == {
            "projection": "connections", "state": "ready", "ready": True,
        }
        assert client.get("/api/oauth/callback", params={
            "state": state, "request_token": "one-time-rt"}).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_oauth_callback_rolls_back_credential_and_readiness_event_together(
        client, vault_key, monkeypatch):
    """Failure after the callback write must commit neither credential nor readiness fact."""
    import app.providers.broker_auth as ba

    user_id, session_id = "oauth-rollback-user", "oauth-rollback-session"
    principal = _oauth_principal(user_id, session_id, "oauth-rollback-bearer")
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        monkeypatch.setattr(ba.KiteAuthenticator, "_client", lambda self, key: _FakeKite(key))
        created = _kite_with_app_keys(client, vault_key)
        started = client.post(f"/api/connections/{created['id']}/oauth/initiate")
        state = parse_qs(urlsplit(started.json()["login_url"]).query)["state"][0]
        with SessionLocal() as session:
            before_ciphertext = session.get(BrokerConnection, created["id"]).credential_ciphertext
        before_events = {event.event_id for event in _connection_change_events(created["id"])}

        def fail_after_callback_write(_self):
            raise RuntimeError("injected callback response failure")

        monkeypatch.setattr(BrokerConnection, "to_dict", fail_after_callback_write)
        with pytest.raises(RuntimeError, match="injected callback response failure"):
            client.get("/api/oauth/callback", params={
                "state": state, "request_token": "one-time-rt"})

        with SessionLocal() as session:
            assert session.get(BrokerConnection, created["id"]).credential_ciphertext == before_ciphertext
        assert {event.event_id for event in _connection_change_events(created["id"])} == before_events
    finally:
        app.dependency_overrides.clear()


def test_oauth_callback_spends_state_before_blocking_broker_exchange(
        client, vault_key, monkeypatch):
    """External broker I/O must hold no DB writer lane or reusable callback state."""
    import threading

    import app.api.connection_routes as routes
    from app.db.models import Membership, Organization, User, UserSession

    user_id, session_id = "oauth-slow-user", "oauth-slow-session"
    with SessionLocal() as s:
        if s.get(Organization, OWNER) is None:
            s.add(Organization(organization_id=OWNER, name=OWNER))
        s.add(User(user_id=user_id, email_normalized="oauth-slow@example.test",
                   display_name="OAuth slow"))
        s.flush()
        s.add_all([
            Membership(organization_id=OWNER, user_id=user_id, role="owner"),
            UserSession(session_id=session_id, token_digest=token_digest("oauth-slow-bearer"),
                        user_id=user_id, organization_id=OWNER, issued_at=dt.datetime.now(),
                        expires_at=dt.datetime.now() + dt.timedelta(hours=1)),
        ])
        s.commit()
    principal = Principal(id=user_id, kind="user", scopes=frozenset({"*"}), user_id=user_id,
                          organization_id=OWNER, role="owner", session_id=session_id)
    app.dependency_overrides[get_principal] = lambda: principal
    entered, release = threading.Event(), threading.Event()

    class SlowAuthenticator:
        def initiate(self, *_args, **_kwargs):
            return "https://example.test/login"

        def exchange(self, _secrets, _request_token):
            entered.set()
            assert release.wait(timeout=5)
            return {"access_token": "slow-token"}

    try:
        created = _kite_with_app_keys(client, vault_key)
        started = client.post(f"/api/connections/{created['id']}/oauth/initiate")
        state = parse_qs(urlsplit(started.json()["login_url"]).query)["state"][0]
        monkeypatch.setattr(routes, "_authenticator", lambda _broker: SlowAuthenticator())
        result = {}
        worker = threading.Thread(target=lambda: result.setdefault("response", client.get(
            "/api/oauth/callback", params={"state": state, "request_token": "one-time-rt"})))
        worker.start()
        assert entered.wait(timeout=3)
        duplicate = client.get("/api/oauth/callback", params={
            "state": state, "request_token": "one-time-rt"})
        assert duplicate.status_code == 400
        with SessionLocal() as s:
            organization = s.get(Organization, OWNER)
            organization.name = "writer-proceeded-during-exchange"
            s.commit()
        release.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert result["response"].status_code == 200
    finally:
        release.set()
        app.dependency_overrides.clear()


def test_oauth_callback_revalidates_identity_after_blocking_exchange(
        client, vault_key, monkeypatch):
    """Revocation during provider I/O must prevent the fresh credential write."""
    import threading

    import app.api.connection_routes as routes
    from app.db.models import Membership, Organization, User, UserSession
    from app.providers.connection_store import OwnedConnectionStore

    user_id, session_id = "oauth-revoke-user", "oauth-revoke-session"
    with SessionLocal() as s:
        if s.get(Organization, OWNER) is None:
            s.add(Organization(organization_id=OWNER, name=OWNER))
        s.add(User(user_id=user_id, email_normalized="oauth-revoke@example.test",
                   display_name="OAuth revoke"))
        s.flush()
        s.add_all([
            Membership(organization_id=OWNER, user_id=user_id, role="owner"),
            UserSession(session_id=session_id, token_digest=token_digest("oauth-revoke-bearer"),
                        user_id=user_id, organization_id=OWNER, issued_at=dt.datetime.now(),
                        expires_at=dt.datetime.now() + dt.timedelta(hours=1)),
        ])
        s.commit()
    principal = Principal(id=user_id, kind="user", scopes=frozenset({"*"}), user_id=user_id,
                          organization_id=OWNER, role="owner", session_id=session_id)
    app.dependency_overrides[get_principal] = lambda: principal
    entered, release = threading.Event(), threading.Event()

    class SlowAuthenticator:
        def exchange(self, _secrets, _request_token):
            entered.set()
            assert release.wait(timeout=5)
            return {"access_token": "must-not-persist"}

    try:
        created = _kite_with_app_keys(client, vault_key)
        started = client.post(f"/api/connections/{created['id']}/oauth/initiate")
        state = parse_qs(urlsplit(started.json()["login_url"]).query)["state"][0]
        monkeypatch.setattr(routes, "_authenticator", lambda _broker: SlowAuthenticator())
        result = {}
        worker = threading.Thread(target=lambda: result.setdefault("response", client.get(
            "/api/oauth/callback", params={"state": state, "request_token": "one-time-rt"})))
        worker.start()
        assert entered.wait(timeout=3)
        with SessionLocal() as s:
            s.get(Membership, (OWNER, user_id)).role = "viewer"
            s.commit()
        release.set()
        worker.join(timeout=5)
        assert result["response"].status_code == 400
        with SessionLocal() as s:
            secrets = OwnedConnectionStore(
                s, owner_id=OWNER,
                broker_account_id=created["broker_account_id"]).live_connection(
                    created["id"]).secrets_source()
        assert secrets == {"api_key": "ak-123", "api_secret": "as-456"}
    finally:
        release.set()
        app.dependency_overrides.clear()


@pytest.mark.parametrize("disabled", ["user", "organization", "role"])
def test_oauth_callback_refuses_when_its_durable_identity_is_disabled(
        client, vault_key, monkeypatch, disabled):
    """A prior browser redirect cannot outlive user or organization revocation."""
    from app.db.models import Membership, Organization, User, UserSession
    import app.providers.broker_auth as ba
    user_id, session_id = f"oauth-{disabled}", f"session-{disabled}"
    with SessionLocal() as s:
        if s.get(Organization, OWNER) is None:
            s.add(Organization(organization_id=OWNER, name=OWNER))
        s.add(User(user_id=user_id, email_normalized=f"{user_id}@example.test", display_name=user_id))
        s.flush()
        s.add_all([
            Membership(organization_id=OWNER, user_id=user_id, role="owner"),
            UserSession(session_id=session_id, token_digest=token_digest(f"bearer-{disabled}"),
                        user_id=user_id, organization_id=OWNER, issued_at=dt.datetime.now(),
                        expires_at=dt.datetime.now() + dt.timedelta(hours=1)),
        ])
        s.commit()
    principal = Principal(id=user_id, kind="user", scopes=frozenset({"*"}), user_id=user_id,
                          organization_id=OWNER, role="owner", session_id=session_id)
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        monkeypatch.setattr(ba.KiteAuthenticator, "_client", lambda self, key: _FakeKite(key))
        created = _kite_with_app_keys(client, vault_key)
        state = parse_qs(urlsplit(client.post(
            f"/api/connections/{created['id']}/oauth/initiate").json()["login_url"]).query)["state"][0]
        with SessionLocal() as s:
            if disabled == "user":
                s.get(User, user_id).status = "disabled"
            elif disabled == "organization":
                s.get(Organization, OWNER).status = "disabled"
            else:
                s.get(Membership, (OWNER, user_id)).role = "viewer"
            s.commit()
        response = client.get("/api/oauth/callback", params={"state": state, "request_token": "x"})
        assert response.status_code == 400
        assert response.json() == {"detail": "invalid login callback"}
    finally:
        app.dependency_overrides.clear()
