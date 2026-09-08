"""Copy immutable strategy presets into the existing owner-scoped V2 editor."""
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, owner_id_for
from app.editor import graph_artifacts as store
from app.ir.original_strategy_presets import instantiate_preset, preset_summaries


router = APIRouter(prefix="/api/ir")


class PresetCopy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identifier: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=128)


@router.get("/presets")
def list_global_presets(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    owner_id_for(principal)
    return {"presets": preset_summaries()}


@router.get("/projects/{project_id}/presets")
def list_presets(project_id: str, principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    try:
        with store.SessionLocal() as session:
            store._active_project(session, project_id, owner_id_for(principal))
    except (store.ProjectNotFound, store.InvalidTransition) as exc:
        raise HTTPException(404, detail={
            "code": "PROJECT_NOT_FOUND", "message": "Choose an active project you own.",
        }) from exc
    return {"presets": preset_summaries()}


@router.post("/projects/{project_id}/presets/{preset_id}/copy",
             status_code=status.HTTP_201_CREATED)
def copy_preset(
    project_id: str, preset_id: str, body: PresetCopy,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    owner_id = owner_id_for(principal)
    try:
        document = instantiate_preset(preset_id, body.identifier, body.name)
    except KeyError as exc:
        raise HTTPException(404, detail={
            "code": "PRESET_NOT_FOUND", "message": "Choose an available strategy preset.",
        }) from exc
    try:
        return asdict(store.create_artifact(
            project_id, body.identifier, document, owner_id=owner_id))
    except (store.ProjectNotFound, store.InvalidTransition) as exc:
        raise HTTPException(404, detail={
            "code": "PROJECT_NOT_FOUND", "message": "Choose an active project you own.",
        }) from exc
    except store.GraphConflict as exc:
        raise HTTPException(409, detail={
            "code": "GRAPH_ALREADY_EXISTS",
            "message": "This strategy identifier is already used. Choose another identifier.",
        }) from exc
    except store.GraphRejected as exc:
        raise HTTPException(422, detail={
            "code": "PRESET_COPY_REJECTED",
            "message": f"{exc}. Review the reported field and try again.",
        }) from exc
