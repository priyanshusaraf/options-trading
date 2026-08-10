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
import json

import pytest
from fastapi.testclient import TestClient

from app.core import credential_vault as vault
from app.core.config import get_settings
from app.db.models import LEGACY_OWNER_ID, BrokerConnection
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app
from app.providers.connection_store import OwnedConnectionStore

KEY = base64.b64encode(b"r" * 32).decode()

#: Deliberately NOT `LEGACY_OWNER_ID`. Three independent mechanisms produce the string `"owner"`
#: — the model column default, `Settings.owner_id`'s default, and `LEGACY_OWNER_ID` itself — so
#: an assertion against it cannot tell which one answered, and the owner test passed under a
#: hardcoded `return "owner"`. A distinct value makes the assertion discriminating. Found by an
#: independent security review, 2026-08-11.
OWNER = "acct-7"


@pytest.fixture()
def client(monkeypatch):
    init_db(reset=True)
    monkeypatch.setattr(get_settings(), "owner_id", OWNER)
    app.state.runner = EngineRunner()
    return TestClient(app)


@pytest.fixture()
def vault_key(monkeypatch):
    monkeypatch.setenv(vault.ENV_KEY, KEY)
    return KEY


def _rows(owner: str = OWNER) -> list[BrokerConnection]:
    with SessionLocal() as s:
        return OwnedConnectionStore(s, owner).list(include_revoked=True)


def _create(client, **kw) -> dict:
    body = {"broker": "kite", "scope": "kite:main", "label": "primary"} | kw
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


def test_a_new_connection_holds_no_credential(client):
    assert _create(client)["has_credential"] is False


def test_a_planned_broker_is_refused_at_create_naming_its_documentation(client):
    """A row naming a broker with no adapter looks configured and can never work."""
    res = client.post("/api/connections",
                      json={"broker": "angelone", "scope": "angel:main"})
    assert res.status_code == 400
    assert "planned" in res.json()["detail"]
    assert _rows() == []


def test_an_unknown_broker_is_refused_at_create(client):
    res = client.post("/api/connections",
                      json={"broker": "not-a-broker", "scope": "x:main"})
    assert res.status_code == 400
    assert _rows() == []


def test_a_duplicate_scope_for_one_owner_is_a_conflict_not_a_server_error(client):
    """Two connections sharing a scope make `ExecutionIntent.connection_scope` ambiguous, and
    that column is what restart recovery matches on."""
    _create(client)
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main"})
    assert res.status_code == 409


def test_a_capability_outside_the_vocabulary_is_refused(client):
    res = client.post("/api/connections",
                      json={"broker": "kite", "scope": "kite:main",
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
        row = OwnedConnectionStore(s, "alice").create(broker="kite", scope="kite:alice")
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
        conn = OwnedConnectionStore(s, OWNER).live_connection(created["id"])
    assert conn.broker == "kite" and conn.scope == "kite:main"
    assert conn.token_source() == "morning-token"


def test_a_revoked_connection_stops_producing_a_token(client, vault_key):
    created = _create(client)
    client.post(f"/api/connections/{created['id']}/credential",
                json={"secrets": {"access_token": "morning-token"}})
    with SessionLocal() as s:
        conn = OwnedConnectionStore(s, OWNER).live_connection(created["id"])
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
