"""Bounded owner-scoped indexes for the V0 desktop research journey.

The routes compose existing project and research read authorities. They do not
create a graph, dataset, experiment, review, or execution authority.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.ir_experiment_routes import GraphRunSummary
from app.api.principal import Principal, get_principal, owner_id_for
from app.core import research_read
from app.core.config import get_settings
from app.db.models import Project
from app.db.session import SessionLocal
from research.config import research_database_url
from research.domain.base import (
    init_research_db,
    make_engine,
    make_sessionmaker,
    research_database_exists,
)
from research.domain.models import ExperimentRun


def _research_gate() -> None:
    if not get_settings().research_enabled:
        raise HTTPException(
            status_code=403,
            detail="research plane disabled (set PT_RESEARCH_ENABLED=1)",
        )


router = APIRouter(prefix="/api/ir", dependencies=[Depends(_research_gate)])


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResearchProjectItem(_ClosedModel):
    project_id: str
    name: str
    description: str
    status: Literal["active", "archived"]


class ResearchProjectPage(_ClosedModel):
    schema_version: Literal["strategy-os-research-project-page/1"] = Field(
        default="strategy-os-research-project-page/1", alias="schema"
    )
    items: list[ResearchProjectItem]
    next_cursor: str | None


class ResearchRunPage(_ClosedModel):
    schema_version: Literal["strategy-os-research-run-page/1"] = Field(
        default="strategy-os-research-run-page/1", alias="schema"
    )
    project_id: str
    runs: list[GraphRunSummary]
    next_cursor: int | None


@router.get("/projects/research-spine/index", response_model=ResearchProjectPage)
def get_research_projects(
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=50, ge=1, le=100),
    after: str | None = Query(default=None, min_length=1, max_length=64),
) -> ResearchProjectPage:
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        query = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.project_id)
            .limit(limit + 1)
        )
        if after is not None:
            query = query.where(Project.project_id > after)
        rows = list(session.scalars(query))
    items = [
        ResearchProjectItem(
            project_id=row.project_id,
            name=row.name,
            description=row.description,
            status=row.status,
        )
        for row in rows[:limit]
    ]
    return ResearchProjectPage(
        items=items,
        next_cursor=items[-1].project_id if len(rows) > limit else None,
    )


def _owner_run_ids(*, owner_id: str, before: int | None, limit: int) -> tuple[list[int], bool]:
    authority = research_database_url()
    if not research_database_exists(authority):
        return [], False
    engine = make_engine(authority)
    try:
        init_research_db(engine)
        with make_sessionmaker(engine)() as session:
            query = (
                select(ExperimentRun.id)
                .where(ExperimentRun.owner_id == owner_id)
                .order_by(ExperimentRun.id.desc())
                .limit(limit + 1)
            )
            if before is not None:
                query = query.where(ExperimentRun.id < before)
            rows = list(session.scalars(query))
        return rows[:limit], len(rows) > limit
    finally:
        engine.dispose()


@router.get(
    "/projects/{project_id}/research-spine/experiments",
    response_model=ResearchRunPage,
)
def get_research_runs(
    project_id: str,
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=25, ge=1, le=50),
    before: int | None = Query(default=None, ge=1),
) -> ResearchRunPage:
    """Scan one bounded owner run window, then apply canonical project privacy."""
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        if session.scalar(select(Project.project_id).where(
            Project.owner_id == owner_id,
            Project.project_id == project_id,
        )) is None:
            raise HTTPException(status_code=404, detail="project not found")
    run_ids, has_more = _owner_run_ids(owner_id=owner_id, before=before, limit=limit)
    runs = []
    for run_id in run_ids:
        run = research_read.get_graph_run(project_id, run_id, owner_id=owner_id)
        if run is not None:
            runs.append(GraphRunSummary(**{
                key: value for key, value in run.items() if key != "evidence"
            }))
    return ResearchRunPage(
        project_id=project_id,
        runs=runs,
        next_cursor=run_ids[-1] if has_more and run_ids else None,
    )


__all__ = ["router"]
