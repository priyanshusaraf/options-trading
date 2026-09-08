"""Explicit real admission evidence for tests that intentionally open exposure."""
from __future__ import annotations

import hashlib
from copy import deepcopy


_ARTIFACTS = {}


def _backtest_graph():
    """Return the shipped graph with a fixture-sized, still-valid history bound."""
    from app.ir.strategies.expanding_z import GRAPH

    graph = deepcopy(GRAPH)
    graph["identifier"] = "test.strategy.expanding_z_impulse"
    graph["version"] = 1
    graph["display_name"] = "Test Expanding Z Impulse"
    for item in graph["interface"]:
        if item.get("item") != "panel":
            continue
        for field in item.get("items", ()):
            if field.get("identifier") == "adapt_length":
                field["default"] = 20
                return graph
    raise AssertionError("shipped expanding-z graph lost adapt_length")


def admitted_artifact(*, graph: dict, owner_id: str):
    """Return the immutable admission artifact for exact fixture bytes and owner."""
    from app.ir.hashing import canonical_json
    from app.ir.library import REGISTRY
    from app.strategy.admission import IRGraphAdmissionInput, admit_strategy

    graph_json = canonical_json(graph)
    cache_key = (owner_id, graph_json)
    artifact = _ARTIFACTS.get(cache_key)
    if artifact is None:
        decision = admit_strategy(
            owner_id=owner_id,
            source_input=IRGraphAdmissionInput(
                graph=graph, parameters={}, risk_model=None),
            registry=REGISTRY,
        )
        assert decision.artifact is not None
        artifact = decision.artifact
        _ARTIFACTS[cache_key] = artifact
    return artifact


def persist_admitted_graph(session, *, graph: dict, owner_id: str, project_id: str,
                           display_name: str):
    """Persist the receipt and immutable graph version a money-path test names.

    The address returned by ``admit_strategy`` is not enough: authority consumers retrieve
    its owner-scoped immutable receipt from the execution database.  Keeping that write in
    this helper prevents lifecycle tests from accidentally treating a plausible hash as
    evidence.
    """
    from app.core import strategy_admissions
    from app.db.models import GraphArtifact, GraphVersion, Organization, Project
    from app.ir.hashing import canonical_json, content_address

    graph_json = canonical_json(graph)
    artifact = admitted_artifact(graph=graph, owner_id=owner_id)

    strategy_admissions.put(session, artifact)
    if session.get(Organization, owner_id) is None:
        session.add(Organization(
            organization_id=owner_id, name=f"Test owner {owner_id}", status="active"))
    if session.get(Project, project_id) is None:
        session.add(Project(
            project_id=project_id, owner_id=owner_id,
            name=display_name, status="active"))
    artifact_key = (owner_id, artifact.graph_identifier)
    if session.get(GraphArtifact, artifact_key) is None:
        session.add(GraphArtifact(
            owner_id=owner_id, identifier=artifact.graph_identifier,
            project_id=project_id, display_name=display_name,
            draft_json=graph_json, draft_revision=0,
            published_revision=0, current_version=artifact.graph_version,
        ))
    version_key = (owner_id, artifact.graph_identifier, artifact.graph_version)
    if session.get(GraphVersion, version_key) is None:
        session.add(GraphVersion(
            owner_id=owner_id,
            graph_identifier=artifact.graph_identifier,
            version=artifact.graph_version,
            artifact_json=graph_json,
            content_address=content_address(graph),
            admission_address=artifact.admission_address,
        ))
    session.flush()
    return artifact


def persist_admitted_entry(session, *, owner_id: str = "owner") -> dict[str, str]:
    artifact = persist_admitted_graph(
        session, graph=_backtest_graph(), owner_id=owner_id,
        project_id="test.admission." + hashlib.sha256(owner_id.encode()).hexdigest()[:24],
        display_name="Test admitted graph",
    )
    # Direct broker checks use this same session, but several legacy lifecycle
    # helpers open a separate verification session before opening exposure.  Make
    # the immutable receipt visible there before returning its identity.
    session.commit()
    return {
        "strategy_key": f"ir.{artifact.graph_identifier}",
        "strategy_version": str(artifact.graph_version),
        "graph_address": artifact.graph_address,
        "attribution_state": "VERIFIED_GRAPH",
        "admission_address": artifact.admission_address,
    }
