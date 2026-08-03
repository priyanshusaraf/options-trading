"""Closed S3.2a edit batches with atomic immutable publication."""
from __future__ import annotations

import math
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api import ir_layout_routes, ir_routes
from app.editor import graph_artifacts as store
from app.ir import edit as ir_edit
from app.ir.kernels import KernelDeclarationError
from app.ir.resolve import ResolutionError, resolve
from app.ir.strategies.expanding_z import LIBRARY
from app.ir.validate import Violation, validate


router = APIRouter(prefix="/api/ir")

_MAX_JSON_DEPTH = 8
_MAX_JSON_ITEMS = 256
_MAX_JSON_STRING = 4096
_MAX_JSON_KEY = 128


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SetDisplayNameEdit(_ClosedModel):
    operation: Literal["set_display_name"]
    display_name: str = Field(min_length=1, max_length=128)


def _bounded_json(value: Any) -> Any:
    items = 0

    def visit(current: Any, depth: int) -> None:
        nonlocal items
        if isinstance(current, float) and not math.isfinite(current):
            raise ValueError("override values cannot contain NaN or Infinity")
        if isinstance(current, str):
            if len(current) > _MAX_JSON_STRING:
                raise ValueError(
                    f"override strings cannot exceed {_MAX_JSON_STRING} characters"
                )
            return
        if current is None or isinstance(current, (bool, int, float)):
            return
        if isinstance(current, (list, dict)):
            if depth > _MAX_JSON_DEPTH:
                raise ValueError(
                    f"override values cannot exceed {_MAX_JSON_DEPTH} nested levels"
                )
            items += len(current)
            if items > _MAX_JSON_ITEMS:
                raise ValueError(
                    f"override values cannot exceed {_MAX_JSON_ITEMS} composite items"
                )
            if isinstance(current, list):
                for item in current:
                    visit(item, depth + 1)
            else:
                for key, item in current.items():
                    if not isinstance(key, str) or len(key) > _MAX_JSON_KEY:
                        raise ValueError(
                            f"override object keys cannot exceed {_MAX_JSON_KEY} characters"
                        )
                    visit(item, depth + 1)
            return
        raise ValueError("override values must be canonical JSON")

    visit(value, 1)
    return value


class SetOverrideEdit(_ClosedModel):
    operation: Literal["set_override"]
    instance_id: str = Field(min_length=1, max_length=128)
    parameter: str = Field(min_length=1, max_length=128)
    value: Any

    _value_is_bounded_json = field_validator("value")(_bounded_json)


class ClearOverrideEdit(_ClosedModel):
    operation: Literal["clear_override"]
    instance_id: str = Field(min_length=1, max_length=128)
    parameter: str = Field(min_length=1, max_length=128)


EditRequest = Annotated[
    SetDisplayNameEdit | SetOverrideEdit | ClearOverrideEdit,
    Field(discriminator="operation"),
]


class GraphEditRequest(_ClosedModel):
    base_revision: int = Field(ge=0)
    edits: list[EditRequest] = Field(min_length=1, max_length=32)


class CommandReceipt(_ClosedModel):
    applied_operations: list[EditRequest]
    inverse_operations: list[EditRequest]
    base_revision: int
    draft_revision: int
    version: int
    content_address: str


class EditableParameterResponse(_ClosedModel):
    identifier: str
    kind: str
    default: Any
    value: Any
    overridden: bool


class EditableNodeResponse(_ClosedModel):
    instance_id: str
    component_identifier: str
    component_version: int
    parameters: list[EditableParameterResponse]


class EditorDocumentResponse(_ClosedModel):
    project_id: str
    identifier: str
    display_name: str
    draft_revision: int
    version: int
    content_address: str
    authored_graph: dict[str, Any]
    view: ir_routes.IrGraphResponse
    editable_nodes: list[EditableNodeResponse]
    layout: ir_layout_routes.IrLayoutResponse
    command_receipt: CommandReceipt | None


class EditorErrorItem(_ClosedModel):
    operation_index: int | None
    clause: str | None
    path: list[str | int]
    message: str


EditorErrorCode = Literal[
    "DRAFT_REVISION_CONFLICT",
    "EDITOR_NOT_PUBLISHED",
    "EDITOR_HAS_UNPUBLISHED_DRAFT",
    "EDITOR_ARCHIVED",
    "REQUEST_VALIDATION_FAILED",
    "IR_VALIDATION_FAILED",
    "EDITOR_DOCUMENT_FAILED",
]


class EditorErrorEnvelope(_ClosedModel):
    code: EditorErrorCode
    message: str
    current_revision: int | None = None
    errors: list[EditorErrorItem] = Field(default_factory=list)


class BatchEditRejected(Exception):
    def __init__(
        self, operation_index: int | None, violations: list[Violation] | tuple[Violation, ...]
    ) -> None:
        super().__init__("edit batch rejected")
        self.operation_index = operation_index
        self.violations = tuple(violations)


def _structured_path(path: str) -> list[str | int]:
    if path == "$":
        return []
    source = path.removeprefix("$.")
    result: list[str | int] = []
    for part in source.split(".") if source else []:
        cursor = 0
        for match in re.finditer(r"([^\[]+)|\[(\d+)\]", part):
            if match.start() != cursor:
                result.append(part[cursor:match.start()])
            result.append(
                int(match.group(2)) if match.group(2) is not None else match.group(1)
            )
            cursor = match.end()
        if cursor < len(part):
            result.append(part[cursor:])
    return [item for item in result if item != ""]


def _error_response(
    status_code: int,
    code: EditorErrorCode,
    message: str,
    *,
    current_revision: int | None = None,
    errors: list[EditorErrorItem] | None = None,
) -> JSONResponse:
    envelope = EditorErrorEnvelope(
        code=code,
        message=message,
        current_revision=current_revision,
        errors=errors or [],
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


def request_validation_envelope(errors: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[EditorErrorItem] = []
    for error in errors:
        loc = list(error.get("loc", ()))
        if loc and loc[0] == "body":
            loc = loc[1:]
        operation_index = (
            int(loc[1])
            if len(loc) > 1 and loc[0] == "edits" and isinstance(loc[1], int)
            else None
        )
        items.append(EditorErrorItem(
            operation_index=operation_index,
            clause=None,
            path=loc,
            message=str(error.get("msg", "Request validation failed")),
        ))
    return EditorErrorEnvelope(
        code="REQUEST_VALIDATION_FAILED",
        message="Editor request validation failed",
        errors=items,
    ).model_dump()


def _transition_code(exc: store.InvalidTransition) -> EditorErrorCode:
    if "no published version" in str(exc):
        return "EDITOR_NOT_PUBLISHED"
    if "unpublished draft" in str(exc):
        return "EDITOR_HAS_UNPUBLISHED_DRAFT"
    return "EDITOR_ARCHIVED"


def _apply_one(graph: dict[str, Any], request: EditRequest) -> dict[str, Any]:
    if isinstance(request, SetOverrideEdit):
        return ir_edit.set_override(
            graph, request.instance_id, request.parameter, request.value
        )
    if isinstance(request, ClearOverrideEdit):
        return ir_edit.clear_override(graph, request.instance_id, request.parameter)
    return ir_edit.rename(graph, request.display_name)


def _node(graph: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
    return next(
        (node for node in graph.get("nodes", ()) if node.get("instance_id") == instance_id),
        None,
    )


def _inverse_for(graph: dict[str, Any], request: EditRequest) -> dict[str, Any]:
    if isinstance(request, SetDisplayNameEdit):
        return {
            "operation": "set_display_name",
            "display_name": str(graph["display_name"]),
        }
    node = _node(graph, request.instance_id)
    if node is None:
        raise RuntimeError("accepted edit has no authored source node for its inverse")
    overrides = node.get("overrides", {})
    if isinstance(request, ClearOverrideEdit) or request.parameter in overrides:
        return {
            "operation": "set_override",
            "instance_id": request.instance_id,
            "parameter": request.parameter,
            "value": overrides[request.parameter],
        }
    return {
        "operation": "clear_override",
        "instance_id": request.instance_id,
        "parameter": request.parameter,
    }


def _apply_all(graph: dict[str, Any], requests: list[EditRequest]) -> store.EditResult:
    edited = graph
    applied: list[dict[str, Any]] = []
    inverse: list[dict[str, Any]] = []
    for index, request in enumerate(requests):
        before = edited
        try:
            edited = _apply_one(edited, request)
        except ir_edit.EditRejected as exc:
            raise BatchEditRejected(index, exc.violations) from exc
        applied.append(request.model_dump(mode="json"))
        inverse.insert(0, _inverse_for(before, request))

    violations = validate(edited, LIBRARY.components)
    if violations:
        raise BatchEditRejected(None, violations)
    try:
        resolve(edited, LIBRARY)
    except ResolutionError as exc:
        raise BatchEditRejected(
            None, [Violation(exc.clause, exc.path, exc.message)]
        ) from exc
    except KernelDeclarationError as exc:
        raise BatchEditRejected(
            None,
            [Violation(
                exc.clause,
                "$",
                str(exc).removeprefix(f"{exc.clause}: "),
            )],
        ) from exc
    return store.EditResult(
        graph=edited,
        applied_operations=tuple(applied),
        inverse_operations=tuple(inverse),
    )


def _parameter_declarations(interface: Any) -> list[dict[str, Any]]:
    declared: list[dict[str, Any]] = []
    for item in interface or ():
        if not isinstance(item, dict):
            continue
        if item.get("item") == "panel":
            declared.extend(_parameter_declarations(item.get("items")))
        elif item.get("item") == "parameter":
            declared.append(item)
    return declared


def _editable_nodes(graph: dict[str, Any]) -> list[EditableNodeResponse]:
    root_defaults = {
        str(item["identifier"]): item.get("default")
        for item in _parameter_declarations(graph.get("interface"))
    }
    result: list[EditableNodeResponse] = []
    for node in graph.get("nodes", ()):
        reference = node.get("component") or {}
        identifier = str(reference.get("identifier"))
        version = int(reference.get("version", 0))
        component = LIBRARY.components.get((identifier, version))
        if component is None:
            continue
        overrides = node.get("overrides") or {}
        parameters: list[EditableParameterResponse] = []
        for declaration in _parameter_declarations(component.get("interface")):
            parameter = str(declaration["identifier"])
            default = declaration.get("default")
            raw_value = overrides.get(parameter, default)
            if (
                isinstance(raw_value, dict)
                and set(raw_value) == {"param_ref"}
                and raw_value["param_ref"] in root_defaults
            ):
                value = root_defaults[raw_value["param_ref"]]
            else:
                value = raw_value
            parameters.append(EditableParameterResponse(
                identifier=parameter,
                kind=str(declaration.get("kind", "value")),
                default=default,
                value=value,
                overridden=parameter in overrides,
            ))
        if parameters:
            result.append(EditableNodeResponse(
                instance_id=str(node["instance_id"]),
                component_identifier=identifier,
                component_version=version,
                parameters=parameters,
            ))
    return result


def _document(
    publication: store.EditPublication | store.EditorSnapshot,
    layout,
    *,
    include_receipt: bool,
) -> EditorDocumentResponse:
    graph = publication.published
    receipt = None
    if include_receipt:
        receipt = CommandReceipt(
            applied_operations=list(publication.applied_operations),
            inverse_operations=list(publication.inverse_operations),
            base_revision=publication.draft_revision - 1,
            draft_revision=publication.draft_revision,
            version=graph.version,
            content_address=graph.content_address,
        )
    return EditorDocumentResponse(
        project_id=graph.project_id,
        identifier=graph.identifier,
        display_name=str(graph.graph["display_name"]),
        draft_revision=publication.draft_revision,
        version=graph.version,
        content_address=graph.content_address,
        authored_graph=graph.graph,
        view=ir_routes.graph_response(graph.graph, LIBRARY),
        editable_nodes=_editable_nodes(graph.graph),
        layout=ir_layout_routes.layout_response(layout),
        command_receipt=receipt,
    )


@router.get(
    "/projects/{project_id}/graphs/{identifier}/editor",
    response_model=EditorDocumentResponse,
)
def get_editor_document(project_id: str, identifier: str):
    try:
        snapshot = store.load_editor_snapshot(project_id, identifier)
        return _document(snapshot, snapshot.layout, include_receipt=False)
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise HTTPException(status_code=404, detail="graph artefact not found") from exc
    except store.InvalidTransition as exc:
        return _error_response(409, _transition_code(exc), str(exc))


@router.post(
    "/projects/{project_id}/graphs/{identifier}/edits",
    response_model=EditorDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_graph_edit(project_id: str, identifier: str, body: GraphEditRequest):
    try:
        return store.apply_and_publish(
            project_id,
            identifier,
            base_revision=body.base_revision,
            transform=lambda graph: _apply_all(graph, body.edits),
            response_factory=lambda publication, layout: _document(
                publication, layout, include_receipt=True
            ),
        )
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise HTTPException(status_code=404, detail="graph artefact not found") from exc
    except store.GraphConflict as exc:
        return _error_response(
            409,
            "DRAFT_REVISION_CONFLICT",
            "Graph draft revision conflict",
            current_revision=exc.current_revision,
        )
    except BatchEditRejected as exc:
        return _error_response(
            422,
            "IR_VALIDATION_FAILED",
            "Graph validation failed",
            errors=[EditorErrorItem(
                operation_index=exc.operation_index,
                clause=violation.clause,
                path=_structured_path(violation.path),
                message=violation.message,
            ) for violation in exc.violations],
        )
    except store.GraphRejected as exc:
        return _error_response(
            422,
            "IR_VALIDATION_FAILED",
            "Graph validation failed",
            errors=[EditorErrorItem(
                operation_index=None,
                clause=None,
                path=[],
                message=str(exc),
            )],
        )
    except store.InvalidTransition as exc:
        return _error_response(409, _transition_code(exc), str(exc))
    except store.EditorDocumentFailed:
        return _error_response(
            500,
            "EDITOR_DOCUMENT_FAILED",
            "Editor document construction failed",
        )
