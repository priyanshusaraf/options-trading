"""Canonical immutable manifests for bounded historical project review capture."""
from __future__ import annotations

import datetime as dt
import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.core.research_review import (
    EVENT_STATUSES,
    EVENT_TYPES,
    ReviewQueryRejected,
    make_review_event,
)
from app.ir.hashing import content_address


MAX_SNAPSHOT_EVENTS = 2_000
MAX_SNAPSHOT_NOTES = 2_000
MAX_SNAPSHOT_QUEUE_ITEMS = 2_000
_SOURCE_FIELDS = {"events", "queues", "source_errors"}
_QUEUE_FIELDS = {"review_needed_runs", "pending_candidates", "active_findings"}
_NOTE_FIELDS = {
    "note_id", "project_id", "event_id", "event_type", "body", "created_by",
    "revision", "anchor_state", "updated_at",
}
_GRAPH_FIELDS = {"identifier", "version", "content_address"}


class SnapshotRejected(Exception):
    pass


@dataclass(frozen=True)
class SnapshotManifest:
    manifest: dict[str, Any]
    content_address: str


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise SnapshotRejected("snapshot timestamp is invalid")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotRejected("snapshot timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise SnapshotRejected("snapshot timestamp is invalid")
    return parsed.astimezone(dt.UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _graph(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _GRAPH_FIELDS:
        raise SnapshotRejected("snapshot graph reference is invalid")
    if (
        not isinstance(value["identifier"], str) or not value["identifier"]
        or len(value["identifier"]) > 128
        or not isinstance(value["version"], int) or isinstance(value["version"], bool)
        or value["version"] < 1
        or not isinstance(value["content_address"], str)
        or not value["content_address"].startswith("sha256:")
        or len(value["content_address"]) != 71
    ):
        raise SnapshotRejected("snapshot graph reference is invalid")
    return dict(value)


def _events(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        raise SnapshotRejected("snapshot event source is invalid")
    if len(values) > MAX_SNAPSHOT_EVENTS:
        raise SnapshotRejected("snapshot event limit is 2000")
    events = []
    for raw in values:
        if not isinstance(raw, Mapping) or set(raw) != {
            "event_id", "type", "occurred_at", "status", "summary", "references",
        }:
            raise SnapshotRejected("snapshot event shape is invalid")
        try:
            event = make_review_event(
                event_id=raw["event_id"], event_type=raw["type"],
                occurred_at=raw["occurred_at"], status=raw["status"],
                summary=raw["summary"], references=raw["references"],
            )
        except ReviewQueryRejected as exc:
            raise SnapshotRejected("snapshot event is invalid") from exc
        events.append(event)
    events.sort(key=lambda item: item["event_id"])
    if len({event["event_id"] for event in events}) != len(events):
        raise SnapshotRejected("snapshot event ids must be unique")
    return events


def _queue_values(value: Any, fields: set[str], label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise SnapshotRejected(f"snapshot {label} queue is invalid")
    if len(value) > MAX_SNAPSHOT_QUEUE_ITEMS:
        raise SnapshotRejected("snapshot queue limit is 2000 per queue")
    if any(not isinstance(item, Mapping) or set(item) != fields for item in value):
        raise SnapshotRejected(f"snapshot {label} queue shape is invalid")
    return list(value)


def _positive_id(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SnapshotRejected(f"snapshot {label} is invalid")
    return value


def _queues(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, Mapping) or set(value) != _QUEUE_FIELDS:
        raise SnapshotRejected("snapshot queue shape is invalid")
    runs = []
    for raw in _queue_values(
        value["review_needed_runs"],
        {"run_id", "status", "evidence_state", "graph"}, "run",
    ):
        if raw["status"] not in EVENT_STATUSES or (
            not isinstance(raw["evidence_state"], str)
            or not raw["evidence_state"] or len(raw["evidence_state"]) > 32
        ):
            raise SnapshotRejected("snapshot run queue state is invalid")
        runs.append({
            "run_id": _positive_id(raw["run_id"], "run id"),
            "status": raw["status"],
            "evidence_state": raw["evidence_state"],
            "graph": _graph(raw["graph"]),
        })
    candidates = []
    for raw in _queue_values(
        value["pending_candidates"],
        {"candidate_id", "run_id", "status", "graph"}, "candidate",
    ):
        if raw["status"] != "pending":
            raise SnapshotRejected("snapshot candidate queue state is invalid")
        candidates.append({
            "candidate_id": _positive_id(raw["candidate_id"], "candidate id"),
            "run_id": _positive_id(raw["run_id"], "run id"),
            "status": "pending",
            "graph": _graph(raw["graph"]),
        })
    findings = []
    for raw in _queue_values(
        value["active_findings"],
        {"finding_id", "evidence_run_id", "polarity", "confidence", "graph"},
        "finding",
    ):
        confidence = raw["confidence"]
        if (
            raw["polarity"] not in {"positive", "negative"}
            or not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
            or not math.isfinite(confidence) or not 0 <= confidence <= 1
        ):
            raise SnapshotRejected("snapshot finding queue state is invalid")
        findings.append({
            "finding_id": _positive_id(raw["finding_id"], "finding id"),
            "evidence_run_id": _positive_id(raw["evidence_run_id"], "run id"),
            "polarity": raw["polarity"],
            "confidence": confidence,
            "graph": _graph(raw["graph"]),
        })
    runs.sort(key=lambda item: item["run_id"])
    candidates.sort(key=lambda item: item["candidate_id"])
    findings.sort(key=lambda item: item["finding_id"])
    for items, key in (
        (runs, "run_id"), (candidates, "candidate_id"), (findings, "finding_id")
    ):
        if len({item[key] for item in items}) != len(items):
            raise SnapshotRejected("snapshot queue ids must be unique")
    return {
        "review_needed_runs": runs,
        "pending_candidates": candidates,
        "active_findings": findings,
    }


def _notes(project_id: str, values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        raise SnapshotRejected("snapshot note source is invalid")
    if len(values) > MAX_SNAPSHOT_NOTES:
        raise SnapshotRejected("snapshot note limit is 2000")
    notes = []
    for raw in values:
        if not isinstance(raw, Mapping) or set(raw) != _NOTE_FIELDS:
            raise SnapshotRejected("snapshot note shape is invalid")
        if (
            raw["project_id"] != project_id
            or not isinstance(raw["created_by"], str) or not raw["created_by"]
            or len(raw["created_by"]) > 64
            or not isinstance(raw["note_id"], str) or not raw["note_id"]
            or len(raw["note_id"]) > 64
            or not isinstance(raw["event_id"], str) or not raw["event_id"]
            or len(raw["event_id"]) > 200
            or raw["event_type"] not in EVENT_TYPES
            or not isinstance(raw["body"], str) or not raw["body"].strip()
            or raw["body"] != raw["body"].strip() or len(raw["body"]) > 4_000
            or not isinstance(raw["revision"], int) or isinstance(raw["revision"], bool)
            or raw["revision"] < 0
            or raw["anchor_state"] not in {"available", "missing"}
        ):
            raise SnapshotRejected("snapshot note project or fields are invalid")
        notes.append({
            "note_id": raw["note_id"],
            "event_id": raw["event_id"],
            "event_type": raw["event_type"],
            "body": raw["body"],
            "revision": raw["revision"],
            "anchor_state": raw["anchor_state"],
            "updated_at": _timestamp(raw["updated_at"]),
        })
    notes.sort(key=lambda item: item["note_id"])
    if len({note["note_id"] for note in notes}) != len(notes):
        raise SnapshotRejected("snapshot note ids must be unique")
    return notes


def build_snapshot_manifest(
    project_id: str,
    source: Mapping[str, Any],
    notes: Iterable[Mapping[str, Any]],
) -> SnapshotManifest:
    if not isinstance(project_id, str) or not project_id or len(project_id) > 64:
        raise SnapshotRejected("snapshot project id is invalid")
    if not isinstance(source, Mapping) or set(source) != _SOURCE_FIELDS:
        raise SnapshotRejected("snapshot source shape is invalid")
    if not isinstance(source["source_errors"], (list, tuple)):
        raise SnapshotRejected("snapshot source errors are invalid")
    if source["source_errors"]:
        raise SnapshotRejected("snapshot capture refuses source errors")
    manifest = {
        "schema_version": 1,
        "project_id": project_id,
        "events": _events(source["events"]),
        "captured_queues": _queues(source["queues"]),
        "notes": _notes(project_id, notes),
        "source_errors": [],
    }
    return SnapshotManifest(manifest=manifest, content_address=content_address(manifest))


def manifest_address_of_bytes(manifest_json: str) -> str:
    """The content address of already-canonical stored manifest bytes.

    `content_address()` is `sha256(canonical_json(value))`, so hashing canonical bytes
    directly yields the same address without parsing the document. A listing can
    therefore verify stored identity in constant memory per row: a byte-level match
    proves the row is identical to what `validate_snapshot_manifest` accepted on insert.
    """
    digest = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def validate_snapshot_manifest(value: Mapping[str, Any]) -> SnapshotManifest:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "project_id", "events", "captured_queues", "notes",
        "source_errors",
    } or value["schema_version"] != 1:
        raise SnapshotRejected("snapshot manifest shape is invalid")
    if not isinstance(value["notes"], (list, tuple)):
        raise SnapshotRejected("snapshot manifest notes are invalid")
    hydrated_notes = []
    for note in value["notes"]:
        if not isinstance(note, Mapping) or set(note) != {
            "note_id", "event_id", "event_type", "body", "revision", "anchor_state",
            "updated_at",
        }:
            raise SnapshotRejected("snapshot manifest note shape is invalid")
        hydrated_notes.append({
            **note,
            "project_id": value["project_id"],
            "created_by": "owner",
        })
    rebuilt = build_snapshot_manifest(
        value["project_id"],
        {
            "events": value["events"],
            "queues": value["captured_queues"],
            "source_errors": value["source_errors"],
        },
        hydrated_notes,
    )
    if rebuilt.manifest != dict(value):
        raise SnapshotRejected("snapshot manifest is not canonical")
    return rebuilt


__all__ = [
    "MAX_SNAPSHOT_EVENTS", "MAX_SNAPSHOT_NOTES", "MAX_SNAPSHOT_QUEUE_ITEMS",
    "SnapshotManifest", "SnapshotRejected", "build_snapshot_manifest",
    "manifest_address_of_bytes", "validate_snapshot_manifest",
]
