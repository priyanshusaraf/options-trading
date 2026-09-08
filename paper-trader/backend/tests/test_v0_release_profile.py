"""V0 release-profile authority, route and ordinary-profile compatibility gates."""
from __future__ import annotations

import re

import pytest
from fastapi import HTTPException, WebSocketDisconnect
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api import connection_routes, portfolio_routes, research_dataset_routes, routes
from app.core.config import BootConfigError, assert_boot_config, get_settings
from app.core.release_profile import (
    V0_ALLOWED_RESEARCH_MUTATION_ROUTES,
    V0_DENIED_MUTATION_ROUTES,
    V0_NONMUTATING_POST_ROUTES,
    V0_DENIED_ROUTES,
    V0_DENIED_READ_ROUTES,
    V0_SERVICE_ROLES,
    denied_route,
    manifest,
    required_readiness_planes,
    parse_release_service_role,
    validate_boot,
)
from app.db.models import AccountExecutionLease
from app.db.session import SessionLocal
from app.ledger import routes as ledger_routes


MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _mutation_inventory(*routers) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for router in routers
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
        if method in MUTATION_METHODS
        if route.path not in V0_NONMUTATING_POST_ROUTES
        if (method, route.path) not in V0_ALLOWED_RESEARCH_MUTATION_ROUTES
    }


def _v0_settings(**updates):
    values = {
        "release_profile": "v0_research_signal",
        "release_service_role": "api",
        "research_enabled": True,
        "execution_worker": "api",
        "execution": "paper",
        "live_ack": "",
        "execution_provider": "",
        "execution_connection": "",
        "execution_owner_id": "",
        "execution_broker_account_id": "",
        "execution_cell_id": "",
    }
    values.update(updates)
    return get_settings().model_copy(update=values)


def test_manifest_is_deeply_immutable_and_names_every_denied_route():
    release = manifest(
        "v0_research_signal", research_enabled=True, service_role="api")
    with pytest.raises(TypeError):
        release["release_profile"] = "standard"
    with pytest.raises(TypeError):
        release["capabilities"]["execution"]["state"] = "ENABLED"
    with pytest.raises(TypeError):
        release["route_rules"][0]["state"] = "ENABLED"
    assert {
        (rule["method"], rule["template"])
        for rule in release["route_rules"]
    } == {
        (route.method, route.template)
        for route in V0_DENIED_ROUTES
    }
    assert release["execution_authority"] is False
    assert release["service_role"] == "api"
    assert release["allowed_service_roles"] == V0_SERVICE_ROLES
    assert release["required_readiness_planes"] == ("execution", "ledger", "research")
    assert release["capabilities"]["strategy_graph"]["ui_navigation"] is True
    assert release["capabilities"]["backtesting"]["ui_navigation"] is False
    assert release["capabilities"]["provider_connections"] == {
        "state": "BLOCKED", "ui_navigation": False,
        "reason": "data-only connection separation is owned by V0-D",
    }
    assert release["capabilities"]["data_provider_onboarding"] == {
        "state": "ENABLED_WITH_LIMIT", "ui_navigation": True,
        "reason": (
            "local encrypted onboarding only; provider activation, expiry, quota "
            "and readiness remain unavailable"
        ),
    }
    assert denied_route(
        "v0_research_signal", "GET", "/api/data-connections/status") is None
    assert denied_route(
        "v0_research_signal", "POST", "/api/connections") is not None


def test_current_execution_shaped_mutation_surface_is_exactly_enumerated():
    actual = _mutation_inventory(
        routes.router, portfolio_routes.router, ledger_routes.router,
        connection_routes.router,
    )
    expected = {(route.method, route.template) for route in V0_DENIED_MUTATION_ROUTES}
    assert actual == expected


def test_accepted_research_mutations_are_exact_nonexecution_routes():
    expected = {
        ("POST", "/api/ir/projects/{project_id}/research-datasets/import-csv"),
        ("POST", "/api/ir/projects/{project_id}/research-datasets/from-provider"),
        ("POST", "/api/ir/projects/{project_id}/experiments/{run_id}/market-context/annotations"),
        ("PUT", "/api/ir/projects/{project_id}/experiments/{run_id}/market-context/annotations/{annotation_id}"),
        ("DELETE", "/api/ir/projects/{project_id}/experiments/{run_id}/market-context/annotations/{annotation_id}"),
    }
    assert V0_ALLOWED_RESEARCH_MUTATION_ROUTES == expected
    composed = {
        (method, route.path)
        for router in (routes.router, research_dataset_routes.router)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
    }
    assert expected <= composed
    assert all(denied_route("v0_research_signal", method, path) is None
               for method, path in expected)
    assert "/api/ir/projects/{project_id}/research-datasets/inspect-csv" in V0_NONMUTATING_POST_ROUTES


@pytest.mark.parametrize(
    "updates, phrase",
    [
        ({"execution_worker": "auto"}, "PT_EXECUTION_WORKER=api"),
        ({"execution_worker": "worker"}, "PT_EXECUTION_WORKER=api"),
        ({"research_enabled": False}, "PT_RESEARCH_ENABLED=1"),
        ({"execution": "live"}, "PT_EXECUTION=paper"),
        ({"live_ack": "I_UNDERSTAND_REAL_MONEY"}, "PT_LIVE_ACK must be empty"),
        ({"execution_provider": "kite"}, "PT_EXECUTION_PROVIDER must be empty"),
        ({"execution_connection": "connection-id"}, "PT_EXECUTION_CONNECTION must be empty"),
        ({"execution_owner_id": "owner"}, "owner/account/cell assignment must be empty"),
        ({"execution_broker_account_id": "account"}, "owner/account/cell assignment must be empty"),
        ({"execution_cell_id": "cell"}, "owner/account/cell assignment must be empty"),
        ({"release_service_role": "other"}, "PT_RELEASE_SERVICE_ROLE"),
        ({
            "service_role": "other",
            "api_token": "test-token",
            "event_cursor_secret": "x" * 32,
        }, "PT_SERVICE_ROLE must be development/test"),
    ],
)
def test_v0_boot_refuses_every_execution_authority_input(updates, phrase):
    with pytest.raises(BootConfigError, match=re.escape(phrase)):
        assert_boot_config(_v0_settings(**updates), env_file=None, under_test=True)


def test_unknown_profile_refuses_boot_and_standard_profile_stays_compatible():
    with pytest.raises(BootConfigError, match="PT_RELEASE_PROFILE"):
        assert_boot_config(
            get_settings().model_copy(update={"release_profile": "unknown"}),
            env_file=None,
            under_test=True,
        )
    standard = get_settings().model_copy(update={"release_profile": "standard"})
    assert validate_boot(standard).value == "standard"
    assert denied_route("standard", "POST", "/api/execution/arm") is None
    assert manifest("standard", research_enabled=False)["execution_authority"] is None


@pytest.mark.parametrize("role", V0_SERVICE_ROLES)
def test_each_typed_v0_service_role_validates_and_names_required_planes(role):
    settings = _v0_settings(release_service_role=role)
    assert_boot_config(settings, env_file=None, under_test=True)
    release = manifest(
        settings.release_profile,
        research_enabled=settings.research_enabled,
        service_role=settings.release_service_role,
    )
    parsed = parse_release_service_role(role)
    assert release["service_role"] == role
    assert release["required_readiness_planes"] == required_readiness_planes(parsed)


def test_v0_http_boot_has_no_runner_or_lease_and_denies_both_route_prefixes(monkeypatch):
    from app.engine import runner as runner_module
    from app.execution import leases as leases_module
    from app.main import app

    settings = get_settings()
    for field, value in _v0_settings().model_dump().items():
        if field in {
            "release_profile", "research_enabled", "execution_worker", "execution", "live_ack",
            "execution_provider", "execution_connection", "execution_owner_id",
            "execution_broker_account_id", "execution_cell_id", "api_token",
        }:
            monkeypatch.setattr(settings, field, value)
    monkeypatch.setattr(settings, "api_token", "")

    def forbidden_runner(*_args, **_kwargs):
        raise AssertionError("V0 constructed EngineRunner")

    def forbidden_lease(*_args, **_kwargs):
        raise AssertionError("V0 claimed an account execution lease")

    monkeypatch.setattr(runner_module, "EngineRunner", forbidden_runner)
    monkeypatch.setattr(leases_module.LeaseRepository, "claim", forbidden_lease)

    for role in V0_SERVICE_ROLES:
        monkeypatch.setattr(settings, "release_service_role", role)
        monkeypatch.setattr(settings, "api_token", "")
        with TestClient(app) as client:
            assert app.state.runner is None
            with SessionLocal() as session:
                assert session.scalar(select(func.count()).select_from(AccountExecutionLease)) == 0

            for prefix in ("/api", "/api/v1"):
                profile = client.get(f"{prefix}/release-profile")
                assert profile.status_code == 200
                assert profile.json()["release_profile"] == "v0_research_signal"
                assert profile.json()["service_role"] == role
                assert profile.json()["execution_authority"] is False

                health = client.get(f"{prefix}/health")
                assert health.status_code == 200
                assert health.json()["release_profile"] == "v0_research_signal"
                assert health.json()["service_role"] == role
                assert health.json()["execution_authority"] is False

                readiness = client.get(f"{prefix}/readiness")
                assert readiness.status_code == 200
                assert readiness.json()["engine"] == {"present": False}
                assert readiness.json()["service_role"] == role
                assert readiness.json()["execution_authority"] is False
                assert set(readiness.json()["database_planes"]) == set(
                    required_readiness_planes(parse_release_service_role(role)))
                assert all(
                    plane["ok"] for plane in readiness.json()["database_planes"].values())

            if role != "api":
                unavailable = client.get("/api/brokers")
                assert unavailable.status_code == 503
                assert unavailable.json()["code"] == "V0_SERVICE_ROLE_UNAVAILABLE"
                continue

            factories = app.state.v0_plane_sessionmakers
            research_factory = factories["research"]

            class _BrokenResearch:
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def execute(self, *_args, **_kwargs):
                    raise RuntimeError("research plane unavailable")

            factories["research"] = _BrokenResearch
            try:
                failed = client.get("/api/readiness")
                assert failed.status_code == 503
                assert failed.json()["database_planes"]["research"]["ok"] is False
                assert failed.json()["failed_checks"] == ["database:research"]
            finally:
                factories["research"] = research_factory

            for rule in V0_DENIED_MUTATION_ROUTES + V0_DENIED_READ_ROUTES:
                sample_path = re.sub(r"\{[^}]+\}", "1", rule.template)
                for versioned in (False, True):
                    path = sample_path.replace("/api", "/api/v1", 1) if versioned else sample_path
                    response = client.request(rule.method, path, json={})
                    assert response.status_code == 409, (rule.method, path, response.text)
                    assert response.json() == {
                        "code": "V0_CAPABILITY_UNAVAILABLE",
                        "release_profile": "v0_research_signal",
                        "capability": rule.capability,
                        "message": f"{rule.capability} is unavailable in the V0 research/signal profile",
                    }

            for path in ("/ws", "/api/v1/ws", "/ws/instrument/sample", "/api/v1/ws/instrument/sample"):
                with pytest.raises(WebSocketDisconnect) as refusal:
                    with client.websocket_connect(path):
                        pass
                assert refusal.value.code == 1008
                assert refusal.value.reason == "V0_CAPABILITY_UNAVAILABLE"

            monkeypatch.setattr(settings, "api_token", "v0-test-token")
            assert client.get("/api/release-profile").status_code == 200
            assert client.post("/api/execution/arm", json={"armed": True}).status_code == 401
            authenticated = client.post(
                "/api/execution/arm",
                json={"armed": True},
                headers={"Authorization": "Bearer v0-test-token"},
            )
            assert authenticated.status_code == 409
            assert authenticated.json()["code"] == "V0_CAPABILITY_UNAVAILABLE"


def test_execution_access_has_a_second_v0_refusal_layer(monkeypatch):
    from app.api.execution_access import _refuse_v0_execution

    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    with pytest.raises(HTTPException) as error:
        _refuse_v0_execution()
    assert getattr(error.value, "status_code", None) == 409
    assert error.value.detail["code"] == "V0_CAPABILITY_UNAVAILABLE"
