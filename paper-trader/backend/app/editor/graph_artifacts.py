"""Durable editor graph lineages and immutable published versions."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, TypeVar

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import LEGACY_OWNER_ID, GraphArtifact, GraphVersion, Project
from app.db.session import SessionLocal
from app.editor import layouts
from app.ir.hashing import canonical_json, content_address
from app.ir.library import LIBRARY
from app.ir.resolve import ResolutionError, resolve
from app.ir.strategies.expanding_z import GRAPH
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
class PublishedGraphIdentity:
    project_id: str
    identifier: str
    version: int
    content_address: str


@dataclass(frozen=True)
class ProjectGraphVersionEvent:
    project_id: str
    identifier: str
    version: int
    content_address: str
    created_at: dt.datetime


@dataclass(frozen=True)
class EditPublication:
    draft_revision: int
    published: PublishedGraph
    applied_operations: tuple[dict[str, Any], ...]
    inverse_operations: tuple[dict[str, Any], ...]
    base_version: int
    base_presentation_revision: int
    presentation_delta: layouts.PresentationDelta


@dataclass(frozen=True)
class PresentationPublication:
    draft_revision: int
    published: PublishedGraph
    base_presentation_revision: int
    layout: layouts.Layout
    presentation_delta: layouts.PresentationDelta


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


class GraphVersionNotFound(Exception):
    pass


class GraphVersionCorrupt(Exception):
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
    try:
        graph = json.loads(version.artifact_json)
    except (TypeError, ValueError) as exc:
        raise GraphVersionCorrupt((version.graph_identifier, version.version)) from exc
    if (
        canonical_json(graph) != version.artifact_json
        or content_address(graph) != version.content_address
    ):
        raise GraphVersionCorrupt((version.graph_identifier, version.version))
    return PublishedGraph(
        project_id=project_id,
        identifier=version.graph_identifier,
        version=version.version,
        content_address=version.content_address,
        graph=graph,
    )


def _active_project(session: Session, project_id: str, owner_id: str) -> Project:
    project = session.scalar(select(Project).where(
        Project.project_id == project_id, Project.owner_id == owner_id,
    ))
    if project is None:
        raise ProjectNotFound(project_id)
    if project.status != "active":
        raise InvalidTransition(f"project {project_id!r} is archived")
    return project


def _owned_artifact(
    session: Session, project_id: str, identifier: str, owner_id: str
) -> GraphArtifact:
    artifact = session.scalar(select(GraphArtifact).where(
        GraphArtifact.owner_id == owner_id,
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


def create_project(name: str, description: str = "", *, owner_id: str) -> ProjectRecord:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    project = Project(
        project_id=f"project.{uuid.uuid4().hex}",
        owner_id=owner_id,
        name=name,
        description=description,
        status="active",
        created_at=now,
        updated_at=now,
    )
    with SessionLocal.begin() as session:
        session.add(project)
    return _project_record(project)


def set_project_status(project_id: str, status: str, *, owner_id: str) -> ProjectRecord:
    if status not in {"active", "archived"}:
        raise InvalidTransition(f"unsupported project status {status!r}")
    with SessionLocal.begin() as session:
        project = session.scalar(select(Project).where(
            Project.project_id == project_id, Project.owner_id == owner_id,
        ))
        if project is None:
            raise ProjectNotFound(project_id)
        project.status = status
        project.updated_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    return _project_record(project)


def list_projects(*, owner_id: str) -> tuple[ProjectRecord, ...]:
    with SessionLocal() as session:
        projects = session.scalars(
            select(Project)
            .where(Project.status == "active", Project.owner_id == owner_id)
            .order_by(Project.created_at, Project.project_id)
        )
        return tuple(_project_record(project) for project in projects)


def create_artifact(
    project_id: str,
    identifier: str,
    graph: Mapping[str, Any],
    *,
    owner_id: str,
) -> GraphDraft:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _active_project(session, project_id, owner_id)
        existing = session.get(GraphArtifact, (owner_id, identifier))
        if existing is not None:
            raise GraphConflict(existing.draft_revision)
        document, encoded = _normalise_graph(identifier, graph, current_version=None)
        artifact = GraphArtifact(
            owner_id=owner_id,
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


def load_draft(project_id: str, identifier: str, *, owner_id: str) -> GraphDraft:
    with SessionLocal() as session:
        return _draft_record(_owned_artifact(session, project_id, identifier, owner_id))


def _authored_ids(graph: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(str(node["instance_id"]) for node in graph.get("nodes", ()))


def load_editor_snapshot(project_id: str, identifier: str, *, owner_id: str) -> EditorSnapshot:
    """Read the published editor head and its presentation state coherently."""
    with SessionLocal() as session:
        _active_project(session, project_id, owner_id)
        artifact = _owned_artifact(session, project_id, identifier, owner_id)
        if artifact.current_version is None:
            raise InvalidTransition("graph has no published version")
        if artifact.published_revision != artifact.draft_revision:
            raise InvalidTransition("graph has unpublished draft changes")
        version = session.get(GraphVersion, (owner_id, identifier, artifact.current_version))
        if version is None:
            raise GraphNotFound((project_id, identifier, artifact.current_version))
        published = _published_record(project_id, version)
        layout = layouts.load_layout_in_session(
            session,
            identifier,
            version.version,
            _authored_ids(published.graph),
            owner_id=owner_id,
        )
        return EditorSnapshot(artifact.draft_revision, published, layout)


def load_published_graph(identifier: str, version: int, *, owner_id: str) -> PublishedGraph:
    """Load one globally identified immutable graph for presentation routes."""
    with SessionLocal() as session:
        artifact = session.scalar(select(GraphArtifact).where(
            GraphArtifact.owner_id == owner_id, GraphArtifact.identifier == identifier,
        ))
        published = session.scalar(select(GraphVersion).join(
            GraphArtifact,
            (GraphArtifact.owner_id == GraphVersion.owner_id)
            & (GraphArtifact.identifier == GraphVersion.graph_identifier),
        ).where(
            GraphVersion.owner_id == owner_id,
            GraphVersion.graph_identifier == identifier, GraphVersion.version == version,
        ))
        if artifact is None or published is None:
            raise GraphNotFound((identifier, version))
        return _published_record(artifact.project_id, published)


def save_draft(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
    graph: Mapping[str, Any],
    owner_id: str,
) -> GraphDraft:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        _active_project(session, project_id, owner_id)
        artifact = _owned_artifact(session, project_id, identifier, owner_id)
        if artifact.draft_revision != base_revision:
            raise GraphConflict(artifact.draft_revision)
        document, encoded = _normalise_graph(
            identifier, graph, current_version=artifact.current_version
        )
        claimed = session.execute(
            update(GraphArtifact)
            .where(
                GraphArtifact.identifier == identifier,
                GraphArtifact.owner_id == owner_id,
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
            current = _owned_artifact(session, project_id, identifier, owner_id)
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
    owner_id: str,
) -> PublishedGraph:
    with SessionLocal.begin() as session:
        _active_project(session, project_id, owner_id)
        artifact = _owned_artifact(session, project_id, identifier, owner_id)
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
            owner_id=owner_id,
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
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=None,
            aggregate_type="graph", aggregate_id=identifier,
            event_type="execution.graph.changed", projection="published_graphs",
            producer_key="graph:" + hashlib.sha256(
                f"{owner_id}\x1f{identifier}\x1f{version.version}".encode("utf-8")
            ).hexdigest(),
            facts={"state": "published", "version": version.version,
                   "content_address": version.content_address},
        )
        result = _published_record(project_id, version)
    return result


def apply_and_publish(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
    base_presentation_revision: int,
    presentation_operations: tuple[dict[str, Any], ...],
    transform: Callable[[dict[str, Any]], EditResult],
    response_factory: Callable[[EditPublication, layouts.Layout], T],
    owner_id: str,
) -> T:
    """Apply an edit and build its canonical response before committing."""
    with SessionLocal.begin() as session:
        _active_project(session, project_id, owner_id)
        artifact = _owned_artifact(session, project_id, identifier, owner_id)
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
            owner_id=owner_id,
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

        source_version = artifact.current_version
        valid_ids = _authored_ids(document)
        layout, presentation_delta = layouts.carry_and_reconcile_presentation(
            session,
            identifier,
            source_version,
            version.version,
            base_revision=base_presentation_revision,
            source_instance_ids=_authored_ids(original),
            target_instance_ids=valid_ids,
            operations=presentation_operations,
            owner_id=owner_id,
        )

        claimed = session.execute(
            update(GraphArtifact)
            .where(
                GraphArtifact.identifier == identifier,
                GraphArtifact.owner_id == owner_id,
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
            current = _owned_artifact(session, project_id, identifier, owner_id)
            raise GraphConflict(current.draft_revision)
        publication = EditPublication(
            draft_revision=next_revision,
            published=_published_record(project_id, version),
            applied_operations=edit_result.applied_operations,
            inverse_operations=edit_result.inverse_operations,
            base_version=source_version,
            base_presentation_revision=base_presentation_revision,
            presentation_delta=presentation_delta,
        )
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=None,
            aggregate_type="graph", aggregate_id=identifier,
            event_type="execution.graph.changed", projection="published_graphs",
            producer_key="graph:" + hashlib.sha256(
                f"{owner_id}\x1f{identifier}\x1f{version.version}".encode("utf-8")
            ).hexdigest(),
            facts={"state": "published", "version": version.version,
                   "content_address": version.content_address},
        )
        try:
            result = response_factory(publication, layout)
        except Exception as exc:
            raise EditorDocumentFailed("editor document construction failed") from exc
    return result


def apply_presentation(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
    base_presentation_revision: int,
    operations: tuple[dict[str, Any], ...],
    response_factory: Callable[[PresentationPublication, layouts.Layout], T],
    owner_id: str,
) -> T:
    """Apply presentation-only commands against the coherent published head."""
    with SessionLocal.begin() as session:
        _active_project(session, project_id, owner_id)
        artifact = _owned_artifact(session, project_id, identifier, owner_id)
        if artifact.draft_revision != base_revision:
            raise GraphConflict(artifact.draft_revision)
        if artifact.current_version is None:
            raise InvalidTransition("graph has no published version")
        if artifact.published_revision != artifact.draft_revision:
            raise InvalidTransition("graph has unpublished draft changes")
        version = session.get(GraphVersion, (owner_id, identifier, artifact.current_version))
        if version is None:
            raise GraphNotFound((project_id, identifier, artifact.current_version))
        published = _published_record(project_id, version)
        layout, delta = layouts.apply_presentation_batch_in_session(
            session,
            identifier,
            version.version,
            base_revision=base_presentation_revision,
            operations=operations,
            valid_instance_ids=_authored_ids(published.graph),
            owner_id=owner_id,
        )
        publication = PresentationPublication(
            draft_revision=artifact.draft_revision,
            published=published,
            base_presentation_revision=base_presentation_revision,
            layout=layout,
            presentation_delta=delta,
        )
        try:
            result = response_factory(publication, layout)
        except Exception as exc:
            raise EditorDocumentFailed("editor document construction failed") from exc
    return result


def load_version(project_id: str, identifier: str, version: int, *, owner_id: str) -> PublishedGraph:
    with SessionLocal() as session:
        published = session.scalar(select(GraphVersion).join(
            GraphArtifact,
            (GraphArtifact.owner_id == GraphVersion.owner_id)
            & (GraphArtifact.identifier == GraphVersion.graph_identifier),
        ).where(
            GraphVersion.owner_id == owner_id,
            GraphVersion.graph_identifier == identifier, GraphVersion.version == version,
            GraphArtifact.project_id == project_id, GraphArtifact.owner_id == owner_id,
        ))
        if published is None:
            raise GraphNotFound()
        return _published_record(project_id, published)


def list_versions(
    project_id: str, identifier: str, *, owner_id: str
) -> tuple[PublishedGraphIdentity, ...]:
    with SessionLocal() as session:
        _owned_artifact(session, project_id, identifier, owner_id)
        versions = session.scalars(
            select(GraphVersion)
            .join(GraphArtifact, (GraphArtifact.owner_id == GraphVersion.owner_id)
                  & (GraphArtifact.identifier == GraphVersion.graph_identifier))
            .where(GraphVersion.owner_id == owner_id, GraphVersion.graph_identifier == identifier,
                   GraphArtifact.project_id == project_id, GraphArtifact.owner_id == owner_id)
            .order_by(GraphVersion.version)
        ).all()
        identities = []
        for version in versions:
            published = _published_record(project_id, version)
            identities.append(PublishedGraphIdentity(
                project_id=project_id,
                identifier=identifier,
                version=published.version,
                content_address=published.content_address,
            ))
        return tuple(identities)


def list_project_version_events(
    project_id: str, *, owner_id: str
) -> tuple[ProjectGraphVersionEvent, ...]:
    """Verified immutable versions owned by a project, including archived projects."""
    with SessionLocal() as session:
        if session.scalar(select(Project).where(
            Project.project_id == project_id, Project.owner_id == owner_id,
        )) is None:
            raise ProjectNotFound(project_id)
        rows = session.execute(
            select(GraphVersion, GraphArtifact)
            .join(GraphArtifact, (GraphArtifact.owner_id == GraphVersion.owner_id)
                  & (GraphArtifact.identifier == GraphVersion.graph_identifier))
            .where(GraphArtifact.project_id == project_id, GraphArtifact.owner_id == owner_id)
            .order_by(GraphVersion.created_at, GraphVersion.graph_identifier, GraphVersion.version)
        ).all()
        events = []
        for version, artifact in rows:
            published = _published_record(project_id, version)
            events.append(ProjectGraphVersionEvent(
                project_id=artifact.project_id,
                identifier=published.identifier,
                version=published.version,
                content_address=published.content_address,
                created_at=version.created_at,
            ))
        return tuple(events)


def load_owned_version_for_experiment(
    project_id: str, identifier: str, version: int, *, owner_id: str
) -> PublishedGraph:
    """Load exactly one active-project published version for research binding."""
    with SessionLocal() as session:
        _active_project(session, project_id, owner_id)
        artifact = _owned_artifact(session, project_id, identifier, owner_id)
        if artifact.current_version is None:
            raise InvalidTransition("graph has no published version")
        if artifact.published_revision != artifact.draft_revision:
            raise InvalidTransition("graph has unpublished draft changes")
        published = session.scalar(select(GraphVersion).join(
            GraphArtifact, (GraphArtifact.owner_id == GraphVersion.owner_id)
            & (GraphArtifact.identifier == GraphVersion.graph_identifier)
        ).where(
            GraphVersion.owner_id == owner_id,
            GraphVersion.graph_identifier == identifier, GraphVersion.version == version,
            GraphArtifact.project_id == project_id, GraphArtifact.owner_id == owner_id,
        ))
        if published is None:
            raise GraphVersionNotFound((project_id, identifier, version))
        return _published_record(project_id, published)


def ensure_catalogue_seed(session: Session) -> None:
    """Create the fixed catalogue lineage for fresh databases.

    Migrated databases receive the same rows in revision 0006. Fresh databases
    are built directly from current ORM metadata and stamped at head, so boot
    must seed them explicitly. Existing drafts are user state and are not reset.
    """
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    project = session.scalar(select(Project).where(
        Project.project_id == CATALOGUE_PROJECT_ID, Project.owner_id == LEGACY_OWNER_ID,
    ))
    if project is None:
        session.add(Project(
            project_id=CATALOGUE_PROJECT_ID,
            owner_id=LEGACY_OWNER_ID,
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
    artifact = session.get(GraphArtifact, (LEGACY_OWNER_ID, identifier))
    if artifact is None:
        session.add(GraphArtifact(
            owner_id=LEGACY_OWNER_ID,
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

    published = session.get(GraphVersion, (LEGACY_OWNER_ID, identifier, version))
    if published is None:
        session.add(GraphVersion(
            owner_id=LEGACY_OWNER_ID,
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
