"""Closed project and graph-lineage persistence routes."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.editor import graph_artifacts as store
from app.api.principal import Principal, get_principal, owner_id_for
from app.api.static_scope_routes import install_routes as install_static_scope_routes
from app.api.watchlist_monitoring_routes import install_routes as install_watchlist_monitoring_routes
from app.db.models import GraphArtifact, Project
from app.db.session import SessionLocal


router = APIRouter(prefix="/api/ir")

install_static_scope_routes(router)
install_watchlist_monitoring_routes(router)


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


class GraphIndexItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str
    display_name: str
    draft_revision: int = Field(ge=0)
    current_version: int | None = Field(ge=1)


class GraphIndexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal["strategy-os-graph-index/1"] = Field(
        default="strategy-os-graph-index/1", alias="schema")
    project_id: str
    items: list[GraphIndexItem]
    next_cursor: str | None


class _ClosedDocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class V1DocumentWriteRequest(_ClosedDocumentModel):
    format_version: Literal[1]
    document: dict[str, Any]


class V2DocumentWriteRequest(_ClosedDocumentModel):
    format_version: Literal[2]
    document: dict[str, Any]


DocumentWriteRequest = Annotated[
    V1DocumentWriteRequest | V2DocumentWriteRequest,
    Field(discriminator="format_version"),
]


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


class V1DocumentResponse(_ClosedDocumentModel):
    format_version: Literal[1] = 1
    document: dict[str, Any]
    content_address: str


class V2DocumentResponse(_ClosedDocumentModel):
    format_version: Literal[2] = 2
    document: dict[str, Any]
    content_address: str
    graph_address: str


DocumentResponse = Annotated[
    V1DocumentResponse | V2DocumentResponse,
    Field(discriminator="format_version"),
]


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


def _document_response_for_value(
    document: dict[str, Any], content_address: str
) -> DocumentResponse:
    if document.get("format_version") == 2:
        from app.ir.formats.v2 import graph_address_for
        from app.ir.library import REGISTRY
        return V2DocumentResponse(
            document=document,
            content_address=content_address,
            graph_address=graph_address_for(document, REGISTRY),
        )
    return V1DocumentResponse(document=document, content_address=content_address)


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
    "/projects/{project_id}/graphs",
    response_model=GraphIndexResponse,
)
def get_graph_index(
    project_id: str,
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=50, ge=1, le=100),
    after: str | None = Query(default=None, min_length=1, max_length=128),
) -> GraphIndexResponse:
    """Bounded metadata projection, not a second graph or evidence registry."""
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        owned_project = (
            Project.project_id == project_id,
            Project.owner_id == owner_id,
            Project.status == "active",
        )
        if session.scalar(select(Project.project_id).where(*owned_project)) is None:
            raise HTTPException(status_code=404, detail="project not found")
        query = (
            select(GraphArtifact.identifier, GraphArtifact.display_name,
                   GraphArtifact.draft_revision, GraphArtifact.current_version)
            .join(Project, (Project.project_id == GraphArtifact.project_id)
                  & (Project.owner_id == GraphArtifact.owner_id))
            .where(*owned_project, GraphArtifact.owner_id == owner_id)
            .order_by(GraphArtifact.identifier)
            .limit(limit + 1)
        )
        if after is not None:
            query = query.where(GraphArtifact.identifier > after)
        rows = session.execute(query).mappings().all()
        items = [GraphIndexItem(**row) for row in rows[:limit]]
        return GraphIndexResponse(
            project_id=project_id, items=items,
            next_cursor=items[-1].identifier if len(rows) > limit else None,
        )


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
    if body.graph.get("format_version") != 1:
        raise HTTPException(
            status_code=422,
            detail="legacy graph writer accepts only format_version 1",
        )
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


@router.post(
    "/projects/{project_id}/documents/{identifier}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_document(
    project_id: str,
    identifier: str,
    body: DocumentWriteRequest,
    principal: Principal = Depends(get_principal),
) -> DocumentResponse:
    """Create one canonical document through an explicit format seam.

    This opt-in route does not replace the accepted v1 graph-editor writer.
    V2 remains an opt-in, non-admitted document capability. A rejected document
    never reaches an artefact row because normalisation occurs inside the
    transaction before the row is added.
    """
    if body.document.get("format_version") != body.format_version:
        raise HTTPException(
            status_code=422,
            detail="document format_version must match the request discriminator",
        )
    try:
        draft = store.create_artifact(
            project_id, identifier, body.document, owner_id=owner_id_for(principal)
        )
        from app.ir.formats.v2 import content_address_for
        from app.ir.library import REGISTRY
        canonical = draft.graph
        address = (
            content_address_for(canonical, REGISTRY)
            if body.format_version == 2 else store.content_address(canonical)
        )
        return _document_response_for_value(canonical, address)
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc
    except store.GraphConflict as exc:
        raise HTTPException(status_code=409, detail="document already exists") from exc
    except store.GraphAdmissionRefused as exc:
        raise HTTPException(status_code=422, detail=exc.code.value) from exc
    except store.GraphRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except store.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/documents/{identifier}/{version}",
    response_model=DocumentResponse,
)
def get_document(
    project_id: str,
    identifier: str,
    version: int,
    format_version: Literal["1", "2"],
    principal: Principal = Depends(get_principal),
) -> DocumentResponse:
    try:
        draft = store.load_draft(
            project_id, identifier, owner_id=owner_id_for(principal)
        )
    except (store.ProjectNotFound, store.GraphNotFound) as exc:
        raise _not_found(exc) from exc
    actual = draft.graph.get("format_version", 1)
    requested_format_version = int(format_version)
    if actual != requested_format_version:
        raise HTTPException(status_code=409, detail="requested format_version does not match stored document")
    if actual == 2 and draft.graph.get("strategy_version") != version:
        raise HTTPException(status_code=404, detail="document version not found")
    if actual == 1 and draft.graph.get("version") != version:
        raise HTTPException(status_code=404, detail="document version not found")
    from app.ir.formats.v2 import content_address_for
    from app.ir.library import REGISTRY
    address = (
        content_address_for(draft.graph, REGISTRY)
        if actual == 2 else store.content_address(draft.graph)
    )
    return _document_response_for_value(draft.graph, address)


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
