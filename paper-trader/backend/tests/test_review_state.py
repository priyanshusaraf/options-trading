import pytest

from app.core import review_state
from app.db.session import init_db
from app.editor import graph_artifacts
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID


@pytest.fixture(autouse=True)
def _database():
    init_db(reset=True)


def test_note_create_reload_update_delete_preserves_immutable_anchor():
    created = review_state.create_note(
        CATALOGUE_PROJECT_ID,
        event_id="graph:strategy.expanding_z_impulse:4",
        event_type="graph_version_published",
        body="Review the immutable baseline.",
        created_by="owner",
    )

    assert created.revision == 0
    assert review_state.list_notes(CATALOGUE_PROJECT_ID) == (created,)
    updated = review_state.update_note(
        CATALOGUE_PROJECT_ID, created.note_id,
        base_revision=0, body="Reviewed the immutable baseline.",
    )
    assert updated.revision == 1
    assert (updated.event_id, updated.event_type) == (created.event_id, created.event_type)
    deleted = review_state.delete_note(
        CATALOGUE_PROJECT_ID, created.note_id, base_revision=1,
    )
    assert deleted.revision == 2
    assert deleted.deleted_at is not None
    assert review_state.list_notes(CATALOGUE_PROJECT_ID) == ()


def test_note_stale_and_wrong_project_writes_make_no_partial_change():
    other = graph_artifacts.create_project("Other")
    note = review_state.create_note(
        CATALOGUE_PROJECT_ID, event_id="run:12", event_type="experiment_run",
        body="Keep exact context.", created_by="owner",
    )

    with pytest.raises(review_state.ReviewStateConflict) as stale:
        review_state.update_note(
            CATALOGUE_PROJECT_ID, note.note_id,
            base_revision=9, body="Must not persist.",
        )
    assert stale.value.current_revision == 0
    with pytest.raises(review_state.ReviewStateNotFound):
        review_state.delete_note(other.project_id, note.note_id, base_revision=0)
    assert review_state.list_notes(CATALOGUE_PROJECT_ID)[0].body == "Keep exact context."


def test_saved_view_is_canonical_optimistic_and_active_name_is_unique():
    filters = {
        "status": "failed", "event_type": "experiment_run",
        "after": "2026-08-01T00:00:00Z", "limit": 25,
    }
    created = review_state.create_saved_view(
        CATALOGUE_PROJECT_ID, name="Failed runs", filters=filters, created_by="owner",
    )

    assert created.filters == {
        "after": "2026-08-01T00:00:00.000000Z",
        "before": None,
        "event_type": "experiment_run",
        "limit": 25,
        "status": "failed",
    }
    assert review_state.list_saved_views(CATALOGUE_PROJECT_ID) == (created,)
    with pytest.raises(review_state.ReviewViewNameConflict):
        review_state.create_saved_view(
            CATALOGUE_PROJECT_ID, name="Failed runs", filters=filters, created_by="owner",
        )
    with pytest.raises(review_state.ReviewStateConflict):
        review_state.update_saved_view(
            CATALOGUE_PROJECT_ID, created.view_id, base_revision=8,
            name="Changed", filters=filters,
        )
    assert review_state.list_saved_views(CATALOGUE_PROJECT_ID)[0].name == "Failed runs"

    updated = review_state.update_saved_view(
        CATALOGUE_PROJECT_ID, created.view_id, base_revision=0,
        name="Failed experiments", filters={"status": "failed", "limit": 50},
    )
    assert updated.revision == 1
    deleted = review_state.delete_saved_view(
        CATALOGUE_PROJECT_ID, created.view_id, base_revision=1,
    )
    replacement = review_state.create_saved_view(
        CATALOGUE_PROJECT_ID, name="Failed runs", filters=filters, created_by="owner",
    )
    assert deleted.deleted_at is not None
    assert replacement.view_id != created.view_id


def test_saved_view_rename_conflict_rolls_back_every_field():
    first = review_state.create_saved_view(
        CATALOGUE_PROJECT_ID, name="First", filters={"status": "failed"},
        created_by="owner",
    )
    second = review_state.create_saved_view(
        CATALOGUE_PROJECT_ID, name="Second", filters={"status": "active"},
        created_by="owner",
    )

    with pytest.raises(review_state.ReviewViewNameConflict):
        review_state.update_saved_view(
            CATALOGUE_PROJECT_ID, second.view_id, base_revision=0,
            name="First", filters={"status": "approved", "limit": 99},
        )

    reloaded = {view.view_id: view for view in review_state.list_saved_views(
        CATALOGUE_PROJECT_ID
    )}
    assert reloaded[first.view_id].name == "First"
    assert reloaded[second.view_id].name == "Second"
    assert reloaded[second.view_id].filters["status"] == "active"
    assert reloaded[second.view_id].revision == 0


def test_review_state_never_changes_graph_or_presentation_identity():
    from app.editor.graph_artifacts import load_editor_snapshot
    from app.ir.hashing import content_address

    before = load_editor_snapshot(CATALOGUE_PROJECT_ID, "strategy.expanding_z_impulse")
    note = review_state.create_note(
        CATALOGUE_PROJECT_ID,
        event_id="graph:strategy.expanding_z_impulse:4",
        event_type="graph_version_published",
        body="Presentation-independent context.", created_by="owner",
    )
    view = review_state.create_saved_view(
        CATALOGUE_PROJECT_ID, name="Published", filters={"status": "published"},
        created_by="owner",
    )
    after = load_editor_snapshot(CATALOGUE_PROJECT_ID, "strategy.expanding_z_impulse")

    assert note.note_id and view.view_id
    assert after == before
    assert after.published.content_address == content_address(after.published.graph)


def test_review_state_rejects_invalid_values_and_archived_writes():
    for body in ("", " " * 4, "x" * 4001):
        with pytest.raises(review_state.ReviewStateRejected):
            review_state.create_note(
                CATALOGUE_PROJECT_ID, event_id="run:1", event_type="experiment_run",
                body=body, created_by="owner",
            )
    with pytest.raises(review_state.ReviewStateRejected):
        review_state.create_saved_view(
            CATALOGUE_PROJECT_ID, name="Invalid", filters={"cursor": "opaque"},
            created_by="owner",
        )
    with pytest.raises(review_state.ReviewStateRejected):
        review_state.create_saved_view(
            CATALOGUE_PROJECT_ID, name="Invalid", filters={"status": "unknown"},
            created_by="owner",
        )

    graph_artifacts.set_project_status(CATALOGUE_PROJECT_ID, "archived")
    with pytest.raises(graph_artifacts.InvalidTransition):
        review_state.create_note(
            CATALOGUE_PROJECT_ID, event_id="run:1", event_type="experiment_run",
            body="Archived projects are read-only.", created_by="owner",
        )
    assert review_state.list_notes(CATALOGUE_PROJECT_ID) == ()
