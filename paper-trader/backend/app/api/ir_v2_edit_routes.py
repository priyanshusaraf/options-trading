"""Authenticated, explicitly v2-named editor routes."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, owner_id_for
from app.editor import v2_editor_store as store
from app.editor.v2_mutations import EditorRefusal


router = APIRouter(prefix="/api/ir/projects/{project_id}/graphs")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class V2GraphCreate(_Closed):
    format_version: Literal[2]
    identifier: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)


class UseCheck(_Closed):
    purpose: Literal["AUTHORING", "RESEARCH", "PAPER", "MONITORING"] = "AUTHORING"
    capability_receipt_address: str | None = Field(default=None, max_length=71)


class SemanticBatch(_Closed):
    schema_name: Literal["strategy-os-v2-semantic-batch/1"] = Field(alias="schema")
    format_version: Literal[2]
    base_revision: int = Field(ge=0)
    intent: Literal["EDIT", "UNDO", "REDO", "REPLAY"] = "EDIT"
    use_check: UseCheck = Field(default_factory=UseCheck)
    source_receipt: dict[str, Any] | None = None
    commands: list[dict[str, Any]] = Field(min_length=1, max_length=32)


class PublishRequest(_Closed):
    format_version: Literal[2]
    base_revision: int = Field(ge=0)
    expected_current_version: int | None = Field(default=None, ge=1)
    target_registry_snapshot_address: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")


class PresentationBatch(_Closed):
    schema_name: Literal["strategy-os-v2-presentation-batch/1"] = Field(alias="schema")
    format_version: Literal[2]
    base_semantic_revision: int = Field(ge=0)
    base_presentation_revision: int = Field(ge=0)
    intent: Literal["EDIT", "UNDO", "REDO", "REPLAY"] = "EDIT"
    source_receipt: dict[str, Any] | None = None
    commands: list[dict[str, Any]] = Field(min_length=1, max_length=32)


def _raise(exc: Exception) -> None:
    if isinstance(exc, store.EditorNotFound):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"}) from exc
    if isinstance(exc, EditorRefusal):
        conflict = exc.code.endswith("CONFLICT") or exc.code in {
            "SEMANTIC_REVISION_CONFLICT", "PRESENTATION_REVISION_CONFLICT",
            "IMMUTABLE_VERSION_CONFLICT", "GRAPH_ALREADY_EXISTS", "STRATEGY_LIBRARY_CHANGED",
        }
        raise HTTPException(status_code=409 if conflict else 422, detail=exc.payload()) from exc
    raise exc


@router.post("/v2/create", status_code=status.HTTP_201_CREATED)
def create_v2_graph(
    project_id: str, body: V2GraphCreate,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        state = store.create_graph(project_id, body.identifier, body.name, body.description,
                                   owner_id=owner_id_for(principal))
        return state.__dict__
    except Exception as exc:
        _raise(exc)


@router.get("/{identifier}/v2")
def read_v2_graph(
    project_id: str, identifier: str,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return store.read_graph(project_id, identifier,
                                owner_id=owner_id_for(principal)).__dict__
    except Exception as exc:
        _raise(exc)


def _semantic(
    project_id: str, identifier: str, body: SemanticBatch, principal: Principal,
    *, dry_run: bool,
) -> dict[str, Any]:
    if not dry_run and body.use_check.purpose != "AUTHORING":
        raise HTTPException(status_code=422, detail={
            "code": "REQUEST_SCHEMA_INVALID", "path": "$.use_check.purpose",
            "message": "commits accept AUTHORING purpose only",
        })
    try:
        return store.mutate_semantic(
            project_id, identifier, base_revision=body.base_revision,
            intent=body.intent, commands=body.commands,
            source_receipt=body.source_receipt, owner_id=owner_id_for(principal),
            dry_run=dry_run, use_check=body.use_check.model_dump(),
        )
    except Exception as exc:
        _raise(exc)


@router.post("/{identifier}/v2/semantic-batches")
def mutate_v2_graph(
    project_id: str, identifier: str, body: SemanticBatch,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if body.intent == "REPLAY":
        raise HTTPException(status_code=422, detail={"code": "REQUEST_SCHEMA_INVALID"})
    return _semantic(project_id, identifier, body, principal, dry_run=False)


@router.post("/{identifier}/v2/validate")
def validate_v2_graph(
    project_id: str, identifier: str, body: SemanticBatch,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    return _semantic(project_id, identifier, body, principal, dry_run=True)


@router.post("/{identifier}/v2/replay")
def replay_v2_graph(
    project_id: str, identifier: str, body: SemanticBatch,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    if body.intent != "REPLAY":
        raise HTTPException(status_code=422, detail={"code": "REQUEST_SCHEMA_INVALID"})
    return _semantic(project_id, identifier, body, principal, dry_run=True)


@router.post("/{identifier}/v2/publish")
def publish_v2_graph(
    project_id: str, identifier: str, body: PublishRequest,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return store.publish(
            project_id, identifier, base_revision=body.base_revision,
            expected_current_version=body.expected_current_version,
            target_registry_snapshot_address=body.target_registry_snapshot_address,
            owner_id=owner_id_for(principal),
        )
    except Exception as exc:
        _raise(exc)


@router.get("/{identifier}/v2/versions/{version}")
def read_v2_version(
    project_id: str, identifier: str, version: int,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return store.read_version(project_id, identifier, version,
                                  owner_id=owner_id_for(principal))
    except Exception as exc:
        _raise(exc)


@router.get("/{identifier}/v2/presentation")
def read_v2_presentation(
    project_id: str, identifier: str,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return store.read_presentation(project_id, identifier,
                                       owner_id=owner_id_for(principal))
    except Exception as exc:
        _raise(exc)


@router.post("/{identifier}/v2/presentation-batches")
def mutate_v2_presentation(
    project_id: str, identifier: str, body: PresentationBatch,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        return store.mutate_presentation(
            project_id, identifier,
            base_semantic_revision=body.base_semantic_revision,
            base_presentation_revision=body.base_presentation_revision,
            commands=body.commands, owner_id=owner_id_for(principal),
            intent=body.intent, source_receipt=body.source_receipt,
        )
    except Exception as exc:
        _raise(exc)
