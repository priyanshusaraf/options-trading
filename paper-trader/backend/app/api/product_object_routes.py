"""Closed project and graph-lineage persistence routes."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.editor import graph_artifacts as store
from app.api.principal import Principal, get_principal, owner_id_for


router = APIRouter(prefix="/api/ir")


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)


class ProjectStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["active", "archived"]


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    name: str
    description: str
    status: Literal["active", "archived"]


class GraphArtifactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str = Field(min_length=1, max_length=128)
    graph: dict[str, Any]


class GraphPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_revision: int = Field(ge=0)


class GraphDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    identifier: str
    display_name: str
    revision: int
    current_version: int | None
    graph: dict[str, Any]


class PublishedGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    identifier: str
    version: int
    content_address: str
    graph: dict[str, Any]


class PublishedGraphIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    identifier: str
    version: int
    content_address: str


def _project_response(project: store.ProjectRecord) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        status=project.status,
    )


def _draft_response(draft: store.GraphDraft) -> GraphDraftResponse:
    return GraphDraftResponse(
        project_id=draft.project_id,
        identifier=draft.identifier,
        display_name=draft.display_name,
        revision=draft.revision,
        current_version=draft.current_version,
        graph=draft.graph,
    )


def _published_response(graph: store.PublishedGraph) -> PublishedGraphResponse:
    return PublishedGraphResponse(
        project_id=graph.project_id,
        identifier=graph.identifier,
        version=graph.version,
        content_address=graph.content_address,
        graph=graph.graph,
    )


def _not_found(exc: Exception) -> HTTPException:
    if isinstance(exc, store.ProjectNotFound):
        return HTTPException(status_code=404, detail="project not found")
    return HTTPException(status_code=404, detail="graph artefact not found")


@router.get("/projects", response_model=list[ProjectResponse])
def get_projects(principal: Principal = Depends(get_principal)) -> list[ProjectResponse]:
    return [_project_response(project) for project in store.list_projects(owner_id=owner_id_for(principal))]


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_project(body: ProjectCreateRequest, principal: Principal = Depends(get_principal)) -> ProjectResponse:
    return _project_response(store.create_project(body.name, body.description, owner_id=owner_id_for(principal)))


@router.put("/projects/{project_id}/status", response_model=ProjectResponse)
def put_project_status(
    project_id: str, body: ProjectStatusRequest, principal: Principal = Depends(get_principal)
) -> ProjectResponse:
    try:
        return _project_response(store.set_project_status(project_id, body.status, owner_id=owner_id_for(principal)))
    except store.ProjectNotFound as exc:
        raise _not_found(exc) from exc
    except store.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/graphs/{identifier}/versions",
    response_model=list[PublishedGraphIdentityResponse],
)
def get_graph_versions(
    project_id: str, identifier: str, principal: Principal = Depends(get_principal)
) -> list[PublishedGraphIdentityResponse]:
    try:
        return [
            PublishedGraphIdentityResponse(**vars(version))
            for version in store.list_versions(project_id, identifier, owner_id=owner_id_for(principal))
        ]
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc
    except store.GraphVersionCorrupt as exc:
        raise HTTPException(status_code=409, detail="graph version is corrupt") from exc


@router.post(
    "/projects/{project_id}/graphs",
    response_model=GraphDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_graph_artifact(
    project_id: str, body: GraphArtifactCreateRequest, principal: Principal = Depends(get_principal)
) -> GraphDraftResponse:
    try:
        return _draft_response(
            store.create_artifact(project_id, body.identifier, body.graph, owner_id=owner_id_for(principal))
        )
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc
    except store.GraphConflict as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "graph artefact already exists",
                "current_revision": exc.current_revision,
            },
        )
    except store.GraphRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except store.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/graphs/{identifier}/draft",
    response_model=GraphDraftResponse,
)
def get_graph_draft(project_id: str, identifier: str, principal: Principal = Depends(get_principal)) -> GraphDraftResponse:
    try:
        return _draft_response(store.load_draft(project_id, identifier, owner_id=owner_id_for(principal)))
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc


@router.post(
    "/projects/{project_id}/graphs/{identifier}/versions",
    response_model=PublishedGraphResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_graph_version(
    project_id: str, identifier: str, body: GraphPublishRequest, principal: Principal = Depends(get_principal)
):
    try:
        return _published_response(store.publish_draft(
            project_id,
            identifier,
            base_revision=body.base_revision,
            owner_id=owner_id_for(principal),
        ))
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc
    except store.GraphConflict as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "graph draft revision conflict",
                "current_revision": exc.current_revision,
            },
        )
    except store.GraphAdmissionRefused as exc:
        raise HTTPException(status_code=422, detail=exc.code.value) from exc
    except store.GraphRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except store.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/graphs/{identifier}/versions/{version}",
    response_model=PublishedGraphResponse,
)
def get_graph_version(
    project_id: str, identifier: str, version: int, principal: Principal = Depends(get_principal)
) -> PublishedGraphResponse:
    try:
        return _published_response(
            store.load_version(project_id, identifier, version, owner_id=owner_id_for(principal))
        )
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc
