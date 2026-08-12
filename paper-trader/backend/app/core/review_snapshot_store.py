"""Transactional append-only persistence for immutable project review snapshots."""
from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.review_aggregation import project_review_source
from app.core.review_snapshot import (
    MAX_SNAPSHOT_NOTES,
    SnapshotRejected,
    build_snapshot_manifest,
    manifest_address_of_bytes,
    validate_snapshot_manifest,
)
from app.db.models import Project, ProjectReviewNote, ProjectReviewSnapshot
from app.db.session import SessionLocal
from app.editor.graph_artifacts import InvalidTransition, ProjectNotFound
from app.ir.hashing import canonical_json


MAX_SNAPSHOT_LISTING = 100


@dataclass(frozen=True)
class SnapshotListing:
    """Bounded metadata for one historical capture. Deliberately carries no manifest:
    a listing must stay constant-size per row however large the captured review was."""

    snapshot_id: str
    project_id: str
    label: str
    capture_key: str
    content_address: str
    created_by: str
    capture_started_at: dt.datetime
    capture_completed_at: dt.datetime
    integrity: str


@dataclass(frozen=True)
class ReviewSnapshot:
    snapshot_id: str
    project_id: str
    label: str
    capture_key: str
    manifest: dict[str, Any]
    content_address: str
    created_by: str
    capture_started_at: dt.datetime
    capture_completed_at: dt.datetime


class SnapshotCaptureRejected(Exception):
    pass


class SnapshotSourceChanged(Exception):
    pass


class SnapshotCaptureConflict(Exception):
    pass


class SnapshotNotFound(Exception):
    pass


class SnapshotCorrupt(Exception):
    pass


def _label(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
        raise SnapshotCaptureRejected("snapshot label must contain 1 to 80 characters")
    return value.strip()


def _capture_key(value: str) -> str:
    if not isinstance(value, str):
        raise SnapshotCaptureRejected("snapshot capture key must be a canonical UUID")
    try:
        parsed = str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise SnapshotCaptureRejected("snapshot capture key must be a canonical UUID") from exc
    if parsed != value:
        raise SnapshotCaptureRejected("snapshot capture key must be a canonical UUID")
    return parsed


def _snapshot(row: ProjectReviewSnapshot) -> ReviewSnapshot:
    try:
        manifest = json.loads(row.manifest_json)
        validated = validate_snapshot_manifest(manifest)
    except (TypeError, ValueError, SnapshotRejected) as exc:
        raise SnapshotCorrupt(row.snapshot_id) from exc
    if (
        canonical_json(manifest) != row.manifest_json
        or validated.content_address != row.content_address
        or manifest["project_id"] != row.project_id
        or not isinstance(row.created_by, str) or not row.created_by
        or len(row.created_by) > 64
        or row.capture_completed_at < row.capture_started_at
    ):
        raise SnapshotCorrupt(row.snapshot_id)
    return ReviewSnapshot(
        snapshot_id=row.snapshot_id,
        project_id=row.project_id,
        label=row.label,
        capture_key=row.capture_key,
        manifest=manifest,
        content_address=row.content_address,
        created_by=row.created_by,
        capture_started_at=row.capture_started_at,
        capture_completed_at=row.capture_completed_at,
    )


def _existing(
    session, project_id: str, capture_key: str, *, owner_id: str,
) -> ProjectReviewSnapshot | None:
    return session.scalar(select(ProjectReviewSnapshot).where(
        ProjectReviewSnapshot.owner_id == owner_id,
        ProjectReviewSnapshot.project_id == project_id,
        ProjectReviewSnapshot.capture_key == capture_key,
    ))


def _project(session, project_id: str, *, owner_id: str, active: bool) -> Project:
    project = session.scalar(select(Project).where(
        Project.owner_id == owner_id, Project.project_id == project_id,
    ))
    if project is None:
        raise ProjectNotFound(project_id)
    if active and project.status != "active":
        raise InvalidTransition(f"project {project_id!r} is archived")
    return project


def _intent(row: ProjectReviewSnapshot, label: str) -> ReviewSnapshot:
    if row.label != label:
        raise SnapshotCaptureConflict(row.capture_key)
    return _snapshot(row)


def _note_documents(
    project_id: str,
    rows: list[ProjectReviewNote],
    source: Mapping[str, Any],
) -> list[dict[str, Any]]:
    event_types = {event["event_id"]: event["type"] for event in source["events"]}
    documents = []
    for note in rows:
        updated_at = note.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=dt.UTC)
        documents.append({
            "note_id": note.note_id,
            "project_id": note.project_id,
            "event_id": note.event_id,
            "event_type": note.event_type,
            "body": note.body,
            "created_by": note.created_by,
            "revision": note.revision,
            "anchor_state": (
                "available" if event_types.get(note.event_id) == note.event_type else "missing"
            ),
            "updated_at": updated_at.astimezone(dt.UTC).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
        })
    return documents


def _after_snapshot_flush(_session, _row) -> None:
    """Failure-injection seam proving post-insert transaction rollback."""


def capture_snapshot(
    project_id: str,
    *,
    owner_id: str,
    label: str,
    capture_key: str,
    created_by: str,
    source_loader: Callable[[str], Mapping[str, Any]] | None = None,
) -> ReviewSnapshot:
    normalized_label = _label(label)
    normalized_key = _capture_key(capture_key)
    if not isinstance(created_by, str) or not created_by or len(created_by) > 64:
        raise SnapshotCaptureRejected("snapshot owner is invalid")
    if source_loader is None:
        loader = partial(project_review_source, owner_id=owner_id)
    else:
        loader = source_loader

    with SessionLocal() as session:
        existing = _existing(session, project_id, normalized_key, owner_id=owner_id)
        if existing is not None:
            # An idempotent retry is a read, so it is served for archived projects too.
            _project(session, project_id, owner_id=owner_id, active=False)
            return _intent(existing, normalized_label)
        # Refuse an archived project before doing any source work: capture is a write.
        _project(session, project_id, owner_id=owner_id, active=True)

    started = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    source_before = loader(project_id)
    try:
        before_identity = build_snapshot_manifest(
            project_id, source_before, []
        ).content_address
    except SnapshotRejected as exc:
        raise SnapshotCaptureRejected(str(exc)) from exc

    try:
        with SessionLocal.begin() as session:
            _project(session, project_id, owner_id=owner_id, active=True)
            existing = _existing(session, project_id, normalized_key, owner_id=owner_id)
            if existing is not None:
                return _intent(existing, normalized_label)
            notes = session.scalars(select(ProjectReviewNote).where(
                ProjectReviewNote.owner_id == owner_id,
                ProjectReviewNote.project_id == project_id,
                ProjectReviewNote.deleted_at.is_(None),
            ).order_by(ProjectReviewNote.note_id).limit(MAX_SNAPSHOT_NOTES + 1)).all()
            source_after = loader(project_id)
            try:
                after_identity = build_snapshot_manifest(
                    project_id, source_after, []
                ).content_address
            except SnapshotRejected as exc:
                raise SnapshotCaptureRejected(str(exc)) from exc
            if before_identity != after_identity:
                raise SnapshotSourceChanged("review sources changed during capture")
            try:
                built = build_snapshot_manifest(
                    project_id, source_after,
                    _note_documents(project_id, list(notes), source_after),
                )
            except SnapshotRejected as exc:
                raise SnapshotCaptureRejected(str(exc)) from exc
            completed = dt.datetime.now(dt.UTC).replace(tzinfo=None)
            row = ProjectReviewSnapshot(
                owner_id=owner_id,
                snapshot_id=f"snapshot.{uuid.uuid4().hex}",
                project_id=project_id,
                label=normalized_label,
                capture_key=normalized_key,
                manifest_json=canonical_json(built.manifest),
                content_address=built.content_address,
                created_by=created_by,
                capture_started_at=started,
                capture_completed_at=completed,
            )
            session.add(row)
            session.flush()
            _after_snapshot_flush(session, row)
            result = _snapshot(row)
        return result
    except IntegrityError as exc:
        with SessionLocal() as session:
            existing = _existing(session, project_id, normalized_key, owner_id=owner_id)
            if existing is not None:
                return _intent(existing, normalized_label)
        raise SnapshotCaptureConflict(normalized_key) from exc


def list_snapshots(project_id: str, *, owner_id: str) -> tuple[SnapshotListing, ...]:
    """The most recent captures as bounded metadata, each verified against its stored
    content address. A row whose bytes no longer hash to its declared address is
    reported as `corrupt` rather than raised: one damaged record must not withhold the
    rest of a project's review history."""
    with SessionLocal() as session:
        _project(session, project_id, owner_id=owner_id, active=False)
        rows = session.execute(select(
            ProjectReviewSnapshot.owner_id,
            ProjectReviewSnapshot.snapshot_id,
            ProjectReviewSnapshot.project_id,
            ProjectReviewSnapshot.label,
            ProjectReviewSnapshot.capture_key,
            ProjectReviewSnapshot.manifest_json,
            ProjectReviewSnapshot.content_address,
            ProjectReviewSnapshot.created_by,
            ProjectReviewSnapshot.capture_started_at,
            ProjectReviewSnapshot.capture_completed_at,
        ).where(
            ProjectReviewSnapshot.owner_id == owner_id,
            ProjectReviewSnapshot.project_id == project_id,
        ).order_by(
            ProjectReviewSnapshot.capture_completed_at.desc(),
            ProjectReviewSnapshot.snapshot_id.desc(),
        ).limit(MAX_SNAPSHOT_LISTING)).all()
        return tuple(SnapshotListing(
            snapshot_id=row.snapshot_id,
            project_id=row.project_id,
            label=row.label,
            capture_key=row.capture_key,
            content_address=row.content_address,
            created_by=row.created_by,
            capture_started_at=row.capture_started_at,
            capture_completed_at=row.capture_completed_at,
            integrity=(
                "verified"
                if (
                    manifest_address_of_bytes(row.manifest_json) == row.content_address
                    and isinstance(row.created_by, str) and row.created_by
                    and len(row.created_by) <= 64
                    and row.capture_completed_at >= row.capture_started_at
                )
                else "corrupt"
            ),
        ) for row in rows)


def get_snapshot(project_id: str, snapshot_id: str, *, owner_id: str) -> ReviewSnapshot:
    with SessionLocal() as session:
        _project(session, project_id, owner_id=owner_id, active=False)
        row = session.get(ProjectReviewSnapshot, (owner_id, snapshot_id))
        if row is None or row.project_id != project_id:
            raise SnapshotNotFound()
        return _snapshot(row)


__all__ = [
    "MAX_SNAPSHOT_LISTING", "ReviewSnapshot", "SnapshotCaptureConflict",
    "SnapshotCaptureRejected", "SnapshotCorrupt", "SnapshotListing", "SnapshotNotFound",
    "SnapshotSourceChanged", "capture_snapshot", "get_snapshot", "list_snapshots",
    "manifest_address_of_bytes",
]
