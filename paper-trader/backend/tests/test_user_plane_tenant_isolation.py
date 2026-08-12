"""Projects and graph reads are scoped by their organization owner."""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import asdict

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.core import review_snapshot_store, review_state
from app.core import generated_strategies, runtime_config, strategy_archive, watchlists
from app.core.review_snapshot import build_snapshot_manifest
from app.db.models import (
    GeneratedStrategyRow, Organization, ProjectReviewNote, ProjectReviewSavedView,
    ProjectReviewSnapshot, RuntimeConfig, StrategyLifecycle, Watchlist,
    WatchlistMembership,
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


def _owned_review_rows(owner_id: str) -> dict[str, tuple[tuple[object, ...], ...]]:
    """All persisted columns make a foreign-row mutation visible to the test."""
    with SessionLocal() as session:
        return {
            table: tuple(session.execute(text(
                f"SELECT * FROM {table} WHERE owner_id=:owner_id ORDER BY 1,2"
            ), {"owner_id": owner_id}).all())
            for table in (
                "project_review_notes", "project_review_saved_views", "project_review_snapshots",
            )
        }


def test_explicit_shared_review_ids_exercise_real_repositories_without_cross_owner_changes() -> None:
    """Removing the owner key would merge same-ID rows or mutate the other tenant's bytes."""
    project_a = store.create_project("Explicit review A", owner_id="owner.a")
    project_b = store.create_project("Explicit review B", owner_id="owner.b")
    now = dt.datetime(2026, 8, 12, 10, 0, 0)
    note_id = "note.explicit.shared"
    view_id = "view.explicit.shared"
    snapshot_id = "snapshot.explicit.shared"
    capture_key = "00000000-0000-4000-8000-000000000009"
    filters = {
        "after": None, "before": None, "event_type": None, "limit": 25, "status": None,
    }
    with SessionLocal.begin() as session:
        for owner_id, project, body in (
            ("owner.a", project_a, "Owner A exact note"),
            ("owner.b", project_b, "Owner B exact note"),
        ):
            manifest = build_snapshot_manifest(project.project_id, _empty_review_source(), [])
            session.add_all((
                ProjectReviewNote(
                    owner_id=owner_id, note_id=note_id, project_id=project.project_id,
                    event_id="run:shared", event_type="experiment_run", body=body,
                    created_by="owner", revision=0, deleted_at=None,
                    created_at=now, updated_at=now,
                ),
                ProjectReviewSavedView(
                    owner_id=owner_id, view_id=view_id, project_id=project.project_id,
                    name="Shared explicit view", filters_json=canonical_json(filters),
                    created_by="owner", revision=0, deleted_at=None,
                    created_at=now, updated_at=now,
                ),
                ProjectReviewSnapshot(
                    owner_id=owner_id, snapshot_id=snapshot_id, project_id=project.project_id,
                    label="Shared explicit snapshot", capture_key=capture_key,
                    manifest_json=canonical_json(manifest.manifest),
                    content_address=manifest.content_address, created_by="owner",
                    capture_started_at=now, capture_completed_at=now,
                ),
            ))

    for owner_id, project, body in (
        ("owner.a", project_a, "Owner A exact note"),
        ("owner.b", project_b, "Owner B exact note"),
    ):
        assert review_state.list_notes(project.project_id, owner_id=owner_id)[0].body == body
        assert review_state.list_saved_views(project.project_id, owner_id=owner_id)[0].view_id == view_id
        assert tuple(snapshot.snapshot_id for snapshot in review_snapshot_store.list_snapshots(
            project.project_id, owner_id=owner_id,
        )) == (snapshot_id,)
        loaded = review_snapshot_store.get_snapshot(
            project.project_id, snapshot_id, owner_id=owner_id,
        )
        assert loaded.snapshot_id == snapshot_id
        assert review_snapshot_store.capture_snapshot(
            project.project_id, owner_id=owner_id, label=loaded.label,
            capture_key=capture_key, created_by="owner",
            source_loader=lambda _project: pytest.fail("an idempotent retry must not load sources"),
        ) == loaded

    owner_b_before = _owned_review_rows("owner.b")
    updated_a_note = review_state.update_note(
        project_a.project_id, note_id, owner_id="owner.a", base_revision=0,
        body="Owner A changed only its row",
    )
    updated_a_view = review_state.update_saved_view(
        project_a.project_id, view_id, owner_id="owner.a", base_revision=0,
        name="Owner A changed view", filters={"limit": 50},
    )
    assert (updated_a_note.revision, updated_a_view.revision) == (1, 1)
    assert _owned_review_rows("owner.b") == owner_b_before
    review_state.delete_note(
        project_a.project_id, note_id, owner_id="owner.a", base_revision=1,
    )
    review_state.delete_saved_view(
        project_a.project_id, view_id, owner_id="owner.a", base_revision=1,
    )
    owner_a_after_delete = _owned_review_rows("owner.a")
    assert review_state.list_notes(project_a.project_id, owner_id="owner.a") == ()
    assert review_state.list_saved_views(project_a.project_id, owner_id="owner.a") == ()

    updated_b_note = review_state.update_note(
        project_b.project_id, note_id, owner_id="owner.b", base_revision=0,
        body="Owner B changed only its row",
    )
    updated_b_view = review_state.update_saved_view(
        project_b.project_id, view_id, owner_id="owner.b", base_revision=0,
        name="Owner B changed view", filters={"limit": 50},
    )
    assert (updated_b_note.revision, updated_b_view.revision) == (1, 1)
    assert _owned_review_rows("owner.a") == owner_a_after_delete
    review_state.delete_note(
        project_b.project_id, note_id, owner_id="owner.b", base_revision=1,
    )
    review_state.delete_saved_view(
        project_b.project_id, view_id, owner_id="owner.b", base_revision=1,
    )
    assert review_state.list_notes(project_b.project_id, owner_id="owner.b") == ()
    assert review_state.list_saved_views(project_b.project_id, owner_id="owner.b") == ()


def test_review_repository_foreign_misses_match_absence_without_mutating_any_row() -> None:
    """Guessed cross-tenant IDs must not reveal a revision, payload, time, or conflict."""
    project_a = store.create_project("Repository owner A", owner_id="owner.a")
    project_b = store.create_project("Repository owner B", owner_id="owner.b")
    note_a = review_state.create_note(
        project_a.project_id, owner_id="owner.a", event_id="run:a",
        event_type="experiment_run", body="Owner A private note", created_by="owner",
    )
    view_a = review_state.create_saved_view(
        project_a.project_id, owner_id="owner.a", name="Owner A private view",
        filters={"limit": 25}, created_by="owner",
    )
    capture_key = "00000000-0000-4000-8000-000000000010"
    snapshot_a = review_snapshot_store.capture_snapshot(
        project_a.project_id, owner_id="owner.a", label="Owner A private snapshot",
        capture_key=capture_key, created_by="owner",
        source_loader=lambda _project: _empty_review_source(),
    )
    owner_a_before = _owned_review_rows("owner.a")
    owner_b_before = _owned_review_rows("owner.b")

    def state_miss(action):
        with pytest.raises(review_state.ReviewStateNotFound) as caught:
            action()
        return type(caught.value), caught.value.args

    assert state_miss(lambda: review_state.delete_note(
        project_b.project_id, note_a.note_id, owner_id="owner.b", base_revision=0,
    )) == state_miss(lambda: review_state.delete_note(
        project_b.project_id, "note.absent", owner_id="owner.b", base_revision=0,
    ))
    assert state_miss(lambda: review_state.update_saved_view(
        project_b.project_id, view_a.view_id, owner_id="owner.b", base_revision=0,
        name="No foreign revision", filters={"limit": 25},
    )) == state_miss(lambda: review_state.update_saved_view(
        project_b.project_id, "view.absent", owner_id="owner.b", base_revision=0,
        name="No absent revision", filters={"limit": 25},
    ))
    assert state_miss(lambda: review_state.delete_saved_view(
        project_b.project_id, view_a.view_id, owner_id="owner.b", base_revision=0,
    )) == state_miss(lambda: review_state.delete_saved_view(
        project_b.project_id, "view.absent", owner_id="owner.b", base_revision=0,
    ))

    def snapshot_miss(snapshot_id: str):
        with pytest.raises(review_snapshot_store.SnapshotNotFound) as caught:
            review_snapshot_store.get_snapshot(
                project_b.project_id, snapshot_id, owner_id="owner.b",
            )
        return type(caught.value), caught.value.args

    assert snapshot_miss(snapshot_a.snapshot_id) == snapshot_miss("snapshot.absent")

    def project_miss(project_id: str, label: str):
        with pytest.raises(store.ProjectNotFound) as caught:
            review_snapshot_store.capture_snapshot(
                project_id, owner_id="owner.b", label=label, capture_key=capture_key,
                created_by="owner",
                source_loader=lambda _project: pytest.fail("a rejected owner must not load sources"),
            )
        return type(caught.value), caught.value.args

    assert project_miss(project_a.project_id, snapshot_a.label)[0] is store.ProjectNotFound
    assert project_miss("project.absent", "Different potential conflict")[0] is store.ProjectNotFound
    assert _owned_review_rows("owner.a") == owner_a_before
    assert _owned_review_rows("owner.b") == owner_b_before


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
        review_state.delete_note(
            project.project_id, note.note_id, owner_id="owner.a", base_revision=1,
        )
        review_state.delete_saved_view(
            project.project_id, view.view_id, owner_id="owner.a", base_revision=1,
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


def test_strategy_configuration_repositories_keep_same_keys_private_to_each_owner() -> None:
    """Dropping any owner predicate would merge this deliberate same-key fixture."""
    composition_a = '{"key":"gen_shared","clauses":[]}'
    composition_b = '{"key":"gen_shared","clauses":["owner-b"]}'
    with SessionLocal() as session:
        watchlist_a = watchlists.create_watchlist(
            session, "default", "trend_impulse_v3", owner_id="owner.a",
        )
        watchlist_b = watchlists.create_watchlist(
            session, "default", "expanding_z_v4", owner_id="owner.b",
        )
        watchlists.assign_instrument(
            session, "NIFTY", watchlist_a.id, owner_id="owner.a",
        )
        watchlists.assign_instrument(
            session, "NIFTY", watchlist_b.id, owner_id="owner.b",
        )
        strategy_archive.record_strategy(
            session, "strategy.shared", owner_id="owner.a", note="A only",
        )
        strategy_archive.record_strategy(
            session, "strategy.shared", owner_id="owner.b", note="B only",
        )
        generated_strategies.save_generated(
            session, "gen_shared", composition_a, owner_id="owner.a",
        )
        generated_strategies.save_generated(
            session, "gen_shared", composition_b, owner_id="owner.b",
        )
        session.commit()

        assert watchlists.get_watchlist(session, "default", owner_id="owner.a").id == watchlist_a.id
        assert watchlists.get_watchlist(session, "default", owner_id="owner.b").id == watchlist_b.id
        assert watchlists.watchlist_of(session, "NIFTY", owner_id="owner.a").id == watchlist_a.id
        assert watchlists.watchlist_of(session, "NIFTY", owner_id="owner.b").id == watchlist_b.id
        assert watchlists.effective_strategy_map(session, owner_id="owner.a") == {
            "NIFTY": "trend_impulse_v3",
        }
        assert watchlists.effective_strategy_map(session, owner_id="owner.b") == {
            "NIFTY": "expanding_z_v4",
        }
        assert strategy_archive.get(session, "strategy.shared", owner_id="owner.a").note == "A only"
        assert strategy_archive.get(session, "strategy.shared", owner_id="owner.b").note == "B only"
        assert generated_strategies.list_generated(session, owner_id="owner.a")[0].composition_json == composition_a
        assert generated_strategies.list_generated(session, owner_id="owner.b")[0].composition_json == composition_b

    assert runtime_config.set_override("max_daily_loss", 111.0, owner_id="owner.a") == {
        "key": "max_daily_loss", "value": "111.0",
    }
    assert runtime_config.set_override("max_daily_loss", 222.0, owner_id="owner.b") == {
        "key": "max_daily_loss", "value": "222.0",
    }
    assert runtime_config.effective(owner_id="owner.a")["max_daily_loss"] == 111.0
    assert runtime_config.effective(owner_id="owner.b")["max_daily_loss"] == 222.0

    with SessionLocal() as session:
        assert session.query(Watchlist).filter_by(name="default").count() == 2
        assert session.query(WatchlistMembership).filter_by(instrument_key="NIFTY").count() == 2
        assert session.query(StrategyLifecycle).filter_by(strategy_key="strategy.shared").count() == 2
        assert session.query(GeneratedStrategyRow).filter_by(key="gen_shared").count() == 2
        assert session.query(RuntimeConfig).filter_by(key="max_daily_loss").count() == 2
        with pytest.raises(TypeError):
            watchlists.get_watchlist(session, "default")
        with pytest.raises(TypeError):
            strategy_archive.get(session, "strategy.shared")
        with pytest.raises(TypeError):
            generated_strategies.list_generated(session)
    with pytest.raises(TypeError):
        runtime_config.effective()


def test_owner_scoped_runtime_config_and_deploy_bridge_ignore_other_tenants() -> None:
    """A foreign incumbent must not block this owner's deployment or settings refresh."""
    from app.core.deploy_bridge import DeployRequest, deploy
    request = DeployRequest("default", "trend_impulse_v3", [("NIFTY", 1.0)])
    with SessionLocal() as session:
        foreign = watchlists.create_watchlist(
            session, "default", "expanding_z_v4", owner_id="owner.b",
        )
        watchlists.assign_instrument(session, "NIFTY", foreign.id, owner_id="owner.b")
        session.commit()
        result = deploy(session, request, owner_id="owner.a")
        session.commit()
        assert result.assigned == ["NIFTY"]
        assert watchlists.watchlist_of(session, "NIFTY", owner_id="owner.a").id == result.watchlist_id
        assert watchlists.watchlist_of(session, "NIFTY", owner_id="owner.b").id == foreign.id

    runtime_config.set_override("max_daily_loss", 111.0, owner_id="owner.a")
    runtime_config.set_override("max_daily_loss", 222.0, owner_id="owner.b")
    assert runtime_config.schema(owner_id="owner.a")[
        next(i for i, row in enumerate(runtime_config.schema(owner_id="owner.a"))
             if row["key"] == "max_daily_loss")
    ]["value"] == 111.0
    runtime_config.clear_override("max_daily_loss", owner_id="owner.a")
    assert runtime_config.effective(owner_id="owner.a")["max_daily_loss"] != 222.0
    assert runtime_config.effective(owner_id="owner.b")["max_daily_loss"] == 222.0

    from app.core import scoped_config
    assert scoped_config.resolve(owner_id="owner.a")["max_daily_loss"] != 222.0
    assert scoped_config.resolve(owner_id="owner.b")["max_daily_loss"] == 222.0


def test_owner_scoped_generated_resolution_and_runner_assignments_never_cross() -> None:
    """Two runners may name the same generated key without sharing executable bytes."""
    from app.strategy.registry import StrategyNotFound, resolve_strategy
    composition_a = '{"key":"gen_shared","longEntry":{"all":["ema_slope_up(50,5)"]},"shortEntry":{"all":["ema_slope_down(50,5)"]},"longExit":{"any":["zscore_lt(50,0.0)"]},"shortExit":{"any":["zscore_gt(50,0.0)"]}}'
    composition_b = composition_a.replace("50,0.0", "50,0.5")
    with SessionLocal() as session:
        generated_strategies.save_generated(session, "gen_shared", composition_a, owner_id="owner.a")
        generated_strategies.save_generated(session, "gen_shared", composition_b, owner_id="owner.b")
        session.commit()
        assert generated_strategies.register_all(session, owner_id="owner.a") == 1
        assert generated_strategies.register_all(session, owner_id="owner.b") == 1
    assert resolve_strategy("gen_shared", owner_id="owner.a").version != resolve_strategy(
        "gen_shared", owner_id="owner.b").version
    with pytest.raises(StrategyNotFound):
        resolve_strategy("gen_shared", owner_id="owner.missing")


def test_two_runners_apply_their_own_same_instrument_watchlist_strategy() -> None:
    """The runner loads one owner map; another tenant's overlay is not a candidate."""
    from app.core.deployments import create_deployment
    from app.db.models import BrokerAccount
    from app.engine.runner import EngineRunner
    with SessionLocal() as session:
        session.add(BrokerAccount(
            broker_account_id="account.a", owner_id="owner.a", broker="mock",
            external_account_id="a", display_name="Owner A",
        ))
        session.add(BrokerAccount(
            broker_account_id="account.b", owner_id="owner.b", broker="mock",
            external_account_id="b", display_name="Owner B",
        ))
        session.flush()
        deployment_a = create_deployment(
            session, "runner-a", owner_id="owner.a", broker_account_id="account.a",
            status="active")
        deployment_b = create_deployment(
            session, "runner-b", owner_id="owner.b", broker_account_id="account.b",
            status="active")
        first = watchlists.create_watchlist(session, "default", "trend_impulse_v3", owner_id="owner.a")
        second = watchlists.create_watchlist(session, "default", "expanding_z_v4", owner_id="owner.b")
        watchlists.assign_instrument(session, "NIFTY", first.id, owner_id="owner.a")
        watchlists.assign_instrument(session, "NIFTY", second.id, owner_id="owner.b")
        session.commit()
    runner_a = EngineRunner(owner_id="owner.a", broker_account_id="account.a",
                            deployment_id=deployment_a.id)
    runner_b = EngineRunner(owner_id="owner.b", broker_account_id="account.b",
                            deployment_id=deployment_b.id)
    try:
        assert runner_a.strategy_keys["NIFTY"] == "trend_impulse_v3"
        assert runner_b.strategy_keys["NIFTY"] == "expanding_z_v4"
        assert runner_a._strategy_for("NIFTY").key == "trend_impulse_v3"
        assert runner_b._strategy_for("NIFTY").key == "expanding_z_v4"
        with SessionLocal() as session:
            first = watchlists.get_watchlist(session, "default", owner_id="owner.a")
            first.strategy_key = "expanding_z_v4"
            session.commit()
        assert runner_a._load_instr_config()[1]["NIFTY"] == "expanding_z_v4"
        assert runner_b._load_instr_config()[1]["NIFTY"] == "expanding_z_v4"
    finally:
        runner_a.broker.close()
        runner_b.broker.close()


def test_deployment_keeps_watchlist_by_value_but_rejects_foreign_owner_value() -> None:
    from sqlalchemy import inspect
    from app.core import deployments
    from app.db.models import BrokerAccount
    with SessionLocal() as session:
        session.add(BrokerAccount(broker_account_id="account.a", owner_id="owner.a", broker="mock",
                                  external_account_id="a", display_name="A"))
        foreign = watchlists.create_watchlist(session, "foreign", "trend_impulse_v3", owner_id="owner.b")
        local = watchlists.create_watchlist(session, "local", "trend_impulse_v3", owner_id="owner.a")
        session.commit()
        for watchlist_id in (foreign.id, 999999):
            with pytest.raises(ValueError, match="no watchlist"):
                deployments.create_deployment(
                    session, f"bad-{watchlist_id}", owner_id="owner.a", broker_account_id="account.a",
                    watchlist_id=watchlist_id,
                )
        row = deployments.create_deployment(
            session, "local", owner_id="owner.a", broker_account_id="account.a", watchlist_id=local.id,
        )
        session.commit()
        assert row.watchlist_id == local.id
        assert not any(foreign_key["constrained_columns"] == ["watchlist_id"]
                       for foreign_key in inspect(session.bind).get_foreign_keys("deployments"))


def test_strategy_configuration_composite_constraints_reject_cross_owner_links() -> None:
    with SessionLocal.begin() as session:
        watchlist = watchlists.create_watchlist(
            session, "owner-b", "trend_impulse_v3", owner_id="owner.b")
        session.flush()
        watchlist_id = watchlist.id
    with SessionLocal.begin() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(
                "INSERT INTO watchlist_membership "
                "(owner_id,instrument_key,watchlist_id,added_at) "
                "VALUES ('owner.a','CROSS',:watchlist,CURRENT_TIMESTAMP)"
            ), {"watchlist": watchlist_id})
    with SessionLocal.begin() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(
                "INSERT INTO strategy_lifecycle "
                "(owner_id,strategy_key,status,source,deployed_watchlist_id,last_dsr,note,created_at,updated_at) "
                "VALUES ('owner.a','cross.strategy','running','builtin',:watchlist,NULL,'',"
                "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ), {"watchlist": watchlist_id})


def test_wrong_owner_strategy_configuration_operations_are_absent_and_do_not_mutate() -> None:
    with SessionLocal() as session:
        foreign = watchlists.create_watchlist(
            session, "foreign-only", "trend_impulse_v3", owner_id="owner.b")
        strategy_archive.record_strategy(
            session, "foreign.strategy", owner_id="owner.b", note="unchanged")
        session.commit()
        before = tuple(session.execute(text(
            "SELECT owner_id,name,strategy_key,status FROM watchlists ORDER BY owner_id,id"
        )).all())
        with pytest.raises(ValueError, match=f"no watchlist with id {foreign.id}"):
            watchlists.assign_instrument(
                session, "NIFTY", foreign.id, owner_id="owner.a")
        assert watchlists.get_watchlist(
            session, "foreign-only", owner_id="owner.a") is None
        assert strategy_archive.get(
            session, "foreign.strategy", owner_id="owner.a") is None
        with pytest.raises(ValueError, match="not in the archive"):
            strategy_archive.set_status(
                session, "foreign.strategy", "running", owner_id="owner.a")
        assert tuple(session.execute(text(
            "SELECT owner_id,name,strategy_key,status FROM watchlists ORDER BY owner_id,id"
        )).all()) == before


def test_every_public_strategy_configuration_repository_requires_owner_scope() -> None:
    with SessionLocal() as session:
        calls = (
            lambda: watchlists.create_watchlist(session, "x", "trend_impulse_v3"),
            lambda: watchlists.get_watchlist(session, "x"),
            lambda: watchlists.assign_instrument(session, "NIFTY", 1),
            lambda: watchlists.unassign_instrument(session, "NIFTY"),
            lambda: watchlists.watchlist_of(session, "NIFTY"),
            lambda: watchlists.effective_strategy_map(session),
            lambda: watchlists.membership_map(session),
            lambda: watchlists.in_watchlist_keys(session),
            lambda: watchlists.list_watchlists(session),
            lambda: strategy_archive.get(session, "x"),
            lambda: strategy_archive.record_strategy(session, "x"),
            lambda: strategy_archive.set_status(session, "x", "running"),
            lambda: strategy_archive.by_status(session, "running"),
            lambda: strategy_archive.list_archive(session),
            lambda: generated_strategies.save_generated(session, "gen_x", '{"key":"gen_x"}'),
            lambda: generated_strategies.list_generated(session),
            lambda: generated_strategies.register_all(session),
        )
        for call in calls:
            with pytest.raises(TypeError):
                call()
    for call in (
        lambda: runtime_config.effective(),
        lambda: runtime_config.schema(),
        lambda: runtime_config.set_override("max_daily_loss", 1),
        lambda: runtime_config.clear_override("max_daily_loss"),
    ):
        with pytest.raises(TypeError):
            call()
