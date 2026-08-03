"""Sparse presentation-state routes for the IR graph editor."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.editor import graph_artifacts
from app.editor import layouts as ir_layouts


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


class IrLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_identifier: str
    graph_version: int
    revision: int
    positions: list[IrLayoutPosition]


def _graph(identifier: str, version: int):
    try:
        return graph_artifacts.load_published_graph(identifier, version).graph
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
    )


@router.get(
    "/graphs/{identifier}/versions/{version}/layout",
    response_model=IrLayoutResponse,
)
def get_layout(identifier: str, version: int) -> IrLayoutResponse:
    graph = _graph(identifier, version)
    return layout_response(ir_layouts.load_layout(
        identifier,
        version,
        valid_instance_ids=_authored_ids(graph),
    ))


@router.put(
    "/graphs/{identifier}/versions/{version}/layout",
    response_model=IrLayoutResponse,
)
def put_layout(identifier: str, version: int, body: IrLayoutWrite):
    graph = _graph(identifier, version)
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
