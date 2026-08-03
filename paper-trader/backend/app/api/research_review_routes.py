"""Closed read-only daily review aggregation for one project."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.core import research_read
from app.core.config import get_settings
from app.core.research_review import (
    ReviewQueryRejected,
    make_review_event,
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

    source_errors: list[dict] = []
    events: list[dict] = []
    try:
        versions = store.list_project_version_events(project_id)
    except store.ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    except store.GraphVersionCorrupt as exc:
        source_errors.append({
            "source": "graph_version",
            "source_id": str(exc.args[0]),
            "code": "GRAPH_VERSION_CORRUPT",
        })
        versions = ()
    for version in versions:
        events.append(make_review_event(
            event_id=f"graph:{version.identifier}:{version.version}",
            event_type="graph_version_published",
            occurred_at=version.created_at,
            status="published",
            summary=f"Published {version.identifier} version {version.version}",
            references={
                "graph": {
                    "identifier": version.identifier,
                    "version": version.version,
                    "content_address": version.content_address,
                },
                "run_id": None,
                "finding_id": None,
                "candidate_id": None,
            },
        ))

    research = research_read.project_review_source(project_id)
    events.extend(research["events"])
    source_errors.extend(research["source_errors"])

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
            events,
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
            **research["queues"],
            "failed_operation": failed_operation,
        },
        "global_operations": global_operations,
        "source_errors": source_errors,
    }
