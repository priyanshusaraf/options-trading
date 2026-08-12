"""Projects and graph reads are scoped by their organization owner."""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import asdict

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.core import review_snapshot_store, review_state
from app.core.review_snapshot import build_snapshot_manifest
from app.db.models import (
    Organization, ProjectReviewNote, ProjectReviewSavedView, ProjectReviewSnapshot,
)
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


def test_review_note_repository_requires_owner_and_hides_another_owners_note() -> None:
    """A review row belongs to its project owner, never the global row identity."""
    project_a = store.create_project("Review owner A", owner_id="owner.a")
    project_b = store.create_project("Review owner B", owner_id="owner.b")
    created = review_state.create_note(
        project_a.project_id,
        owner_id="owner.a",
        event_id="graph:review.a:1",
        event_type="graph_version_published",
        body="Only owner A can read this note.",
        created_by="owner",
    )

    assert review_state.list_notes(project_a.project_id, owner_id="owner.a") == (created,)
    assert review_state.list_notes(project_b.project_id, owner_id="owner.b") == ()
    with pytest.raises(review_state.ReviewStateNotFound):
        review_state.update_note(
            project_b.project_id,
            created.note_id,
            owner_id="owner.b",
            base_revision=0,
            body="Guessed row IDs cannot cross tenants.",
        )


def test_review_composite_project_foreign_keys_reject_cross_owner_rows() -> None:
    project = store.create_project("Owner B review", owner_id="owner.b")
    with SessionLocal.begin() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(
                "INSERT INTO project_review_notes "
                "(owner_id,note_id,project_id,event_id,event_type,body,created_by,revision,created_at,updated_at) "
                "VALUES ('owner.a','note.cross-owner',:project,'run:1','experiment_run',"
                "'cross-owner write','owner',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ), {"project": project.project_id})
    with SessionLocal.begin() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(
                "INSERT INTO project_review_saved_views "
                "(owner_id,view_id,project_id,name,filters_json,created_by,revision,created_at,updated_at) "
                "VALUES ('owner.a','view.cross-owner',:project,'Cross',:filters,"
                "'owner',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ), {"project": project.project_id, "filters": '{"limit":25}'})
    with SessionLocal.begin() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(
                "INSERT INTO project_review_snapshots "
                "(owner_id,snapshot_id,project_id,label,capture_key,manifest_json,content_address,created_by,"
                "capture_started_at,capture_completed_at) "
                "VALUES ('owner.a','snapshot.cross-owner',:project,'Cross',"
                "'00000000-0000-4000-8000-000000000001',"
                "json_object('schema_version',1,'project_id',:project),'sha256:' || printf('%064d', 0),"
                "'owner',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ), {"project": project.project_id})


def test_review_rows_allow_real_shared_tenant_local_identities() -> None:
    """Every review key and uniqueness rule includes the owner, not just generated IDs."""
    project_a = store.create_project("Shared review A", owner_id="owner.a")
    project_b = store.create_project("Shared review B", owner_id="owner.b")
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        for owner_id, project in (("owner.a", project_a), ("owner.b", project_b)):
            manifest = build_snapshot_manifest(project.project_id, _empty_review_source(), [])
            session.add_all((
                ProjectReviewNote(
                    owner_id=owner_id, note_id="note.shared", project_id=project.project_id,
                    event_id="run:shared", event_type="experiment_run", body="Shared ID", created_by="owner",
                    revision=0, created_at=now, updated_at=now,
                ),
                ProjectReviewSavedView(
                    owner_id=owner_id, view_id="view.shared", project_id=project.project_id,
                    name="Shared active name", filters_json=canonical_json({"limit": 25}),
                    created_by="owner", revision=0, created_at=now, updated_at=now,
                ),
                ProjectReviewSnapshot(
                    owner_id=owner_id, snapshot_id="snapshot.shared", project_id=project.project_id,
                    label="Shared", capture_key="00000000-0000-4000-8000-000000000009",
                    manifest_json=canonical_json(manifest.manifest), content_address=manifest.content_address,
                    created_by="owner", capture_started_at=now, capture_completed_at=now,
                ),
            ))
    with SessionLocal() as session:
        assert session.query(ProjectReviewNote).filter_by(note_id="note.shared").count() == 2
        assert session.query(ProjectReviewSavedView).filter_by(view_id="view.shared").count() == 2
        assert session.query(ProjectReviewSnapshot).filter_by(snapshot_id="snapshot.shared").count() == 2


def _empty_review_source() -> dict:
    return {
        "events": [],
        "queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "source_errors": [],
    }


def test_review_repositories_isolate_two_owners_with_shared_view_name_and_capture_key() -> None:
    """Tenant-local review identities never disclose or mutate the other owner's rows."""
    project_a = store.create_project("Review A", owner_id="owner.a")
    project_b = store.create_project("Review B", owner_id="owner.b")
    note_a = review_state.create_note(
        project_a.project_id, owner_id="owner.a", event_id="run:a", event_type="experiment_run",
        body="Owner A note", created_by="owner",
    )
    note_b = review_state.create_note(
        project_b.project_id, owner_id="owner.b", event_id="run:b", event_type="experiment_run",
        body="Owner B note", created_by="owner",
    )
    view_a = review_state.create_saved_view(
        project_a.project_id, owner_id="owner.a", name="Daily", filters={"limit": 25},
        created_by="owner",
    )
    view_b = review_state.create_saved_view(
        project_b.project_id, owner_id="owner.b", name="Daily", filters={"limit": 25},
        created_by="owner",
    )
    capture_key = "2ba56d22-7094-4a8d-9bf5-b84a4e8f083f"
    snapshot_a = review_snapshot_store.capture_snapshot(
        project_a.project_id, owner_id="owner.a", label="Daily", capture_key=capture_key,
        created_by="owner", source_loader=lambda _project: _empty_review_source(),
    )
    snapshot_b = review_snapshot_store.capture_snapshot(
        project_b.project_id, owner_id="owner.b", label="Daily", capture_key=capture_key,
        created_by="owner", source_loader=lambda _project: _empty_review_source(),
    )
    owner_b_before = (
        review_state.list_notes(project_b.project_id, owner_id="owner.b"),
        review_state.list_saved_views(project_b.project_id, owner_id="owner.b"),
        review_snapshot_store.list_snapshots(project_b.project_id, owner_id="owner.b"),
    )

    updated = review_state.update_note(
        project_a.project_id, note_a.note_id, owner_id="owner.a", base_revision=0,
        body="Owner A changed only its own note",
    )
    assert updated.revision == 1
    assert view_a.name == view_b.name == "Daily"
    assert snapshot_a.capture_key == snapshot_b.capture_key == capture_key
    assert review_snapshot_store.capture_snapshot(
        project_a.project_id, owner_id="owner.a", label="Daily", capture_key=capture_key,
        created_by="owner", source_loader=lambda _project: pytest.fail("retry must not load source"),
    ) == snapshot_a
    assert (
        review_state.list_notes(project_b.project_id, owner_id="owner.b"),
        review_state.list_saved_views(project_b.project_id, owner_id="owner.b"),
        review_snapshot_store.list_snapshots(project_b.project_id, owner_id="owner.b"),
    ) == owner_b_before == ((note_b,), (view_b,), owner_b_before[2])

    def note_miss(note_id: str):
        with pytest.raises(review_state.ReviewStateNotFound) as caught:
            review_state.update_note(
                project_b.project_id, note_id, owner_id="owner.b", base_revision=0, body="nope",
            )
        return type(caught.value), caught.value.args

    assert note_miss(note_a.note_id) == note_miss("note.absent")
    with pytest.raises(review_snapshot_store.SnapshotNotFound) as wrong_owner:
        review_snapshot_store.get_snapshot(
            project_b.project_id, snapshot_a.snapshot_id, owner_id="owner.b"
        )
    with pytest.raises(review_snapshot_store.SnapshotNotFound) as absent:
        review_snapshot_store.get_snapshot(
            project_b.project_id, "snapshot.absent", owner_id="owner.b"
        )
    assert (type(wrong_owner.value), wrong_owner.value.args) == (
        type(absent.value), absent.value.args
    )


def test_review_repository_selects_start_with_owner_scope() -> None:
    project = store.create_project("Owner-first review", owner_id="owner.a")
    note = review_state.create_note(
        project.project_id, owner_id="owner.a", event_id="run:scope", event_type="experiment_run",
        body="The first predicate owns the row.", created_by="owner",
    )
    view = review_state.create_saved_view(
        project.project_id, owner_id="owner.a", name="Owner first", filters={"limit": 25},
        created_by="owner",
    )
    capture_key = "00000000-0000-4000-8000-000000000007"
    snapshot = review_snapshot_store.capture_snapshot(
        project.project_id, owner_id="owner.a", label="Owner first", capture_key=capture_key,
        created_by="owner", source_loader=lambda _project: _empty_review_source(),
    )
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "project_review_" in statement:
            statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert review_state.list_notes(project.project_id, owner_id="owner.a")
        assert review_state.list_saved_views(project.project_id, owner_id="owner.a")
        assert review_snapshot_store.list_snapshots(project.project_id, owner_id="owner.a")
        assert review_snapshot_store.get_snapshot(
            project.project_id, snapshot.snapshot_id, owner_id="owner.a"
        ) == snapshot
        review_state.update_note(
            project.project_id, note.note_id, owner_id="owner.a", base_revision=0,
            body="Owner predicate remains first.",
        )
        review_state.update_saved_view(
            project.project_id, view.view_id, owner_id="owner.a", base_revision=0,
            name="Owner first", filters={"limit": 25},
        )
        assert review_snapshot_store.capture_snapshot(
            project.project_id, owner_id="owner.a", label="Owner first", capture_key=capture_key,
            created_by="owner", source_loader=lambda _project: pytest.fail("retry must be owner scoped"),
        ) == snapshot
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    for table in (
        "project_review_notes", "project_review_saved_views", "project_review_snapshots",
    ):
        scoped = [statement for statement in statements if table in statement and "where" in statement]
        assert scoped, f"{table} had no owner-scoped query"
        for statement in scoped:
            assert statement.index(f"{table}.owner_id") < statement.index(
                f"{table}.", statement.index(f"{table}.owner_id") + 1
            )


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
