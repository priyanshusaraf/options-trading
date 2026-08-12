"""Optimistic application-DB persistence for non-authoritative review state."""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.research_review import (
    EVENT_TYPES,
    ReviewQueryRejected,
    normalize_review_filters,
)
from app.db.models import Project, ProjectReviewNote, ProjectReviewSavedView
from app.db.session import SessionLocal
from app.editor.graph_artifacts import InvalidTransition, ProjectNotFound
from app.ir.hashing import canonical_json


@dataclass(frozen=True)
class ReviewNote:
    note_id: str
    project_id: str
    event_id: str
    event_type: str
    body: str
    created_by: str
    revision: int
    deleted_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime


@dataclass(frozen=True)
class ReviewSavedView:
    view_id: str
    project_id: str
    name: str
    filters: dict[str, Any]
    created_by: str
    revision: int
    deleted_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ReviewStateNotFound(Exception):
    pass


class ReviewStateRejected(Exception):
    pass


class ReviewStateCorrupt(Exception):
    pass


class ReviewViewNameConflict(Exception):
    pass


class ReviewStateConflict(Exception):
    def __init__(self, current_revision: int):
        super().__init__(f"review state is at revision {current_revision}")
        self.current_revision = current_revision


def _project(session, project_id: str, *, owner_id: str, active: bool) -> Project:
    project = session.scalar(select(Project).where(
        Project.owner_id == owner_id, Project.project_id == project_id,
    ))
    if project is None:
        raise ProjectNotFound(project_id)
    if active and project.status != "active":
        raise InvalidTransition(f"project {project_id!r} is archived")
    return project


def _note(row: ProjectReviewNote) -> ReviewNote:
    return ReviewNote(
        note_id=row.note_id,
        project_id=row.project_id,
        event_id=row.event_id,
        event_type=row.event_type,
        body=row.body,
        created_by=row.created_by,
        revision=row.revision,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _saved_view(row: ProjectReviewSavedView) -> ReviewSavedView:
    try:
        decoded = json.loads(row.filters_json)
        filters = normalize_review_filters(decoded)
    except (TypeError, ValueError, ReviewQueryRejected) as exc:
        raise ReviewStateCorrupt(row.view_id) from exc
    if canonical_json(filters) != row.filters_json:
        raise ReviewStateCorrupt(row.view_id)
    return ReviewSavedView(
        view_id=row.view_id,
        project_id=row.project_id,
        name=row.name,
        filters=filters,
        created_by=row.created_by,
        revision=row.revision,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _body(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 4000:
        raise ReviewStateRejected("review note body must contain 1 to 4000 characters")
    return value.strip()


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
        raise ReviewStateRejected("saved review name must contain 1 to 80 characters")
    return value.strip()


def _filters(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return normalize_review_filters(value)
    except ReviewQueryRejected as exc:
        raise ReviewStateRejected(str(exc)) from exc


def create_note(
    project_id: str,
    *,
    owner_id: str,
    event_id: str,
    event_type: str,
    body: str,
    created_by: str,
) -> ReviewNote:
    if (
        not isinstance(event_id, str) or not event_id or len(event_id) > 200
        or event_type not in EVENT_TYPES
        or not isinstance(created_by, str) or not created_by or len(created_by) > 64
    ):
        raise ReviewStateRejected("review note anchor or owner is invalid")
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _project(session, project_id, owner_id=owner_id, active=True)
        row = ProjectReviewNote(
            owner_id=owner_id,
            note_id=f"note.{uuid.uuid4().hex}",
            project_id=project_id,
            event_id=event_id,
            event_type=event_type,
            body=_body(body),
            created_by=created_by,
            revision=0,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        result = _note(row)
    return result


def list_notes(project_id: str, *, owner_id: str) -> tuple[ReviewNote, ...]:
    with SessionLocal() as session:
        _project(session, project_id, owner_id=owner_id, active=False)
        rows = session.scalars(
            select(ProjectReviewNote)
            .where(
                ProjectReviewNote.owner_id == owner_id,
                ProjectReviewNote.project_id == project_id,
                ProjectReviewNote.deleted_at.is_(None),
            )
            .order_by(ProjectReviewNote.created_at, ProjectReviewNote.note_id)
        ).all()
        return tuple(_note(row) for row in rows)


def _owned_note(session, project_id: str, note_id: str, *, owner_id: str,
                actor_id: str | None = None, can_manage: bool = True) -> ProjectReviewNote:
    row = session.get(ProjectReviewNote, (owner_id, note_id))
    if (row is None or row.project_id != project_id or row.deleted_at is not None
            or (not can_manage and row.created_by != actor_id)):
        raise ReviewStateNotFound()
    return row


def update_note(
    project_id: str, note_id: str, *, owner_id: str, base_revision: int, body: str,
    actor_id: str | None = None, can_manage: bool = True,
) -> ReviewNote:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _project(session, project_id, owner_id=owner_id, active=True)
        row = _owned_note(session, project_id, note_id, owner_id=owner_id,
                          actor_id=actor_id, can_manage=can_manage)
        if row.revision != base_revision:
            raise ReviewStateConflict(row.revision)
        claimed = session.execute(
            update(ProjectReviewNote)
            .where(
                ProjectReviewNote.owner_id == owner_id,
                ProjectReviewNote.note_id == note_id,
                ProjectReviewNote.project_id == project_id,
                ProjectReviewNote.revision == base_revision,
                ProjectReviewNote.deleted_at.is_(None),
                *(() if can_manage else (ProjectReviewNote.created_by == actor_id,)),
            )
            .values(body=_body(body), revision=base_revision + 1, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.expire_all()
            current = _owned_note(session, project_id, note_id, owner_id=owner_id,
                                  actor_id=actor_id, can_manage=can_manage)
            raise ReviewStateConflict(current.revision)
        session.expire_all()
        result = _note(_owned_note(session, project_id, note_id, owner_id=owner_id))
    return result


def delete_note(project_id: str, note_id: str, *, owner_id: str, base_revision: int,
                actor_id: str | None = None, can_manage: bool = True) -> ReviewNote:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _project(session, project_id, owner_id=owner_id, active=True)
        row = _owned_note(session, project_id, note_id, owner_id=owner_id,
                          actor_id=actor_id, can_manage=can_manage)
        if row.revision != base_revision:
            raise ReviewStateConflict(row.revision)
        claimed = session.execute(
            update(ProjectReviewNote)
            .where(
                ProjectReviewNote.owner_id == owner_id,
                ProjectReviewNote.note_id == note_id,
                ProjectReviewNote.project_id == project_id,
                ProjectReviewNote.revision == base_revision,
                ProjectReviewNote.deleted_at.is_(None),
                *(() if can_manage else (ProjectReviewNote.created_by == actor_id,)),
            )
            .values(
                deleted_at=now, revision=base_revision + 1, updated_at=now
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.expire_all()
            current = _owned_note(session, project_id, note_id, owner_id=owner_id,
                                  actor_id=actor_id, can_manage=can_manage)
            raise ReviewStateConflict(current.revision)
        session.expire_all()
        result = _note(session.get(ProjectReviewNote, (owner_id, note_id)))
    return result


def create_saved_view(
    project_id: str,
    *,
    owner_id: str,
    name: str,
    filters: Mapping[str, Any],
    created_by: str,
) -> ReviewSavedView:
    if not isinstance(created_by, str) or not created_by or len(created_by) > 64:
        raise ReviewStateRejected("saved review owner is invalid")
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _project(session, project_id, owner_id=owner_id, active=True)
        row = ProjectReviewSavedView(
            owner_id=owner_id,
            view_id=f"view.{uuid.uuid4().hex}",
            project_id=project_id,
            name=_name(name),
            filters_json=canonical_json(_filters(filters)),
            created_by=created_by,
            revision=0,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            raise ReviewViewNameConflict(row.name) from exc
        result = _saved_view(row)
    return result


def list_saved_views(project_id: str, *, owner_id: str) -> tuple[ReviewSavedView, ...]:
    with SessionLocal() as session:
        _project(session, project_id, owner_id=owner_id, active=False)
        rows = session.scalars(
            select(ProjectReviewSavedView)
            .where(
                ProjectReviewSavedView.owner_id == owner_id,
                ProjectReviewSavedView.project_id == project_id,
                ProjectReviewSavedView.deleted_at.is_(None),
            )
            .order_by(ProjectReviewSavedView.name, ProjectReviewSavedView.view_id)
        ).all()
        return tuple(_saved_view(row) for row in rows)


def _owned_saved_view(
    session, project_id: str, view_id: str, *, owner_id: str,
    actor_id: str | None = None, can_manage: bool = True,
) -> ProjectReviewSavedView:
    row = session.get(ProjectReviewSavedView, (owner_id, view_id))
    if (row is None or row.project_id != project_id or row.deleted_at is not None
            or (not can_manage and row.created_by != actor_id)):
        raise ReviewStateNotFound()
    return row


def update_saved_view(
    project_id: str,
    view_id: str,
    *,
    owner_id: str,
    base_revision: int,
    name: str,
    filters: Mapping[str, Any],
    actor_id: str | None = None,
    can_manage: bool = True,
) -> ReviewSavedView:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _project(session, project_id, owner_id=owner_id, active=True)
        row = _owned_saved_view(session, project_id, view_id, owner_id=owner_id,
                                actor_id=actor_id, can_manage=can_manage)
        if row.revision != base_revision:
            raise ReviewStateConflict(row.revision)
        try:
            claimed = session.execute(
                update(ProjectReviewSavedView)
                .where(
                    ProjectReviewSavedView.owner_id == owner_id,
                    ProjectReviewSavedView.view_id == view_id,
                    ProjectReviewSavedView.project_id == project_id,
                    ProjectReviewSavedView.revision == base_revision,
                    ProjectReviewSavedView.deleted_at.is_(None),
                    *(() if can_manage else (ProjectReviewSavedView.created_by == actor_id,)),
                )
                .values(
                    name=_name(name),
                    filters_json=canonical_json(_filters(filters)),
                    revision=base_revision + 1,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            session.flush()
        except IntegrityError as exc:
            raise ReviewViewNameConflict(name) from exc
        if claimed.rowcount != 1:
            session.expire_all()
            current = _owned_saved_view(session, project_id, view_id, owner_id=owner_id,
                                        actor_id=actor_id, can_manage=can_manage)
            raise ReviewStateConflict(current.revision)
        session.expire_all()
        result = _saved_view(_owned_saved_view(session, project_id, view_id, owner_id=owner_id))
    return result


def delete_saved_view(
    project_id: str, view_id: str, *, owner_id: str, base_revision: int,
    actor_id: str | None = None, can_manage: bool = True,
) -> ReviewSavedView:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _project(session, project_id, owner_id=owner_id, active=True)
        row = _owned_saved_view(session, project_id, view_id, owner_id=owner_id,
                                actor_id=actor_id, can_manage=can_manage)
        if row.revision != base_revision:
            raise ReviewStateConflict(row.revision)
        claimed = session.execute(
            update(ProjectReviewSavedView)
            .where(
                ProjectReviewSavedView.owner_id == owner_id,
                ProjectReviewSavedView.view_id == view_id,
                ProjectReviewSavedView.project_id == project_id,
                ProjectReviewSavedView.revision == base_revision,
                ProjectReviewSavedView.deleted_at.is_(None),
                *(() if can_manage else (ProjectReviewSavedView.created_by == actor_id,)),
            )
            .values(
                deleted_at=now, revision=base_revision + 1, updated_at=now
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.expire_all()
            current = _owned_saved_view(session, project_id, view_id, owner_id=owner_id,
                                        actor_id=actor_id, can_manage=can_manage)
            raise ReviewStateConflict(current.revision)
        session.expire_all()
        result = _saved_view(session.get(ProjectReviewSavedView, (owner_id, view_id)))
    return result
