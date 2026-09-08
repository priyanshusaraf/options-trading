from __future__ import annotations

import ast
from pathlib import Path
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.api.principal import DEVELOPMENT_ANONYMOUS, Principal, get_principal
from app.api import monitoring_read_routes as subject
from app.db.models import Base
from tests.test_v0_monitoring_inbox_query import SECRET, _seed
from tests.test_v0_monitoring_persistence import _engine
from tests.test_v0_monitoring_persistence import watchlist_case


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "paper-trader/backend/app/api/monitoring_read_routes.py"


def _principal(owner: str, user: str) -> Principal:
    return Principal(
        id=user, kind="user", scopes=frozenset(), user_id=user,
        organization_id=owner, role="owner", session_id=f"session.{user}",
    )


def _client(engine, principal, *, attributed=False):
    maker = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    app = FastAPI()
    app.include_router(subject.build_monitoring_read_router(
        sessionmaker=maker, cursor_secret=SECRET, attributed=attributed,
    ))
    app.dependency_overrides[get_principal] = lambda: principal
    return TestClient(app)


@pytest.mark.parametrize("attributed", [False, True])
def test_research_alert_api_returns_pending_protections_and_owner_scoped_persisted_evidence(tmp_path, attributed):
    from app.monitoring.research_runtime import persist_research_transitions
    from tests.test_v0_monitoring_persistence import _research_snapshot_repository
    from tests.test_v0_monitoring_persistence_orchestration import _research_runtime_case
    initial, transitions, cutoff = _research_runtime_case(last=1)
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        repository.append_state_snapshot(initial, created_at=initial.effective_at)
        alert = persist_research_transitions(repository, transitions, created_at=cutoff)[0].alert
    client = _client(engine, _principal(initial.owner_id, "replay.user"), attributed=attributed)
    response = client.get("/api/v1/monitoring/alerts")
    assert response.status_code == 200, response.text
    item, = response.json()["items"]
    assert item["schema"] == "monitoring-research-alert-read/1"
    assert item["alert_address"] == alert.address
    assert item["monitoring_event_address"] == alert.monitoring_event_address
    assert item["entry_reference_value"] == alert.entry_reference.value
    assert item["simulated_position_state"] == "FLAT" and item["decision_kind"] == "ENTER"
    assert item["stop_loss"]["status"] == item["take_profit"]["status"] == "UNRESOLVED"
    for name in ("stop_loss", "take_profit"):
        assert item[name]["rules"]
        assert all(rule["resolved_value"] is None for rule in item[name]["rules"])
        assert [rule["definition_address"] for rule in item[name]["rules"]] == [
            rule.definition_address for rule in getattr(alert, name).rules]
    path = f"/api/v1/monitoring/assignments/{alert.assignment_id}/alerts/{alert.address}"
    assert client.get(path).json() == item
    foreign = _client(engine, _principal("tenant.foreign", "foreign.user"), attributed=attributed)
    assert foreign.get(path).status_code == 404
    assert foreign.get("/api/v1/monitoring/alerts").json()["items"] == []
    engine.dispose()


def _all_counts(engine):
    tables = tuple(
        table for name, table in Base.metadata.tables.items()
        if name.startswith("monitoring_")
    )
    assert len(tables) == 9
    with Session(engine) as session:
        return {
            table.name: session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in tables
        }


def test_authenticated_list_and_detail_return_closed_alert_copy(tmp_path):
    engine = _engine(tmp_path)
    first, second, _beta = _seed(engine)
    client = _client(engine, _principal("tenant.alpha", "user.alpha"))
    response = client.get("/api/v1/monitoring/alerts")
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "monitoring-alert-page/1"
    assert [item["alert_address"] for item in body["items"]] == [
        second.alert.address, first.alert.address,
    ]
    item = body["items"][0]
    assert item["action"] == second.alert.action.value
    assert item["target_state"] == second.alert.target_state.value
    assert item["entry_reference_value"] == second.alert.entry_reference.value
    assert item["stop_loss_resolved_value"] == second.alert.stop_loss.resolved_value
    assert item["take_profit_resolved_value"] == second.alert.take_profit.resolved_value
    assert not ({"owner_id", "graph_version_address", "credential", "note"} & set(item))
    detail = client.get(
        f"/api/v1/monitoring/assignments/{first.alert.assignment_id}/alerts/{first.alert.address}"
    )
    assert detail.status_code == 200
    assert detail.json()["alert_address"] == first.alert.address


def test_two_tenants_are_isolated_for_list_detail_and_guessed_ids(tmp_path):
    engine = _engine(tmp_path)
    first, _second, beta = _seed(engine)
    alpha = _client(engine, _principal("tenant.alpha", "user.alpha"))
    beta_client = _client(engine, _principal("tenant.beta", "user.beta"))
    assert len(alpha.get("/api/v1/monitoring/alerts").json()["items"]) == 2
    assert [item["alert_address"] for item in beta_client.get(
        "/api/v1/monitoring/alerts"
    ).json()["items"]] == [beta.alert.address]
    foreign = alpha.get(
        f"/api/v1/monitoring/assignments/{beta.alert.assignment_id}/alerts/{beta.alert.address}"
    )
    missing = alpha.get(
        "/api/v1/monitoring/assignments/assignment.missing/alerts/sha256:" + "0" * 64
    )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "monitoring object not found"}
    same_owner = alpha.get(
        f"/api/v1/monitoring/assignments/{first.alert.assignment_id}/alerts/{first.alert.address}"
    )
    assert same_owner.status_code == 200


def test_cursor_filters_page_bounds_and_errors_are_safe(tmp_path):
    engine = _engine(tmp_path)
    first, second, _beta = _seed(engine)
    client = _client(engine, _principal("tenant.alpha", "user.alpha"))
    page1 = client.get("/api/v1/monitoring/alerts", params={"limit": 1})
    assert page1.status_code == 200
    token = page1.json()["next_cursor"]
    page2 = client.get(
        "/api/v1/monitoring/alerts", params={"limit": 1, "cursor": token},
    )
    assert page1.json()["items"][0]["alert_address"] == second.alert.address
    assert page2.json()["items"][0]["alert_address"] == first.alert.address
    filtered = client.get(
        "/api/v1/monitoring/alerts",
        params={"assignment_id": first.alert.assignment_id, "unread_only": True},
    )
    assert filtered.status_code == 200
    invalid = client.get(
        "/api/v1/monitoring/alerts", params={"cursor": token[:-1] + "A"},
    )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "invalid monitoring query"}
    assert token not in invalid.text
    assert client.get("/api/v1/monitoring/alerts", params={"limit": 101}).status_code == 422


def test_development_anonymous_refuses_before_sessionmaker_work():
    calls = []

    def forbidden_sessionmaker():
        calls.append(True)
        raise AssertionError("sessionmaker reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_read_router(
        sessionmaker=forbidden_sessionmaker, cursor_secret=SECRET,
    ))

    app.dependency_overrides[get_principal] = lambda: DEVELOPMENT_ANONYMOUS
    response = TestClient(app).get("/api/v1/monitoring/alerts")
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}
    assert calls == []


def test_malformed_identifiers_refuse_safely_before_repository_work():
    calls = []

    def forbidden_sessionmaker():
        calls.append(True)
        raise AssertionError("sessionmaker reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_read_router(
        sessionmaker=forbidden_sessionmaker, cursor_secret=SECRET,
    ))
    app.dependency_overrides[get_principal] = lambda: _principal(
        "tenant.alpha", "user.alpha",
    )
    client = TestClient(app)
    requests = (
        client.get("/api/v1/monitoring/alerts", params={"assignment_id": "bad value"}),
        client.get(
            "/api/v1/monitoring/assignments/bad%20value/alerts/sha256:" + "0" * 64,
        ),
        client.get(
            "/api/v1/monitoring/assignments/assignment.alpha/alerts/not-an-address",
        ),
    )
    for response in requests:
        assert response.status_code == 400
        assert response.json() == {"detail": "invalid monitoring query"}
        assert "bad value" not in response.text
        assert "not-an-address" not in response.text
    assert calls == []


def test_oversized_cursor_is_rejected_without_echo_before_repository_work():
    calls = []

    def forbidden_sessionmaker():
        calls.append(True)
        raise AssertionError("sessionmaker reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_read_router(
        sessionmaker=forbidden_sessionmaker, cursor_secret=SECRET,
    ))
    app.dependency_overrides[get_principal] = lambda: _principal(
        "tenant.alpha", "user.alpha",
    )
    oversized = "A" * 2048 + ".A"
    response = TestClient(app).get(
        "/api/v1/monitoring/alerts", params={"cursor": oversized},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid monitoring query"}
    assert oversized not in response.text
    assert calls == []


def test_get_routes_never_mutate_any_monitoring_table(tmp_path):
    engine = _engine(tmp_path)
    _seed(engine)
    client = _client(engine, _principal("tenant.alpha", "user.alpha"))
    before = _all_counts(engine)
    for _ in range(5):
        assert client.get("/api/v1/monitoring/alerts").status_code == 200
    assert _all_counts(engine) == before
    assert client.post("/api/v1/monitoring/alerts").status_code == 405


def test_router_is_factory_only_without_default_secret_or_forbidden_imports():
    assert not hasattr(subject, "router")
    source = SOURCE.read_text()
    assert "cursor_secret: bytes" in source
    tree = ast.parse(source)
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    }
    forbidden = (
        "app.main", "app.api.routes", "app.core.release_profile", "app.providers",
        "app.engine", "app.execution", "app.ledger", "paper-trader.frontend",
    )
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    try:
        subject.build_monitoring_read_router(sessionmaker=lambda: None, cursor_secret=b"short")
    except ValueError:
        pass
    else:
        raise AssertionError("short/default-equivalent cursor secret accepted")


def test_attributed_alert_projection_exposes_real_event_and_attention_sequence(tmp_path):
    engine = _engine(tmp_path)
    first, _, _ = _seed(engine)
    maker = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    app = FastAPI()
    app.include_router(subject.build_monitoring_read_router(sessionmaker=maker, cursor_secret=SECRET, attributed=True))
    app.dependency_overrides[get_principal] = lambda: _principal("tenant.alpha", "user.alpha")
    client = TestClient(app)
    page = client.get("/api/v1/monitoring/alerts").json()
    assert page["schema"] == "monitoring-alert-page/2"
    detail = client.get(f"/api/v1/monitoring/assignments/{first.alert.assignment_id}/alerts/{first.alert.address}").json()
    assert detail["schema"] == "monitoring-alert-read/2"
    assert detail["monitoring_event_address"] == first.event.address
    assert detail["strategy_id"] == first.alert.strategy_id
    assert detail["graph_version_address"] == first.alert.graph_version_address
    with Session(engine) as session:
        from app.monitoring.repository import MonitoringRepository
        attention = MonitoringRepository(session, owner_id="tenant.alpha").get_attention_state(first.alert.assignment_id, first.alert.address)
        assert detail["last_sequence"] == attention.last_sequence
    assert "owner_id" not in detail
    engine.dispose()


def _watchlist_api(case, monkeypatch, principal=None):
    from fastapi import APIRouter
    from app.api import watchlist_monitoring_routes as routes
    from app.api.static_scope_routes import require_static_scopes
    engine, context, _members, _graph = case
    monkeypatch.setattr(routes, 'SessionLocal', sessionmaker(bind=engine, expire_on_commit=False))
    app = FastAPI()
    router = APIRouter(prefix='/api/v1/ir')
    routes.install_routes(router)
    app.include_router(router)
    app.dependency_overrides[get_principal] = lambda: principal or _principal('tenant.alpha', 'user.alpha')
    app.dependency_overrides[require_static_scopes] = lambda: None
    path = f'/api/v1/ir/projects/{context.project_id}/static-scopes/{context.scope_id}/monitoring-rows'
    return TestClient(app), path


def _watchlist_query(case):
    return {key: value for key, value in case[1].model_dump().items()
            if key not in ('project_id', 'scope_id')}


def _watchlist_body(case, operation='CONFIGURE', revision=0, flag=None):
    from uuid import uuid4
    _engine, context, members, graph = case
    return dict(context=context.model_dump(), member={'kind': 'CANONICAL', 'instrument_address': members[0].address},
        request_id=str(uuid4()), command=dict(operation=operation, expected_revision=revision, flag=flag,
            selection=dict(graph_id=graph.graph_identifier, graph_version=1, timeframe='30minute')
                if operation == 'CONFIGURE' else None))


def test_watchlist_rows_api_saves_reads_and_retries_without_false_live_state(watchlist_case, monkeypatch):
    client, path = _watchlist_api(watchlist_case, monkeypatch)
    initial = client.get(path, params=_watchlist_query(watchlist_case))
    assert initial.status_code == 200, initial.text
    assert len(initial.json()['rows']) == 2
    assert all(row['result']['kind'] == 'NOT_EVALUATED' for row in initial.json()['rows'])
    body = _watchlist_body(watchlist_case)
    saved = client.post(path, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()['row']['configuration_revision'] == 1
    assert saved.json()['row']['graph']['graph_version_address'] == watchlist_case[3].content_address
    assert client.post(path, json=body).json() == saved.json()
    pin = client.post(path, json=_watchlist_body(watchlist_case, 'PIN', 1, True))
    assert pin.status_code == 200, pin.text
    assert pin.json()['row']['pinned'] is True
    assert pin.json()['row']['monitoring'] == 'OFF'
    started = client.post(path, json=_watchlist_body(watchlist_case, 'MONITOR', 2, True))
    assert started.status_code == 200, started.text
    assert started.json()['row']['monitoring'] == 'STARTING'
    assert started.json()['row']['result']['kind'] == 'NOT_EVALUATED'
    reopened = client.get(path, params=_watchlist_query(watchlist_case)).json()
    assert started.json()['row'] in reopened['rows']


def test_watchlist_rows_api_isolates_owner_and_checks_exact_context(watchlist_case, monkeypatch):
    client, path = _watchlist_api(watchlist_case, monkeypatch, _principal('tenant.beta', 'user.beta'))
    assert client.get(path, params=_watchlist_query(watchlist_case)).status_code == 404
    assert client.post(path, json=_watchlist_body(watchlist_case)).status_code == 404
    client, path = _watchlist_api(watchlist_case, monkeypatch)
    query = {**_watchlist_query(watchlist_case), 'scope_revision': 2}
    assert client.get(path, params=query).status_code == 409
    body = _watchlist_body(watchlist_case)
    body['context']['scope_id'] = 'scope.foreign'
    assert client.post(path, json=body).status_code == 422
    body = _watchlist_body(watchlist_case)
    body['command']['flag'] = True
    assert client.post(path, json=body).status_code == 422


def test_watchlist_rows_api_refuses_anonymous_and_uses_existing_project_permissions(watchlist_case, monkeypatch):
    from app.api.request_actions import classify_request
    client, path = _watchlist_api(watchlist_case, monkeypatch, DEVELOPMENT_ANONYMOUS)
    assert client.get(path, params=_watchlist_query(watchlist_case)).status_code == 401
    assert client.post(path, json=_watchlist_body(watchlist_case)).status_code == 401
    unversioned = path.replace('/api/v1/', '/api/')
    assert classify_request('GET', unversioned) == 'read:project'
    assert classify_request('POST', unversioned) == 'write:project'


def test_watchlist_rows_api_explains_unavailable_saved_strategy(watchlist_case, monkeypatch):
    client, path = _watchlist_api(watchlist_case, monkeypatch)
    body = _watchlist_body(watchlist_case)
    body['command']['selection']['graph_id'] = 'missing.strategy'
    refused = client.post(path, json=body)
    assert refused.status_code == 422
    assert refused.json()['detail'] == {
        'code': 'WATCHLIST_MONITORING_UNAVAILABLE',
        'message': 'Choose a saved Build strategy from this project. Older bot strategies cannot use this monitoring path.',
    }
    reopened = client.get(path, params=_watchlist_query(watchlist_case))
    assert reopened.status_code == 200
    assert all(row['configuration_revision'] == 0 for row in reopened.json()['rows'])
