"""Sparse presentation-state routes for the IR graph editor."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.editor import graph_artifacts
from app.editor import layouts as ir_layouts
from app.api.principal import Principal, get_principal, owner_id_for


router = APIRouter(prefix="/api/ir")


class IrLayoutPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    instance_id: str
    x: float
    y: float


class IrLayoutWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_revision: int = Field(ge=0)
    positions: list[IrLayoutPosition]


class IrLayoutGroupFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    x: float
    y: float
    width: float
    height: float


class IrLayoutGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str
    display_name: str
    frame: IrLayoutGroupFrame
    collapsed: bool
    members: list[str]


class IrLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_identifier: str
    graph_version: int
    revision: int
    positions: list[IrLayoutPosition]
    groups: list[IrLayoutGroup]


def _graph(identifier: str, version: int, *, owner_id: str):
    try:
        return graph_artifacts.load_published_graph(identifier, version, owner_id=owner_id).graph
    except graph_artifacts.GraphNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=f"no IR graph named {identifier!r} at version {version}",
        ) from exc


def _authored_ids(graph) -> frozenset[str]:
    return frozenset(node["instance_id"] for node in graph["nodes"])


def layout_response(layout: ir_layouts.Layout) -> IrLayoutResponse:
    return IrLayoutResponse(
        graph_identifier=layout.graph_identifier,
        graph_version=layout.graph_version,
        revision=layout.revision,
        positions=[
            IrLayoutPosition(instance_id=p.instance_id, x=p.x, y=p.y)
            for p in layout.positions
        ],
        groups=[
            IrLayoutGroup(
                identifier=group.identifier,
                display_name=group.display_name,
                frame=IrLayoutGroupFrame(
                    x=group.frame.x,
                    y=group.frame.y,
                    width=group.frame.width,
                    height=group.frame.height,
                ),
                collapsed=group.collapsed,
                members=list(group.members),
            )
            for group in layout.groups
        ],
    )


@router.get(
    "/graphs/{identifier}/versions/{version}/layout",
    response_model=IrLayoutResponse,
)
def get_layout(
    identifier: str,
    version: int,
    principal: Principal = Depends(get_principal),
) -> IrLayoutResponse:
    graph = _graph(identifier, version, owner_id=owner_id_for(principal))
    return layout_response(ir_layouts.load_layout(
        identifier,
        version,
        valid_instance_ids=_authored_ids(graph),
    ))


@router.put(
    "/graphs/{identifier}/versions/{version}/layout",
    response_model=IrLayoutResponse,
)
def put_layout(
    identifier: str,
    version: int,
    body: IrLayoutWrite,
    principal: Principal = Depends(get_principal),
):
    graph = _graph(identifier, version, owner_id=owner_id_for(principal))
    valid_ids = _authored_ids(graph)
    ids = [position.instance_id for position in body.positions]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="layout contains duplicate instance IDs")
    unknown = sorted(set(ids) - valid_ids)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"layout contains unknown or derived instance IDs: {unknown}",
        )

    try:
        saved = ir_layouts.save_layout(
            identifier,
            version,
            base_revision=body.base_revision,
            positions=(
                ir_layouts.Position(position.instance_id, position.x, position.y)
                for position in body.positions
            ),
        )
    except ir_layouts.LayoutConflict as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "layout revision conflict",
                "current_revision": exc.current_revision,
            },
        )
    return layout_response(saved)
