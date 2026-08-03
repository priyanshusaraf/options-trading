import copy

import pytest

from app.core.review_snapshot import SnapshotRejected, build_snapshot_manifest


GRAPH = {
    "identifier": "strategy.alpha",
    "version": 4,
    "content_address": f"sha256:{4:064x}",
}


def _event(event_id="run:12", summary="Experiment run 12: completed"):
    return {
        "event_id": event_id,
        "type": "experiment_run",
        "occurred_at": "2026-08-03T10:00:00.000000Z",
        "status": "completed",
        "summary": summary,
        "references": {
            "graph": GRAPH,
            "run_id": 12,
            "finding_id": None,
            "candidate_id": None,
        },
    }


def _source():
    return {
        "events": [_event()],
        "queues": {
            "review_needed_runs": [{
                "run_id": 12,
                "status": "needs_review",
                "evidence_state": "verified",
                "graph": GRAPH,
            }],
            "pending_candidates": [{
                "candidate_id": 7, "run_id": 12, "status": "pending", "graph": GRAPH,
            }],
            "active_findings": [{
                "finding_id": 9, "evidence_run_id": 12, "polarity": "negative",
                "confidence": 0.4, "graph": GRAPH,
            }],
        },
        "source_errors": [],
    }


def _note(note_id="note.1"):
    return {
        "note_id": note_id,
        "project_id": "project.alpha",
        "event_id": "run:12",
        "event_type": "experiment_run",
        "body": "Review this exact run.",
        "created_by": "owner",
        "revision": 2,
        "anchor_state": "available",
        "updated_at": "2026-08-03T10:01:00.000000Z",
    }


def test_manifest_is_closed_canonical_and_content_addressed():
    source = _source()
    source["events"].insert(0, _event("run:2", "Experiment run 2: completed"))
    notes = [_note("note.z"), _note("note.a")]

    built = build_snapshot_manifest("project.alpha", source, notes)

    assert built.content_address.startswith("sha256:")
    assert built.manifest == {
        "schema_version": 1,
        "project_id": "project.alpha",
        "events": sorted(source["events"], key=lambda item: item["event_id"]),
        "captured_queues": source["queues"],
        "notes": [{
            "note_id": note["note_id"],
            "event_id": note["event_id"],
            "event_type": note["event_type"],
            "body": note["body"],
            "revision": note["revision"],
            "anchor_state": note["anchor_state"],
            "updated_at": note["updated_at"],
        } for note in sorted(notes, key=lambda item: item["note_id"])],
        "source_errors": [],
    }


def test_canonical_equivalents_share_identity_and_allowed_changes_do_not():
    left_source = _source()
    left_source["events"].append(_event("run:2", "Second event"))
    right_source = copy.deepcopy(left_source)
    right_source["events"].reverse()
    left_notes = [_note("note.z"), _note("note.a")]
    right_notes = list(reversed(copy.deepcopy(left_notes)))

    left = build_snapshot_manifest("project.alpha", left_source, left_notes)
    right = build_snapshot_manifest("project.alpha", right_source, right_notes)
    assert left == right

    changed = copy.deepcopy(right_notes)
    changed[0]["body"] = "Changed owner interpretation."
    assert build_snapshot_manifest(
        "project.alpha", right_source, changed
    ).content_address != left.content_address


def test_manifest_keeps_missing_anchor_without_inventing_source_text():
    note = _note()
    note["event_id"] = "run:missing"
    note["anchor_state"] = "missing"

    manifest = build_snapshot_manifest("project.alpha", _source(), [note]).manifest

    assert manifest["notes"][0]["anchor_state"] == "missing"
    assert manifest["notes"][0]["event_id"] == "run:missing"
    assert "summary" not in manifest["notes"][0]


def test_source_errors_unknown_fields_cross_project_notes_and_raw_content_fail_closed():
    corrupt = _source()
    corrupt["source_errors"] = [{
        "source": "candidate", "source_id": "7", "code": "CANDIDATE_DECISION_CORRUPT",
    }]
    with pytest.raises(SnapshotRejected, match="source errors"):
        build_snapshot_manifest("project.alpha", corrupt, [])

    wrong = _note()
    wrong["project_id"] = "project.other"
    with pytest.raises(SnapshotRejected, match="project"):
        build_snapshot_manifest("project.alpha", _source(), [wrong])

    for field in ("raw_graph", "evidence", "scorecard", "decision_reason", "global_operations"):
        widened = _source()
        widened[field] = {"secret": "must not persist"}
        with pytest.raises(SnapshotRejected, match="shape"):
            build_snapshot_manifest("project.alpha", widened, [])


def test_document_and_queue_bounds_refuse_capture():
    too_many = _source()
    too_many["events"] = [_event(f"run:{index}") for index in range(2001)]
    with pytest.raises(SnapshotRejected, match="event limit"):
        build_snapshot_manifest("project.alpha", too_many, [])

    too_many = _source()
    too_many["queues"]["pending_candidates"] = [
        {"candidate_id": index, "run_id": 12, "status": "pending", "graph": GRAPH}
        for index in range(1, 2002)
    ]
    with pytest.raises(SnapshotRejected, match="queue limit"):
        build_snapshot_manifest("project.alpha", too_many, [])
