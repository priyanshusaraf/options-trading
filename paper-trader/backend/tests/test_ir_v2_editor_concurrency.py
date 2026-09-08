"""Optimistic semantic revisions permit one winner and no partial effects."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from alembic import command
from sqlalchemy.orm import sessionmaker

from app.db import migrate
from app.db.models import Base, GraphArtifact, Organization, Project
from app.db.session import SessionLocal, init_db
from app.editor.graph_artifacts import create_project
from app.editor.v2_editor_store import (
    create_graph, mutate_presentation, mutate_semantic, read_graph, read_presentation,
)
from app.editor.v2_mutations import EditorRefusal


def test_twenty_sqlite_batches_at_one_base_have_exactly_one_winner():
    init_db(reset=True)
    project = create_project("Concurrent v2", owner_id="owner")
    create_graph(project.project_id, "concurrent-v2", "Concurrent", "", owner_id="owner")

    def attempt(index: int) -> str:
        try:
            mutate_semantic(
                project.project_id, "concurrent-v2", base_revision=0, intent="EDIT",
                commands=[{"command": "add_node", "node_id": f"logic-{index}",
                           "component_id": "logic.and", "component_version": 1,
                           "parameters": {}}],
                source_receipt=None, owner_id="owner",
            )
            return "won"
        except EditorRefusal as exc:
            assert exc.code == "SEMANTIC_REVISION_CONFLICT"
            return "lost"

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(attempt, range(20)))
    assert results.count("won") == 1
    assert results.count("lost") == 19
    state = read_graph(project.project_id, "concurrent-v2", owner_id="owner")
    assert state.semantic_revision == 1
    assert len(state.document["nodes"]) == 1


def test_sqlite_sealed_imported_edge_inverse_has_one_cas_winner_and_exact_bytes():
    from app.editor.v2_editor_store import REGISTRY
    from app.editor.v2_mutations import apply_semantic_commands
    from app.ir.formats.v2 import content_address_for, graph_address_for
    from app.ir.hashing import canonical_json

    init_db(reset=True)
    project = create_project("SQLite imported edge", owner_id="owner")
    create_graph(project.project_id, "imported-edge-sqlite", "SQLite", "", owner_id="owner")
    base = read_graph(project.project_id, "imported-edge-sqlite", owner_id="owner").document
    imported = apply_semantic_commands(base, [
        {"command": "add_node", "node_id": "left", "component_id": "logic.and",
         "component_version": 1, "parameters": {}},
        {"command": "add_node", "node_id": "right", "component_id": "logic.and",
         "component_version": 1, "parameters": {}},
        {"command": "connect", "source": {"node_id": "left", "port_id": "value"},
         "target": {"node_id": "right", "port_id": "input"},
         "binding": {"kind": "single"}},
    ], registry=REGISTRY).document
    imported["edges"][0]["edge_id"] = "caller.sqlite.edge"
    expected_content = content_address_for(imported, REGISTRY)
    expected_graph = graph_address_for(imported, REGISTRY)
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "imported-edge-sqlite"))
        row.draft_json = canonical_json(imported)
    edit = mutate_semantic(
        project.project_id, "imported-edge-sqlite", base_revision=0, intent="EDIT",
        commands=[{"command": "remove_node", "node_id": "right"}],
        source_receipt=None, owner_id="owner")

    def undo() -> str:
        try:
            mutate_semantic(
                project.project_id, "imported-edge-sqlite", base_revision=1, intent="UNDO",
                commands=edit["inverse_commands"], source_receipt=edit, owner_id="owner")
            return "won"
        except EditorRefusal as exc:
            assert exc.code in {"SEMANTIC_REVISION_CONFLICT", "UNDO_BASE_MISMATCH"}
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: undo(), range(2)))
    assert results.count("won") == 1
    assert results.count("lost") == 1
    restored = read_graph(project.project_id, "imported-edge-sqlite", owner_id="owner")
    assert restored.document == imported
    assert restored.content_address == expected_content
    assert restored.graph_address == expected_graph


def test_twenty_sqlite_presentation_batches_have_one_winner_and_no_semantic_change():
    init_db(reset=True)
    project = create_project("Concurrent presentation", owner_id="owner")
    create_graph(project.project_id, "presentation-concurrent", "Presentation", "", owner_id="owner")
    semantic_before = read_graph(project.project_id, "presentation-concurrent", owner_id="owner")

    def attempt(index: int) -> str:
        try:
            mutate_presentation(
                project.project_id, "presentation-concurrent", base_semantic_revision=0,
                base_presentation_revision=0,
                commands=[{"command": "set_viewport", "x": index, "y": index, "zoom": 1}],
                owner_id="owner")
            return "won"
        except EditorRefusal as exc:
            assert exc.code == "PRESENTATION_REVISION_CONFLICT"
            return "lost"

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(attempt, range(20)))
    assert results.count("won") == 1
    assert results.count("lost") == 19
    assert read_presentation(project.project_id, "presentation-concurrent",
                             owner_id="owner")["presentation_revision"] == 1
    assert read_graph(project.project_id, "presentation-concurrent",
                      owner_id="owner") == semantic_before


def test_twenty_postgresql_batches_and_0046_upgrade_have_one_winner(pg_sandbox, monkeypatch):
    engine = pg_sandbox.execution_engine
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE ir_v2_editor_presentations")
        command.stamp(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(engine) == "0046"
    assert migrate.upgrade_to_head(engine) == "0047"

    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr("app.editor.v2_editor_store.SessionLocal", factory)
    with factory.begin() as session:
        session.add(Organization(organization_id="owner-pg", name="Owner PG"))
        session.add(Project(project_id="project-pg", owner_id="owner-pg", name="PG",
                            description="", status="active"))
    create_graph("project-pg", "concurrent-pg", "Concurrent PG", "", owner_id="owner-pg")

    def attempt(index: int) -> str:
        try:
            mutate_semantic(
                "project-pg", "concurrent-pg", base_revision=0, intent="EDIT",
                commands=[{"command": "add_node", "node_id": f"logic-{index}",
                           "component_id": "logic.and", "component_version": 1,
                           "parameters": {}}], source_receipt=None, owner_id="owner-pg",
            )
            return "won"
        except EditorRefusal as exc:
            assert exc.code == "SEMANTIC_REVISION_CONFLICT"
            return "lost"

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(attempt, range(20)))
    assert results.count("won") == 1
    assert results.count("lost") == 19
    state = read_graph("project-pg", "concurrent-pg", owner_id="owner-pg")
    assert state.semantic_revision == 1
    assert len(state.document["nodes"]) == 1

    def presentation_attempt(index: int) -> str:
        try:
            mutate_presentation(
                "project-pg", "concurrent-pg", base_semantic_revision=1,
                base_presentation_revision=0,
                commands=[{"command": "set_viewport", "x": index, "y": index, "zoom": 1}],
                owner_id="owner-pg")
            return "won"
        except EditorRefusal as exc:
            assert exc.code == "PRESENTATION_REVISION_CONFLICT"
            return "lost"

    with ThreadPoolExecutor(max_workers=20) as executor:
        presentation_results = list(executor.map(presentation_attempt, range(20)))
    assert presentation_results.count("won") == 1
    assert presentation_results.count("lost") == 19
    assert read_presentation("project-pg", "concurrent-pg",
                             owner_id="owner-pg")["presentation_revision"] == 1


def test_postgresql_sealed_imported_edge_inverse_has_one_cas_winner_and_exact_bytes(
        pg_sandbox, monkeypatch):
    from app.editor.v2_editor_store import REGISTRY
    from app.editor.v2_mutations import apply_semantic_commands
    from app.ir.formats.v2 import content_address_for, graph_address_for
    from app.ir.hashing import canonical_json

    engine = pg_sandbox.execution_engine
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr("app.editor.v2_editor_store.SessionLocal", factory)
    with factory.begin() as session:
        session.add(Organization(organization_id="owner-edge-pg", name="Owner Edge PG"))
        session.add(Project(project_id="project-edge-pg", owner_id="owner-edge-pg", name="PG Edge",
                            description="", status="active"))
    create_graph(
        "project-edge-pg", "imported-edge-pg", "Imported PG", "", owner_id="owner-edge-pg")
    base = read_graph("project-edge-pg", "imported-edge-pg", owner_id="owner-edge-pg").document
    imported = apply_semantic_commands(base, [
        {"command": "add_node", "node_id": "left", "component_id": "logic.and",
         "component_version": 1, "parameters": {}},
        {"command": "add_node", "node_id": "right", "component_id": "logic.and",
         "component_version": 1, "parameters": {}},
        {"command": "connect", "source": {"node_id": "left", "port_id": "value"},
         "target": {"node_id": "right", "port_id": "input"},
         "binding": {"kind": "single"}},
    ], registry=REGISTRY).document
    imported["edges"][0]["edge_id"] = "caller.postgresql.edge"
    expected_content = content_address_for(imported, REGISTRY)
    expected_graph = graph_address_for(imported, REGISTRY)
    with factory.begin() as session:
        row = session.get(GraphArtifact, ("owner-edge-pg", "imported-edge-pg"))
        row.draft_json = canonical_json(imported)
    edit = mutate_semantic(
        "project-edge-pg", "imported-edge-pg", base_revision=0, intent="EDIT",
        commands=[{"command": "remove_node", "node_id": "right"}],
        source_receipt=None, owner_id="owner-edge-pg")

    def undo() -> str:
        try:
            mutate_semantic(
                "project-edge-pg", "imported-edge-pg", base_revision=1, intent="UNDO",
                commands=edit["inverse_commands"], source_receipt=edit,
                owner_id="owner-edge-pg")
            return "won"
        except EditorRefusal as exc:
            assert exc.code in {"SEMANTIC_REVISION_CONFLICT", "UNDO_BASE_MISMATCH"}
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: undo(), range(2)))
    assert results.count("won") == 1
    assert results.count("lost") == 1
    restored = read_graph("project-edge-pg", "imported-edge-pg", owner_id="owner-edge-pg")
    assert restored.document == imported
    assert restored.content_address == expected_content
    assert restored.graph_address == expected_graph
