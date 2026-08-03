"""Closed IR edit batches with atomic immutable publication."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.editor import graph_artifacts as store
from app.ir import edit as ir_edit
from app.ir.resolve import ResolutionError, resolve
from app.ir.strategies.expanding_z import LIBRARY
from app.ir.validate import Violation, validate


router = APIRouter(prefix="/api/ir")


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SocketRef(_ClosedModel):
    instance_id: str = Field(min_length=1, max_length=128)
    socket: str = Field(min_length=1, max_length=128)


class AddNodeEdit(_ClosedModel):
    operation: Literal["add_node"]
    instance_id: str = Field(min_length=1, max_length=128)
    component_identifier: str = Field(min_length=1, max_length=128)
    component_version: int = Field(ge=1)
    overrides: dict[str, Any] = Field(default_factory=dict)
    domain: dict[str, str] | None = None


class RemoveNodeEdit(_ClosedModel):
    operation: Literal["remove_node"]
    instance_id: str = Field(min_length=1, max_length=128)


class SetOverrideEdit(_ClosedModel):
    operation: Literal["set_override"]
    instance_id: str = Field(min_length=1, max_length=128)
    parameter: str = Field(min_length=1, max_length=128)
    value: Any


class ClearOverrideEdit(_ClosedModel):
    operation: Literal["clear_override"]
    instance_id: str = Field(min_length=1, max_length=128)
    parameter: str = Field(min_length=1, max_length=128)


class ConnectEdit(_ClosedModel):
    operation: Literal["connect"]
    source: SocketRef
    target: SocketRef


class DisconnectEdit(_ClosedModel):
    operation: Literal["disconnect"]
    source: SocketRef
    target: SocketRef


class GroupEdit(_ClosedModel):
    operation: Literal["group"]
    identifier: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    members: list[str]


class RenameEdit(_ClosedModel):
    operation: Literal["rename"]
    display_name: str = Field(min_length=1, max_length=128)


EditRequest = Annotated[
    AddNodeEdit
    | RemoveNodeEdit
    | SetOverrideEdit
    | ClearOverrideEdit
    | ConnectEdit
    | DisconnectEdit
    | GroupEdit
    | RenameEdit,
    Field(discriminator="operation"),
]


class GraphEditRequest(_ClosedModel):
    base_revision: int = Field(ge=0)
    edits: list[EditRequest] = Field(min_length=1, max_length=32)


class GraphEditResponse(_ClosedModel):
    project_id: str
    identifier: str
    draft_revision: int
    version: int
    content_address: str
    graph: dict[str, Any]


def _socket(ref: SocketRef) -> tuple[str, str]:
    return ref.instance_id, ref.socket


def _apply_one(graph: dict[str, Any], request: EditRequest) -> dict[str, Any]:
    if isinstance(request, AddNodeEdit):
        edited = ir_edit.add_node(
            graph,
            request.instance_id,
            request.component_identifier,
            request.component_version,
            request.overrides,
            request.domain,
        )
    elif isinstance(request, RemoveNodeEdit):
        edited = ir_edit.remove_node(graph, request.instance_id)
    elif isinstance(request, SetOverrideEdit):
        edited = ir_edit.set_override(
            graph, request.instance_id, request.parameter, request.value
        )
    elif isinstance(request, ClearOverrideEdit):
        edited = ir_edit.clear_override(
            graph, request.instance_id, request.parameter
        )
    elif isinstance(request, ConnectEdit):
        edited = ir_edit.connect(graph, _socket(request.source), _socket(request.target))
    elif isinstance(request, DisconnectEdit):
        edited = ir_edit.disconnect(
            graph, _socket(request.source), _socket(request.target)
        )
    elif isinstance(request, GroupEdit):
        edited = ir_edit.group(
            graph, request.identifier, request.display_name, request.members
        )
    else:
        edited = ir_edit.rename(graph, request.display_name)

    return edited


def _apply_all(
    graph: dict[str, Any], requests: list[EditRequest]
) -> dict[str, Any]:
    edited = graph
    for request in requests:
        edited = _apply_one(edited, request)

    violations = validate(edited, LIBRARY.components)
    if violations:
        raise ir_edit.EditRejected("edit batch", violations)
    try:
        resolve(edited, LIBRARY)
    except ResolutionError as exc:
        raise ir_edit.EditRejected(
            "edit batch",
            [Violation(exc.clause, exc.path, exc.message)],
        ) from exc
    return edited


def _response(publication: store.EditPublication) -> GraphEditResponse:
    graph = publication.published
    return GraphEditResponse(
        project_id=graph.project_id,
        identifier=graph.identifier,
        draft_revision=publication.draft_revision,
        version=graph.version,
        content_address=graph.content_address,
        graph=graph.graph,
    )


@router.post(
    "/projects/{project_id}/graphs/{identifier}/edits",
    response_model=GraphEditResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_graph_edit(project_id: str, identifier: str, body: GraphEditRequest):
    try:
        return _response(store.apply_and_publish(
            project_id,
            identifier,
            base_revision=body.base_revision,
            transform=lambda graph: _apply_all(graph, body.edits),
        ))
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise HTTPException(status_code=404, detail="graph artefact not found") from exc
    except store.GraphConflict as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "graph draft revision conflict",
                "current_revision": exc.current_revision,
            },
        )
    except ir_edit.EditRejected as exc:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "edit rejected",
                "action": exc.action,
                "violations": [
                    {
                        "clause": violation.clause,
                        "path": violation.path,
                        "message": violation.message,
                    }
                    for violation in exc.violations
                ],
            },
        )
    except store.GraphRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
