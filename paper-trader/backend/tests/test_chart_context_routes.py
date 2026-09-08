from __future__ import annotations

import datetime as dt
import hashlib
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.api.principal import Principal
from app.chart.annotation_context import MarketContextUnavailable
from app.chart.annotation_geometry import CausalApplicability, Level
from app.chart.annotation_repository import AnnotationLimit
from app.core.config import get_settings
from app.db.models import Membership, Organization, User, UserSession
from app.db.session import SessionLocal, init_db
from app.main import app


def address(digit: str) -> str:
    return "sha256:" + digit * 64


def authenticated_client(monkeypatch, owner: str = "owner.a") -> TestClient:
    import importlib
    main_module = importlib.import_module("app.main")
    principal = Principal(id=f"user.{owner}", kind="user", scopes=frozenset({"*"}),
                          user_id=f"user.{owner}", organization_id=owner, role="owner")
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "api_token", "synthetic-test-token")
    monkeypatch.setattr(main_module, "resolve_http_principal", lambda _request: principal)
    return TestClient(app)


def app_paths() -> set[str]:
    seen: set[str] = set()

    def walk(routes):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                walk(inner.routes)
            elif hasattr(route, "path"):
                seen.add(route.path)

    walk(app.router.routes)
    return seen


def test_market_context_route_is_versioned_once_bounded_and_no_store(monkeypatch):
    from app.api import chart_context_routes as routes
    monkeypatch.setattr(routes, "build_market_context", lambda *_args, **_kwargs: {
        "schema": "strategy-os-market-context/1", "state": "EMPTY",
        "market_context_address": address("a"), "bars": [],
    })
    client = authenticated_client(monkeypatch)
    response = client.get(
        "/api/v1/ir/projects/project.a/experiments/7/market-context?limit=500")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    path = "/api/ir/projects/{project_id}/experiments/{run_id}/market-context"
    matching = [route for route in routes.router.routes
                if getattr(route, "path", None) == path and "GET" in route.methods]
    assert len(matching) == 1
    assert "/api/v1" + path.removeprefix("/api") in app_paths()
    assert client.get(
        "/api/v1/ir/projects/project.a/experiments/7/market-context?limit=501").headers[
            "cache-control"] == "no-store"


def test_missing_and_foreign_context_have_same_privacy_safe_response(monkeypatch):
    from app.api import chart_context_routes as routes
    monkeypatch.setattr(routes, "build_market_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(MarketContextUnavailable()))
    client = authenticated_client(monkeypatch)
    foreign = client.get("/api/v1/ir/projects/project.foreign/experiments/7/market-context")
    guessed = client.get("/api/v1/ir/projects/project.guessed/experiments/999/market-context")
    assert foreign.status_code == guessed.status_code == 404
    assert foreign.json() == guessed.json()
    assert foreign.headers["cache-control"] == guessed.headers["cache-control"] == "no-store"
    assert "canonical" not in foreign.text.lower()


def test_annotation_route_accepts_only_closed_bounded_geometry(monkeypatch):
    from app.api import chart_context_routes as routes
    monkeypatch.setattr(routes, "_identity", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(routes, "create_annotation", lambda *_args, **_kwargs: {
        "annotation_id": "00000000-0000-0000-0000-000000000001", "revision": 1})
    applicability = CausalApplicability.from_bytes if False else CausalApplicability
    body = {"geometry": Level("100").to_dict(), "applicability": CausalApplicability(
        __import__("datetime").datetime(2026, 1, 1, 9, 0, tzinfo=__import__("datetime").timezone.utc),
        __import__("datetime").datetime(2026, 1, 1, 9, 1, tzinfo=__import__("datetime").timezone.utc),
        __import__("datetime").datetime(2026, 1, 1, 9, 2, tzinfo=__import__("datetime").timezone.utc),
    ).to_dict()}
    client = authenticated_client(monkeypatch)
    response = client.post(
        "/api/v1/ir/projects/project.a/experiments/7/market-context/annotations", json=body)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    validation = client.post(
        "/api/v1/ir/projects/project.a/experiments/7/market-context/annotations",
        json={**body, "free_text": "private"})
    assert validation.status_code == 422
    assert validation.headers["cache-control"] == "no-store"
    oversized = client.post(
        "/api/v1/ir/projects/project.a/experiments/7/market-context/annotations",
        content=b"{" + b" " * 65536 + b"}", headers={"content-type": "application/json"})
    assert oversized.status_code == 413
    assert oversized.headers["cache-control"] == "no-store"
    monkeypatch.setattr(routes, "create_annotation",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(AnnotationLimit()))
    conflict = client.post(
        "/api/v1/ir/projects/project.a/experiments/7/market-context/annotations", json=body)
    assert conflict.status_code == 409
    assert conflict.headers["cache-control"] == "no-store"
    monkeypatch.setattr(routes, "list_annotations",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(AnnotationLimit()))
    corrupt_list = client.get(
        "/api/v1/ir/projects/project.a/experiments/7/market-context/annotations")
    assert corrupt_list.status_code == 404
    assert corrupt_list.json()["detail"]["code"] == "MARKET_CONTEXT_NOT_FOUND"
    assert corrupt_list.headers["cache-control"] == "no-store"
    delete_validation = client.request("DELETE",
        "/api/v1/ir/projects/project.a/experiments/7/market-context/annotations/"
        "00000000-0000-0000-0000-000000000001", json={})
    assert delete_validation.status_code == 422
    assert delete_validation.headers["cache-control"] == "no-store"


def test_removed_membership_revokes_route_before_source_resolution(monkeypatch):
    from app.api import chart_context_routes as routes
    settings = get_settings()
    monkeypatch.setattr(settings, "research_enabled", True)
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "browser_auth_enabled", False)
    monkeypatch.setattr(settings, "api_token", "legacy-bridge-enabled")
    init_db(reset=True)
    token = "synthetic-chart-session"
    now = dt.datetime.now()
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="owner.revoked", name="Revoked"))
        session.add(User(user_id="user.revoked", email_normalized="revoked@example.test",
                         display_name="Revoked"))
        session.flush()
        session.add(Membership(organization_id="owner.revoked", user_id="user.revoked",
                               role="owner", status="active"))
        session.flush()
        session.add(UserSession(session_id="session.revoked",
            token_digest=hashlib.sha256(token.encode()).hexdigest(), user_id="user.revoked",
            organization_id="owner.revoked", issued_at=now,
            expires_at=now + dt.timedelta(hours=1)))
    projection = {"schema": "strategy-os-market-context/1", "state": "EMPTY",
                  "market_context_address": address("a"), "bars": []}
    monkeypatch.setattr(routes, "build_market_context", Mock(return_value=projection))
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    same_owner = client.get(
        "/api/v1/ir/projects/project.a/experiments/7/market-context", headers=headers)
    assert same_owner.status_code == 200
    with SessionLocal.begin() as session:
        session.execute(update(Membership).where(
            Membership.organization_id == "owner.revoked",
            Membership.user_id == "user.revoked").values(status="revoked"))
    removed = client.get(
        "/api/v1/ir/projects/project.a/experiments/7/market-context", headers=headers)
    assert removed.status_code == 401
    assert removed.headers["cache-control"] == "no-store"
    assert routes.build_market_context.call_count == 1
