"""Daily review aggregation plus non-authoritative project review state."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, require
from app.core import review_state
from app.core.config import get_settings
from app.core.review_aggregation import project_review_source
from app.core.research_review import (
    ReviewQueryRejected,
    paginate_review_events,
)
from app.editor import graph_artifacts as store
from research.config import operation_receipt_path
from research.operations import OperationStateCorrupt, ResearchOperationRecorder


def _research_gate() -> None:
    if not get_settings().research_enabled:
        raise HTTPException(
            status_code=403,
            detail="research plane disabled (set PT_RESEARCH_ENABLED=1)",
        )


router = APIRouter(prefix="/api/ir", dependencies=[Depends(_research_gate)])
_QUERY_FIELDS = frozenset({
    "limit", "cursor", "event_type", "status", "after", "before"
})


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NoteCreate(_ClosedModel):
    event_id: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)


class NoteUpdate(_ClosedModel):
    base_revision: int = Field(ge=0)
    body: str = Field(min_length=1, max_length=4000)


class RevisionRequest(_ClosedModel):
    base_revision: int = Field(ge=0)


ReviewEventType = Literal[
    "graph_version_published", "experiment_run", "finding_created",
    "candidate_created", "candidate_decided",
]
ReviewStatus = Literal[
    "published", "pending", "running", "failed", "completed", "needs_review",
    "active", "superseded", "created", "shadow", "approved", "rejected",
]


class SavedFilters(_ClosedModel):
    event_type: ReviewEventType | None = None
    status: ReviewStatus | None = None
    after: str | None = Field(default=None, max_length=40)
    before: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=25, ge=1, le=100)


class ViewCreate(_ClosedModel):
    name: str = Field(min_length=1, max_length=80)
    filters: SavedFilters


class ViewUpdate(ViewCreate):
    base_revision: int = Field(ge=0)


def _query_rejected(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": "REVIEW_QUERY_INVALID", "message": message},
    )


@router.get("/projects/{project_id}/review")
def get_project_review(
    request: Request,
    project_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
    event_type: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    after: str | None = Query(default=None, max_length=40),
    before: str | None = Query(default=None, max_length=40),
):
    """Derive verified timeline facts without invoking any research write or run seam."""
    unknown = sorted(set(request.query_params) - _QUERY_FIELDS)
    if unknown:
        return _query_rejected(f"unknown review query field: {unknown[0]}")
    if (event_type is not None and len(event_type) > len(set(event_type))) or (
        status is not None and len(status) > len(set(status))
    ):
        return _query_rejected("review filters must not contain duplicates")

    try:
        project_source = project_review_source(project_id)
    except store.ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    source_errors = list(project_source["source_errors"])

    global_operations = None
    failed_operation = None
    try:
        operation_state = ResearchOperationRecorder.load(operation_receipt_path())
        global_operations = {
            "state": (
                "never_run" if operation_state == {"active": None, "last": None}
                else "available"
            ),
            **operation_state,
        }
        last = operation_state["last"]
        if last is not None and last["state"] == "failed":
            failed_operation = {
                "operation_id": last["operation_id"],
                "trigger": last["trigger"],
                "stage": last["stage"],
                "completed_at": last["completed_at"],
                "failure": last["failure"],
            }
    except OperationStateCorrupt:
        source_errors.append({
            "source": "global_operation",
            "source_id": "current_last",
            "code": "OPERATION_STATE_CORRUPT",
        })

    try:
        timeline = paginate_review_events(
            project_source["events"],
            limit=limit,
            cursor=cursor,
            event_types=set(event_type) if event_type is not None else None,
            statuses=set(status) if status is not None else None,
            after=after,
            before=before,
        )
    except ReviewQueryRejected as exc:
        return _query_rejected(str(exc))

    return {
        "project_id": project_id,
        "as_of": dt.datetime.now(dt.UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "timeline": timeline,
        "queues": {
            **project_source["queues"],
            "failed_operation": failed_operation,
        },
        "global_operations": global_operations,
        "source_errors": source_errors,
    }


def _owner(principal: Principal, action: str, project_id: str) -> str:
    require(principal, action, project_id)
    return "owner"


def _state_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, store.ProjectNotFound):
        return JSONResponse(
            status_code=404,
            content={"code": "REVIEW_PROJECT_NOT_FOUND", "message": "project not found"},
        )
    if isinstance(exc, review_state.ReviewStateNotFound):
        return JSONResponse(
            status_code=404,
            content={"code": "REVIEW_STATE_NOT_FOUND", "message": "review state not found"},
        )
    if isinstance(exc, review_state.ReviewStateConflict):
        return JSONResponse(
            status_code=409,
            content={
                "code": "REVIEW_STATE_CONFLICT",
                "message": "review state changed since it was loaded",
                "current_revision": exc.current_revision,
            },
        )
    if isinstance(exc, review_state.ReviewViewNameConflict):
        return JSONResponse(
            status_code=409,
            content={
                "code": "REVIEW_VIEW_NAME_CONFLICT",
                "message": "an active saved view already uses this name",
            },
        )
    if isinstance(exc, review_state.ReviewStateCorrupt):
        return JSONResponse(
            status_code=409,
            content={
                "code": "REVIEW_STATE_CORRUPT",
                "message": "persisted review state failed integrity verification",
            },
        )
    if isinstance(exc, store.InvalidTransition):
        return JSONResponse(
            status_code=409,
            content={"code": "REVIEW_PROJECT_ARCHIVED", "message": "project is archived"},
        )
    return JSONResponse(
        status_code=422,
        content={"code": "REVIEW_STATE_INVALID", "message": str(exc)},
    )


_STATE_EXCEPTIONS = (
    store.ProjectNotFound,
    store.InvalidTransition,
    review_state.ReviewStateNotFound,
    review_state.ReviewStateConflict,
    review_state.ReviewStateRejected,
    review_state.ReviewStateCorrupt,
    review_state.ReviewViewNameConflict,
)


def _event_types(project_id: str) -> dict[str, str]:
    source = project_review_source(project_id)
    return {event["event_id"]: event["type"] for event in source["events"]}


def _timestamp(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _note_response(note: review_state.ReviewNote, event_types: dict[str, str]) -> dict:
    return {
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
        "created_at": _timestamp(note.created_at),
        "updated_at": _timestamp(note.updated_at),
    }


def _view_response(view: review_state.ReviewSavedView) -> dict:
    return {
        "view_id": view.view_id,
        "project_id": view.project_id,
        "name": view.name,
        "filters": view.filters,
        "created_by": view.created_by,
        "revision": view.revision,
        "created_at": _timestamp(view.created_at),
        "updated_at": _timestamp(view.updated_at),
    }


@router.get("/projects/{project_id}/review/notes")
def get_review_notes(
    project_id: str, principal: Principal = Depends(get_principal)
):
    _owner(principal, "read review notes", project_id)
    try:
        event_types = _event_types(project_id)
        notes = review_state.list_notes(project_id)
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return {"notes": [_note_response(note, event_types) for note in notes]}


@router.post(
    "/projects/{project_id}/review/notes",
    status_code=status.HTTP_201_CREATED,
)
def post_review_note(
    project_id: str,
    body: NoteCreate,
    principal: Principal = Depends(get_principal),
):
    actor = _owner(principal, "create review note", project_id)
    try:
        event_types = _event_types(project_id)
        event_type = event_types.get(body.event_id)
        if event_type is None:
            return JSONResponse(
                status_code=422,
                content={
                    "code": "REVIEW_NOTE_ANCHOR_INVALID",
                    "message": "event is not an available project review fact",
                },
            )
        note = review_state.create_note(
            project_id,
            event_id=body.event_id,
            event_type=event_type,
            body=body.body,
            created_by=actor,
        )
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return _note_response(note, event_types)


@router.patch("/projects/{project_id}/review/notes/{note_id}")
def patch_review_note(
    project_id: str,
    note_id: str,
    body: NoteUpdate,
    principal: Principal = Depends(get_principal),
):
    _owner(principal, "update review note", project_id)
    try:
        event_types = _event_types(project_id)
        note = review_state.update_note(
            project_id, note_id, base_revision=body.base_revision, body=body.body
        )
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return _note_response(note, event_types)


@router.delete("/projects/{project_id}/review/notes/{note_id}")
def delete_review_note(
    project_id: str,
    note_id: str,
    body: RevisionRequest,
    principal: Principal = Depends(get_principal),
):
    _owner(principal, "delete review note", project_id)
    try:
        review_state.delete_note(
            project_id, note_id, base_revision=body.base_revision
        )
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return Response(status_code=204)


@router.get("/projects/{project_id}/review/views")
def get_review_views(
    project_id: str, principal: Principal = Depends(get_principal)
):
    _owner(principal, "read saved review views", project_id)
    try:
        views = review_state.list_saved_views(project_id)
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return {"views": [_view_response(view) for view in views]}


@router.post(
    "/projects/{project_id}/review/views",
    status_code=status.HTTP_201_CREATED,
)
def post_review_view(
    project_id: str,
    body: ViewCreate,
    principal: Principal = Depends(get_principal),
):
    actor = _owner(principal, "create saved review view", project_id)
    try:
        view = review_state.create_saved_view(
            project_id,
            name=body.name,
            filters=body.filters.model_dump(),
            created_by=actor,
        )
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return _view_response(view)


@router.patch("/projects/{project_id}/review/views/{view_id}")
def patch_review_view(
    project_id: str,
    view_id: str,
    body: ViewUpdate,
    principal: Principal = Depends(get_principal),
):
    _owner(principal, "update saved review view", project_id)
    try:
        view = review_state.update_saved_view(
            project_id,
            view_id,
            base_revision=body.base_revision,
            name=body.name,
            filters=body.filters.model_dump(),
        )
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return _view_response(view)


@router.delete("/projects/{project_id}/review/views/{view_id}")
def delete_review_view(
    project_id: str,
    view_id: str,
    body: RevisionRequest,
    principal: Principal = Depends(get_principal),
):
    _owner(principal, "delete saved review view", project_id)
    try:
        review_state.delete_saved_view(
            project_id, view_id, base_revision=body.base_revision
        )
    except _STATE_EXCEPTIONS as exc:
        return _state_error(exc)
    return Response(status_code=204)
