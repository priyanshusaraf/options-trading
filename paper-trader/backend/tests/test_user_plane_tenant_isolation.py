"""Projects and graph reads are scoped by their organization owner."""
from __future__ import annotations

import copy
from dataclasses import asdict

import pytest
from sqlalchemy import event, text

from app.db.models import Organization
from app.db.session import SessionLocal, engine, init_db
from app.editor import graph_artifacts as store
from app.editor import layouts
from app.ir.strategies.expanding_z import GRAPH
from app.ir.hashing import canonical_json


@pytest.fixture(autouse=True)
def _database() -> None:
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add_all((
            Organization(organization_id="owner.a", name="Owner A"),
            Organization(organization_id="owner.b", name="Owner B"),
        ))


def _graph(identifier: str) -> dict:
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    graph["version"] = 99
    graph.pop("parent_version", None)
    return graph


def test_project_and_graph_loads_require_owner_and_hide_other_owner() -> None:
    project_a = store.create_project("Same name", owner_id="owner.a")
    project_b = store.create_project("Same name", owner_id="owner.b")
    store.create_artifact(project_a.project_id, "owner.a.graph", _graph("owner.a.graph"), owner_id="owner.a")
    published = store.publish_draft(
        project_a.project_id, "owner.a.graph", base_revision=0, owner_id="owner.a"
    )

    assert {project.project_id for project in store.list_projects(owner_id="owner.a")} == {
        project_a.project_id
    }
    assert {project.project_id for project in store.list_projects(owner_id="owner.b")} == {
        project_b.project_id
    }
    assert store.load_version(
        project_a.project_id, "owner.a.graph", 1, owner_id="owner.a"
    ).content_address == published.content_address
    with pytest.raises(store.GraphNotFound):
        store.load_draft(project_a.project_id, "owner.a.graph", owner_id="owner.b")
    with pytest.raises(store.ProjectNotFound):
        store.set_project_status(project_a.project_id, "archived", owner_id="owner.b")
    with pytest.raises(TypeError):
        store.create_project("Unscoped")
    with pytest.raises(TypeError):
        store.list_projects()
    with pytest.raises(TypeError):
        store.load_draft(project_a.project_id, "owner.a.graph")
    with pytest.raises(TypeError):
        store.load_version(project_a.project_id, "owner.a.graph", 1)


def test_two_owners_can_persist_the_same_graph_and_layout_identities() -> None:
    """Tenant-local graph/layout keys keep overlapping authored presentation isolated."""
    project_a = store.create_project("Same project", owner_id="owner.a")
    project_b = store.create_project("Same project", owner_id="owner.b")
    identifier = "same.graph"
    graph = _graph(identifier)
    store.create_artifact(project_a.project_id, identifier, graph, owner_id="owner.a")
    store.create_artifact(project_b.project_id, identifier, graph, owner_id="owner.b")

    published_a = store.publish_draft(
        project_a.project_id, identifier, base_revision=0, owner_id="owner.a"
    )
    published_b = store.publish_draft(
        project_b.project_id, identifier, base_revision=0, owner_id="owner.b"
    )
    assert published_a.graph == published_b.graph
    assert published_a.content_address == published_b.content_address

    layout_a = layouts.save_layout(
        identifier,
        1,
        base_revision=0,
        positions=(layouts.Position("n_ema", 10.0, 20.0),),
        owner_id="owner.a",
    )
    layout_b = layouts.save_layout(
        identifier,
        1,
        base_revision=0,
        positions=(layouts.Position("n_ema", 30.0, 40.0),),
        owner_id="owner.b",
    )
    grouped_a = layouts.save_groups(
        identifier,
        1,
        base_revision=layout_a.revision,
        groups=(layouts.VisualGroup(
            "same.group", "Owner A", layouts.GroupFrame(1.0, 2.0, 3.0, 4.0),
            False, ("n_ema",),
        ),),
        valid_instance_ids=frozenset({"n_ema"}),
        owner_id="owner.a",
    )
    grouped_b = layouts.save_groups(
        identifier,
        1,
        base_revision=layout_b.revision,
        groups=(layouts.VisualGroup(
            "same.group", "Owner B", layouts.GroupFrame(5.0, 6.0, 7.0, 8.0),
            True, ("n_ema",),
        ),),
        valid_instance_ids=frozenset({"n_ema"}),
        owner_id="owner.b",
    )

    assert store.load_version(project_a.project_id, identifier, 1, owner_id="owner.a") == published_a
    assert store.load_version(project_b.project_id, identifier, 1, owner_id="owner.b") == published_b
    assert layouts.load_layout(
        identifier, 1, valid_instance_ids=frozenset({"n_ema"}), owner_id="owner.a"
    ).groups[0].display_name == "Owner A"
    assert layouts.load_layout(
        identifier, 1, valid_instance_ids=frozenset({"n_ema"}), owner_id="owner.b"
    ).groups[0].display_name == "Owner B"
    assert grouped_a.revision == grouped_b.revision == 2


def test_owner_a_graph_and_presentation_changes_leave_owner_b_lineage_byte_for_byte_intact() -> None:
    """Composite graph/layout keys isolate drafts, carries, archives, and public bytes."""
    identifier = "shared.mutation.graph"
    projects = {
        owner: store.create_project("Shared", owner_id=owner)
        for owner in ("owner.a", "owner.b")
    }
    published = {}
    for owner, project in projects.items():
        store.create_artifact(project.project_id, identifier, _graph(identifier), owner_id=owner)
        published[owner] = store.publish_draft(project.project_id, identifier, base_revision=0, owner_id=owner)
        saved = layouts.save_layout(
            identifier, 1, base_revision=0,
            positions=(layouts.Position("n_ema", 10.0 if owner == "owner.a" else 30.0, 20.0),),
            owner_id=owner,
        )
        layouts.save_groups(
            identifier, 1, base_revision=saved.revision,
            groups=(layouts.VisualGroup(
                "shared.group", owner, layouts.GroupFrame(1.0, 2.0, 3.0, 4.0), False, ("n_ema",),
            ),), valid_instance_ids=frozenset({"n_ema"}), owner_id=owner,
        )
    with SessionLocal.begin() as session:
        session.execute(text(
            "INSERT INTO ir_graph_layout_orphan_archive "
            "(owner_id,graph_identifier,graph_version,revision,updated_at,archived_at) "
            "VALUES ('owner.b',:identifier,41,17,'2026-08-12 09:10:11','2026-08-12 09:10:12')"
        ), {"identifier": identifier})
        session.execute(text(
            "INSERT INTO ir_graph_layout_position_orphan_archive "
            "(owner_id,graph_identifier,graph_version,instance_id,x,y) "
            "VALUES ('owner.b',:identifier,41,'private.archive.node',91.25,92.5)"
        ), {"identifier": identifier})

    tables = (
        "graph_artifacts", "graph_versions", "ir_graph_layouts", "ir_graph_layout_positions",
        "ir_graph_layout_groups", "ir_graph_layout_group_members", "ir_graph_layout_orphan_archive",
        "ir_graph_layout_position_orphan_archive",
    )
    with SessionLocal() as session:
        owner_b_rows = {
            table: tuple(session.execute(text(
                f"SELECT * FROM {table} WHERE owner_id='owner.b' ORDER BY rowid"
            )).all()) for table in tables
        }
    assert owner_b_rows["ir_graph_layout_orphan_archive"]
    assert owner_b_rows["ir_graph_layout_position_orphan_archive"]

    changed = _graph(identifier)
    changed["display_name"] = "Owner A revision two"
    store.save_draft(projects["owner.a"].project_id, identifier, base_revision=0, graph=changed, owner_id="owner.a")
    second = store.publish_draft(projects["owner.a"].project_id, identifier, base_revision=1, owner_id="owner.a")
    with SessionLocal.begin() as session:
        layouts.carry_and_reconcile_presentation(
            session, identifier, 1, second.version, base_revision=2,
            source_instance_ids=frozenset({"n_ema"}), target_instance_ids=frozenset(), owner_id="owner.a",
        )

    assert store.load_version(projects["owner.b"].project_id, identifier, 1, owner_id="owner.b") == published["owner.b"]
    assert layouts.load_layout(identifier, 1, valid_instance_ids=frozenset({"n_ema"}), owner_id="owner.b").revision == 2
    with SessionLocal() as session:
        assert {
            table: tuple(session.execute(text(
                f"SELECT * FROM {table} WHERE owner_id='owner.b' ORDER BY rowid"
            )).all()) for table in tables
        } == owner_b_rows
        stored = session.execute(text(
            "SELECT artifact_json, content_address FROM graph_versions "
            "WHERE owner_id IN ('owner.a','owner.b') AND graph_identifier=:identifier AND version=1 ORDER BY owner_id"
        ), {"identifier": identifier}).all()
    assert stored[0] == stored[1]
    for record in (published["owner.a"], published["owner.b"]):
        public = asdict(record)
        assert "owner_id" not in public
        assert "visibility" not in public
        assert "owner_id" not in canonical_json(record.graph)
        assert "visibility" not in canonical_json(record.graph)


def test_load_version_uses_one_absent_shape_for_owner_graph_and_version_misses() -> None:
    project = store.create_project("Owner A", owner_id="owner.a")
    store.create_artifact(
        project.project_id, "owner.a.graph", _graph("owner.a.graph"), owner_id="owner.a"
    )
    store.publish_draft(project.project_id, "owner.a.graph", base_revision=0, owner_id="owner.a")

    def absent_shape(**request):
        with pytest.raises(store.GraphNotFound) as caught:
            store.load_version(**request)
        return type(caught.value), caught.value.args, str(caught.value)

    wrong_owner = absent_shape(
        project_id=project.project_id, identifier="owner.a.graph", version=1, owner_id="owner.b"
    )
    absent_version = absent_shape(
        project_id=project.project_id, identifier="owner.a.graph", version=2, owner_id="owner.a"
    )
    absent_graph = absent_shape(
        project_id=project.project_id, identifier="absent.graph", version=1, owner_id="owner.a"
    )

    assert wrong_owner == absent_version == absent_graph


def test_list_versions_hides_another_owners_graph_as_an_absent_graph() -> None:
    project = store.create_project("Owner A", owner_id="owner.a")
    store.create_artifact(
        project.project_id, "owner.a.graph", _graph("owner.a.graph"), owner_id="owner.a"
    )

    with pytest.raises(store.GraphNotFound) as wrong_owner:
        store.list_versions(project.project_id, "owner.a.graph", owner_id="owner.b")
    with pytest.raises(store.GraphNotFound) as absent_graph:
        store.list_versions(project.project_id, "absent.graph", owner_id="owner.a")

    assert type(wrong_owner.value) is type(absent_graph.value) is store.GraphNotFound


def test_project_version_events_do_not_duplicate_for_another_owned_project() -> None:
    project = store.create_project("First", owner_id="owner.a")
    store.create_project("Second", owner_id="owner.a")
    store.create_artifact(project.project_id, "owner.a.events", _graph("owner.a.events"), owner_id="owner.a")
    store.publish_draft(project.project_id, "owner.a.events", base_revision=0, owner_id="owner.a")

    assert [event.identifier for event in store.list_project_version_events(
        project.project_id, owner_id="owner.a"
    )] == ["owner.a.events"]


def test_layout_repository_operations_require_an_explicit_owner() -> None:
    """Removing the owner keyword must reject the repository call at its boundary."""
    project = store.create_project("Owner A", owner_id="owner.a")
    store.create_artifact(
        project.project_id, "owner.a.layout", _graph("owner.a.layout"), owner_id="owner.a"
    )
    store.publish_draft(project.project_id, "owner.a.layout", base_revision=0, owner_id="owner.a")

    with pytest.raises(TypeError):
        layouts.load_layout("owner.a.layout", 1, valid_instance_ids=frozenset())
    with pytest.raises(TypeError):
        layouts.save_layout("owner.a.layout", 1, base_revision=0, positions=())
    with pytest.raises(TypeError):
        layouts.save_groups(
            "owner.a.layout", 1, base_revision=0, groups=(), valid_instance_ids=frozenset()
        )
    with SessionLocal.begin() as session:
        with pytest.raises(TypeError):
            layouts.apply_presentation_batch_in_session(
                session,
                "owner.a.layout",
                1,
                base_revision=0,
                operations=(),
                valid_instance_ids=frozenset(),
            )
    with SessionLocal.begin() as session:
        with pytest.raises(TypeError):
            layouts.carry_and_reconcile_presentation(
                session,
                "owner.a.layout",
                1,
                1,
                base_revision=0,
                source_instance_ids=frozenset(),
                target_instance_ids=frozenset(),
            )


def test_layout_store_scopes_reads_and_refuses_other_owner_before_layout_sql() -> None:
    """A guessed graph/version cannot materialize or change another owner's layout."""
    project = store.create_project("Owner A", owner_id="owner.a")
    store.create_artifact(
        project.project_id, "owner.a.layout", _graph("owner.a.layout"), owner_id="owner.a"
    )
    store.publish_draft(project.project_id, "owner.a.layout", base_revision=0, owner_id="owner.a")
    valid_ids = frozenset({"n_ema", "n_impulse"})
    saved = layouts.save_layout(
        "owner.a.layout",
        1,
        base_revision=0,
        positions=(layouts.Position("n_ema", 12.0, 24.0),),
        owner_id="owner.a",
    )
    grouped = layouts.save_groups(
        "owner.a.layout",
        1,
        base_revision=saved.revision,
        groups=(layouts.VisualGroup(
            "group.a",
            "Owner A",
            layouts.GroupFrame(1.0, 2.0, 3.0, 4.0),
            False,
            ("n_ema",),
        ),),
        valid_instance_ids=valid_ids,
        owner_id="owner.a",
    )
    assert layouts.load_layout(
        "owner.a.layout", 1, valid_instance_ids=valid_ids, owner_id="owner.a"
    ).revision == grouped.revision == 2

    def layout_rows() -> tuple[tuple[str, tuple[tuple[object, ...], ...]], ...]:
        tables = (
            "ir_graph_layouts",
            "ir_graph_layout_positions",
            "ir_graph_layout_groups",
            "ir_graph_layout_group_members",
            "ir_graph_layout_orphan_archive",
            "ir_graph_layout_position_orphan_archive",
        )
        with SessionLocal() as session:
            return tuple(
                (table, tuple(session.execute(text(f"SELECT * FROM {table}")).all()))
                for table in tables
            )

    before = layout_rows()

    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with pytest.raises(store.GraphNotFound) as wrong_owner:
            layouts.load_layout(
                "owner.a.layout", 1, valid_instance_ids=valid_ids, owner_id="owner.b"
            )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    with pytest.raises(store.GraphNotFound) as absent_version:
        layouts.load_layout(
            "owner.a.layout", 2, valid_instance_ids=valid_ids, owner_id="owner.a"
        )
    assert (
        type(wrong_owner.value), wrong_owner.value.args, str(wrong_owner.value)
    ) == (type(absent_version.value), absent_version.value.args, str(absent_version.value))
    assert statements and "graph_versions" in statements[0]
    assert "ir_graph_layout" not in statements[0]

    with pytest.raises(store.GraphNotFound):
        layouts.save_layout(
            "owner.a.layout", 1, base_revision=2, positions=(), owner_id="owner.b"
        )
    with pytest.raises(store.GraphNotFound):
        layouts.save_groups(
            "owner.a.layout", 1, base_revision=2, groups=(),
            valid_instance_ids=valid_ids, owner_id="owner.b"
        )
    with SessionLocal.begin() as session:
        with pytest.raises(store.GraphNotFound):
            layouts.apply_presentation_batch_in_session(
                session,
                "owner.a.layout",
                1,
                base_revision=2,
                operations=(),
                valid_instance_ids=valid_ids,
                owner_id="owner.b",
            )

    assert layout_rows() == before
