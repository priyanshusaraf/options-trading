"""Foreign owners receive the same non-leaking refusal as missing graphs."""
from __future__ import annotations

import pytest

from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from app.editor.v2_editor_store import EditorNotFound, create_graph, read_graph


def test_cross_owner_missing_and_archived_are_uniform_not_found():
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="owner-b", name="Owner B"))
    from app.editor.graph_artifacts import create_project, set_project_status
    project = create_project("A", owner_id="owner")
    create_graph(project.project_id, "owned-a", "A", "", owner_id="owner")
    with pytest.raises(EditorNotFound):
        read_graph(project.project_id, "owned-a", owner_id="owner-b")
    with pytest.raises(EditorNotFound):
        read_graph(project.project_id, "missing", owner_id="owner-b")
    set_project_status(project.project_id, "archived", owner_id="owner")
    with pytest.raises(EditorNotFound):
        read_graph(project.project_id, "owned-a", owner_id="owner")


def test_http_principal_derives_owner_and_cross_owner_matches_missing():
    from fastapi.testclient import TestClient
    from app.api.principal import Principal, get_principal
    from app.main import app

    init_db(reset=True)
    with TestClient(app) as client:
        project = client.post("/api/ir/projects", json={"name": "HTTP A", "description": ""})
        assert project.status_code == 201
        project_id = project.json()["project_id"]
        created = client.post(f"/api/ir/projects/{project_id}/graphs/v2/create", json={
            "format_version": 2, "identifier": "owned-http", "name": "Owned", "description": "",
        })
        assert created.status_code == 201
        app.dependency_overrides[get_principal] = lambda: Principal(
            id="user-b", kind="user", scopes=frozenset({"*"}), user_id="user-b",
            organization_id="owner-b", role="owner")
        try:
            foreign = client.get(f"/api/ir/projects/{project_id}/graphs/owned-http/v2")
            missing = client.get(f"/api/ir/projects/{project_id}/graphs/missing/v2")
        finally:
            app.dependency_overrides.pop(get_principal, None)
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json() == {"detail": {"code": "NOT_FOUND"}}


def test_anonymous_principal_is_denied_across_full_v2_route_matrix():
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from app.api.principal import get_principal
    from app.db.session import init_db
    from app.main import app

    init_db(reset=True)
    denial = "anonymous"

    def denied():
        raise HTTPException(status_code=401, detail=denial)

    app.dependency_overrides[get_principal] = denied
    semantic = {
        "schema": "strategy-os-v2-semantic-batch/1", "format_version": 2,
        "base_revision": 0, "intent": "EDIT",
        "use_check": {"purpose": "AUTHORING", "capability_receipt_address": None},
        "source_receipt": None,
        "commands": [{"command": "remove_node", "node_id": "missing"}],
    }
    presentation = {
        "schema": "strategy-os-v2-presentation-batch/1", "format_version": 2,
        "base_semantic_revision": 0, "base_presentation_revision": 0,
        "intent": "EDIT", "source_receipt": None,
        "commands": [{"command": "clear_selection"}],
    }
    requests = [
        ("post", "/api/ir/projects/project/graphs/v2/create", {
            "format_version": 2, "identifier": "graph", "name": "Graph", "description": ""}),
        ("get", "/api/ir/projects/project/graphs/graph/v2", None),
        ("post", "/api/ir/projects/project/graphs/graph/v2/semantic-batches", semantic),
        ("post", "/api/ir/projects/project/graphs/graph/v2/validate", semantic),
        ("post", "/api/ir/projects/project/graphs/graph/v2/replay", {**semantic, "intent": "REPLAY"}),
        ("post", "/api/ir/projects/project/graphs/graph/v2/publish", {
            "format_version": 2, "base_revision": 0, "expected_current_version": None}),
        ("get", "/api/ir/projects/project/graphs/graph/v2/versions/1", None),
        ("get", "/api/ir/projects/project/graphs/graph/v2/presentation", None),
        ("post", "/api/ir/projects/project/graphs/graph/v2/presentation-batches", presentation),
    ]
    try:
        with TestClient(app) as client:
            for method, path, body in requests:
                response = getattr(client, method)(path, json=body) if body is not None \
                    else getattr(client, method)(path)
                assert response.status_code == 401, (method, path, response.text)
    finally:
        app.dependency_overrides.pop(get_principal, None)


def test_persisted_revoked_session_denies_full_editor_receipt_matrix_without_repository_access(
        monkeypatch):
    import datetime as dt

    from fastapi.testclient import TestClient
    from sqlalchemy import event, func, select

    from app.api.principal import issue_user_session, resolve_principal, revoke_user_session
    from app.core.config import get_settings
    from app.db import models
    from app.db.session import engine
    from app.main import app

    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "")
    init_db(reset=True)
    with TestClient(app) as client:
        with SessionLocal.begin() as session:
            session.add(models.Organization(organization_id="revocation-org", name="Revocation"))
            session.add(models.User(
                user_id="revocation-user", email_normalized="revocation@example.test",
                display_name="Revocation User"))
            session.flush()
            session.add(models.Membership(
                organization_id="revocation-org", user_id="revocation-user",
                role="owner", status="active"))
        with SessionLocal.begin() as session:
            issued = issue_user_session(
                session, user_id="revocation-user", organization_id="revocation-org",
                expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1))
        headers = {"Authorization": f"Bearer {issued.token}"}
        project = client.post(
            "/api/ir/projects", headers=headers,
            json={"name": "Revocation project", "description": ""})
        assert project.status_code == 201, project.text
        project_id = project.json()["project_id"]
        path = f"/api/ir/projects/{project_id}/graphs/revoked-v2/v2"
        created = client.post(
            f"/api/ir/projects/{project_id}/graphs/v2/create", headers=headers,
            json={"format_version": 2, "identifier": "revoked-v2",
                  "name": "Revoked", "description": ""})
        assert created.status_code == 201, created.text
        edit_body = {
            "schema": "strategy-os-v2-semantic-batch/1", "format_version": 2,
            "base_revision": 0, "intent": "EDIT",
            "use_check": {"purpose": "AUTHORING", "capability_receipt_address": None},
            "source_receipt": None,
            "commands": [{"command": "add_node", "node_id": "logic",
                          "component_id": "logic.and", "component_version": 1,
                          "parameters": {}}],
        }
        edit = client.post(path + "/semantic-batches", headers=headers, json=edit_body)
        assert edit.status_code == 200, edit.text
        edit_receipt = edit.json()
        presentation_body = {
            "schema": "strategy-os-v2-presentation-batch/1", "format_version": 2,
            "base_semantic_revision": 1, "base_presentation_revision": 0,
            "intent": "EDIT", "source_receipt": None,
            "commands": [{"command": "set_viewport", "x": 1, "y": 2, "zoom": 1}],
        }
        presentation = client.post(
            path + "/presentation-batches", headers=headers, json=presentation_body)
        assert presentation.status_code == 200, presentation.text
        presentation_receipt = presentation.json()
        assert client.get(path, headers=headers).status_code == 200

        with SessionLocal.begin() as session:
            assert revoke_user_session(session, issued.session_id) is True
        with SessionLocal() as session:
            durable = session.get(models.UserSession, issued.session_id)
            assert durable.revoked_at is not None
        assert resolve_principal(issued.token) is None

        semantic_undo = {
            **edit_body, "base_revision": 1, "intent": "UNDO",
            "source_receipt": edit_receipt,
            "commands": edit_receipt["inverse_commands"],
        }
        presentation_undo = {
            **presentation_body, "base_presentation_revision": 1, "intent": "UNDO",
            "source_receipt": presentation_receipt,
            "commands": presentation_receipt["inverse_commands"],
        }
        requests = [
            ("post", f"/api/ir/projects/{project_id}/graphs/v2/create", {
                "format_version": 2, "identifier": "denied-v2", "name": "Denied",
                "description": ""}),
            ("get", path, None),
            ("post", path + "/semantic-batches", semantic_undo),
            ("post", path + "/validate", semantic_undo),
            ("post", path + "/replay", {**semantic_undo, "intent": "REPLAY"}),
            ("post", path + "/publish", {
                "format_version": 2, "base_revision": 1,
                "expected_current_version": None}),
            ("get", path + "/versions/1", None),
            ("get", path + "/presentation", None),
            ("post", path + "/presentation-batches", presentation_undo),
        ]

        def snapshot():
            with SessionLocal() as session:
                artifact = session.get(models.GraphArtifact, ("revocation-org", "revoked-v2"))
                presentation_row = session.get(
                    models.IrV2EditorPresentation, ("revocation-org", "revoked-v2"))
                return (
                    artifact.draft_json, artifact.draft_revision, artifact.current_version,
                    artifact.published_revision, artifact.updated_at,
                    presentation_row.presentation_json, presentation_row.revision,
                    presentation_row.updated_at,
                    session.scalar(select(func.count()).select_from(models.IrV2GraphVersion)),
                )

        before = snapshot()
        statements = []

        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", capture)
        try:
            for method, request_path, body in requests:
                revoked = getattr(client, method)(
                    request_path, headers=headers, json=body) if body is not None \
                    else getattr(client, method)(request_path, headers=headers)
                anonymous = getattr(client, method)(request_path, json=body) if body is not None \
                    else getattr(client, method)(request_path)
                assert revoked.status_code == anonymous.status_code == 401
                assert revoked.json() == anonymous.json()
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert snapshot() == before
        assert not any(
            table in statement for statement in statements
            for table in ("graph_artifacts", "ir_v2_editor_presentations", "ir_v2_graph_versions")
        )

        with SessionLocal.begin() as session:
            replacement = issue_user_session(
                session, user_id="revocation-user", organization_id="revocation-org",
                expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1))
        assert client.get(
            path, headers={"Authorization": f"Bearer {replacement.token}"}).status_code == 200
