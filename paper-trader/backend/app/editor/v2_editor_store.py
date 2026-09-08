"""Owner-scoped transactional store for canonical v2 editor operations."""
from __future__ import annotations

import copy
import datetime as dt
import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.db.models import (
    GraphArtifact, IrV2EditorPresentation, IrV2GraphVersion, Project,
)
from app.db.session import SessionLocal
from app.editor.v2_mutations import (
    NONAUTHORITY, MAX_RECEIPT_BYTES, EditorRefusal, apply_presentation_commands, apply_semantic_commands,
    _new_receipt_restore_invocation, empty_presentation, seal_receipt,
    seal_semantic_receipt, semantic_ids, validate_presentation_receipt,
    validate_semantic_receipt,
)
from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for, validate_document
from app.ir.hashing import canonical_json, content_address
from app.ir.library import REGISTRY
from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.schema import is_content_address
from app.ir.v2_graph_versions import V2GraphFacts, facts_from_row, require_row_matches


class EditorNotFound(LookupError):
    """Uniform missing, foreign-owner, archived, or revoked resource refusal."""


@dataclass(frozen=True)
class DraftState:
    project_id: str
    graph_identifier: str
    semantic_revision: int
    current_version: int | None
    published_revision: int | None
    document: dict[str, Any]
    content_address: str
    graph_address: str


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _capability_check_time() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@contextmanager
def _editor_transaction(conflict_code: str):
    session = SessionLocal()
    try:
        with session.begin():
            yield session
    except OperationalError as exc:
        session.rollback()
        raise EditorRefusal(conflict_code, "editor compare-and-swap could not acquire its writer slot") from exc
    finally:
        session.close()


def _project(session, owner_id: str, project_id: str) -> Project:
    row = session.scalar(select(Project).where(
        Project.owner_id == owner_id, Project.project_id == project_id,
        Project.status == "active",
    ))
    if row is None:
        raise EditorNotFound()
    return row


def _artifact(session, owner_id: str, project_id: str, identifier: str) -> GraphArtifact:
    _project(session, owner_id, project_id)
    row = session.scalar(select(GraphArtifact).where(
        GraphArtifact.owner_id == owner_id,
        GraphArtifact.project_id == project_id,
        GraphArtifact.identifier == identifier,
    ))
    if row is None:
        raise EditorNotFound()
    try:
        document = json.loads(row.draft_json)
    except (TypeError, ValueError) as exc:
        raise EditorRefusal("SEMANTIC_CORRUPT", "stored semantic document is invalid") from exc
    if document.get("format_version") != 2:
        raise EditorRefusal("V1_LEGACY_ONLY", "legacy graph lineages have no v2 editor mapping")
    return row


def _canonical_facts(document: Mapping[str, Any], *, registry=None) -> tuple[dict[str, Any], str, str, str]:
    registry = REGISTRY if registry is None else registry
    violations = validate_document(document, registry)
    if violations:
        first = violations[0]
        raise EditorRefusal("SEMANTIC_INVALID", first.message, path=first.path)
    canonical = dict(canonical_document(document, registry))
    try:
        resolved = resolve_v2(canonical, registry)
    except ResolutionError as exc:
        raise EditorRefusal("SEMANTIC_INVALID", str(exc), path=getattr(exc, "path", "$")) from exc
    return (canonical, content_address_for(canonical, registry),
            graph_address_for(canonical, registry), resolved.resolved_graph_address)


def _state(artifact: GraphArtifact) -> DraftState:
    document, content, graph, _resolved = _canonical_facts(json.loads(artifact.draft_json))
    return DraftState(
        project_id=artifact.project_id, graph_identifier=artifact.identifier,
        semantic_revision=artifact.draft_revision, current_version=artifact.current_version,
        published_revision=artifact.published_revision, document=document,
        content_address=content, graph_address=graph,
    )


def create_graph(project_id: str, identifier: str, name: str, description: str, *, owner_id: str) -> DraftState:
    now = _now()
    document = {
        "format_version": 2, "strategy_id": identifier, "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": name, "description": description, "tags": []},
        "graph_inputs": [], "graph_outputs": [], "nodes": [], "edges": [],
    }
    canonical, _content, _graph, _resolved = _canonical_facts(document)
    with _editor_transaction("SEMANTIC_REVISION_CONFLICT") as session:
        _project(session, owner_id, project_id)
        if session.get(GraphArtifact, (owner_id, identifier)) is not None:
            raise EditorRefusal("GRAPH_ALREADY_EXISTS", "graph identifier already exists")
        artifact = GraphArtifact(
            owner_id=owner_id, identifier=identifier, project_id=project_id,
            display_name=name, draft_json=canonical_json(canonical), draft_revision=0,
            published_revision=None, current_version=None, created_at=now, updated_at=now,
        )
        session.add(artifact)
        session.flush()
        return _state(artifact)


def read_graph(project_id: str, identifier: str, *, owner_id: str) -> DraftState:
    with SessionLocal() as session:
        return _state(_artifact(session, owner_id, project_id, identifier))


def _semantic_receipt(
    *, artifact: GraphArtifact, base_document: Mapping[str, Any], result: Any,
    intent: str, commit_state: str, source_receipt_address: str | None,
) -> dict[str, Any]:
    base_content = content_address_for(base_document, REGISTRY)
    base_graph = graph_address_for(base_document, REGISTRY)
    current = artifact.current_version
    return seal_semantic_receipt({
        "schema": "strategy-os-v2-semantic-receipt/2",
        "receipt_class": "SEALED_EDITOR_INVERSE",
        "owner_id": artifact.owner_id, "project_id": artifact.project_id,
        "graph_identifier": artifact.identifier,
        "format_version": 2, "intent": intent,
        "source_receipt_address": source_receipt_address,
        "registry_snapshot_address": REGISTRY.registry_snapshot_address,
        "base_semantic_revision": artifact.draft_revision,
        "result_semantic_revision": artifact.draft_revision + 1,
        "base_content_address": base_content, "result_content_address": result.content_address,
        "base_graph_address": base_graph, "result_graph_address": result.graph_address,
        "current_version": current, "next_candidate_version": 1 if current is None else current + 1,
        "forward_commands": list(result.forward_commands),
        "inverse_commands": list(result.inverse_commands),
        "resolved_topology_address": result.resolved_address,
        "commit_state": commit_state, "nonauthority": NONAUTHORITY,
    })


def _verified_commands(
    document: Mapping[str, Any], commands: Sequence[Mapping[str, Any]], *, intent: str,
    source_receipt: Mapping[str, Any] | None, owner_id: str, project_id: str,
    identifier: str, base_revision: int, current_version: int | None,
) -> tuple[
    Sequence[Mapping[str, Any]], dict[str, Any] | None, str | None, str | None,
    Any | None,
]:
    if intent == "EDIT":
        if source_receipt is not None:
            raise EditorRefusal("REQUEST_SCHEMA_INVALID", "EDIT cannot carry a source receipt")
        if any(command.get("command") == "restore_edge_from_receipt" for command in commands):
            raise EditorRefusal("REQUEST_SCHEMA_INVALID", "EDIT cannot restore receipt-private edge identity")
        return commands, None, None, None, None
    if intent not in {"UNDO", "REDO", "REPLAY"} or source_receipt is None:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "intent requires a source receipt")
    receipt = validate_semantic_receipt(source_receipt)
    if (receipt["owner_id"] != owner_id or receipt["project_id"] != project_id
            or receipt["graph_identifier"] != identifier
            or receipt["registry_snapshot_address"] != REGISTRY.registry_snapshot_address
            or receipt["current_version"] != current_version
            or receipt["next_candidate_version"] != (
                1 if current_version is None else current_version + 1)):
        raise EditorRefusal("RECEIPT_LINEAGE_INVALID", "receipt does not belong to this graph lineage")
    if intent == "UNDO":
        if receipt["intent"] not in {"EDIT", "REDO"} \
                or receipt["commit_state"] != "DRAFT_COMMITTED":
            raise EditorRefusal("RECEIPT_LINEAGE_INVALID", "receipt cannot drive UNDO")
        expected_current_content = receipt["result_content_address"]
        expected_current_graph = receipt["result_graph_address"]
        expected_commands = receipt["inverse_commands"]
        target_content = receipt["base_content_address"]
        target_graph = receipt["base_graph_address"]
        expected_revision = receipt["result_semantic_revision"]
        mismatch = "UNDO_BASE_MISMATCH"
    elif intent == "REDO":
        if receipt["intent"] != "UNDO" or receipt["commit_state"] != "DRAFT_COMMITTED":
            raise EditorRefusal("RECEIPT_LINEAGE_INVALID", "receipt cannot drive REDO")
        expected_current_content = receipt["result_content_address"]
        expected_current_graph = receipt["result_graph_address"]
        expected_commands = receipt["inverse_commands"]
        target_content = receipt["base_content_address"]
        target_graph = receipt["base_graph_address"]
        expected_revision = receipt["result_semantic_revision"]
        mismatch = "UNDO_BASE_MISMATCH"
    else:
        expected_current_content = receipt["base_content_address"]
        expected_current_graph = receipt["base_graph_address"]
        expected_commands = receipt["forward_commands"]
        target_content = receipt["result_content_address"]
        target_graph = receipt["result_graph_address"]
        # Replay is allowed after a receipt-driven undo restored the exact named
        # base bytes. The request still CAS-binds the actual current revision.
        expected_revision = base_revision
        mismatch = "REPLAY_DIVERGED"
    if base_revision != expected_revision:
        raise EditorRefusal(mismatch, "receipt revision does not name the current base")
    if (content_address_for(document, REGISTRY) != expected_current_content
            or graph_address_for(document, REGISTRY) != expected_current_graph):
        raise EditorRefusal(mismatch, "current semantic address does not match the receipt base")
    if list(commands) != expected_commands:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "commands differ from the sealed receipt")
    restore_invocation = (
        _new_receipt_restore_invocation(
            receipt,
            document,
            commands,
            opposite_commands=(
                receipt["inverse_commands"]
                if list(commands) == receipt["forward_commands"]
                else receipt["forward_commands"]
            ),
            registry=REGISTRY,
            catalogue_identities=None,
            owner_id=owner_id,
            project_id=project_id,
            graph_identifier=identifier,
            current_version=current_version,
            base_revision=base_revision,
            requested_intent=intent,
            target_content=target_content,
            target_graph=target_graph,
        )
        if any(command.get("command") == "restore_edge_from_receipt" for command in commands)
        else None
    )
    return commands, receipt, target_content, target_graph, restore_invocation


def _validate_use_check(
    session, document: Mapping[str, Any], *, use_check: Mapping[str, Any] | None,
    owner_id: str, allow_non_authoring: bool,
) -> None:
    check = {"purpose": "AUTHORING", "capability_receipt_address": None} \
        if use_check is None else dict(use_check)
    if set(check) != {"purpose", "capability_receipt_address"} \
            or check["purpose"] not in {"AUTHORING", "RESEARCH", "PAPER", "MONITORING"}:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "use_check is open or invalid", path="$.use_check")
    purpose = check["purpose"]
    capability_address = check["capability_receipt_address"]
    if purpose == "AUTHORING":
        if capability_address is not None:
            raise EditorRefusal(
                "REQUEST_SCHEMA_INVALID", "AUTHORING does not accept capability claims",
                path="$.use_check.capability_receipt_address")
        return
    if not allow_non_authoring:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "non-authoring use checks are rollback-only")
    from app.ir.schema import is_content_address
    if not is_content_address(capability_address):
        raise EditorRefusal("CAPABILITY_UNPROVEN", "server-owned capability receipt is required")
    resolved = resolve_v2(document, REGISTRY)
    mode_key = "paper" if purpose == "PAPER" else "research"
    for node in resolved.nodes:
        contract = REGISTRY.node_contracts.get(node.component)
        if contract is None or contract.get("mode_eligibility", {}).get(mode_key) is not True:
            raise EditorRefusal("MODE_INELIGIBLE", "node contract is ineligible for requested purpose")
        if purpose == "MONITORING" and contract.get("visible_family") != "TYPE_1":
            raise EditorRefusal("MODE_INELIGIBLE", "MONITORING accepts only monitoring Type 1 nodes")
    try:
        from app.market_data.requirements import compile_data_requirement_plan
        from app.market_data.authority import load_capability_assessment
        from app.market_data.capability import CapabilityRefusal
        from app.market_data.requirements import DataRequirementRefusal

        plan = compile_data_requirement_plan(resolved, registry=REGISTRY)
        assessment = load_capability_assessment(
            session, capability_address, plan=plan,
            at_time=_capability_check_time(),
        )
    except DataRequirementRefusal as exc:
        raise EditorRefusal("DATA_REQUIREMENT_REFUSED", str(exc)) from exc
    except CapabilityRefusal as exc:
        raise EditorRefusal("CAPABILITY_UNPROVEN", str(exc)) from exc
    expected_mode = "PAPER" if purpose == "PAPER" else "RESEARCH"
    if assessment.owner_id != owner_id or assessment.mode != expected_mode \
            or any(row["result"] != "SATISFIED" for row in assessment.requirement_results):
        raise EditorRefusal("CAPABILITY_UNPROVEN", "capability receipt does not cover owner, mode, and requirements")


def mutate_semantic(
    project_id: str, identifier: str, *, base_revision: int, intent: str,
    commands: Sequence[Mapping[str, Any]], source_receipt: Mapping[str, Any] | None,
    owner_id: str, dry_run: bool = False, use_check: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    # A dry-run owns its session and always exits through rollback, including
    # success.  It uses the exact same candidate function and owner predicate.
    session = SessionLocal()
    try:
        artifact = _artifact(session, owner_id, project_id, identifier)
        if artifact.draft_revision != base_revision:
            raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "semantic revision is stale",
                                current_revision=artifact.draft_revision)
        base_document = json.loads(artifact.draft_json)
        verified, verified_receipt, target_content, target_graph, restore_invocation = _verified_commands(
            base_document, commands, intent=intent, source_receipt=source_receipt,
            owner_id=owner_id, project_id=project_id, identifier=identifier,
            base_revision=base_revision, current_version=artifact.current_version)
        result = (
            restore_invocation.invoke()
            if restore_invocation is not None
            else apply_semantic_commands(base_document, verified, registry=REGISTRY)
        )
        if intent in {"UNDO", "REDO", "REPLAY"}:
            if result.content_address != target_content or result.graph_address != target_graph:
                raise EditorRefusal("REPLAY_DIVERGED", "receipt replay did not reproduce its target")
        _validate_use_check(
            session, result.document, use_check=use_check, owner_id=owner_id,
            allow_non_authoring=dry_run or intent == "REPLAY")
        receipt = _semantic_receipt(
            artifact=artifact, base_document=base_document, result=result, intent=intent,
            commit_state="DRY_RUN_ROLLED_BACK" if dry_run or intent == "REPLAY" else "DRAFT_COMMITTED",
            source_receipt_address=(verified_receipt["receipt_address"]
                                    if verified_receipt is not None else None),
        )
        if dry_run or intent == "REPLAY":
            claimed = session.execute(update(GraphArtifact).where(
                GraphArtifact.owner_id == owner_id,
                GraphArtifact.project_id == project_id,
                GraphArtifact.identifier == identifier,
                GraphArtifact.draft_revision == base_revision,
            ).values(
                draft_json=canonical_json(result.document), draft_revision=base_revision + 1,
                display_name=result.document["metadata"]["name"], updated_at=_now(),
            ))
            if claimed.rowcount != 1:
                session.rollback()
                raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "validation compare-and-swap lost")
            session.flush()
            session.rollback()
            return receipt
        claimed = session.execute(update(GraphArtifact).where(
            GraphArtifact.owner_id == owner_id,
            GraphArtifact.project_id == project_id,
            GraphArtifact.identifier == identifier,
            GraphArtifact.draft_revision == base_revision,
        ).values(
            draft_json=canonical_json(result.document), draft_revision=base_revision + 1,
            display_name=result.document["metadata"]["name"], updated_at=_now(),
        ))
        if claimed.rowcount != 1:
            session.rollback()
            raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "semantic compare-and-swap lost")
        session.commit()
        return receipt
    except OperationalError as exc:
        session.rollback()
        raise EditorRefusal(
            "SEMANTIC_REVISION_CONFLICT", "semantic compare-and-swap could not acquire its writer slot",
        ) from exc
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


_PUBLICATION_RECEIPT_KEYS = frozenset({
    "schema", "project_id", "graph_identifier", "graph_version", "semantic_revision",
    "format_version", "canonical_document", "content_address", "graph_address",
    "registry_snapshot_address", "resolved_topology_address", "predecessor",
    "created_at", "nonauthority", "receipt_address",
})


def _library_changed():
    return EditorRefusal("STRATEGY_LIBRARY_CHANGED",
        "The strategy library changed. Reload the current library, review the strategy and save a new version. Earlier versions and results remain unchanged.")


def _require_publication_target(target):
    if target is not None and (not is_content_address(target) or target != REGISTRY.registry_snapshot_address):
        raise _library_changed()


def _publication_predecessor(session, row):
    if row.graph_version <= 1:
        return None
    prior = session.get(IrV2GraphVersion, (row.owner_id, row.graph_identifier, row.graph_version - 1))
    if prior is None:
        return None
    facts_from_row(prior)
    return {"version": prior.graph_version, "content_address": prior.content_address,
            "graph_address": prior.graph_address}


def _receipt_row_fields(session, row):
    return {
        "schema": "strategy-os-v2-publish-receipt/1", "graph_identifier": row.graph_identifier,
        "graph_version": row.graph_version, "format_version": 2,
        "canonical_document": json.loads(row.artifact_json), "content_address": row.content_address,
        "graph_address": row.graph_address, "registry_snapshot_address": row.registry_snapshot_address,
        "created_at": row.created_at.isoformat(timespec="microseconds"),
        "predecessor": _publication_predecessor(session, row), "nonauthority": NONAUTHORITY,
    }


def _validate_publication_metadata(receipt):
    if type(receipt["semantic_revision"]) is not int or receipt["semantic_revision"] < 0:
        raise ValueError("publication semantic revision differs")
    if not isinstance(receipt["project_id"], str) or not 0 < len(receipt["project_id"]) <= 64:
        raise ValueError("publication project differs")
    if not is_content_address(receipt["resolved_topology_address"]):
        raise ValueError("publication topology address differs")


def _validate_publication_receipt(session, row, receipt):
    if not isinstance(receipt, dict) or set(receipt) != _PUBLICATION_RECEIPT_KEYS:
        raise ValueError("publication receipt shape differs")
    _validate_publication_metadata(receipt)
    expected = _receipt_row_fields(session, row)
    if canonical_json({key: receipt[key] for key in expected}) != canonical_json(expected):
        raise ValueError("publication receipt row binding differs")
    if seal_receipt(receipt) != receipt:
        raise ValueError("publication receipt seal differs")
    return receipt


def _stored_publication_receipt(session, row):
    if row.publication_receipt_json is None:
        return None
    try:
        facts_from_row(row)
        if len(row.publication_receipt_json.encode("utf-8")) > MAX_RECEIPT_BYTES:
            raise ValueError("publication receipt exceeds its byte bound")
        receipt = json.loads(row.publication_receipt_json)
        if canonical_json(receipt) != row.publication_receipt_json:
            raise ValueError("publication receipt bytes are not canonical")
        return _validate_publication_receipt(session, row, receipt)
    except (TypeError, ValueError, KeyError) as exc:
        raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "stored publication receipt is invalid") from exc


def _publication_retry_row(session, artifact, version, target, legacy_retry):
    row = session.get(IrV2GraphVersion, (artifact.owner_id, artifact.identifier, version))
    if row is None:
        if legacy_retry:
            raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "published pointer has no immutable row")
        return None
    if target is not None and row.registry_snapshot_address != target:
        return None
    return row


def _publication_retry(session, artifact, base, expected, target):
    version = 1 if expected is None else expected + 1
    legacy_retry = (artifact.draft_revision == base and artifact.published_revision == base
                    and artifact.current_version == version)
    row = _publication_retry_row(session, artifact, version, target, legacy_retry)
    if row is None:
        return None
    receipt = _stored_publication_receipt(session, row)
    if receipt is not None:
        return _matching_publication_retry(receipt, artifact, base)
    if row.registry_snapshot_address != REGISTRY.registry_snapshot_address:
        raise _library_changed()
    if legacy_retry:
        return _publish_receipt(artifact, row)
    return None


def _matching_publication_retry(receipt, artifact, base):
    if receipt["project_id"] == artifact.project_id and receipt["semantic_revision"] == base:
        return receipt
    return None


def _require_new_publication(session, artifact, base, expected, target):
    if artifact.draft_revision != base:
        raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "semantic revision is stale",
                            current_revision=artifact.draft_revision)
    if artifact.current_version != expected:
        raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "current immutable version differs")
    _require_publication_target(target)
    unchanged = artifact.current_version is not None and artifact.published_revision == artifact.draft_revision
    if unchanged and not _can_revalidate_library(session, artifact, target):
        raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "graph has no unpublished semantic revision",
                            current_revision=artifact.draft_revision)


def _can_revalidate_library(session, artifact, target):
    if target is None:
        return False
    prior = session.get(IrV2GraphVersion, (artifact.owner_id, artifact.identifier, artifact.current_version))
    if prior is None:
        raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "published pointer has no immutable row")
    facts_from_row(prior)
    return prior.registry_snapshot_address != target


def _publication_row(session, artifact, version, base, target):
    registry = REGISTRY
    document = json.loads(artifact.draft_json)
    document["strategy_version"] = version
    canonical, content, graph, resolved = _canonical_facts(document, registry=registry)
    _require_publication_target(target)
    facts = V2GraphFacts(owner_id=artifact.owner_id, graph_identifier=artifact.identifier,
        graph_version=version, artifact_json=canonical_json(canonical), format_version=2,
        content_address=content, graph_address=graph, registry_snapshot_address=registry.registry_snapshot_address)
    existing = session.get(IrV2GraphVersion, (artifact.owner_id, artifact.identifier, version))
    if existing is not None:
        _refuse_existing_publication(existing, facts)
    row = IrV2GraphVersion(**facts.__dict__, created_at=_now())
    receipt = seal_receipt({**_receipt_row_fields(session, row), "project_id": artifact.project_id,
        "semantic_revision": base, "resolved_topology_address": resolved})
    row.publication_receipt_json = canonical_json(receipt)
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "immutable version insert lost") from exc
    return row, receipt, registry


def _refuse_existing_publication(existing, facts):
    try:
        require_row_matches(existing, facts)
    except Exception as exc:
        raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "immutable identity has different bytes") from exc
    raise EditorRefusal("IMMUTABLE_VERSION_CONFLICT", "immutable row exists without matching pointer")


def _advance_publication(session, artifact, row, base, expected, target, registry):
    next_draft = json.loads(row.artifact_json)
    next_draft["strategy_version"] = row.graph_version + 1
    next_draft = dict(canonical_document(next_draft, registry))
    _require_publication_target(target)
    claimed = session.execute(update(GraphArtifact).where(
        GraphArtifact.owner_id == artifact.owner_id, GraphArtifact.project_id == artifact.project_id,
        GraphArtifact.identifier == artifact.identifier, GraphArtifact.draft_revision == base,
        GraphArtifact.current_version.is_(expected) if expected is None else GraphArtifact.current_version == expected,
    ).values(draft_json=canonical_json(next_draft), current_version=row.graph_version,
             published_revision=base, updated_at=row.created_at))
    if claimed.rowcount != 1:
        raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "publication compare-and-swap lost")


def publish(
    project_id: str, identifier: str, *, base_revision: int,
    expected_current_version: int | None, owner_id: str,
    target_registry_snapshot_address: str | None = None,
) -> dict[str, Any]:
    with _editor_transaction("IMMUTABLE_VERSION_CONFLICT") as session:
        artifact = _artifact(session, owner_id, project_id, identifier)
        receipt = _publication_retry(session, artifact, base_revision, expected_current_version,
                                     target_registry_snapshot_address)
        if receipt is not None:
            return receipt
        _require_new_publication(session, artifact, base_revision, expected_current_version,
                                 target_registry_snapshot_address)
        version = 1 if expected_current_version is None else expected_current_version + 1
        row, receipt, registry = _publication_row(session, artifact, version, base_revision,
                                                   target_registry_snapshot_address)
        _advance_publication(session, artifact, row, base_revision, expected_current_version,
                              target_registry_snapshot_address, registry)
        return receipt


def _publish_receipt(artifact: GraphArtifact, row: IrV2GraphVersion) -> dict[str, Any]:
    # Historical NULL rows have no retained resolution; never resolve them against a new library.
    if row.registry_snapshot_address != REGISTRY.registry_snapshot_address:
        raise _library_changed()
    facts_from_row(row)
    canonical, _content, _graph, resolved = _canonical_facts(json.loads(row.artifact_json))
    with SessionLocal() as lookup:
        return seal_receipt({**_receipt_row_fields(lookup, row), "project_id": artifact.project_id,
            "semantic_revision": artifact.published_revision, "canonical_document": canonical,
            "resolved_topology_address": resolved})


def read_version(project_id: str, identifier: str, version: int, *, owner_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        _artifact(session, owner_id, project_id, identifier)
        row = session.get(IrV2GraphVersion, (owner_id, identifier, version))
        if row is None:
            raise EditorNotFound()
        require_row_matches(row, V2GraphFacts(
            owner_id=row.owner_id, graph_identifier=row.graph_identifier,
            graph_version=row.graph_version, artifact_json=row.artifact_json,
            format_version=row.format_version, content_address=row.content_address,
            graph_address=row.graph_address, registry_snapshot_address=row.registry_snapshot_address,
        ))
        return {"format_version": 2, "graph_identifier": identifier, "graph_version": version,
                "document": json.loads(row.artifact_json), "content_address": row.content_address,
                "graph_address": row.graph_address,
                "registry_snapshot_address": row.registry_snapshot_address,
                "nonauthority": NONAUTHORITY}


def read_presentation(project_id: str, identifier: str, *, owner_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        artifact = _artifact(session, owner_id, project_id, identifier)
        semantic = json.loads(artifact.draft_json)
        row = session.get(IrV2EditorPresentation, (owner_id, identifier))
        document = empty_presentation() if row is None else json.loads(row.presentation_json)
        revision = 0 if row is None else row.revision
        ids = semantic_ids(semantic)
        orphaned = {
            "positions": sorted(set(document["positions"]) - ids["nodes"]),
            "groups": sorted(group_id for group_id, group in document["groups"].items()
                             if set(group["members"]) - ids["nodes"]),
            "selection_nodes": sorted(set(document["selection"]["nodes"]) - ids["nodes"]),
            "selection_edges": sorted(set(document["selection"]["edges"]) - ids["edges"]),
            "selection_outputs": sorted(set(document["selection"]["outputs"]) - ids["outputs"]),
        }
        active = copy.deepcopy(document)
        active["positions"] = {key: value for key, value in active["positions"].items() if key in ids["nodes"]}
        active["groups"] = {key: value for key, value in active["groups"].items()
                            if not (set(value["members"]) - ids["nodes"])}
        active["selection"] = {key: [value for value in active["selection"][key] if value in ids[key]]
                               for key in ("nodes", "edges", "outputs")}
        from app.ir.hashing import content_address
        return {"schema": "strategy-os-v2-presentation-state/1", "format_version": 2,
                "semantic_revision": artifact.draft_revision, "presentation_revision": revision,
                "presentation": active, "presentation_address": content_address(document),
                "orphaned_references": orphaned, "executable_identity": False}


def _verified_presentation_commands(
    *, commands: Sequence[Mapping[str, Any]], intent: str,
    source_receipt: Mapping[str, Any] | None, owner_id: str, project_id: str,
    identifier: str, semantic_revision: int, semantic_content_address: str,
    presentation_revision: int, presentation_address: str,
) -> tuple[Sequence[Mapping[str, Any]], dict[str, Any] | None, str | None]:
    if intent == "EDIT":
        if source_receipt is not None:
            raise EditorRefusal("REQUEST_SCHEMA_INVALID", "presentation EDIT cannot carry a source receipt")
        return commands, None, None
    if intent not in {"UNDO", "REDO", "REPLAY"} or source_receipt is None:
        raise EditorRefusal("REQUEST_SCHEMA_INVALID", "presentation intent requires a source receipt")
    receipt = validate_presentation_receipt(source_receipt)
    if (receipt["owner_id"] != owner_id or receipt["project_id"] != project_id
            or receipt["graph_identifier"] != identifier
            or receipt["semantic_revision"] != semantic_revision
            or receipt["semantic_content_address"] != semantic_content_address):
        raise EditorRefusal("RECEIPT_LINEAGE_INVALID", "presentation receipt has foreign lineage")
    if intent == "UNDO":
        if receipt["intent"] not in {"EDIT", "REDO"} \
                or receipt["commit_state"] != "PRESENTATION_COMMITTED":
            raise EditorRefusal("RECEIPT_LINEAGE_INVALID", "presentation receipt cannot drive UNDO")
        expected_revision = receipt["result_presentation_revision"]
        expected_address = receipt["result_presentation_address"]
        expected_commands = receipt["inverse_commands"]
        target_address = receipt["base_presentation_address"]
    elif intent == "REDO":
        if receipt["intent"] != "UNDO" or receipt["commit_state"] != "PRESENTATION_COMMITTED":
            raise EditorRefusal("RECEIPT_LINEAGE_INVALID", "presentation receipt cannot drive REDO")
        expected_revision = receipt["result_presentation_revision"]
        expected_address = receipt["result_presentation_address"]
        expected_commands = receipt["inverse_commands"]
        target_address = receipt["base_presentation_address"]
    else:
        # A prior undo may restore the exact base bytes at a later revision.
        expected_revision = presentation_revision
        expected_address = receipt["base_presentation_address"]
        expected_commands = receipt["forward_commands"]
        target_address = receipt["result_presentation_address"]
    mismatch = "REPLAY_DIVERGED" if intent == "REPLAY" else "UNDO_BASE_MISMATCH"
    if presentation_revision != expected_revision or presentation_address != expected_address:
        raise EditorRefusal(mismatch, "presentation receipt does not name the current base")
    if list(commands) != expected_commands:
        raise EditorRefusal("RECEIPT_ADDRESS_INVALID", "presentation commands differ from receipt")
    return commands, receipt, target_address


def mutate_presentation(
    project_id: str, identifier: str, *, base_semantic_revision: int,
    base_presentation_revision: int, commands: Sequence[Mapping[str, Any]], owner_id: str,
    intent: str = "EDIT", source_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    with _editor_transaction("PRESENTATION_REVISION_CONFLICT") as session:
        artifact = _artifact(session, owner_id, project_id, identifier)
        if artifact.draft_revision != base_semantic_revision:
            raise EditorRefusal("SEMANTIC_REVISION_CONFLICT", "semantic revision is stale",
                                current_revision=artifact.draft_revision)
        row = session.get(IrV2EditorPresentation, (owner_id, identifier))
        revision = 0 if row is None else row.revision
        if revision != base_presentation_revision:
            raise EditorRefusal("PRESENTATION_REVISION_CONFLICT", "presentation revision is stale",
                                current_revision=revision)
        semantic_document = json.loads(artifact.draft_json)
        semantic_content_address = content_address_for(semantic_document, REGISTRY)
        before = empty_presentation() if row is None else json.loads(row.presentation_json)
        before_address = content_address(before)
        verified, verified_receipt, target_address = _verified_presentation_commands(
            commands=commands, intent=intent, source_receipt=source_receipt,
            owner_id=owner_id, project_id=project_id, identifier=identifier,
            semantic_revision=base_semantic_revision,
            semantic_content_address=semantic_content_address,
            presentation_revision=base_presentation_revision,
            presentation_address=before_address)
        result = apply_presentation_commands(
            before, verified, semantic_ids=semantic_ids(semantic_document))
        if target_address is not None and result.presentation_address != target_address:
            raise EditorRefusal("REPLAY_DIVERGED", "presentation receipt did not reproduce its target")
        commit_state = "DRY_RUN_ROLLED_BACK" if intent == "REPLAY" else "PRESENTATION_COMMITTED"
        receipt = seal_receipt({
            "schema": "strategy-os-v2-presentation-receipt/1", "format_version": 2,
            "owner_id": owner_id, "project_id": project_id, "graph_identifier": identifier,
            "intent": intent,
            "source_receipt_address": (verified_receipt["receipt_address"]
                                       if verified_receipt is not None else None),
            "semantic_revision": base_semantic_revision,
            "semantic_content_address": semantic_content_address,
            "base_presentation_revision": base_presentation_revision,
            "result_presentation_revision": base_presentation_revision + 1,
            "base_presentation_address": before_address,
            "result_presentation_address": result.presentation_address,
            "forward_commands": list(result.forward_commands),
            "inverse_commands": list(result.inverse_commands),
            "commit_state": commit_state,
            "identity_class": "NOT_EXECUTABLE_IDENTITY", "nonauthority": NONAUTHORITY,
        })
        if intent == "REPLAY":
            return receipt
        now = _now()
        if row is None:
            row = IrV2EditorPresentation(
                owner_id=owner_id, graph_identifier=identifier, format_version=2,
                presentation_json=canonical_json(result.document), revision=1, updated_at=now,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as exc:
                raise EditorRefusal("PRESENTATION_REVISION_CONFLICT", "presentation insert lost") from exc
        else:
            claimed = session.execute(update(IrV2EditorPresentation).where(
                IrV2EditorPresentation.owner_id == owner_id,
                IrV2EditorPresentation.graph_identifier == identifier,
                IrV2EditorPresentation.revision == base_presentation_revision,
            ).values(presentation_json=canonical_json(result.document),
                     revision=base_presentation_revision + 1, updated_at=now))
            if claimed.rowcount != 1:
                raise EditorRefusal("PRESENTATION_REVISION_CONFLICT", "presentation compare-and-swap lost")
        return receipt
