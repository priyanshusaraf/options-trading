"""
Read-only IR graph views for the editor (WS-04).

The first route that imports `app/ir/`, and deliberately the smallest one that
can be: it resolves an artefact and returns the view model. Nothing here writes,
resolves on a caller's behalf from arbitrary input, or touches execution.
"""
from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.ir.resolve import Library, ResolutionError, resolve
from app.ir.strategies import expanding_z
from app.ir.validate import validate
from app.ir.view import graph_view

router = APIRouter(prefix="/api/ir")


class IrNodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instance_id: str
    label: str
    container: str
    definition: str
    params: dict[str, Any]
    warmup: int
    purity: str
    cache_id: str
    derived: bool
    layer: int
    row: int
    placed: tuple[int, int] | None


class IrEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    target: str
    source_socket: str
    target_socket: str
    derived: bool


class IrGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str
    version: int
    display_name: str
    warmup: int
    layers: int
    inputs: list[str]
    outputs: list[str]
    nodes: list[IrNodeResponse]
    edges: list[IrEdgeResponse]


def _catalogue() -> dict[str, tuple[Mapping[str, Any], Library]]:
    """Artefacts this build can render.

    A fixed table, not a registry lookup: a route that resolves whatever it is
    handed is an execution surface, and this one is a viewer.
    """
    return {expanding_z.GRAPH["identifier"]: (expanding_z.GRAPH, expanding_z.LIBRARY)}


def _resolved(identifier: str):
    entry = _catalogue().get(identifier)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no IR graph named {identifier!r}")
    graph, library = entry
    violations = validate(graph, library.components)
    if violations:
        violation = violations[0]
        raise HTTPException(
            status_code=500,
            detail=f"{violation.clause} at {violation.path}: {violation.message}",
        )
    try:
        return graph, graph_view(resolve(graph, library))
    except ResolutionError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{exc.clause} at {exc.path}: {exc.message}") from exc


@router.get("/graphs/{identifier}", response_model=IrGraphResponse)
def get_graph(identifier: str) -> IrGraphResponse:
    graph, view = _resolved(identifier)
    return IrGraphResponse(
        identifier=view.identifier,
        version=view.version,
        display_name=graph["display_name"],
        warmup=view.warmup,
        layers=view.layers,
        inputs=list(view.inputs),
        outputs=list(view.outputs),
        # Built field by field rather than with `asdict`: a ResolvedNode holds
        # read-only mappings, which is what makes the resolved graph
        # uneditable (C3), and `asdict` deep-copies and cannot pickle those.
        nodes=[IrNodeResponse(
            instance_id=n.instance_id, label=n.label, container=n.container,
            definition=n.definition, params=dict(n.params), warmup=n.warmup,
            purity=n.purity, cache_id=n.cache_id, derived=n.derived,
            layer=n.layer, row=n.row, placed=n.placed,
        ) for n in view.nodes],
        edges=[IrEdgeResponse(
            source=e.source, target=e.target, source_socket=e.source_socket,
            target_socket=e.target_socket, derived=e.derived,
        ) for e in view.edges],
    )
