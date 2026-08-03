"""Durable editor graph lineages and immutable published versions."""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, TypeVar

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import GraphArtifact, GraphVersion, Project
from app.db.session import SessionLocal
from app.editor import layouts
from app.ir.hashing import canonical_json, content_address
from app.ir.resolve import ResolutionError, resolve
from app.ir.strategies.expanding_z import GRAPH, LIBRARY
from app.ir.validate import validate


CATALOGUE_PROJECT_ID = "project.repository_catalogue"
CATALOGUE_CONTENT_ADDRESS = (
    "sha256:d78b424e8247e26663728b19980e197fb5e84a4e21c08c4df00ac704db1ae02b"
)


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    description: str
    status: str


@dataclass(frozen=True)
class GraphDraft:
    project_id: str
    identifier: str
    display_name: str
    revision: int
    current_version: int | None
    graph: dict[str, Any]


@dataclass(frozen=True)
class PublishedGraph:
    project_id: str
    identifier: str
    version: int
    content_address: str
    graph: dict[str, Any]


@dataclass(frozen=True)
class EditPublication:
    draft_revision: int
    published: PublishedGraph
    applied_operations: tuple[dict[str, Any], ...]
    inverse_operations: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class EditResult:
    graph: dict[str, Any]
    applied_operations: tuple[dict[str, Any], ...]
    inverse_operations: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class EditorSnapshot:
    draft_revision: int
    published: PublishedGraph
    layout: layouts.Layout


class ProjectNotFound(Exception):
    pass


class GraphNotFound(Exception):
    pass


class GraphConflict(Exception):
    def __init__(self, current_revision: int):
        super().__init__(f"graph draft is at revision {current_revision}")
        self.current_revision = current_revision


class GraphRejected(Exception):
    pass


class InvalidTransition(Exception):
    pass


class EditorDocumentFailed(Exception):
    pass


T = TypeVar("T")


def _project_record(project: Project) -> ProjectRecord:
    return ProjectRecord(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        status=project.status,
    )


def _draft_record(artifact: GraphArtifact) -> GraphDraft:
    return GraphDraft(
        project_id=artifact.project_id,
        identifier=artifact.identifier,
        display_name=artifact.display_name,
        revision=artifact.draft_revision,
        current_version=artifact.current_version,
        graph=json.loads(artifact.draft_json),
    )


def _published_record(project_id: str, version: GraphVersion) -> PublishedGraph:
    return PublishedGraph(
        project_id=project_id,
        identifier=version.graph_identifier,
        version=version.version,
        content_address=version.content_address,
        graph=json.loads(version.artifact_json),
    )


def _active_project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFound(project_id)
    if project.status != "active":
        raise InvalidTransition(f"project {project_id!r} is archived")
    return project


def _owned_artifact(session: Session, project_id: str, identifier: str) -> GraphArtifact:
    artifact = session.scalar(select(GraphArtifact).where(
        GraphArtifact.identifier == identifier,
        GraphArtifact.project_id == project_id,
    ))
    if artifact is None:
        raise GraphNotFound((project_id, identifier))
    return artifact


def _normalise_graph(
    identifier: str,
    graph: Mapping[str, Any],
    *,
    current_version: int | None,
) -> tuple[dict[str, Any], str]:
    try:
        document = json.loads(canonical_json(graph))
    except (TypeError, ValueError) as exc:
        raise GraphRejected(f"graph is not canonical JSON: {exc}") from exc
    if document.get("identifier") != identifier:
        raise GraphRejected("graph identifier does not match its artefact lineage")

    next_version = (current_version or 0) + 1
    document["version"] = next_version
    if current_version is None:
        document.pop("parent_version", None)
    else:
        document["parent_version"] = current_version

    violations = validate(document, LIBRARY.components)
    if violations:
        first = violations[0]
        raise GraphRejected(f"{first.clause} at {first.path}: {first.message}")
    return document, canonical_json(document)


def _require_resolvable(graph: Mapping[str, Any]) -> None:
    try:
        resolve(graph, LIBRARY)
    except ResolutionError as exc:
        raise GraphRejected(
            f"{exc.clause} at {exc.path}: {exc.message}"
        ) from exc


def create_project(name: str, description: str = "") -> ProjectRecord:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    project = Project(
        project_id=f"project.{uuid.uuid4().hex}",
        name=name,
        description=description,
        status="active",
        created_at=now,
        updated_at=now,
    )
    with SessionLocal.begin() as session:
        session.add(project)
    return _project_record(project)


def set_project_status(project_id: str, status: str) -> ProjectRecord:
    if status not in {"active", "archived"}:
        raise InvalidTransition(f"unsupported project status {status!r}")
    with SessionLocal.begin() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ProjectNotFound(project_id)
        project.status = status
        project.updated_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    return _project_record(project)


def list_projects() -> tuple[ProjectRecord, ...]:
    with SessionLocal() as session:
        projects = session.scalars(
            select(Project)
            .where(Project.status == "active")
            .order_by(Project.created_at, Project.project_id)
        )
        return tuple(_project_record(project) for project in projects)


def create_artifact(
    project_id: str,
    identifier: str,
    graph: Mapping[str, Any],
) -> GraphDraft:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _active_project(session, project_id)
        existing = session.get(GraphArtifact, identifier)
        if existing is not None:
            raise GraphConflict(existing.draft_revision)
        document, encoded = _normalise_graph(identifier, graph, current_version=None)
        artifact = GraphArtifact(
            identifier=identifier,
            project_id=project_id,
            display_name=str(document["display_name"]),
            draft_json=encoded,
            draft_revision=0,
            published_revision=None,
            current_version=None,
            created_at=now,
            updated_at=now,
        )
        session.add(artifact)
    return _draft_record(artifact)


def load_draft(project_id: str, identifier: str) -> GraphDraft:
    with SessionLocal() as session:
        return _draft_record(_owned_artifact(session, project_id, identifier))


def _authored_ids(graph: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(str(node["instance_id"]) for node in graph.get("nodes", ()))


def load_editor_snapshot(project_id: str, identifier: str) -> EditorSnapshot:
    """Read the published editor head and its presentation state coherently."""
    with SessionLocal() as session:
        _active_project(session, project_id)
        artifact = _owned_artifact(session, project_id, identifier)
        if artifact.current_version is None:
            raise InvalidTransition("graph has no published version")
        if artifact.published_revision != artifact.draft_revision:
            raise InvalidTransition("graph has unpublished draft changes")
        version = session.get(GraphVersion, (identifier, artifact.current_version))
        if version is None:
            raise GraphNotFound((project_id, identifier, artifact.current_version))
        published = _published_record(project_id, version)
        layout = layouts.load_layout_in_session(
            session,
            identifier,
            version.version,
            _authored_ids(published.graph),
        )
        return EditorSnapshot(artifact.draft_revision, published, layout)


def load_published_graph(identifier: str, version: int) -> PublishedGraph:
    """Load one globally identified immutable graph for presentation routes."""
    with SessionLocal() as session:
        artifact = session.get(GraphArtifact, identifier)
        published = session.get(GraphVersion, (identifier, version))
        if artifact is None or published is None:
            raise GraphNotFound((identifier, version))
        return _published_record(artifact.project_id, published)


def save_draft(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
    graph: Mapping[str, Any],
) -> GraphDraft:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _active_project(session, project_id)
        artifact = _owned_artifact(session, project_id, identifier)
        if artifact.draft_revision != base_revision:
            raise GraphConflict(artifact.draft_revision)
        document, encoded = _normalise_graph(
            identifier, graph, current_version=artifact.current_version
        )
        claimed = session.execute(
            update(GraphArtifact)
            .where(
                GraphArtifact.identifier == identifier,
                GraphArtifact.project_id == project_id,
                GraphArtifact.draft_revision == base_revision,
            )
            .values(
                display_name=str(document["display_name"]),
                draft_json=encoded,
                draft_revision=base_revision + 1,
                updated_at=now,
            )
        )
        if claimed.rowcount != 1:
            session.expire_all()
            current = _owned_artifact(session, project_id, identifier)
            raise GraphConflict(current.draft_revision)
        session.expire(artifact)
        result = _draft_record(artifact)
    return result


def _after_version_insert(_session: Session, _version: GraphVersion) -> None:
    """Failure-injection seam proving version insert and pointer advance are atomic."""


def publish_draft(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
) -> PublishedGraph:
    with SessionLocal.begin() as session:
        _active_project(session, project_id)
        artifact = _owned_artifact(session, project_id, identifier)
        if artifact.draft_revision != base_revision:
            raise GraphConflict(artifact.draft_revision)
        if artifact.published_revision == artifact.draft_revision:
            raise InvalidTransition("this draft revision is already published")

        document, encoded = _normalise_graph(
            identifier,
            json.loads(artifact.draft_json),
            current_version=artifact.current_version,
        )
        _require_resolvable(document)
        version = GraphVersion(
            graph_identifier=identifier,
            version=int(document["version"]),
            artifact_json=encoded,
            content_address=content_address(document),
            created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
        )
        session.add(version)
        try:
            session.flush()
        except IntegrityError as exc:
            raise GraphConflict(artifact.draft_revision) from exc
        _after_version_insert(session, version)

        artifact.current_version = version.version
        artifact.published_revision = artifact.draft_revision
        artifact.draft_json = encoded
        artifact.updated_at = version.created_at
        result = _published_record(project_id, version)
    return result


def apply_and_publish(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
    transform: Callable[[dict[str, Any]], EditResult],
    response_factory: Callable[[EditPublication, layouts.Layout], T],
) -> T:
    """Apply an edit and build its canonical response before committing."""
    with SessionLocal.begin() as session:
        _active_project(session, project_id)
        artifact = _owned_artifact(session, project_id, identifier)
        if artifact.draft_revision != base_revision:
            raise GraphConflict(artifact.draft_revision)
        if artifact.current_version is None:
            raise InvalidTransition("graph has no published version")
        if artifact.published_revision != artifact.draft_revision:
            raise InvalidTransition("graph has unpublished draft changes")

        original = json.loads(artifact.draft_json)
        edit_result = transform(original)
        document, encoded = _normalise_graph(
            identifier, edit_result.graph, current_version=artifact.current_version
        )
        _require_resolvable(document)
        next_revision = base_revision + 1
        version = GraphVersion(
            graph_identifier=identifier,
            version=int(document["version"]),
            artifact_json=encoded,
            content_address=content_address(document),
            created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
        )
        session.add(version)
        try:
            session.flush()
        except IntegrityError as exc:
            raise GraphConflict(artifact.draft_revision) from exc
        _after_version_insert(session, version)

        valid_ids = _authored_ids(document)
        if _authored_ids(original) == valid_ids:
            layout = layouts.carry_layout_forward(
                session,
                identifier,
                artifact.current_version,
                version.version,
                valid_ids,
            )
        else:
            layout = layouts.Layout(identifier, version.version, 0, ())

        claimed = session.execute(
            update(GraphArtifact)
            .where(
                GraphArtifact.identifier == identifier,
                GraphArtifact.project_id == project_id,
                GraphArtifact.draft_revision == base_revision,
            )
            .values(
                display_name=str(document["display_name"]),
                draft_json=encoded,
                draft_revision=next_revision,
                published_revision=next_revision,
                current_version=version.version,
                updated_at=version.created_at,
            )
        )
        if claimed.rowcount != 1:
            session.expire_all()
            current = _owned_artifact(session, project_id, identifier)
            raise GraphConflict(current.draft_revision)
        publication = EditPublication(
            draft_revision=next_revision,
            published=_published_record(project_id, version),
            applied_operations=edit_result.applied_operations,
            inverse_operations=edit_result.inverse_operations,
        )
        try:
            result = response_factory(publication, layout)
        except Exception as exc:
            raise EditorDocumentFailed("editor document construction failed") from exc
    return result


def load_version(project_id: str, identifier: str, version: int) -> PublishedGraph:
    with SessionLocal() as session:
        _owned_artifact(session, project_id, identifier)
        published = session.get(GraphVersion, (identifier, version))
        if published is None:
            raise GraphNotFound((project_id, identifier, version))
        return _published_record(project_id, published)


def ensure_catalogue_seed(session: Session) -> None:
    """Create the fixed catalogue lineage for fresh databases.

    Migrated databases receive the same rows in revision 0006. Fresh databases
    are built directly from current ORM metadata and stamped at head, so boot
    must seed them explicitly. Existing drafts are user state and are not reset.
    """
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    project = session.get(Project, CATALOGUE_PROJECT_ID)
    if project is None:
        session.add(Project(
            project_id=CATALOGUE_PROJECT_ID,
            name="Repository catalogue",
            description="",
            status="active",
            created_at=now,
            updated_at=now,
        ))

    identifier = str(GRAPH["identifier"])
    version = int(GRAPH["version"])
    encoded = canonical_json(GRAPH)
    if content_address(GRAPH) != CATALOGUE_CONTENT_ADDRESS:
        raise RuntimeError(
            "repository catalogue graph changed without a new immutable version"
        )
    artifact = session.get(GraphArtifact, identifier)
    if artifact is None:
        session.add(GraphArtifact(
            identifier=identifier,
            project_id=CATALOGUE_PROJECT_ID,
            display_name=str(GRAPH["display_name"]),
            draft_json=encoded,
            draft_revision=0,
            published_revision=0,
            current_version=version,
            created_at=now,
            updated_at=now,
        ))

    published = session.get(GraphVersion, (identifier, version))
    if published is None:
        session.add(GraphVersion(
            graph_identifier=identifier,
            version=version,
            artifact_json=encoded,
            content_address=CATALOGUE_CONTENT_ADDRESS,
            created_at=now,
        ))
    elif (
        published.artifact_json != encoded
        or published.content_address != CATALOGUE_CONTENT_ADDRESS
    ):
        raise RuntimeError(
            "repository catalogue graph differs from immutable persisted version"
        )
