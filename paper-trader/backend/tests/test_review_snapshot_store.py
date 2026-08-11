import copy
import uuid

import pytest
import sqlalchemy as sa

from app.core import review_snapshot_store, review_state
from app.db.session import SessionLocal, init_db
from app.editor import graph_artifacts
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID


CAPTURE_KEY = "2ba56d22-7094-4a8d-9bf5-b84a4e8f083f"


def _source():
    return {
        "events": [{
            "event_id": "graph:strategy.expanding_z_impulse:4",
            "type": "graph_version_published",
            "occurred_at": "2026-08-03T10:00:00.000000Z",
            "status": "published",
            "summary": "Published strategy.expanding_z_impulse version 4",
            "references": {
                "graph": {
                    "identifier": "strategy.expanding_z_impulse", "version": 4,
                    "content_address": f"sha256:{4:064x}",
                },
                "run_id": None, "finding_id": None, "candidate_id": None,
            },
        }],
        "queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "source_errors": [],
    }


@pytest.fixture(autouse=True)
def _database():
    init_db(reset=True)


def test_capture_is_stabilized_append_only_and_losslessly_reloadable():
    review_state.create_note(
        CATALOGUE_PROJECT_ID,
        owner_id="owner",
        event_id="graph:strategy.expanding_z_impulse:4",
        event_type="graph_version_published",
        body="Freeze this interpretation.", created_by="owner",
    )
    calls = []

    def source_loader(project_id):
        calls.append(project_id)
        return copy.deepcopy(_source())

    captured = review_snapshot_store.capture_snapshot(
        CATALOGUE_PROJECT_ID, label="Morning review", capture_key=CAPTURE_KEY,
        owner_id="owner",
        created_by="owner", source_loader=source_loader,
    )

    assert calls == [CATALOGUE_PROJECT_ID, CATALOGUE_PROJECT_ID]
    assert captured.label == "Morning review"
    assert captured.capture_started_at <= captured.capture_completed_at
    assert captured.manifest["notes"][0]["body"] == "Freeze this interpretation."
    assert captured.manifest["captured_queues"] == _source()["queues"]
    listing = review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner")
    assert [entry.snapshot_id for entry in listing] == [captured.snapshot_id]
    assert listing[0].integrity == "verified"
    assert listing[0].content_address == captured.content_address
    assert not hasattr(listing[0], "manifest")
    assert review_snapshot_store.get_snapshot(
        CATALOGUE_PROJECT_ID, captured.snapshot_id, owner_id="owner"
    ) == captured


def test_source_change_error_and_post_flush_failure_each_leave_no_snapshot(monkeypatch):
    changed = _source()
    changed["events"][0]["status"] = "superseded"
    changed["events"][0]["summary"] = "Changed during capture"
    values = iter((_source(), changed))
    with pytest.raises(review_snapshot_store.SnapshotSourceChanged):
        review_snapshot_store.capture_snapshot(
            CATALOGUE_PROJECT_ID, label="Unstable", capture_key=str(uuid.uuid4()),
            owner_id="owner",
            created_by="owner", source_loader=lambda _project: next(values),
        )
    assert review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner") == ()

    incomplete = _source()
    incomplete["source_errors"] = [{
        "source": "run", "source_id": "12", "code": "RUN_BINDING_CORRUPT",
    }]
    with pytest.raises(review_snapshot_store.SnapshotCaptureRejected, match="source errors"):
        review_snapshot_store.capture_snapshot(
            CATALOGUE_PROJECT_ID, label="Incomplete", capture_key=str(uuid.uuid4()),
            owner_id="owner",
            created_by="owner", source_loader=lambda _project: incomplete,
        )
    assert review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner") == ()

    monkeypatch.setattr(
        review_snapshot_store, "_after_snapshot_flush",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("after flush")),
    )
    with pytest.raises(RuntimeError, match="after flush"):
        review_snapshot_store.capture_snapshot(
            CATALOGUE_PROJECT_ID, label="Rollback", capture_key=str(uuid.uuid4()),
            owner_id="owner",
            created_by="owner", source_loader=lambda _project: _source(),
        )
    assert review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner") == ()


def test_capture_key_retry_is_idempotent_and_conflicting_reuse_fails_closed():
    first = review_snapshot_store.capture_snapshot(
        CATALOGUE_PROJECT_ID, label="Daily", capture_key=CAPTURE_KEY,
        owner_id="owner",
        created_by="owner", source_loader=lambda _project: _source(),
    )
    retry = review_snapshot_store.capture_snapshot(
        CATALOGUE_PROJECT_ID, label="Daily", capture_key=CAPTURE_KEY,
        owner_id="owner",
        created_by="owner",
        source_loader=lambda _project: pytest.fail("retry reloaded sources"),
    )
    assert retry == first

    with pytest.raises(review_snapshot_store.SnapshotCaptureConflict):
        review_snapshot_store.capture_snapshot(
            CATALOGUE_PROJECT_ID, label="Different intent", capture_key=CAPTURE_KEY,
            owner_id="owner",
            created_by="owner", source_loader=lambda _project: _source(),
        )
    assert [entry.snapshot_id for entry in review_snapshot_store.list_snapshots(
        CATALOGUE_PROJECT_ID, owner_id="owner"
    )] == [first.snapshot_id]


def test_snapshot_is_project_isolated_archived_readable_and_database_immutable():
    captured = review_snapshot_store.capture_snapshot(
        CATALOGUE_PROJECT_ID, label="Archive me", capture_key=CAPTURE_KEY,
        owner_id="owner",
        created_by="owner", source_loader=lambda _project: _source(),
    )
    other = graph_artifacts.create_project("Other", owner_id="owner")
    with pytest.raises(review_snapshot_store.SnapshotNotFound):
        review_snapshot_store.get_snapshot(other.project_id, captured.snapshot_id, owner_id="owner")

    graph_artifacts.set_project_status(CATALOGUE_PROJECT_ID, "archived", owner_id="owner")
    assert review_snapshot_store.get_snapshot(
        CATALOGUE_PROJECT_ID, captured.snapshot_id, owner_id="owner"
    ) == captured
    with pytest.raises(graph_artifacts.InvalidTransition):
        review_snapshot_store.capture_snapshot(
            CATALOGUE_PROJECT_ID, label="No archived writes",
            owner_id="owner",
            capture_key=str(uuid.uuid4()), created_by="owner",
            source_loader=lambda _project: _source(),
        )

    with SessionLocal.begin() as session:
        with pytest.raises(sa.exc.IntegrityError, match="immutable"):
            session.execute(sa.text(
                "UPDATE project_review_snapshots SET label = 'changed' "
                "WHERE snapshot_id = :snapshot_id"
            ), {"snapshot_id": captured.snapshot_id})


def _insert_raw(session, snapshot_id, *, manifest_json, content_address, completed):
    session.execute(sa.text(
        "INSERT INTO project_review_snapshots "
        "(owner_id, snapshot_id, project_id, label, capture_key, manifest_json, content_address, "
        " created_by, capture_started_at, capture_completed_at) VALUES "
        "('owner', :snapshot_id, :project_id, :label, :capture_key, :manifest, :address, 'owner', "
        " '2026-08-03 10:00:00', :completed)"
    ), {
        "snapshot_id": snapshot_id, "project_id": CATALOGUE_PROJECT_ID,
        "label": snapshot_id, "capture_key": str(uuid.uuid5(uuid.NAMESPACE_OID, snapshot_id)),
        "manifest": manifest_json, "address": content_address, "completed": completed,
    })


def _empty_manifest_json():
    from app.ir.hashing import canonical_json

    return canonical_json({
        "schema_version": 1,
        "project_id": CATALOGUE_PROJECT_ID,
        "events": [],
        "captured_queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "notes": [],
        "source_errors": [],
    })


def test_listing_is_bounded_and_never_loads_manifest_documents():
    manifest_json = _empty_manifest_json()
    address = review_snapshot_store.manifest_address_of_bytes(manifest_json)
    limit = review_snapshot_store.MAX_SNAPSHOT_LISTING
    with SessionLocal.begin() as session:
        for index in range(limit + 5):
            _insert_raw(
                session, f"snapshot.{index:04d}", manifest_json=manifest_json,
                content_address=address, completed=f"2026-08-03 10:{index % 60:02d}:00",
            )

    listing = review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner")

    assert len(listing) == limit
    assert all(entry.integrity == "verified" for entry in listing)
    assert all(not hasattr(entry, "manifest") for entry in listing)


def test_a_corrupt_record_is_contained_and_never_hides_intact_history():
    manifest_json = _empty_manifest_json()
    address = review_snapshot_store.manifest_address_of_bytes(manifest_json)
    with SessionLocal.begin() as session:
        _insert_raw(
            session, "snapshot.intact", manifest_json=manifest_json,
            content_address=address, completed="2026-08-03 10:00:01",
        )
        _insert_raw(
            session, "snapshot.tampered", manifest_json=manifest_json.replace(
                '"events":[]', '"events":[{"smuggled":true}]'
            ), content_address=address, completed="2026-08-03 10:00:02",
        )

    listing = {entry.snapshot_id: entry for entry in
               review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner")}

    assert set(listing) == {"snapshot.intact", "snapshot.tampered"}
    assert listing["snapshot.intact"].integrity == "verified"
    assert listing["snapshot.tampered"].integrity == "corrupt"
    assert review_snapshot_store.get_snapshot(
        CATALOGUE_PROJECT_ID, "snapshot.intact", owner_id="owner"
    ).content_address == address
    with pytest.raises(review_snapshot_store.SnapshotCorrupt):
        review_snapshot_store.get_snapshot(CATALOGUE_PROJECT_ID, "snapshot.tampered", owner_id="owner")


def test_database_refuses_delete_as_well_as_update():
    captured = review_snapshot_store.capture_snapshot(
        CATALOGUE_PROJECT_ID, label="Permanent", capture_key=CAPTURE_KEY,
        owner_id="owner",
        created_by="owner", source_loader=lambda _project: _source(),
    )

    with SessionLocal.begin() as session:
        with pytest.raises(sa.exc.IntegrityError, match="immutable"):
            session.execute(sa.text(
                "DELETE FROM project_review_snapshots WHERE snapshot_id = :snapshot_id"
            ), {"snapshot_id": captured.snapshot_id})

    assert review_snapshot_store.get_snapshot(
        CATALOGUE_PROJECT_ID, captured.snapshot_id, owner_id="owner"
    ) == captured


def test_capture_refuses_an_archived_project_before_reading_any_source():
    graph_artifacts.set_project_status(CATALOGUE_PROJECT_ID, "archived", owner_id="owner")

    with pytest.raises(graph_artifacts.InvalidTransition):
        review_snapshot_store.capture_snapshot(
            CATALOGUE_PROJECT_ID, label="Archived", capture_key=CAPTURE_KEY,
            owner_id="owner",
            created_by="owner",
            source_loader=lambda _project: pytest.fail("archived capture read sources"),
        )

    assert review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner") == ()


def test_a_valid_manifest_with_a_false_declared_address_is_refused_on_read():
    """Isolates the content-address check itself.

    The tampered row in the containment test fails schema validation first, so it
    never reaches the address comparison. Here the manifest is canonical and fully
    valid; only the declared address is a lie, so nothing but the address check can
    catch it.
    """
    manifest_json = _empty_manifest_json()
    honest = review_snapshot_store.manifest_address_of_bytes(manifest_json)
    false_address = f"sha256:{0:064x}"
    assert false_address != honest
    with SessionLocal.begin() as session:
        _insert_raw(
            session, "snapshot.lying", manifest_json=manifest_json,
            content_address=false_address, completed="2026-08-03 10:00:03",
        )

    with pytest.raises(review_snapshot_store.SnapshotCorrupt):
        review_snapshot_store.get_snapshot(CATALOGUE_PROJECT_ID, "snapshot.lying", owner_id="owner")

    listing = review_snapshot_store.list_snapshots(CATALOGUE_PROJECT_ID, owner_id="owner")
    assert [entry.integrity for entry in listing] == ["corrupt"]
