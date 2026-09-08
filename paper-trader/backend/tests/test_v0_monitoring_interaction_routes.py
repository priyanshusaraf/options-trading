from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.api import monitoring_interaction_routes as subject
from app.api.principal import DEVELOPMENT_ANONYMOUS, Principal, get_principal
from app.db.models import (
    MonitoringAlertAttentionEventRow,
    MonitoringAlertAttentionStateRow,
    MonitoringSignalReviewRow,
)
from app.monitoring.repository import MonitoringRepository
from tests.test_v0_monitoring_inbox_query import _seed
from tests.test_v0_monitoring_persistence import _engine


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "paper-trader/backend/app/api/monitoring_interaction_routes.py"


def _principal(owner: str, user: str) -> Principal:
    return Principal(
        id=user,
        kind="user",
        scopes=frozenset(),
        user_id=user,
        organization_id=owner,
        role="owner",
        session_id=f"session.{user}",
    )


def _app(engine, principal, now, *, raise_server_exceptions=True):
    maker = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    app = FastAPI()
    app.include_router(subject.build_monitoring_interaction_router(
        sessionmaker=maker, clock=lambda: now,
    ))
    app.dependency_overrides[get_principal] = lambda: principal
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def _attention_path(alert):
    return (
        f"/api/v1/monitoring/assignments/{alert.assignment_id}"
        f"/alerts/{alert.address}/attention"
    )


def _review_path(alert):
    return (
        f"/api/v1/monitoring/assignments/{alert.assignment_id}"
        f"/alerts/{alert.address}/review"
    )


def test_authenticated_attention_and_review_commit_closed_server_derived_facts(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    now = first.alert.event_at + timedelta(minutes=10)
    client = _app(engine, _principal("tenant.alpha", "user.alpha"), now)
    attention = client.post(
        _attention_path(first.alert),
        json={"expected_sequence": 0, "action": "READ"},
    )
    assert attention.status_code == 200
    body = attention.json()
    assert body["schema"] == "monitoring-attention-mutation-read/1"
    assert body["sequence"] == body["last_sequence"] == 1
    assert body["action"] == "READ" and body["replayed"] is False
    assert not ({"owner_id", "reviewer_user_id", "credential", "graph"} & set(body))
    replay = client.post(
        _attention_path(first.alert),
        json={"expected_sequence": 0, "action": "READ"},
    )
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    assert replay.json()["attention_event_address"] == body["attention_event_address"]

    review = client.post(
        _review_path(first.alert),
        json={
            "disposition": "CONFIRMED",
            "reason_code": "MATCHED_EXPECTATION",
            "note": "Expected transition",
        },
    )
    assert review.status_code == 200
    review_body = review.json()
    assert review_body["schema"] == "monitoring-review-mutation-read/1"
    assert review_body["monitoring_event_address"] == first.event.address
    assert review_body["replayed"] is False
    assert "reviewer_user_id" not in review_body and "owner_id" not in review_body
    review_replay = client.post(
        _review_path(first.alert),
        json={
            "disposition": "CONFIRMED",
            "reason_code": "MATCHED_EXPECTATION",
            "note": "Expected transition",
        },
    )
    assert review_replay.status_code == 200
    assert review_replay.json()["replayed"] is True
    with Session(engine) as session:
        stored = session.scalar(sa.select(MonitoringSignalReviewRow))
        assert stored.owner_id == "tenant.alpha"
        assert stored.reviewer_user_id == "user.alpha"
        assert stored.monitoring_event_address == first.event.address


def test_two_tenants_are_private_and_beta_reviewer_is_server_derived(tmp_path):
    engine = _engine(tmp_path)
    first, _second, beta = _seed(engine)
    now = beta.alert.event_at + timedelta(minutes=10)
    alpha = _app(engine, _principal("tenant.alpha", "user.alpha"), now)
    beta_client = _app(engine, _principal("tenant.beta", "user.beta"), now)
    foreign = alpha.post(
        _attention_path(beta.alert),
        json={"expected_sequence": 0, "action": "READ"},
    )
    missing = alpha.post(
        "/api/v1/monitoring/assignments/assignment.missing/alerts/sha256:"
        + "0" * 64 + "/attention",
        json={"expected_sequence": 0, "action": "READ"},
    )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "monitoring object not found"}

    foreign_review = alpha.post(
        _review_path(beta.alert),
        json={
            "disposition": "REJECTED",
            "reason_code": "UNEXPECTED_TRANSITION",
            "note": "Foreign review stays absent",
        },
    )
    missing_review = alpha.post(
        "/api/v1/monitoring/assignments/assignment.missing/alerts/sha256:"
        + "0" * 64 + "/review",
        json={
            "disposition": "REJECTED",
            "reason_code": "UNEXPECTED_TRANSITION",
            "note": "Missing review stays absent",
        },
    )
    assert foreign_review.status_code == missing_review.status_code == 404
    assert foreign_review.json() == missing_review.json() \
        == {"detail": "monitoring object not found"}
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 0

    beta_review = beta_client.post(
        _review_path(beta.alert),
        json={
            "disposition": "REJECTED",
            "reason_code": "UNEXPECTED_TRANSITION",
            "note": "Beta decision",
        },
    )
    assert beta_review.status_code == 200
    assert beta_review.json()["monitoring_event_address"] == beta.event.address
    with Session(engine) as session:
        row = session.scalar(sa.select(MonitoringSignalReviewRow).where(
            MonitoringSignalReviewRow.owner_id == "tenant.beta",
        ))
        assert row.reviewer_user_id == "user.beta"
        assert row.monitoring_event_address == beta.event.address
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 0


def test_development_anonymous_refuses_before_sessionmaker_and_clock():
    calls = []

    def forbidden_sessionmaker():
        calls.append("session")
        raise AssertionError("sessionmaker reached")

    def forbidden_clock():
        calls.append("clock")
        raise AssertionError("clock reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_interaction_router(
        sessionmaker=forbidden_sessionmaker, clock=forbidden_clock,
    ))
    app.dependency_overrides[get_principal] = lambda: DEVELOPMENT_ANONYMOUS
    response = TestClient(app).post(
        "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
        + "0" * 64 + "/attention",
        json={"expected_sequence": 0, "action": "READ"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}
    assert calls == []


def test_malformed_identifiers_and_closed_bodies_refuse_without_echo_or_work():
    calls = []

    def forbidden_sessionmaker():
        calls.append("session")
        raise AssertionError("sessionmaker reached")

    def clock():
        calls.append("clock")
        raise AssertionError("clock reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_interaction_router(
        sessionmaker=forbidden_sessionmaker, clock=clock,
    ))
    app.dependency_overrides[get_principal] = lambda: _principal(
        "tenant.alpha", "user.alpha",
    )
    client = TestClient(app)
    secret = "private-note-sentinel"
    requests = (
        client.post(
            "/api/v1/monitoring/assignments/bad%20value/alerts/sha256:"
            + "0" * 64 + "/attention",
            json={"expected_sequence": 0, "action": "READ"},
        ),
        client.post(
            "/api/v1/monitoring/assignments/assignment.alpha/alerts/not-address/attention",
            json={"expected_sequence": 0, "action": "READ"},
        ),
        client.post(
            "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
            + "0" * 64 + "/attention",
            json={"expected_sequence": 0, "action": "READ", "owner_id": secret},
        ),
        client.post(
            "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
            + "0" * 64 + "/review",
            json={
                "disposition": "CONFIRMED",
                "reason_code": "MATCHED_EXPECTATION",
                "note": secret,
                "reviewer_user_id": "foreign.user",
            },
        ),
        client.post(
            "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
            + "0" * 64 + "/review",
            json={
                "disposition": "CONFIRMED",
                "reason_code": "MATCHED_EXPECTATION",
                "note": "x" * 4097,
            },
        ),
        client.post(
            "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
            + "0" * 64 + "/review",
            json={
                "disposition": ["CONFIRMED"],
                "reason_code": "MATCHED_EXPECTATION",
                "note": secret,
            },
        ),
    )
    for response in requests:
        assert response.status_code == 400
        assert response.json() == {"detail": "invalid monitoring command"}
        assert secret not in response.text and "foreign.user" not in response.text
    assert calls == []


def test_missing_malformed_duplicate_nonobject_and_oversized_json_share_safe_400():
    calls = []

    def forbidden_sessionmaker():
        calls.append("session")
        raise AssertionError("sessionmaker reached")

    def forbidden_clock():
        calls.append("clock")
        raise AssertionError("clock reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_interaction_router(
        sessionmaker=forbidden_sessionmaker, clock=forbidden_clock,
    ))
    app.dependency_overrides[get_principal] = lambda: _principal(
        "tenant.alpha", "user.alpha",
    )
    client = TestClient(app)
    path = (
        "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
        + "0" * 64 + "/attention"
    )
    sentinel = "private-json-sentinel"
    responses = (
        client.post(path),
        client.post(
            path,
            content='{"expected_sequence":0,"action":"READ","x":"'
            + sentinel,
            headers={"content-type": "application/json"},
        ),
        client.post(
            path,
            content='{"expected_sequence":0,"action":"READ","action":"DISMISS"}',
            headers={"content-type": "application/json"},
        ),
        client.post(path, json=[{"expected_sequence": 0, "action": "READ"}]),
        client.post(path, json="READ"),
        client.post(path, json=None),
        client.post(
            path,
            content='{"expected_sequence":0,"action":"READ","padding":"'
            + "x" * 17000 + '"}',
            headers={"content-type": "application/json"},
        ),
    )
    for response in responses:
        assert response.status_code == 400
        assert response.json() == {"detail": "invalid monitoring command"}
        assert sentinel not in response.text and "json_invalid" not in response.text
    assert calls == []


def test_review_note_accepts_exact_4096_byte_boundary(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    client = _app(
        engine, _principal("tenant.alpha", "user.alpha"),
        first.alert.event_at + timedelta(minutes=10),
    )
    note = "₹" * 1365 + "a"
    assert len(note.encode("utf-8")) == 4096
    response = client.post(
        _review_path(first.alert),
        json={
            "disposition": "CONFIRMED",
            "reason_code": "MATCHED_EXPECTATION",
            "note": note,
        },
    )
    assert response.status_code == 200
    assert len(response.json()["note"].encode("utf-8")) == 4096


def test_escaped_lone_surrogate_notes_share_safe_400_before_clock_or_session():
    calls = []

    def forbidden_sessionmaker():
        calls.append("session")
        raise AssertionError("sessionmaker reached")

    def forbidden_clock():
        calls.append("clock")
        raise AssertionError("clock reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_interaction_router(
        sessionmaker=forbidden_sessionmaker, clock=forbidden_clock,
    ))
    app.dependency_overrides[get_principal] = lambda: _principal(
        "tenant.alpha", "user.alpha",
    )
    client = TestClient(app, raise_server_exceptions=False)
    path = (
        "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
        + "0" * 64 + "/review"
    )
    prefix = (
        b'{"disposition":"CONFIRMED","reason_code":"MATCHED_EXPECTATION",'
        b'"note":"'
    )
    responses = tuple(
        client.post(
            path,
            content=prefix + escaped + b'"}',
            headers={"content-type": "application/json"},
        )
        for escaped in (b"\\ud800", b"\\udc00")
    )
    for response in responses:
        assert response.status_code == 400
        assert response.json() == {"detail": "invalid monitoring command"}
        assert "surrogate" not in response.text and "Unicode" not in response.text
    assert calls == []


def test_conflicts_are_bounded_and_do_not_change_accepted_facts(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    now = first.alert.event_at + timedelta(minutes=10)
    client = _app(engine, _principal("tenant.alpha", "user.alpha"), now)
    assert client.post(
        _attention_path(first.alert),
        json={"expected_sequence": 0, "action": "READ"},
    ).status_code == 200
    conflict = client.post(
        _attention_path(first.alert),
        json={"expected_sequence": 0, "action": "ACKNOWLEDGE"},
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "monitoring command conflict"}
    assert client.post(
        _review_path(first.alert),
        json={
            "disposition": "CONFIRMED", "reason_code": "MATCHED_EXPECTATION",
            "note": "first",
        },
    ).status_code == 200
    review_conflict = client.post(
        _review_path(first.alert),
        json={
            "disposition": "REJECTED", "reason_code": "UNEXPECTED_TRANSITION",
            "note": "overwrite",
        },
    )
    assert review_conflict.status_code == 409
    assert review_conflict.json() == {"detail": "monitoring command conflict"}
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 1


def test_unexpected_post_write_failures_roll_back_without_private_error_echo(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    now = first.alert.event_at + timedelta(minutes=10)
    original_attention = subject.apply_attention_command

    def fail_after_attention(*args, **kwargs):
        original_attention(*args, **kwargs)
        raise RuntimeError("private-attention-error-sentinel")

    with monkeypatch.context() as patcher:
        patcher.setattr(subject, "apply_attention_command", fail_after_attention)
        client = _app(
            engine, _principal("tenant.alpha", "user.alpha"), now,
            raise_server_exceptions=False,
        )
        response = client.post(
            _attention_path(first.alert),
            json={"expected_sequence": 0, "action": "READ"},
        )
    assert response.status_code == 500
    assert "private-attention-error-sentinel" not in response.text
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 0
        projection = session.get(MonitoringAlertAttentionStateRow, (
            "tenant.alpha", first.alert.assignment_id, first.alert.address,
        ))
        assert projection.last_sequence == 0

    original_review = subject.submit_signal_review_command

    def fail_after_review(*args, **kwargs):
        original_review(*args, **kwargs)
        raise RuntimeError("private-review-error-sentinel")

    with monkeypatch.context() as patcher:
        patcher.setattr(subject, "submit_signal_review_command", fail_after_review)
        client = _app(
            engine, _principal("tenant.alpha", "user.alpha"), now,
            raise_server_exceptions=False,
        )
        response = client.post(
            _review_path(first.alert),
            json={
                "disposition": "CONFIRMED",
                "reason_code": "MATCHED_EXPECTATION",
                "note": "private note",
            },
        )
    assert response.status_code == 500
    assert "private-review-error-sentinel" not in response.text
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 0


def test_database_commit_failures_roll_back_both_write_shapes_without_echo(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    now = first.alert.event_at + timedelta(minutes=10)
    sentinel = "private-database-error-sentinel"

    def fail_commit(_session):
        raise sa.exc.OperationalError("commit", {}, RuntimeError(sentinel))

    with monkeypatch.context() as patcher:
        patcher.setattr(Session, "commit", fail_commit)
        client = _app(
            engine, _principal("tenant.alpha", "user.alpha"), now,
            raise_server_exceptions=False,
        )
        attention = client.post(
            _attention_path(first.alert),
            json={"expected_sequence": 0, "action": "READ"},
        )
    assert attention.status_code == 500 and sentinel not in attention.text
    with Session(engine) as session:
        attention_before = session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        ))
        projection = session.get(MonitoringAlertAttentionStateRow, (
            "tenant.alpha", first.alert.assignment_id, first.alert.address,
        ))
        assert attention_before == 0 and projection.last_sequence == 0

    with monkeypatch.context() as patcher:
        patcher.setattr(Session, "commit", fail_commit)
        client = _app(
            engine, _principal("tenant.alpha", "user.alpha"), now,
            raise_server_exceptions=False,
        )
        review = client.post(
            _review_path(first.alert),
            json={
                "disposition": "CONFIRMED",
                "reason_code": "MATCHED_EXPECTATION",
                "note": "private note",
            },
        )
    assert review.status_code == 500 and sentinel not in review.text
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 0


def test_clock_refusal_is_safe_and_precedes_sessionmaker():
    calls = []

    def forbidden_sessionmaker():
        calls.append("session")
        raise AssertionError("sessionmaker reached")

    app = FastAPI()
    app.include_router(subject.build_monitoring_interaction_router(
        sessionmaker=forbidden_sessionmaker,
        clock=lambda: "not-utc",
    ))
    app.dependency_overrides[get_principal] = lambda: _principal(
        "tenant.alpha", "user.alpha",
    )
    response = TestClient(app).post(
        "/api/v1/monitoring/assignments/assignment.alpha/alerts/sha256:"
        + "0" * 64 + "/attention",
        json={"expected_sequence": 0, "action": "READ"},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "monitoring command unavailable"}
    assert calls == []


def test_router_is_factory_only_post_only_and_has_no_forbidden_imports(tmp_path):
    assert not hasattr(subject, "router")
    source = SOURCE.read_text()
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
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in imports for prefix in forbidden
    )
    for path in (
        ROOT / "paper-trader/backend/app/main.py",
        ROOT / "paper-trader/backend/app/api/routes.py",
        ROOT / "paper-trader/backend/app/core/release_profile.py",
    ):
        assert "monitoring_interaction_routes" not in path.read_text()
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    client = _app(
        engine, _principal("tenant.alpha", "user.alpha"),
        first.alert.event_at + timedelta(minutes=10),
    )
    assert client.get(_attention_path(first.alert)).status_code == 405
    try:
        subject.build_monitoring_interaction_router(
            sessionmaker=None, clock=lambda: first.alert.event_at,
        )
    except TypeError:
        pass
    else:
        raise AssertionError("non-callable sessionmaker accepted")
