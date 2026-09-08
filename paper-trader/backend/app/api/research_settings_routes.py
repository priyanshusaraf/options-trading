"""Owner-scoped preference histories; these routes never change queued plans."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.api.principal import Principal, get_principal, owner_id_for
from app.db.models import LEGACY_USER_ID
from app.editor import graph_artifacts as graphs
from research.domain.settings import ResearchSettingsRepository, SettingsConflict, fixed_assumptions

router = APIRouter(prefix="/api")


class WorkspaceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    expected_revision: int = Field(ge=0, le=2_147_483_646)
    values: dict[str, Any]


class StrategySettingsUpdate(WorkspaceSettingsUpdate):
    enabled: bool


def _owned_graph(session, principal, project_id, identifier):
    owner = owner_id_for(principal)
    try:
        graphs._active_project(session, project_id, owner)
        graphs._owned_artifact(session, project_id, identifier, owner)
    except (graphs.ProjectNotFound, graphs.GraphNotFound, graphs.InvalidTransition) as exc:
        raise HTTPException(404, detail={"code": "GRAPH_NOT_FOUND",
            "message": "Choose an active project and strategy you own."}) from exc
    return owner


def _update(repository, principal, body, identifier=None):
    try:
        return repository.update(owner_id=owner_id_for(principal),
            created_by=principal.user_id or LEGACY_USER_ID, graph_identifier=identifier,
            **body.model_dump())
    except SettingsConflict as exc:
        raise HTTPException(409, detail={"code": "RESEARCH_SETTINGS_CONFLICT", "message": str(exc)}) from exc
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, detail={"code": "RESEARCH_SETTINGS_INVALID",
            "message": "Use supported research fields and values within their displayed bounds."}) from exc


@router.get("/research-settings")
def get_workspace_settings(principal: Principal = Depends(get_principal)):
    with graphs.SessionLocal() as session:
        workspace = ResearchSettingsRepository(session).read(owner_id=owner_id_for(principal))
        return {"workspace": workspace, "supported_values_schema": "research-values/3",
                "fixed_assumptions": fixed_assumptions(workspace["values"]["risk_policy"])}


@router.put("/research-settings")
def put_workspace_settings(body: WorkspaceSettingsUpdate, principal: Principal = Depends(get_principal)):
    with graphs.SessionLocal() as session:
        return _update(ResearchSettingsRepository(session), principal, body)


@router.get("/ir/projects/{project_id}/graphs/{identifier}/research-settings")
def get_strategy_settings(project_id: str, identifier: str, principal: Principal = Depends(get_principal)):
    with graphs.SessionLocal() as session:
        owner = _owned_graph(session, principal, project_id, identifier)
        preview = ResearchSettingsRepository(session).effective(owner_id=owner, graph_identifier=identifier)
        return {**preview, "fixed_assumptions": fixed_assumptions(preview["values"]["risk_policy"])}


@router.put("/ir/projects/{project_id}/graphs/{identifier}/research-settings")
def put_strategy_settings(project_id: str, identifier: str, body: StrategySettingsUpdate,
                          principal: Principal = Depends(get_principal)):
    with graphs.SessionLocal() as session:
        _owned_graph(session, principal, project_id, identifier)
        return _update(ResearchSettingsRepository(session), principal, body, identifier)
