"""Owner-scoped, bounded research Market context and drawing routes."""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.api.principal import Principal, get_principal, owner_id_for
from app.chart.annotation_context import (
    MarketContextUnavailable, build_market_context, resolve_market_context,
)
from app.chart.annotation_geometry import GeometryError
from app.chart.annotation_repository import (
    AnnotationConflict, AnnotationLimit, AnnotationNotFound,
    create_annotation, delete_annotation, list_annotations, update_annotation,
)
from app.core.config import get_settings
from app.ir.hashing import canonical_json

router = APIRouter(prefix="/api/ir", dependencies=[Depends(
    lambda: _research_gate())])
MAX_BODY_BYTES = 64 * 1024


def _research_gate() -> None:
    if not get_settings().research_enabled:
        raise HTTPException(status_code=403, detail="research is unavailable")


async def _bounded_body(request: Request) -> None:
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
        raise HTTPException(status_code=413, detail={
            "code": "MARKET_CONTEXT_REQUEST_TOO_LARGE", "message": "The request is too large."})
    if len(await request.body()) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail={
            "code": "MARKET_CONTEXT_REQUEST_TOO_LARGE", "message": "The request is too large."})


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "MARKET_CONTEXT_NOT_FOUND", "message": "Market context unavailable"})


def _conflict() -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": "REVIEW_DRAWING_CONFLICT",
        "message": "This review drawing changed elsewhere. Reload it and try again."})


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class AnnotationValue(_Closed):
    geometry: dict[str, Any]
    applicability: dict[str, Any]

    @model_validator(mode="after")
    def _bounded(self):
        if len(canonical_json(self.model_dump()).encode()) > MAX_BODY_BYTES:
            raise ValueError("request exceeds 64 KiB")
        return self


class AnnotationUpdate(AnnotationValue):
    expected_revision: int = Field(ge=1)


class AnnotationDelete(_Closed):
    expected_revision: int = Field(ge=1)


def _identity(project_id: str, run_id: int, principal: Principal):
    try:
        return resolve_market_context(project_id, run_id, owner_id=owner_id_for(principal))
    except (MarketContextUnavailable, ValueError, TypeError, KeyError):
        raise _not_found() from None


@router.get("/projects/{project_id}/experiments/{run_id}/market-context")
def get_market_context(project_id: str, run_id: int, response: Response,
                       after: int = Query(default=0, ge=0),
                       limit: int = Query(default=500, ge=1, le=500),
                       replay_at: AwareDatetime | None = None,
                       principal: Principal = Depends(get_principal)) -> dict:
    _no_store(response)
    try:
        if replay_at is not None and (replay_at.utcoffset() != dt.timedelta(0) or replay_at.microsecond):
            raise MarketContextUnavailable()
        return build_market_context(project_id, run_id, owner_id=owner_id_for(principal),
                                    after=after, limit=limit, replay_at=replay_at)
    except (MarketContextUnavailable, ValueError, TypeError, KeyError):
        raise _not_found() from None


@router.get("/projects/{project_id}/experiments/{run_id}/market-context/annotations")
def get_annotations(project_id: str, run_id: int, response: Response,
                    after: str | None = Query(default=None, max_length=36),
                    limit: int = Query(default=50, ge=1, le=50),
                    principal: Principal = Depends(get_principal)) -> dict:
    _no_store(response)
    try:
        return list_annotations(_identity(project_id, run_id, principal), after=after, limit=limit)
    except (AnnotationNotFound, AnnotationLimit):
        raise _not_found() from None


@router.post("/projects/{project_id}/experiments/{run_id}/market-context/annotations",
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(_bounded_body)])
def post_annotation(project_id: str, run_id: int, body: AnnotationValue, response: Response,
                    principal: Principal = Depends(get_principal)) -> dict:
    _no_store(response)
    try:
        return create_annotation(_identity(project_id, run_id, principal),
            canonical_json(body.geometry), canonical_json(body.applicability))
    except (GeometryError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=422, detail={
            "code": "REVIEW_DRAWING_INVALID", "message": "Check the review drawing values."}) from None
    except AnnotationLimit:
        raise HTTPException(status_code=409, detail={
            "code": "REVIEW_DRAWING_LIMIT", "message": "This result already has 256 review drawings."}) from None
    except AnnotationConflict:
        raise _conflict() from None


@router.put("/projects/{project_id}/experiments/{run_id}/market-context/annotations/{annotation_id}",
            dependencies=[Depends(_bounded_body)])
def put_annotation(project_id: str, run_id: int, annotation_id: str, body: AnnotationUpdate,
                   response: Response, principal: Principal = Depends(get_principal)) -> dict:
    _no_store(response)
    try:
        return update_annotation(_identity(project_id, run_id, principal), annotation_id,
            body.expected_revision, canonical_json(body.geometry), canonical_json(body.applicability))
    except AnnotationNotFound:
        raise _not_found() from None
    except AnnotationConflict:
        raise _conflict() from None
    except (GeometryError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=422, detail={
            "code": "REVIEW_DRAWING_INVALID", "message": "Check the review drawing values."}) from None


@router.delete("/projects/{project_id}/experiments/{run_id}/market-context/annotations/{annotation_id}",
               dependencies=[Depends(_bounded_body)])
def remove_annotation(project_id: str, run_id: int, annotation_id: str,
                      body: AnnotationDelete, response: Response,
                      principal: Principal = Depends(get_principal)) -> dict:
    _no_store(response)
    try:
        delete_annotation(_identity(project_id, run_id, principal), annotation_id,
                          body.expected_revision)
    except AnnotationNotFound:
        raise _not_found() from None
    except AnnotationConflict:
        raise _conflict() from None
    return {"deleted": True}


__all__ = ["router"]
