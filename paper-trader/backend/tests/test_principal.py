"""H3 — there is a principal on every request, and one place that authorizes it.

The audit's finding was "there is no principal in the system", so permissions have
nothing to attach to. These tests pin the seam's contract, not any policy: today
the owner may do everything, and the value of the seam is that the day that stops
being true, the diff is confined to `is_allowed`.

Bare `TestClient(app)` throughout — the lifespan starts the real engine lanes.
"""
from __future__ import annotations

import dataclasses

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.api.principal import (
    ANONYMOUS_OWNER,
    OWNER,
    Forbidden,
    Principal,
    get_principal,
    is_allowed,
    require,
    resolve_principal,
    resolve_ws_principal,
)
from app.core.config import get_settings
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client() -> TestClient:
    init_db(reset=True)
    app.state.runner = EngineRunner()
    return TestClient(app)


def _request(headers: dict[str, str] | None = None, principal=...) -> Request:
    scope = {
        "type": "http", "method": "GET", "path": "/api/status", "query_string": b"",
        "headers": [(k.lower().encode(), v.encode())
                    for k, v in (headers or {}).items()],
    }
    if principal is not ...:
        scope["state"] = {"principal": principal}
    return Request(scope)


class _FakeWs:
    def __init__(self, token: str | None = None):
        self.query_params = {"token": token} if token is not None else {}


# ── resolution ─────────────────────────────────────────────────────────────

def test_auth_disabled_resolves_an_explicit_anonymous_owner(monkeypatch):
    """The whole point of this test: NOT None. A null here would grow a
    null-principal branch into every future caller."""
    monkeypatch.setattr(get_settings(), "api_token", "")
    p = resolve_principal(None)
    assert p is ANONYMOUS_OWNER
    assert p is not None
    assert p.kind == "anonymous_owner"
    assert p.authenticated is False
    assert p.is_owner is True


def test_correct_token_resolves_the_owner(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    p = resolve_principal("secret-token")
    assert p is OWNER
    assert p.id == "owner"
    assert p.authenticated is True


@pytest.mark.parametrize("supplied", [None, "", "wrong-token"])
def test_rejected_credential_resolves_to_none(monkeypatch, supplied):
    """None means one thing only — presented and refused. It never reaches a
    route; the middleware turns it into 401."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    assert resolve_principal(supplied) is None


def test_ws_principal_uses_the_query_param(monkeypatch):
    """Browsers cannot set headers on a WS handshake, so the token rides in the
    query string — a different extraction, the same principals."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    assert resolve_ws_principal(_FakeWs("secret-token")) is OWNER
    assert resolve_ws_principal(_FakeWs("nope")) is None
    assert resolve_ws_principal(_FakeWs()) is None
    monkeypatch.setattr(get_settings(), "api_token", "")
    assert resolve_ws_principal(_FakeWs()) is ANONYMOUS_OWNER


# ── the principal object ───────────────────────────────────────────────────

def test_principal_is_immutable():
    """A handler that can rewrite its own principal is an authorization bug."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        OWNER.id = "someone-else"        # type: ignore[misc]


def test_owner_carries_the_wildcard_scope():
    assert OWNER.has_scope("anything")
    assert ANONYMOUS_OWNER.has_scope("anything")
    scoped = Principal(id="x", kind="owner", scopes=frozenset({"read:trades"}))
    assert scoped.has_scope("read:trades")
    assert not scoped.has_scope("write:orders")


def test_to_dict_is_serialisable():
    d = OWNER.to_dict()
    assert d == {"id": "owner", "kind": "owner", "scopes": ["*"],
                 "authenticated": True}


# ── the authorization boundary ─────────────────────────────────────────────

@pytest.mark.parametrize("principal", [OWNER, ANONYMOUS_OWNER])
def test_owner_is_allowed_everything(principal):
    """Not a placeholder — the accurate policy of a single-user system."""
    for action in ("read:status", "write:orders", "admin:settings"):
        assert is_allowed(principal, action) is True
        require(principal, action)            # must not raise


def test_require_refuses_a_null_principal():
    assert is_allowed(None, "read:status") is False
    with pytest.raises(Forbidden) as e:
        require(None, "read:status")
    assert e.value.status_code == 403


def test_require_accepts_a_resource_argument():
    """C1 is about to re-key resources; taking the argument now means that phase
    changes policy, not every call site."""
    require(OWNER, "close", {"position_id": 1})
    assert is_allowed(None, "close", {"position_id": 1}) is False


# ── the dependency ─────────────────────────────────────────────────────────

def test_get_principal_reads_what_the_middleware_resolved():
    assert get_principal(_request(principal=OWNER)) is OWNER


def test_get_principal_resolves_inline_when_middleware_did_not_run(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "")
    assert get_principal(_request(principal=None)) is ANONYMOUS_OWNER


def test_get_principal_never_falls_back_to_anonymous_on_a_bad_token(monkeypatch):
    """The fallback re-checks the credential. Defaulting to anonymous here would
    be a bypass on any path the middleware exempts."""
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    with pytest.raises(HTTPException) as e:
        get_principal(_request({"Authorization": "Bearer wrong"}, principal=None))
    assert e.value.status_code == 401


# ── end to end ─────────────────────────────────────────────────────────────

def test_middleware_attaches_a_principal_to_every_request(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "")
    seen: list = []

    # Read the principal off the live request without touching routes.py: a
    # throwaway route registered on the app for the duration of the test.
    @app.get("/api/_test_principal_probe")
    def _probe(request: Request):
        seen.append(get_principal(request))
        return {"ok": True}

    try:
        c = _client()
        assert c.get("/api/_test_principal_probe").status_code == 200
        assert seen == [ANONYMOUS_OWNER]
    finally:
        app.router.routes[:] = [r for r in app.router.routes
                                if getattr(r, "path", None) != "/api/_test_principal_probe"]


def test_principal_is_owner_when_a_valid_token_is_presented(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "secret-token")
    seen: list = []

    @app.get("/api/_test_principal_probe2")
    def _probe(request: Request):
        seen.append(get_principal(request))
        return {"ok": True}

    try:
        c = _client()
        res = c.get("/api/_test_principal_probe2",
                    headers={"Authorization": "Bearer secret-token"})
        assert res.status_code == 200
        assert seen == [OWNER]
    finally:
        app.router.routes[:] = [r for r in app.router.routes
                                if getattr(r, "path", None) != "/api/_test_principal_probe2"]


# ── per-resource ownership (2026-08-11) ───────────────────────────────────
# `resource` was accepted and ignored from H3 until migrations 0015–0017 gave the money plane an
# `owner_id`. These pin the rule that the argument now carries, and each fails differently.

class _Owned:
    """Stands in for any money-plane row. The policy is structural — it asks the object for an
    `owner_id` rather than consulting a list of table names — so a fake with the attribute is a
    faithful stand-in, and that is the property being tested."""

    def __init__(self, owner_id):
        self.owner_id = owner_id


@pytest.mark.parametrize("principal", [OWNER, ANONYMOUS_OWNER])
def test_a_resource_belonging_to_another_owner_is_refused(principal, monkeypatch):
    from app.api.principal import is_allowed
    monkeypatch.setattr(get_settings(), "owner_id", "acct-7")
    assert is_allowed(principal, "read", _Owned("acct-7")) is True
    assert is_allowed(principal, "read", _Owned("someone-else")) is False


@pytest.mark.parametrize("principal", [OWNER, ANONYMOUS_OWNER])
def test_the_check_is_structural_so_a_new_owned_table_cannot_opt_out_by_being_forgotten(
        principal, monkeypatch):
    """A table-name allowlist would have to be updated in lockstep with every migration, and the
    failure mode of forgetting is silent: an unenforced owned table looks exactly like an
    enforced one. Asking the object means a table can only opt out by genuinely having no
    owner."""
    from app.api.principal import is_allowed
    monkeypatch.setattr(get_settings(), "owner_id", "acct-7")

    class NeverSeenBefore:
        owner_id = "someone-else"

    assert is_allowed(principal, "read", NeverSeenBefore()) is False


@pytest.mark.parametrize("principal", [OWNER, ANONYMOUS_OWNER])
def test_a_resource_with_no_owner_is_still_allowed(principal):
    """The three singleton-keyed money tables have no `owner_id`, and neither do the user/market
    planes. They pass by having nothing to check, which is honest — inventing a refusal here
    would be a policy reading a field that does not exist."""
    from app.api.principal import is_allowed

    class Unowned:
        pass

    assert is_allowed(principal, "read", Unowned()) is True
    assert is_allowed(principal, "read", "a-project-id") is True
    assert is_allowed(principal, "read", None) is True


@pytest.mark.parametrize("principal", [OWNER, ANONYMOUS_OWNER])
def test_the_real_money_plane_models_are_actually_subject_to_the_check(principal, monkeypatch):
    """Guards against the check being real and the models being shaped so it never fires. Uses
    the ORM classes themselves rather than a fake, because a fake proves the predicate and this
    proves the predicate meets the schema."""
    from app.api.principal import is_allowed
    from app.db.models import Position, Trade
    monkeypatch.setattr(get_settings(), "owner_id", "acct-7")
    for model in (Position, Trade):
        row = model()
        row.owner_id = "someone-else"
        assert is_allowed(principal, "read", row) is False, (
            f"{model.__name__} carries an owner_id that the policy does not enforce")
