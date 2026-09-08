"""HTTP contract for owner-scoped v2 create/edit/validate/publish/reload."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.db.models import GraphArtifact, GraphVersion, IrV2GraphVersion, StrategyAdmission
from app.db.session import SessionLocal, init_db


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    init_db(reset=True)
    with TestClient(app) as value:
        yield value


def _project(client) -> str:
    response = client.post("/api/ir/projects", json={
        "name": "V2 editor " + uuid.uuid4().hex, "description": "",
    })
    assert response.status_code == 201, response.text
    return response.json()["project_id"]


def _create(client, project_id: str, identifier: str = "editor-v2"):
    response = client.post(f"/api/ir/projects/{project_id}/graphs/v2/create", json={
        "format_version": 2, "identifier": identifier, "name": "Editor v2", "description": "",
    })
    assert response.status_code == 201, response.text
    return response


def _batch(*, base: int, commands, intent="EDIT", source=None):
    return {
        "schema": "strategy-os-v2-semantic-batch/1", "format_version": 2,
        "base_revision": base, "intent": intent,
        "use_check": {"purpose": "AUTHORING", "capability_receipt_address": None},
        "source_receipt": source, "commands": commands,
    }


def _logic_node():
    return {"command": "add_node", "node_id": "logic",
            "component_id": "logic.and", "component_version": 1, "parameters": {}}


def _persist_use_check_capabilities(document, *, owner_id="owner"):
    import datetime as dt
    from app.editor.v2_editor_store import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.market_data.authority import persist_capability_assessment, persist_capability_profile
    from app.market_data.capability import CapabilityProfile, assess_capability
    from app.market_data.requirements import compile_data_requirement_plan
    from app.market_truth.identity import ProviderContract, persist_provider_identity
    from tests.test_phase4_dataset_assessment_authority import (
        T0, _authority, _seed_execution, address,
    )

    plan = compile_data_requirement_plan(resolve_v2(document, REGISTRY), registry=REGISTRY)
    at_time = T0 + dt.timedelta(hours=3)
    result = {}
    with SessionLocal.begin() as session:
        values = _seed_execution(session, owner_id=owner_id)
        manifest, _segments = _authority(values, owner_id=owner_id)
        profiles = {"RESEARCH": values["profile"]}
        paper_contract = ProviderContract(
            owner_id, values["product"].address, "PAPER", ("HISTORICAL",), T0, None,
            address("paper-contract-evidence"))
        persist_provider_identity(
            session, values["entity"], values["product"], paper_contract)
        paper_profile = CapabilityProfile(
            owner_id, "PAPER", 1, values["profile"].observed_at,
            values["profile"].expires_at, values["conformance"].address,
            tuple(values["profile"].offers), 0,
            values["entity"].address, values["product"].address, paper_contract.address)
        persist_capability_profile(session, paper_profile)
        profiles["PAPER"] = paper_profile
        for mode, profile in profiles.items():
            assessment = assess_capability(
                plan=plan, profile=profile, owner_id=owner_id, mode=mode,
                dataset_manifest_address=manifest.manifest_address,
                market_truth_snapshot_address=values["truth"].address,
                evaluation_policy_address=address("editor-evaluation-policy-" + mode),
                assessment_evidence_address=address("editor-assessment-evidence-" + mode),
                at_time=int(at_time.timestamp()), conformance=values["conformance"],
                provider_contract=(paper_contract if mode == "PAPER" else values["contract"]))
            persist_capability_assessment(session, assessment, plan=plan, at_time=at_time)
            result[mode] = assessment.authority_address
    return result


def _monitoring_document(identifier="monitoring-v2"):
    import json
    from app.editor.v2_editor_store import REGISTRY
    from app.ir.hashing import canonical_json
    component = REGISTRY.v2_components[("intent.buy", 2)]
    input_port = json.loads(canonical_json(
        next(port for port in component["ports"] if port["direction"] == "input")))
    return {
        "format_version": 2, "strategy_id": identifier, "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Monitoring", "description": "", "tags": []},
        "graph_inputs": [dict(input_port)], "graph_outputs": [],
        "nodes": [{"node_id": "intent", "component": {
            "component_id": "intent.buy", "component_version": 2}, "parameters": {}}],
        "edges": [{"edge_id": "monitoring-condition", "source": {
            "scope": "graph_input", "port_id": input_port["port_id"]}, "target": {
            "scope": "node", "node_id": "intent", "port_id": input_port["port_id"]},
            "binding": {"kind": "single"}}],
    }


def _dynamic_data_document(identifier="dynamic-data-v2"):
    import json
    from app.editor.v2_editor_store import REGISTRY
    from app.editor.v2_catalogue import CATALOGUE_DOCUMENT

    admitted = {(row["component_id"], row["component_version"])
                for group in CATALOGUE_DOCUMENT["groups"] for row in group["components"]}
    key = next(key for key, declaration in REGISTRY.data_requirement_declarations.items()
               if key in admitted and declaration.get("schema") == "first-party-node-contract/2")
    component = REGISTRY.v2_components[key]
    from app.ir.hashing import canonical_json
    inputs = [json.loads(canonical_json(port)) for port in component["ports"]
              if port["direction"] == "input"]
    return {
        "format_version": 2, "strategy_id": identifier, "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Dynamic data", "description": "", "tags": []},
        "graph_inputs": inputs, "graph_outputs": [],
        "nodes": [{"node_id": "dynamic", "component": {
            "component_id": key[0], "component_version": key[1]}, "parameters": {}}],
        "edges": [{"edge_id": f"dynamic-{port['port_id']}", "source": {
            "scope": "graph_input", "port_id": port["port_id"]}, "target": {
            "scope": "node", "node_id": "dynamic", "port_id": port["port_id"]},
            "binding": {"kind": "single"}} for port in inputs],
    }


def test_validate_rolls_back_then_commit_publish_retry_and_reload_are_exact(client):
    project = _project(client)
    created = _create(client, project).json()
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
    before = client.get(path).json()
    with SessionLocal() as session:
        row = session.get(GraphArtifact, ("owner", "editor-v2"))
        persisted_before = (row.draft_json, row.draft_revision, row.updated_at)
        tables_before = (
            session.scalar(select(func.count()).select_from(IrV2GraphVersion)),
            session.scalar(select(func.count()).select_from(GraphVersion)),
            session.scalar(select(func.count()).select_from(StrategyAdmission)),
        )

    dry = client.post(path + "/validate", json=_batch(base=0, commands=[_logic_node()]))
    assert dry.status_code == 200, dry.text
    assert dry.json()["commit_state"] == "DRY_RUN_ROLLED_BACK"
    assert client.get(path).json() == before == created
    with SessionLocal() as session:
        row = session.get(GraphArtifact, ("owner", "editor-v2"))
        assert (row.draft_json, row.draft_revision, row.updated_at) == persisted_before
        assert (
            session.scalar(select(func.count()).select_from(IrV2GraphVersion)),
            session.scalar(select(func.count()).select_from(GraphVersion)),
            session.scalar(select(func.count()).select_from(StrategyAdmission)),
        ) == tables_before
    invalid_command = _logic_node() | {"component_id": "unknown.component"}
    invalid = client.post(path + "/validate",
                          json=_batch(base=0, commands=[invalid_command]))
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "COMPONENT_NOT_IN_V0_CATALOGUE"
    assert client.get(path).json() == before

    committed = client.post(path + "/semantic-batches",
                            json=_batch(base=0, commands=[_logic_node()]))
    assert committed.status_code == 200, committed.text
    receipt = committed.json()
    assert receipt["commit_state"] == "DRAFT_COMMITTED"
    assert receipt["result_semantic_revision"] == 1
    assert client.get(path).json()["semantic_revision"] == 1

    stale = client.post(path + "/semantic-batches",
                        json=_batch(base=0, commands=[_logic_node()]))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "SEMANTIC_REVISION_CONFLICT"

    published = client.post(path + "/publish", json={
        "format_version": 2, "base_revision": 1, "expected_current_version": None,
    })
    assert published.status_code == 200, published.text
    retry = client.post(path + "/publish", json={
        "format_version": 2, "base_revision": 1, "expected_current_version": None,
    })
    assert retry.status_code == 200
    assert retry.json() == published.json()
    loaded = client.get(path + "/versions/1")
    assert loaded.status_code == 200
    assert loaded.json()["content_address"] == published.json()["content_address"]

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(IrV2GraphVersion)) == 1
        assert session.scalar(select(func.count()).select_from(GraphVersion).where(
            GraphVersion.graph_identifier == "editor-v2")) == 0
        assert session.scalar(select(func.count()).select_from(StrategyAdmission).where(
            StrategyAdmission.graph_identifier == "editor-v2")) == 0


def test_undo_redo_receipts_and_v1_lineage_refusal_have_no_mapping(client):
    project = _project(client)
    _create(client, project)
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
    edit = client.post(path + "/semantic-batches",
                       json=_batch(base=0, commands=[_logic_node()])).json()
    undo = client.post(path + "/semantic-batches", json=_batch(
        base=1, intent="UNDO", commands=edit["inverse_commands"], source=edit))
    assert undo.status_code == 200, undo.text
    assert undo.json()["result_content_address"] == edit["base_content_address"]
    redo = client.post(path + "/semantic-batches", json=_batch(
        base=2, intent="REDO", commands=undo.json()["inverse_commands"], source=undo.json()))
    assert redo.status_code == 200, redo.text
    assert redo.json()["result_content_address"] == edit["result_content_address"]

    # A legacy artifact can share the identifier only in a different owner;
    # within one lineage the v2 store checks format and refuses explicitly.
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "editor-v2"))
        row.draft_json = '{"format_version":1}'
    refused = client.get(path)
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "V1_LEGACY_ONLY"


def test_authenticated_http_undo_restores_imported_edge_id_and_exact_addresses(client, monkeypatch):
    import copy

    import app.editor.v2_editor_store as editor_store
    from app.editor.v2_editor_store import REGISTRY
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands, seal_receipt
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for
    from app.ir.hashing import canonical_json

    project = _project(client)
    _create(client, project, identifier="imported-edge-v2")
    path = f"/api/ir/projects/{project}/graphs/imported-edge-v2/v2"
    base = client.get(path).json()["document"]
    imported = apply_semantic_commands(base, [
        _logic_node() | {"node_id": "left"},
        _logic_node() | {"node_id": "right"},
        {"command": "connect", "source": {"node_id": "left", "port_id": "value"},
         "target": {"node_id": "right", "port_id": "input"},
         "binding": {"kind": "single"}},
    ], registry=REGISTRY).document
    imported["edges"][0]["edge_id"] = "caller.edge.identity"
    before_content = content_address_for(imported, REGISTRY)
    before_graph = graph_address_for(imported, REGISTRY)
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "imported-edge-v2"))
        row.draft_json = canonical_json(imported)

    removed = client.post(path + "/semantic-batches", json=_batch(
        base=0, commands=[{"command": "remove_node", "node_id": "right"}]))
    assert removed.status_code == 200, removed.text
    receipt = removed.json()
    assert receipt["schema"] == "strategy-os-v2-semantic-receipt/2"
    assert receipt["receipt_class"] == "SEALED_EDITOR_INVERSE"
    assert receipt["server_seal"]["algorithm"] == "hmac-sha256"
    public_restore = client.post(path + "/semantic-batches", json=_batch(
        base=1, intent="EDIT", commands=receipt["inverse_commands"]))
    assert public_restore.status_code == 422
    assert public_restore.json()["detail"]["code"] == "REQUEST_SCHEMA_INVALID"
    forged = copy.deepcopy(receipt)
    forged["inverse_commands"][1]["edge"]["edge_id"] = "attacker-selected-edge"
    forged = seal_receipt({
        key: value for key, value in forged.items() if key != "receipt_address"
    })
    forged_undo = client.post(path + "/semantic-batches", json=_batch(
        base=1, intent="UNDO", commands=forged["inverse_commands"], source=forged))
    assert forged_undo.status_code == 422
    assert forged_undo.json()["detail"]["code"] == "RECEIPT_SEAL_INVALID"
    assert client.get(path).json()["semantic_revision"] == 1
    captured_invocations = []
    real_invocation = editor_store._new_receipt_restore_invocation

    def capture_invocation(*args, **kwargs):
        invocation = real_invocation(*args, **kwargs)
        captured_invocations.append(invocation)
        return invocation

    monkeypatch.setattr(editor_store, "_new_receipt_restore_invocation", capture_invocation)
    undo = client.post(path + "/semantic-batches", json=_batch(
        base=1, intent="UNDO", commands=receipt["inverse_commands"], source=receipt))
    assert undo.status_code == 200, undo.text
    undo_receipt = undo.json()
    state = client.get(path).json()
    assert state["document"] == imported
    assert state["content_address"] == before_content
    assert state["graph_address"] == before_graph
    assert len(captured_invocations) == 1
    with pytest.raises(EditorRefusal) as reused:
        captured_invocations[0].invoke()
    assert getattr(reused.value, "code", None) == "RECEIPT_CAPABILITY_INVALID"
    assert client.get(path).json() == state
    redo = client.post(path + "/semantic-batches", json=_batch(
        base=2, intent="REDO", commands=undo_receipt["inverse_commands"], source=undo_receipt))
    assert redo.status_code == 200, redo.text
    assert client.get(path).json()["document"]["edges"] == []
    redo_receipt = redo.json()
    second_undo = client.post(path + "/semantic-batches", json=_batch(
        base=3, intent="UNDO", commands=redo_receipt["inverse_commands"], source=redo_receipt))
    assert second_undo.status_code == 200, second_undo.text
    before_replay = client.get(path).json()
    replay = client.post(path + "/replay", json=_batch(
        base=4, intent="REPLAY", commands=receipt["forward_commands"], source=receipt))
    assert replay.status_code == 200, replay.text
    assert replay.json()["commit_state"] == "DRY_RUN_ROLLED_BACK"
    assert client.get(path).json() == before_replay
    published = client.post(path + "/publish", json={
        "format_version": 2, "base_revision": 4, "expected_current_version": None,
    })
    assert published.status_code == 200, published.text
    assert published.json()["content_address"] == before_content
    assert published.json()["graph_address"] == before_graph


def test_authenticated_http_remove_node_restores_graph_input_edge_identity(client):
    from app.editor.v2_editor_store import REGISTRY
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for
    from app.ir.hashing import canonical_json

    project = _project(client)
    _create(client, project, identifier="boundary-input-v2")
    path = f"/api/ir/projects/{project}/graphs/boundary-input-v2/v2"
    imported = dict(canonical_document(_monitoring_document("boundary-input-v2"), REGISTRY))
    imported["edges"][0]["edge_id"] = "caller.graph-input.edge"
    before_content = content_address_for(imported, REGISTRY)
    before_graph = graph_address_for(imported, REGISTRY)
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "boundary-input-v2"))
        row.draft_json = canonical_json(imported)
    removed = client.post(path + "/semantic-batches", json=_batch(
        base=0, commands=[{"command": "remove_node", "node_id": "intent"}]))
    assert removed.status_code == 200, removed.text
    receipt = removed.json()
    restored = client.post(path + "/semantic-batches", json=_batch(
        base=1, intent="UNDO", commands=receipt["inverse_commands"], source=receipt))
    assert restored.status_code == 200, restored.text
    state = client.get(path).json()
    assert state["document"] == imported
    assert state["content_address"] == before_content
    assert state["graph_address"] == before_graph


def test_store_private_restore_invocation_is_consumed_after_exact_undo(monkeypatch):
    import app.editor.v2_editor_store as editor_store
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands
    from app.ir.hashing import canonical_json

    init_db(reset=True)
    project = create_project("Store one-shot", owner_id="owner")
    editor_store.create_graph(project.project_id, "store-one-shot-v2", "Store", "",
                              owner_id="owner")
    base = editor_store.read_graph(
        project.project_id, "store-one-shot-v2", owner_id="owner").document
    imported = apply_semantic_commands(base, [
        _logic_node() | {"node_id": "left"},
        _logic_node() | {"node_id": "right"},
        {"command": "connect", "source": {"node_id": "left", "port_id": "value"},
         "target": {"node_id": "right", "port_id": "input"},
         "binding": {"kind": "single"}},
    ], registry=editor_store.REGISTRY).document
    imported["edges"][0]["edge_id"] = "caller.store.one-shot"
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "store-one-shot-v2"))
        row.draft_json = canonical_json(imported)
    edit = editor_store.mutate_semantic(
        project.project_id, "store-one-shot-v2", base_revision=0, intent="EDIT",
        commands=[{"command": "remove_node", "node_id": "right"}],
        source_receipt=None, owner_id="owner")
    captured = []
    real_factory = editor_store._new_receipt_restore_invocation

    def capture(*args, **kwargs):
        invocation = real_factory(*args, **kwargs)
        captured.append(invocation)
        return invocation

    monkeypatch.setattr(editor_store, "_new_receipt_restore_invocation", capture)
    editor_store.mutate_semantic(
        project.project_id, "store-one-shot-v2", base_revision=1, intent="UNDO",
        commands=edit["inverse_commands"], source_receipt=edit, owner_id="owner")
    restored = editor_store.read_graph(
        project.project_id, "store-one-shot-v2", owner_id="owner")
    assert restored.document == imported
    with pytest.raises(EditorRefusal) as reused:
        captured[0].invoke()
    assert reused.value.code == "RECEIPT_CAPABILITY_INVALID"
    assert editor_store.read_graph(
        project.project_id, "store-one-shot-v2", owner_id="owner") == restored


def test_semantic_undo_requires_the_exact_sealed_receipt(client):
    project = _project(client)
    _create(client, project)
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
    edit = client.post(path + "/semantic-batches",
                       json=_batch(base=0, commands=[_logic_node()])).json()
    unsealed = dict(edit)
    unsealed.pop("receipt_address")
    refused = client.post(path + "/semantic-batches", json=_batch(
        base=1, intent="UNDO", commands=edit["inverse_commands"], source=unsealed))
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "RECEIPT_ADDRESS_INVALID"
    assert client.get(path).json()["semantic_revision"] == 1


def test_semantic_receipt_rejects_resealed_foreign_project_registry_and_open_shape(client):
    from app.editor.v2_mutations import seal_receipt

    project = _project(client)
    _create(client, project)
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
    edit = client.post(path + "/semantic-batches",
                       json=_batch(base=0, commands=[_logic_node()])).json()
    for change in (
        {"project_id": "project.foreign"},
        {"registry_snapshot_address": "sha256:" + "f" * 64},
        {"unexpected": True},
    ):
        body = {key: value for key, value in edit.items() if key != "receipt_address"}
        body.update(change)
        forged = seal_receipt(body)
        refused = client.post(path + "/semantic-batches", json=_batch(
            base=1, intent="UNDO", commands=edit["inverse_commands"], source=forged))
        assert refused.status_code == 422
        assert refused.json()["detail"]["code"] in {
            "RECEIPT_ADDRESS_INVALID", "RECEIPT_LINEAGE_INVALID", "RECEIPT_SEAL_INVALID"}
        assert client.get(path).json()["semantic_revision"] == 1


def test_semantic_receipt_cannot_cross_owner_same_identifier_lineage():
    from app.db.models import Organization
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import create_graph, mutate_semantic, read_graph
    from app.editor.v2_mutations import EditorRefusal

    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="owner-b", name="Owner B"))
    project_a = create_project("A", owner_id="owner")
    project_b = create_project("B", owner_id="owner-b")
    for project, owner in ((project_a, "owner"), (project_b, "owner-b")):
        create_graph(project.project_id, "same-v2", "Same", "", owner_id=owner)
    receipt_a = mutate_semantic(
        project_a.project_id, "same-v2", base_revision=0, intent="EDIT",
        commands=[_logic_node()], source_receipt=None, owner_id="owner")
    mutate_semantic(
        project_b.project_id, "same-v2", base_revision=0, intent="EDIT",
        commands=[_logic_node()], source_receipt=None, owner_id="owner-b")
    try:
        mutate_semantic(
            project_b.project_id, "same-v2", base_revision=1, intent="UNDO",
            commands=receipt_a["inverse_commands"], source_receipt=receipt_a,
            owner_id="owner-b")
    except EditorRefusal as exc:
        assert exc.code == "RECEIPT_LINEAGE_INVALID"
    else:
        raise AssertionError("foreign-owner semantic receipt crossed lineages")
    assert read_graph(project_b.project_id, "same-v2", owner_id="owner-b").semantic_revision == 1


@pytest.mark.parametrize("secret", ["", "s" * 31])
def test_semantic_receipt_secret_absent_or_short_refuses_before_store_write(monkeypatch, secret):
    from app.core.config import get_settings
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import create_graph, mutate_semantic, read_graph
    from app.editor.v2_mutations import EditorRefusal

    init_db(reset=True)
    project = create_project("Seal unavailable", owner_id="owner")
    create_graph(project.project_id, "seal-unavailable-v2", "Seal", "", owner_id="owner")
    monkeypatch.setattr(get_settings(), "event_cursor_secret", secret)
    with pytest.raises(EditorRefusal) as refused:
        mutate_semantic(
            project.project_id, "seal-unavailable-v2", base_revision=0, intent="EDIT",
            commands=[_logic_node()], source_receipt=None, owner_id="owner")
    assert refused.value.code == "RECEIPT_SEAL_UNAVAILABLE"
    assert read_graph(
        project.project_id, "seal-unavailable-v2", owner_id="owner"
    ).semantic_revision == 0


def test_final_target_address_guard_refuses_mutated_candidate_without_write(monkeypatch):
    from dataclasses import replace

    import app.editor.v2_editor_store as editor_store
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import create_graph, mutate_semantic, read_graph
    from app.editor.v2_mutations import EditorRefusal

    init_db(reset=True)
    project = create_project("Target equality", owner_id="owner")
    create_graph(project.project_id, "target-equality-v2", "Target", "", owner_id="owner")
    edit = mutate_semantic(
        project.project_id, "target-equality-v2", base_revision=0, intent="EDIT",
        commands=[_logic_node()], source_receipt=None, owner_id="owner")
    before = read_graph(project.project_id, "target-equality-v2", owner_id="owner")
    real_apply = editor_store.apply_semantic_commands

    def divergent(*args, **kwargs):
        result = real_apply(*args, **kwargs)
        return replace(result, content_address="sha256:" + "f" * 64)

    monkeypatch.setattr(editor_store, "apply_semantic_commands", divergent)
    with pytest.raises(EditorRefusal) as refused:
        mutate_semantic(
            project.project_id, "target-equality-v2", base_revision=1, intent="UNDO",
            commands=edit["inverse_commands"], source_receipt=edit, owner_id="owner")
    assert refused.value.code == "REPLAY_DIVERGED"
    after = read_graph(project.project_id, "target-equality-v2", owner_id="owner")
    assert after == before


def test_semantic_dry_receipt_replays_after_cold_client_reload_without_writes(client):
    import json
    import os
    import secrets
    import subprocess
    import sys

    project = _project(client)
    _create(client, project)
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
    dry = client.post(path + "/validate", json=_batch(base=0, commands=[_logic_node()]))
    assert dry.status_code == 200
    receipt = dry.json()
    script = r'''import json,sys
from app.editor.v2_editor_store import mutate_semantic,read_graph
receipt=json.loads(sys.argv[3])
result=mutate_semantic(sys.argv[1],"editor-v2",base_revision=0,intent="REPLAY",
 commands=receipt["forward_commands"],source_receipt=receipt,owner_id="owner",dry_run=True,
 use_check={"purpose":"AUTHORING","capability_receipt_address":None})
print(json.dumps({"state":result["commit_state"],"revision":read_graph(sys.argv[1],"editor-v2",owner_id="owner").semantic_revision}))'''
    cold = subprocess.run(
        [sys.executable, "-c", script, project, "editor-v2", json.dumps(receipt)],
        check=True, capture_output=True, text=True)
    assert json.loads(cold.stdout.strip()) == {
        "state": "DRY_RUN_ROLLED_BACK", "revision": 0}
    foreign_script = r'''import json,sys
from app.editor.v2_editor_store import mutate_semantic,read_graph
from app.editor.v2_mutations import EditorRefusal
receipt=json.loads(sys.argv[2])
try:
 mutate_semantic(sys.argv[1],"editor-v2",base_revision=0,intent="REPLAY",
  commands=receipt["forward_commands"],source_receipt=receipt,owner_id="owner",dry_run=True,
  use_check={"purpose":"AUTHORING","capability_receipt_address":None})
except EditorRefusal as exc:
 print(json.dumps({"code":exc.code,"revision":read_graph(sys.argv[1],"editor-v2",owner_id="owner").semantic_revision}))
else:
 raise SystemExit("foreign receipt secret was accepted")'''
    foreign_env = dict(os.environ)
    foreign_env["PT_EVENT_CURSOR_SECRET"] = secrets.token_urlsafe(32)
    foreign = subprocess.run(
        [sys.executable, "-c", foreign_script, project, json.dumps(receipt)],
        check=True, capture_output=True, text=True, env=foreign_env)
    assert json.loads(foreign.stdout.strip()) == {
        "code": "RECEIPT_SEAL_INVALID", "revision": 0}


def test_same_secret_cold_store_restores_imported_edge_identity_exactly():
    import json
    import subprocess
    import sys

    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import REGISTRY, create_graph, mutate_semantic, read_graph
    from app.editor.v2_mutations import apply_semantic_commands
    from app.ir.formats.v2 import content_address_for, graph_address_for
    from app.ir.hashing import canonical_json

    init_db(reset=True)
    project = create_project("Cold imported edge", owner_id="owner")
    create_graph(project.project_id, "cold-imported-v2", "Cold", "", owner_id="owner")
    base = read_graph(project.project_id, "cold-imported-v2", owner_id="owner").document
    imported = apply_semantic_commands(base, [
        _logic_node() | {"node_id": "left"},
        _logic_node() | {"node_id": "right"},
        {"command": "connect", "source": {"node_id": "left", "port_id": "value"},
         "target": {"node_id": "right", "port_id": "input"},
         "binding": {"kind": "single"}},
    ], registry=REGISTRY).document
    imported["edges"][0]["edge_id"] = "caller.cold.edge.identity"
    expected_content = content_address_for(imported, REGISTRY)
    expected_graph = graph_address_for(imported, REGISTRY)
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "cold-imported-v2"))
        row.draft_json = canonical_json(imported)
    edit = mutate_semantic(
        project.project_id, "cold-imported-v2", base_revision=0, intent="EDIT",
        commands=[{"command": "remove_node", "node_id": "right"}],
        source_receipt=None, owner_id="owner")
    script = r'''import json,sys
from app.editor.v2_editor_store import mutate_semantic,read_graph
receipt=json.loads(sys.argv[2])
mutate_semantic(sys.argv[1],"cold-imported-v2",base_revision=1,intent="UNDO",
 commands=receipt["inverse_commands"],source_receipt=receipt,owner_id="owner")
state=read_graph(sys.argv[1],"cold-imported-v2",owner_id="owner")
print(json.dumps({"revision":state.semantic_revision,"edge_ids":[edge["edge_id"] for edge in state.document["edges"]],"content":state.content_address,"graph":state.graph_address}))'''
    cold = subprocess.run(
        [sys.executable, "-c", script, project.project_id, json.dumps(edit)],
        check=True, capture_output=True, text=True)
    assert json.loads(cold.stdout.strip()) == {
        "revision": 2, "edge_ids": ["caller.cold.edge.identity"],
        "content": expected_content, "graph": expected_graph,
    }
    assert read_graph(
        project.project_id, "cold-imported-v2", owner_id="owner"
    ).document == imported


def test_request_owner_and_raw_document_fields_are_closed(client):
    project = _project(client)
    _create(client, project)
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2/semantic-batches"
    body = _batch(base=0, commands=[_logic_node()])
    body["owner_id"] = "attacker"
    body["document"] = {"format_version": 2}
    refused = client.post(path, json=body)
    assert refused.status_code == 422
    with SessionLocal() as session:
        assert session.get(GraphArtifact, ("owner", "editor-v2")).draft_revision == 0


def test_server_owned_use_check_controls_research_and_paper_without_granting_authority(
        client, monkeypatch):
    import datetime as dt
    import app.editor.v2_editor_store as editor_store
    from tests.test_phase4_dataset_assessment_authority import T0

    monkeypatch.setattr(editor_store, "_capability_check_time", lambda: T0 + dt.timedelta(hours=3))
    project = _project(client)
    _create(client, project)
    path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
    assert client.post(path + "/semantic-batches",
                       json=_batch(base=0, commands=[_logic_node()])).status_code == 200
    document = client.get(path).json()["document"]
    capabilities = _persist_use_check_capabilities(document)
    commands = [
        {"command": "remove_node", "node_id": "logic"},
        _logic_node(),
    ]
    for purpose, mode in (("RESEARCH", "RESEARCH"), ("PAPER", "PAPER")):
        body = _batch(base=1, commands=commands)
        body["use_check"] = {
            "purpose": purpose, "capability_receipt_address": capabilities[mode]}
        response = client.post(path + "/validate", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["commit_state"] == "DRY_RUN_ROLLED_BACK"
        assert response.json()["nonauthority"] == {
            "research_admission": False, "deployment_authority": False,
            "execution_authority": False, "provider_capability": False,
            "money_authority": False,
        }
    wrong = _batch(base=1, commands=commands)
    wrong["use_check"] = {
        "purpose": "RESEARCH", "capability_receipt_address": capabilities["PAPER"]}
    refused = client.post(path + "/validate", json=wrong)
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "CAPABILITY_UNPROVEN"
    absent = _batch(base=1, commands=commands)
    absent["use_check"] = {
        "purpose": "RESEARCH", "capability_receipt_address": "sha256:" + "f" * 64}
    missing = client.post(path + "/validate", json=absent)
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "CAPABILITY_UNPROVEN"
    commit = client.post(path + "/semantic-batches", json={**wrong, "base_revision": 1})
    assert commit.status_code == 422
    assert commit.json()["detail"]["code"] == "REQUEST_SCHEMA_INVALID"
    assert client.get(path).json()["semantic_revision"] == 1


def test_server_owned_monitoring_control_and_mode_ineligible_refusal(client, monkeypatch):
    import datetime as dt
    import app.editor.v2_editor_store as editor_store
    from tests.test_phase4_dataset_assessment_authority import T0
    from app.editor.v2_editor_store import REGISTRY
    from app.ir.formats.v2 import canonical_document
    from app.ir.hashing import canonical_json

    monkeypatch.setattr(editor_store, "_capability_check_time", lambda: T0 + dt.timedelta(hours=3))

    project = _project(client)
    _create(client, project, identifier="monitoring-v2")
    document = dict(canonical_document(_monitoring_document(), REGISTRY))
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "monitoring-v2"))
        row.draft_json = canonical_json(document)
    capabilities = _persist_use_check_capabilities(document)
    path = f"/api/ir/projects/{project}/graphs/monitoring-v2/v2"
    commands = [
        {"command": "add_node", "node_id": "temporary", "component_id": "intent.sell",
         "component_version": 2, "parameters": {}},
        {"command": "remove_node", "node_id": "temporary"},
    ]
    monitoring = _batch(base=0, commands=commands)
    monitoring["use_check"] = {
        "purpose": "MONITORING", "capability_receipt_address": capabilities["RESEARCH"]}
    accepted = client.post(path + "/validate", json=monitoring)
    assert accepted.status_code == 200, accepted.text
    paper = _batch(base=0, commands=commands)
    paper["use_check"] = {
        "purpose": "PAPER", "capability_receipt_address": capabilities["PAPER"]}
    refused = client.post(path + "/validate", json=paper)
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "MODE_INELIGIBLE"


def test_dynamic_data_requirement_refusal_and_static_control(client):
    from app.editor.v2_editor_store import REGISTRY
    from app.ir.formats.v2 import canonical_document
    from app.ir.hashing import canonical_json

    project = _project(client)
    _create(client, project, identifier="dynamic-data-v2")
    document = dict(canonical_document(_dynamic_data_document(), REGISTRY))
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", "dynamic-data-v2"))
        row.draft_json = canonical_json(document)
    path = f"/api/ir/projects/{project}/graphs/dynamic-data-v2/v2"
    commands = [
        _logic_node() | {"node_id": "temporary"},
        {"command": "remove_node", "node_id": "temporary"},
    ]
    body = _batch(base=0, commands=commands)
    body["use_check"] = {
        "purpose": "RESEARCH", "capability_receipt_address": "sha256:" + "a" * 64}
    refused = client.post(path + "/validate", json=body)
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "DATA_REQUIREMENT_REFUSED"


@pytest.mark.parametrize("edge_count,expected_status", [(31, 200), (32, 422)])
def test_http_and_store_enforce_durable_inverse_limit_atomically(
        client, monkeypatch, edge_count, expected_status):
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for
    from app.ir.hashing import canonical_json, content_address
    import app.editor.v2_editor_store as editor_store
    import app.editor.v2_mutations as mutations
    from tests.test_ir_v2_editor_mutations import _resource_registry

    registry = _resource_registry()
    allowed = frozenset({("resource.source", 2), ("resource.target", 2)})
    project = _project(client)
    identifier = f"inverse-{edge_count}"
    _create(client, project, identifier=identifier)
    registry.registry_snapshot_payload = {"schema": "resource-test-registry/1"}
    registry.registry_snapshot_address = content_address(registry.registry_snapshot_payload)
    monkeypatch.setattr(editor_store, "REGISTRY", registry)
    monkeypatch.setattr(mutations, "_catalogue_identities", lambda: allowed)
    path = f"/api/ir/projects/{project}/graphs/{identifier}/v2"
    nodes = client.post(path + "/semantic-batches", json=_batch(base=0, commands=[
        {"command": "add_node", "node_id": "source", "component_id": "resource.source",
         "component_version": 2, "parameters": {}},
        {"command": "add_node", "node_id": "target", "component_id": "resource.target",
         "component_version": 2, "parameters": {}},
    ]))
    assert nodes.status_code == 200, nodes.text
    edges = [{
        "command": "connect",
        "source": {"node_id": "source", "port_id": "out"},
        "target": {"node_id": "target", "port_id": "members"},
        "binding": {"kind": "keyed", "key": f"member-{index}"},
    } for index in range(edge_count)]
    connected = client.post(path + "/semantic-batches", json=_batch(base=1, commands=edges))
    assert connected.status_code == 200, connected.text
    imported = client.get(path).json()["document"]
    for index, edge in enumerate(imported["edges"]):
        edge["edge_id"] = f"caller-imported-{index}"
    imported = dict(canonical_document(imported, registry))
    before_content = content_address_for(imported, registry)
    before_graph = graph_address_for(imported, registry)
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", identifier))
        row.draft_json = canonical_json(imported)
    removed = client.post(path + "/semantic-batches", json=_batch(
        base=2, commands=[{"command": "remove_node", "node_id": "target"}]))
    assert removed.status_code == expected_status, removed.text
    if edge_count == 32:
        assert removed.json()["detail"]["code"] == "EDITOR_RESOURCE_LIMIT"
        assert client.get(path).json()["semantic_revision"] == 2
    else:
        assert len(removed.json()["inverse_commands"]) == 32
        assert client.get(path).json()["semantic_revision"] == 3
        undo = client.post(path + "/semantic-batches", json=_batch(
            base=3, intent="UNDO", commands=removed.json()["inverse_commands"],
            source=removed.json()))
        assert undo.status_code == 200, undo.text
        restored = client.get(path).json()
        assert restored["document"] == imported
        assert restored["content_address"] == before_content
        assert restored["graph_address"] == before_graph


@pytest.mark.parametrize("node_count,edge_count", [(300, 600), (2000, 10000)])
def test_fixed_editor_store_workloads_bound_receipt_and_rollback_all_database_bytes(
        monkeypatch, node_count, edge_count):
    import json
    import app.editor.v2_editor_store as editor_store
    import app.editor.v2_mutations as mutations
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.ir.formats.v2 import canonical_document
    from app.ir.hashing import canonical_json
    from tests.test_ir_v2_editor_mutations import _resource_document, _resource_registry

    init_db(reset=True)
    registry = _resource_registry()
    allowed = frozenset({("resource.source", 2), ("resource.target", 2)})
    monkeypatch.setattr(editor_store, "REGISTRY", registry)
    monkeypatch.setattr(mutations, "_catalogue_identities", lambda: allowed)
    project = create_project(f"Resource {node_count}", owner_id="owner")
    identifier = f"resource-{node_count}-{edge_count}"
    editor_store.create_graph(project.project_id, identifier, "Resource", "", owner_id="owner")
    document = _resource_document(node_count, edge_count)
    document["strategy_id"] = identifier
    document = dict(canonical_document(document, registry))
    with SessionLocal.begin() as session:
        row = session.get(GraphArtifact, ("owner", identifier))
        row.draft_json = canonical_json(document)
        row.display_name = "Resource"
    with SessionLocal() as session:
        row = session.get(GraphArtifact, ("owner", identifier))
        before = (row.draft_json, row.draft_revision, row.updated_at)
    receipt = editor_store.mutate_semantic(
        project.project_id, identifier, base_revision=0, intent="EDIT",
        commands=[
            {"command": "add_node", "node_id": "temporary",
             "component_id": "resource.source", "component_version": 2, "parameters": {}},
            {"command": "remove_node", "node_id": "temporary"},
        ], source_receipt=None, owner_id="owner", dry_run=True,
        use_check={"purpose": "AUTHORING", "capability_receipt_address": None})
    assert len(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()) < 1_048_576
    with SessionLocal() as session:
        row = session.get(GraphArtifact, ("owner", identifier))
        assert (row.draft_json, row.draft_revision, row.updated_at) == before


def test_publish_failure_after_immutable_insert_rolls_back_row_and_pointer():
    import sqlalchemy as sa
    from app.db.session import engine
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import create_graph, mutate_semantic, publish

    init_db(reset=True)
    project = create_project("Atomic publish", owner_id="owner")
    create_graph(project.project_id, "atomic-v2", "Atomic", "", owner_id="owner")
    mutate_semantic(
        project.project_id, "atomic-v2", base_revision=0, intent="EDIT",
        commands=[_logic_node()], source_receipt=None, owner_id="owner")

    def fail_pointer(_connection, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("UPDATE GRAPH_ARTIFACTS"):
            raise RuntimeError("injected pointer failure")

    sa.event.listen(engine, "before_cursor_execute", fail_pointer)
    try:
        with pytest.raises(RuntimeError, match="injected pointer failure"):
            publish(project.project_id, "atomic-v2", base_revision=1,
                    expected_current_version=None, owner_id="owner")
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail_pointer)
    with SessionLocal() as session:
        artifact = session.get(GraphArtifact, ("owner", "atomic-v2"))
        assert artifact.current_version is None
        assert artifact.published_revision is None
        assert session.get(IrV2GraphVersion, ("owner", "atomic-v2", 1)) is None


def test_original_presets_copy_edit_reload_and_owner_isolation(client):
    from app.db.models import Organization
    from app.editor.graph_artifacts import create_project, set_project_status
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from tests.test_strategy_registry import _synthetic

    project = _project(client)
    listing = client.get(f"/api/ir/projects/{project}/presets")
    assert listing.status_code == 200, listing.text
    assert {item["preset_id"] for item in listing.json()["presets"]} == {"trend_impulse_v3", "expanding_z_v4"}
    for preset in ("trend_impulse_v3", "expanding_z_v4"):
        identifier = "copy-" + preset
        url = f"/api/ir/projects/{project}/presets/{preset}/copy"
        copied = client.post(url, json={"identifier": identifier, "name": "My " + preset})
        assert copied.status_code == 201, copied.text
        assert copied.json()["current_version"] is None
        assert copied.json()["graph"]["nodes"][0]["parameters"]["ema_length"] == 50
        assert client.post(url, json={"identifier": identifier}).status_code == 409
        assert client.post(url, json={"identifier": "bad", "owner_id": "foreign"}).status_code == 422
        edit = client.post(f"/api/ir/projects/{project}/graphs/{identifier}/v2/semantic-batches", json=_batch(
            base=0, commands=[{"command": "set_parameter", "node_id": "rules",
                               "parameter_id": "ema_length", "value": 20}]))
        assert edit.status_code == 200, edit.text
        reloaded = client.get(f"/api/ir/projects/{project}/graphs/{identifier}/v2")
        assert reloaded.status_code == 200, reloaded.text
        assert reloaded.json()["document"]["nodes"][0]["parameters"]["ema_length"] == 20
        frame = _synthetic(80).set_index("date")
        inputs = {"frame": dict(frame.items())}
        saved = evaluate_v2(resolve_v2(reloaded.json()["document"], REGISTRY), inputs, REGISTRY)
        expected_document = instantiate_preset(preset, "expected")
        expected_document["nodes"][0]["parameters"]["ema_length"] = 20
        expected = evaluate_v2(resolve_v2(expected_document, REGISTRY), inputs, REGISTRY)
        assert {key: series.tolist() for key, series in saved.items()} == {
            key: series.tolist() for key, series in expected.items()}
        assert instantiate_preset(preset, "fresh")["nodes"][0]["parameters"]["ema_length"] == 50
    unknown = client.post(f"/api/ir/projects/{project}/presets/unknown/copy",
                          json={"identifier": "unknown-copy"})
    assert unknown.status_code == 404
    rejected = client.post(f"/api/ir/projects/{project}/presets/trend_impulse_v3/copy",
                           json={"identifier": "rejected-copy", "name": "Cafe\u0301"})
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "PRESET_COPY_REJECTED"
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="foreign", name="Foreign test owner"))
    foreign = create_project("Foreign preset project", owner_id="foreign")
    for project_id in (foreign.project_id, "missing-project"):
        assert client.get(f"/api/ir/projects/{project_id}/presets").status_code == 404
        assert client.post(f"/api/ir/projects/{project_id}/presets/trend_impulse_v3/copy",
                           json={"identifier": "foreign-copy"}).status_code == 404
    set_project_status(project, "archived", owner_id="owner")
    assert client.get(f"/api/ir/projects/{project}/presets").status_code == 404
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(StrategyAdmission)) == 0
        assert session.scalar(select(func.count()).select_from(IrV2GraphVersion)) == 0


def test_original_presets_durable_sessions_keep_copies_private(client, monkeypatch):
    from app.core.config import get_settings
    from app.editor.graph_artifacts import create_project
    from tests.test_user_sessions import _seed, _issue

    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "preset-test-dummy-token")
    a = _issue(user_id="user.a", organization_id="org.a")
    b = _issue(user_id="user.b", organization_id="org.b")
    headers_a = {"Authorization": "Bearer " + a.token}
    headers_b = {"Authorization": "Bearer " + b.token}
    assert client.get("/api/ir/presets").status_code == 401
    global_list = client.get("/api/ir/presets", headers=headers_a)
    assert global_list.status_code == 200, global_list.text
    assert {row["preset_id"] for row in global_list.json()["presets"]} == {
        "trend_impulse_v3", "expanding_z_v4"}
    assert client.get("/api/v1/ir/presets", headers=headers_b).status_code == 200
    project_a = create_project("Preset A", owner_id="org.a").project_id
    project_b = create_project("Preset B", owner_id="org.b").project_id
    path_a = f"/api/ir/projects/{project_a}/presets"
    assert client.get(path_a).status_code == 401
    assert client.get(path_a, headers=headers_a).status_code == 200
    assert client.get(path_a, headers=headers_b).status_code == 404
    assert client.post(path_a + "/trend_impulse_v3/copy", headers=headers_b,
                       json={"identifier": "same-preset"}).status_code == 404
    for project, headers in ((project_a, headers_a), (project_b, headers_b)):
        response = client.post(f"/api/ir/projects/{project}/presets/trend_impulse_v3/copy",
                               headers=headers, json={"identifier": "same-preset"})
        assert response.status_code == 201, response.text
        assert response.json()["graph"]["strategy_id"] == "same-preset"
    assert client.get(f"/api/ir/projects/{project_a}/graphs/same-preset/v2",
                      headers=headers_b).status_code == 404
    assert client.get(f"/api/v1/ir/projects/{project_a}/presets", headers=headers_a).status_code == 200
    with SessionLocal() as session:
        assert session.get(GraphArtifact, ("org.a", "same-preset")).project_id == project_a
        assert session.get(GraphArtifact, ("org.b", "same-preset")).project_id == project_b


def test_research_settings_revision_cas_inheritance_and_idempotency(tmp_path):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.db.models import Base, Organization, User, Project, GraphArtifact
    from research.domain.settings import ResearchSettingsRepository, PLATFORM_DEFAULTS, SettingsConflict

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'settings.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Organization(organization_id="settings-owner", name="Owner"))
        session.add(User(user_id="settings-user", email_normalized="settings@example.test", display_name="User"))
        session.commit()
        session.add(Project(owner_id="settings-owner", project_id="settings-project", name="Project"))
        session.commit()
        session.add(GraphArtifact(owner_id="settings-owner", project_id="settings-project",
            identifier="same-id", display_name="Graph", draft_json="{}"))
        session.commit()
        repository = ResearchSettingsRepository(session)
        original = repository.effective(owner_id="settings-owner", graph_identifier="same-id")
        assert original["workspace"]["revision"] == original["strategy"]["revision"] == 0
        request = dict(owner_id="settings-owner", created_by="settings-user", expected_revision=0,
                       request_id=str(uuid.uuid4()), values={**PLATFORM_DEFAULTS, "seed": 42})
        first = repository.update(**request)
        assert first["revision"] == 1
        assert repository.update(**request) == first
        with pytest.raises(SettingsConflict):
            repository.update(**{**request, "values": PLATFORM_DEFAULTS})
        with pytest.raises(SettingsConflict):
            repository.update(**{**request, "request_id": str(uuid.uuid4())})
        override = repository.update(owner_id="settings-owner", created_by="settings-user",
            graph_identifier="same-id", expected_revision=0, request_id=str(uuid.uuid4()),
            values={"seed": 42}, enabled=True)
        preview = repository.effective(owner_id="settings-owner", graph_identifier="same-id")
        assert preview["sources"]["seed"] == "strategy"  # Equal remains explicit.
        pinned = repository.snapshot(owner_id="settings-owner", graph_identifier="same-id",
            workspace_revision=1, strategy_revision=1, run_overrides={"n_folds": 3})
        assert pinned["sources"]["n_folds"] == "run" and pinned["values"]["n_folds"] == 3
        repository.update(**{**request, "expected_revision": 1, "request_id": str(uuid.uuid4()),
                             "values": {**PLATFORM_DEFAULTS, "seed": 43}})
        assert repository.update(**request) == first  # Replay returns its historical receipt.
        with pytest.raises(SettingsConflict, match="changed"):
            repository.snapshot(owner_id="settings-owner", graph_identifier="same-id",
                workspace_revision=1, strategy_revision=1, run_overrides={"n_folds": 3})
        assert repository.snapshot(owner_id="settings-owner", graph_identifier="same-id",
            workspace_revision=1, strategy_revision=1, run_overrides={"n_folds": 3}, require_current=False) == pinned
        repository.update(owner_id="settings-owner", created_by="settings-user", graph_identifier="same-id",
            expected_revision=override["revision"], request_id=str(uuid.uuid4()), values={"seed": 42}, enabled=False)
        preview = repository.effective(owner_id="settings-owner", graph_identifier="same-id")
        assert preview["values"]["seed"] == 43 and preview["sources"]["seed"] == "workspace"
        assert preview["strategy"]["values"] == {"seed": 42}
        assert original["values"]["seed"] == 0  # Prior snapshots remain unchanged.
        assert repository.read(owner_id="foreign")["revision"] == 0
        with pytest.raises(sa.exc.DatabaseError, match="immutable"):
            session.execute(sa.text("UPDATE workspace_research_settings_revisions SET revision=99"))
        session.rollback()
    engine.dispose()


@pytest.mark.parametrize("values", [{"unknown": 1}, {"seed": True}, {"seed": None},
    {"research_capital": float("nan")}, {"n_folds": 1}, {"risk_policy": "live"}])
def test_research_settings_refuses_unsupported_sparse_values(values):
    from pydantic import ValidationError
    from research.domain.settings import validate_values
    with pytest.raises((ValidationError, ValueError)):
        validate_values(values, sparse=True)


def test_research_settings_http_graph_override_clear_and_closed_fields(client):
    from research.domain.settings import PLATFORM_DEFAULTS
    project = _project(client)
    _create(client, project, "settings-graph")
    path = f"/api/ir/projects/{project}/graphs/settings-graph/research-settings"
    body = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "enabled": True,
            "values": {"seed": 7}}
    saved = client.put(path, json=body)
    assert saved.status_code == 200, saved.text
    preview = client.get(path).json()
    assert preview["values"]["seed"] == 7 and preview["sources"]["seed"] == "strategy"
    reset = {**body, "request_id": str(uuid.uuid4()), "expected_revision": 1, "values": {}}
    assert client.put(path, json=reset).status_code == 200
    assert client.get(path).json()["values"] == PLATFORM_DEFAULTS
    assert client.put(path, json=body).json() == saved.json()
    for changed in ({"cost": 1}, {"values": {"seed": None}}, {"enabled": "false"}):
        response = client.put(path, json={**reset, **changed})
        assert response.status_code == 422, response.text
    assert client.get(path.replace(project, "missing-project")).status_code == 404


def test_research_settings_concurrent_compare_and_swap_has_one_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.db.models import Base, Organization, User, WorkspaceResearchSettingsRevision
    from research.domain.settings import ResearchSettingsRepository, PLATFORM_DEFAULTS, SettingsConflict
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'settings-cas.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Organization(organization_id="cas-owner", name="Owner"))
        session.add(User(user_id="cas-user", email_normalized="cas-settings@example.test", display_name="User"))
        session.commit()
    barrier = threading.Barrier(2)
    def update(seed):
        with Session(engine) as session:
            barrier.wait(timeout=5)
            try:
                return ResearchSettingsRepository(session).update(owner_id="cas-owner", created_by="cas-user",
                    expected_revision=0, request_id=str(uuid.uuid4()), values={**PLATFORM_DEFAULTS, "seed": seed})["revision"]
            except SettingsConflict:
                return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, (1, 2)))
    assert sorted(map(str, results)) == ["1", "conflict"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(WorkspaceResearchSettingsRevision)) == 1
    engine.dispose()


def _publication_test_registry(unused=0):
    from app.ir.registry import PlatformRegistry
    components = {(f"leaf.unused{index}", 1): {
        "component_id": f"leaf.unused{index}", "component_version": 1,
        "domain_family": "transform", "structural_role": "transform", "ports": [], "parameters": {},
    } for index in range(unused)}
    return PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components=components)


@pytest.fixture
def registry_publication_store(tmp_path, monkeypatch):
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.db.models import Base, Organization, Project
    from app.editor import v2_editor_store as store
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'publication.db'}")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(engine, expire_on_commit=False)
    with Sessions.begin() as session:
        session.add(Organization(organization_id="publication-owner", name="Owner"))
        session.flush()
        session.add(Project(owner_id="publication-owner", project_id="publication-project", name="Project"))
    monkeypatch.setattr(store, "SessionLocal", Sessions)
    monkeypatch.setattr(store, "REGISTRY", _publication_test_registry())
    store.create_graph("publication-project", "publication-graph", "Graph", "", owner_id="publication-owner")
    yield store, Sessions
    engine.dispose()


def test_explicit_registry_republication_preserves_history_and_exact_later_retry(registry_publication_store, monkeypatch):
    from app.editor.v2_mutations import EditorRefusal
    store, Sessions = registry_publication_store
    arguments = dict(project_id="publication-project", identifier="publication-graph",
                     base_revision=0, owner_id="publication-owner")
    first = store.publish(**arguments, expected_current_version=None)
    with Sessions() as session:
        row = session.get(IrV2GraphVersion, ("publication-owner", "publication-graph", 1))
        original = (row.artifact_json, row.content_address, row.graph_address,
                    row.registry_snapshot_address, row.publication_receipt_json)
    registry_b = _publication_test_registry(1)
    monkeypatch.setattr(store, "REGISTRY", registry_b)
    with pytest.raises(EditorRefusal, match="no unpublished"):
        store.publish(**arguments, expected_current_version=1)
    with pytest.raises(EditorRefusal) as stale:
        store.publish(**arguments, expected_current_version=1,
                      target_registry_snapshot_address=first["registry_snapshot_address"])
    assert stale.value.code == "STRATEGY_LIBRARY_CHANGED"
    second = store.publish(**arguments, expected_current_version=1,
                           target_registry_snapshot_address=registry_b.registry_snapshot_address)
    assert second["graph_version"] == 2 and second["semantic_revision"] == 0
    assert second["graph_address"] == first["graph_address"]
    assert second["registry_snapshot_address"] != first["registry_snapshot_address"]
    assert second["predecessor"]["content_address"] == first["content_address"]
    registry_c = _publication_test_registry(2)
    monkeypatch.setattr(store, "REGISTRY", registry_c)
    with monkeypatch.context() as guard:
        guard.setattr(store, "_canonical_facts", lambda *_args, **_kwargs: pytest.fail("retry resolved a later registry"))
        assert store.publish(**arguments, expected_current_version=1,
            target_registry_snapshot_address=registry_b.registry_snapshot_address) == second
        assert store.publish(**arguments, expected_current_version=None) == first
    third = store.publish(**arguments, expected_current_version=2,
                          target_registry_snapshot_address=registry_c.registry_snapshot_address)
    assert third["graph_version"] == 3
    assert store.publish(**arguments, expected_current_version=1,
        target_registry_snapshot_address=registry_b.registry_snapshot_address) == second
    assert store.read_version("publication-project", "publication-graph", 1,
                              owner_id="publication-owner")["registry_snapshot_address"] == first["registry_snapshot_address"]
    with Sessions() as session:
        row = session.get(IrV2GraphVersion, ("publication-owner", "publication-graph", 1))
        assert (row.artifact_json, row.content_address, row.graph_address,
                row.registry_snapshot_address, row.publication_receipt_json) == original


def test_registry_target_race_rolls_back_publication(registry_publication_store, monkeypatch):
    from app.editor.v2_mutations import EditorRefusal
    store, Sessions = registry_publication_store
    target = store.REGISTRY.registry_snapshot_address
    original = store._publication_row
    def change_after_insert(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(store, "REGISTRY", _publication_test_registry(1))
        return result
    monkeypatch.setattr(store, "_publication_row", change_after_insert)
    with pytest.raises(EditorRefusal) as refused:
        store.publish("publication-project", "publication-graph", base_revision=0,
            expected_current_version=None, target_registry_snapshot_address=target, owner_id="publication-owner")
    assert refused.value.code == "STRATEGY_LIBRARY_CHANGED"
    with Sessions() as session:
        assert session.scalar(select(func.count()).select_from(IrV2GraphVersion)) == 0
        assert session.get(GraphArtifact, ("publication-owner", "publication-graph")).current_version is None


def test_stored_publication_receipt_refuses_corruption_without_row_rewrite(registry_publication_store):
    import json
    from app.editor.v2_mutations import EditorRefusal, seal_receipt
    from app.ir.hashing import canonical_json
    store, Sessions = registry_publication_store
    receipt = store.publish("publication-project", "publication-graph", base_revision=0,
                            expected_current_version=None, owner_id="publication-owner")
    mutations = ["{", " " + canonical_json(receipt),
                 canonical_json({**receipt, "receipt_address": "sha256:" + "0" * 64}),
                 canonical_json(seal_receipt({**receipt, "unexpected": True})),
                 canonical_json({**receipt, "graph_version": 99}),
                 canonical_json(seal_receipt({**receipt, "graph_version": 99})),
                 canonical_json(seal_receipt({**receipt, "semantic_revision": False})),
                 "x" * (store.MAX_RECEIPT_BYTES + 1)]
    with Sessions() as session:
        for raw in mutations:
            row = session.get(IrV2GraphVersion, ("publication-owner", "publication-graph", 1))
            with session.no_autoflush:
                row.publication_receipt_json = raw
                with pytest.raises(EditorRefusal, match="stored publication receipt is invalid"):
                    store._stored_publication_receipt(session, row)
            session.rollback()
        row = session.get(IrV2GraphVersion, ("publication-owner", "publication-graph", 1))
        assert json.loads(row.publication_receipt_json) == receipt


def test_publish_http_accepts_explicit_current_library_target(client):
    from app.editor import v2_editor_store as store
    project = _project(client)
    _create(client, project, "explicit-library")
    response = client.post(f"/api/ir/projects/{project}/graphs/explicit-library/v2/publish", json={
        "format_version": 2, "base_revision": 0, "expected_current_version": None,
        "target_registry_snapshot_address": store.REGISTRY.registry_snapshot_address,
    })
    assert response.status_code == 200, response.text
    assert response.json()["schema"] == "strategy-os-v2-publish-receipt/1"


def test_changed_library_refuses_both_fresh_preparation_paths_before_queue(registry_publication_store, monkeypatch):
    from app.api.principal import Principal
    import app.api.ir_experiment_routes as routes
    import app.ir.library as library
    from research.orchestrator.v2_preparation import _saved_version, require_current_strategy_library
    from research.orchestrator.v2_operation import V2OperationRefusal
    store, Sessions = registry_publication_store
    first = store.publish("publication-project", "publication-graph", base_revision=0,
                          expected_current_version=None, owner_id="publication-owner")
    registry_b = _publication_test_registry(1)
    monkeypatch.setattr(library, "REGISTRY", registry_b)
    monkeypatch.setattr(store, "REGISTRY", registry_b)
    monkeypatch.setattr(routes, "SessionLocal", Sessions)
    monkeypatch.setattr(routes, "_existing_preparation", lambda *_args: None)
    monkeypatch.setattr(routes, "_enqueue_preparation", lambda *_args: pytest.fail("library refusal reached queue"))
    saved = store.read_version("publication-project", "publication-graph", 1, owner_id="publication-owner")
    principal = Principal(id="author", kind="user", scopes=frozenset({"*"}),
                          organization_id="publication-owner", role="owner")
    common = {"request_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
              "dataset_manifest_address": "sha256:" + "0" * 64,
              "dataset_as_of": "2026-09-05T00:00:00+00:00", "hypothesis": "Library preflight"}
    direct = routes.V2GraphResearchPreparationRequest(**common, research_capital=100000.0,
        seed=0, min_trades=1, n_folds=2, min_positive_fold_frac=0.0)
    settings = routes.V2SettingsResearchPreparationRequest(**common,
        expected_workspace_revision=0, expected_strategy_revision=0)
    for handler, body in ((routes.post_v2_graph_research_preparation, direct),
                          (routes.post_v2_settings_research_preparation, settings)):
        with pytest.raises(routes.GraphExperimentFailure) as failure:
            handler("publication-project", "publication-graph", 1, body, principal)
        assert failure.value.status_code == 409 and failure.value.code == "STRATEGY_LIBRARY_CHANGED"
    with pytest.raises(V2OperationRefusal) as queued:
        _saved_version({"owner_id": "publication-owner", "project_id": "publication-project",
            "graph_identifier": "publication-graph", "graph_version": 1,
            **{key: saved[key] for key in ("content_address", "graph_address", "registry_snapshot_address")}})
    assert queued.value.code == "STRATEGY_LIBRARY_CHANGED"
    refreshed = store.publish("publication-project", "publication-graph", base_revision=0,
        expected_current_version=1, target_registry_snapshot_address=registry_b.registry_snapshot_address,
        owner_id="publication-owner")
    require_current_strategy_library(refreshed)
    assert saved["registry_snapshot_address"] == first["registry_snapshot_address"]


def test_historical_null_publication_receipt_is_not_backfilled(registry_publication_store, monkeypatch):
    import json
    from app.editor.v2_mutations import EditorRefusal
    from app.ir.hashing import canonical_json
    store, Sessions = registry_publication_store
    with Sessions() as session:
        artifact = session.get(GraphArtifact, ("publication-owner", "publication-graph"))
        canonical, content, graph, _ = store._canonical_facts(json.loads(artifact.draft_json))
        session.add(IrV2GraphVersion(owner_id=artifact.owner_id, graph_identifier=artifact.identifier,
            graph_version=1, artifact_json=canonical_json(canonical), format_version=2,
            content_address=content, graph_address=graph, registry_snapshot_address=store.REGISTRY.registry_snapshot_address))
        next_draft = {**canonical, "strategy_version": 2}
        artifact.draft_json = canonical_json(next_draft)
        artifact.current_version = 1
        artifact.published_revision = 0
        session.commit()
    first = store.publish("publication-project", "publication-graph", base_revision=0,
                          expected_current_version=None, owner_id="publication-owner")
    assert first["graph_version"] == 1
    with Sessions() as session:
        assert session.get(IrV2GraphVersion, ("publication-owner", "publication-graph", 1)).publication_receipt_json is None
    monkeypatch.setattr(store, "REGISTRY", _publication_test_registry(1))
    with pytest.raises(EditorRefusal) as failure:
        store.publish("publication-project", "publication-graph", base_revision=0,
                      expected_current_version=None, owner_id="publication-owner")
    assert failure.value.code == "STRATEGY_LIBRARY_CHANGED"
    assert store.read_version("publication-project", "publication-graph", 1,
        owner_id="publication-owner")["registry_snapshot_address"] == first["registry_snapshot_address"]


def test_publication_receipt_retry_is_owner_scoped(registry_publication_store):
    store, _ = registry_publication_store
    store.publish("publication-project", "publication-graph", base_revision=0,
                  expected_current_version=None, owner_id="publication-owner")
    for owner, graph in (("foreign", "publication-graph"), ("publication-owner", "missing")):
        with pytest.raises(store.EditorNotFound):
            store.publish("publication-project", graph, base_revision=0, expected_current_version=None,
                target_registry_snapshot_address=store.REGISTRY.registry_snapshot_address, owner_id=owner)


def test_concurrent_registry_republication_creates_one_version(registry_publication_store, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from app.editor.v2_mutations import EditorRefusal
    store, Sessions = registry_publication_store
    store.publish("publication-project", "publication-graph", base_revision=0,
                  expected_current_version=None, owner_id="publication-owner")
    registry = _publication_test_registry(1)
    monkeypatch.setattr(store, "REGISTRY", registry)
    barrier = threading.Barrier(2)
    def publish():
        barrier.wait(timeout=5)
        try:
            return store.publish("publication-project", "publication-graph", base_revision=0,
                expected_current_version=1, target_registry_snapshot_address=registry.registry_snapshot_address,
                owner_id="publication-owner")
        except EditorRefusal as exc:
            assert exc.code in {"IMMUTABLE_VERSION_CONFLICT", "SEMANTIC_REVISION_CONFLICT"}
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    receipts = [item for item in results if item is not None]
    assert receipts and all(item == receipts[0] for item in receipts)
    with Sessions() as session:
        assert session.scalar(select(func.count()).select_from(IrV2GraphVersion)) == 2
        assert session.get(GraphArtifact, ("publication-owner", "publication-graph")).current_version == 2



def test_publication_semantic_cas_loss_rolls_back_insert(registry_publication_store, monkeypatch):
    from sqlalchemy import update
    from app.editor.v2_mutations import EditorRefusal
    store, Sessions = registry_publication_store
    original = store._publication_row
    def change_after_insert(session, artifact, *args, **kwargs):
        result = original(session, artifact, *args, **kwargs)
        session.execute(update(GraphArtifact).where(GraphArtifact.owner_id == artifact.owner_id,
            GraphArtifact.identifier == artifact.identifier).values(draft_revision=artifact.draft_revision + 1))
        return result
    monkeypatch.setattr(store, "_publication_row", change_after_insert)
    with pytest.raises(EditorRefusal) as failure:
        store.publish("publication-project", "publication-graph", base_revision=0,
                      expected_current_version=None, owner_id="publication-owner")
    assert failure.value.code == "SEMANTIC_REVISION_CONFLICT"
    with Sessions() as session:
        assert session.scalar(select(func.count()).select_from(IrV2GraphVersion)) == 0
        artifact = session.get(GraphArtifact, ("publication-owner", "publication-graph"))
        assert artifact.current_version is None and artifact.draft_revision == 0


def test_research_settings_v2_bands_preserve_legacy_snapshot_bytes():
    from research.domain.settings import (
        LEGACY_DEFAULTS, V2_DEFAULTS, _document, _view, resolve_snapshot, validate_snapshot,
    )
    workspace = _view(_document("owner", None, 0, 0, None, LEGACY_DEFAULTS, True,
                                schema="research-settings-revision/1"))
    strategy = _view(_document("owner", "graph", 0, 0, None, {}, True,
                               schema="research-settings-revision/1"))
    old = resolve_snapshot(owner_id="owner", graph_identifier="graph", workspace=workspace,
                           strategy=strategy, run_overrides={})
    assert old["schema"] == "research-settings-snapshot/1"
    assert old["values"] == LEGACY_DEFAULTS
    assert validate_snapshot(old, owner_id="owner", graph_identifier="graph") == old
    current = _view(_document("owner", None, 1, 0, str(uuid.uuid4()),
                              {**V2_DEFAULTS, "stop_loss_pct": .01, "take_profit_pct": .02}, True,
                              schema="research-settings-revision/2"))
    new = resolve_snapshot(owner_id="owner", graph_identifier="graph", workspace=current,
                           strategy=strategy, run_overrides={"take_profit_pct": .03})
    assert new["schema"] == "research-settings-snapshot/2"
    assert new["values"]["stop_loss_pct"] == .01
    assert new["values"]["take_profit_pct"] == .03
    assert new["sources"]["stop_loss_pct"] == "workspace"
    assert new["sources"]["take_profit_pct"] == "run"
    assert validate_snapshot(old, owner_id="owner", graph_identifier="graph") == old


@pytest.mark.parametrize("value", [None, True, -0.01, 1.0, float("nan"), float("inf")])
@pytest.mark.parametrize("key", ["stop_loss_pct", "take_profit_pct"])
def test_research_settings_v2_refuses_invalid_percentage(key, value):
    from research.domain.settings import validate_values
    with pytest.raises(ValueError):
        validate_values({key: value}, sparse=True)


def test_research_settings_persisted_legacy_retry_keeps_original_receipt(tmp_path):
    import datetime as dt
    import json
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.db.models import Base, Organization, User, WorkspaceResearchSettingsRevision
    from research.domain.settings import (
        LEGACY_DEFAULTS, PLATFORM_DEFAULTS, ResearchSettingsRepository, SettingsConflict, _document, _view,
    )
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy-settings.db'}")
    Base.metadata.create_all(engine)
    request_id = str(uuid.uuid4())
    document = _document("old-owner", None, 1, 0, request_id, LEGACY_DEFAULTS, True,
                         schema="research-settings-revision/1")
    receipt = _view(document)
    with Session(engine) as session:
        session.add(Organization(organization_id="old-owner", name="Owner"))
        session.add(User(user_id="old-user", email_normalized="old@example.test", display_name="User"))
        session.commit()
        session.add(WorkspaceResearchSettingsRevision(owner_id="old-owner", revision=1,
            request_id=request_id, created_by="old-user", created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
            document_json=json.dumps(document), content_address=receipt["content_address"]))
        session.commit()
        repository = ResearchSettingsRepository(session)
        request = dict(owner_id="old-owner", created_by="old-user", expected_revision=0,
                       request_id=request_id, values=LEGACY_DEFAULTS)
        assert repository.read(owner_id="old-owner") == receipt
        assert repository.update(**request) == receipt
        with pytest.raises(SettingsConflict):
            repository.update(**{**request, "values": {**LEGACY_DEFAULTS, "take_profit_pct": .02}})
        current = repository.update(**{**request, "expected_revision": 1,
            "request_id": str(uuid.uuid4()), "values": {**PLATFORM_DEFAULTS, "take_profit_pct": .02}})
        assert current["schema"] == "research-settings-revision/3"
        assert repository.update(**request) == receipt
        assert repository.read_revision(owner_id="old-owner", revision=1) == receipt
    engine.dispose()


@pytest.mark.parametrize("fault", ["fields", "schema", "revision", "request", "owner", "zero_values", "hash"])
def test_research_settings_pinned_revision_refuses_tampering(fault):
    from research.domain.settings import PLATFORM_DEFAULTS, _document, _view, _validate_revision_view
    document = _view(_document("owner", None, 0, 0, None, PLATFORM_DEFAULTS, True))
    if fault == "fields": document["unexpected"] = True
    elif fault == "schema": document["schema"] = "research-settings-revision/9"
    elif fault == "revision": document["revision"] = True
    elif fault == "request": document.update(revision=1, request_id="not-a-request")
    elif fault == "owner": document["owner_id"] = "other"
    elif fault == "zero_values": document["values"] = {**PLATFORM_DEFAULTS, "seed": 7}
    else: document["content_address"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        _validate_revision_view(document, "owner", None)


@pytest.mark.parametrize("schema", ["research-settings-snapshot/1", "research-settings-snapshot/9"])
def test_research_settings_v2_refuses_downgraded_snapshot(schema):
    from research.domain.settings import PLATFORM_DEFAULTS, _document, _view, resolve_snapshot
    with pytest.raises(ValueError):
        resolve_snapshot(owner_id="owner", graph_identifier="graph",
            workspace=_view(_document("owner", None, 0, 0, None, PLATFORM_DEFAULTS, True)),
            strategy=_view(_document("owner", "graph", 0, 0, None, {}, True)),
            run_overrides={}, schema=schema)


@pytest.mark.parametrize("rehash", [False, True])
@pytest.mark.parametrize("field,value", [("expected_revision", False), ("research_capital", 100000)])
def test_research_settings_canonical_revision_rejects_python_numeric_aliases(field, value, rehash):
    from research.domain.settings import PLATFORM_DEFAULTS, _document, _view, _validate_revision_view
    from app.ir.hashing import content_address
    document = _view(_document("owner", None, 0, 0, None, dict(PLATFORM_DEFAULTS), True))
    if field == "research_capital": document["values"][field] = value
    else: document[field] = value
    if rehash:
        document["content_address"] = content_address({key: item for key, item in document.items() if key != "content_address"})
    with pytest.raises(ValueError):
        _validate_revision_view(document, "owner", None)


def test_research_settings_canonical_snapshot_rejects_stale_numeric_alias():
    from research.domain.settings import PLATFORM_DEFAULTS, _document, _view, resolve_snapshot, validate_snapshot
    snapshot = resolve_snapshot(owner_id="owner", graph_identifier="graph",
        workspace=_view(_document("owner", None, 0, 0, None, dict(PLATFORM_DEFAULTS), True)),
        strategy=_view(_document("owner", "graph", 0, 0, None, {}, True)), run_overrides={})
    snapshot["values"]["research_capital"] = 100000
    with pytest.raises(ValueError):
        validate_snapshot(snapshot, owner_id="owner", graph_identifier="graph")


@pytest.mark.parametrize("field,value", [("expected_revision", False), ("research_capital", 100000)])
def test_research_settings_stored_revision_rejects_rehashed_numeric_alias(field, value):
    import json
    from types import SimpleNamespace
    from app.ir.hashing import content_address
    from research.domain.settings import PLATFORM_DEFAULTS, ResearchSettingsRepository, _document
    request_id = str(uuid.uuid4())
    document = _document("owner", None, 1, 0, request_id, dict(PLATFORM_DEFAULTS), True)
    if field == "research_capital": document["values"][field] = value
    else: document[field] = value
    row = SimpleNamespace(owner_id="owner", revision=1, request_id=request_id,
        document_json=json.dumps(document), content_address=content_address(document))
    with pytest.raises(ValueError):
        ResearchSettingsRepository(None)._read_row(row)


def test_research_settings_queue_pins_current_values_and_retries_without_reading_them(registry_publication_store, monkeypatch):
    from types import SimpleNamespace
    from app.api import ir_experiment_routes as routes
    from app.ir.library import REGISTRY
    from research.domain.settings import ResearchSettingsRepository
    _, sessions = registry_publication_store
    monkeypatch.setattr(routes, "SessionLocal", sessions)
    monkeypatch.setattr(routes, "_existing_preparation", lambda *_: None)
    monkeypatch.setattr(routes, "_enqueue_preparation", lambda plan, *_: plan)
    saved = {"content_address": "sha256:" + "a" * 64, "graph_address": "sha256:" + "b" * 64,
             "registry_snapshot_address": REGISTRY.registry_snapshot_address}
    body = routes.V2SettingsResearchPreparationRequest(request_id=str(uuid.uuid4()),
        dataset_manifest_address="sha256:" + "c" * 64, dataset_as_of="2026-09-01T00:00:00Z",
        hypothesis="Pinned percentage queue", expected_workspace_revision=0, expected_strategy_revision=0,
        run_overrides={"stop_loss_pct": .01, "take_profit_pct": .02})
    args = dict(owner_id="publication-owner", project_id="publication-project", identifier="publication-graph", version=1)
    plan = routes._queue_settings_preparation(saved, body, **args)
    item = plan["v2_graphs"][0]
    assert item["settings_snapshot"]["values"]["stop_loss_pct"] == .01
    assert item["execution_policy"]["risk"]["protective_band"]["take_profit_pct"] == .02
    monkeypatch.setattr(routes, "_existing_preparation", lambda *_: SimpleNamespace(plan=plan))
    monkeypatch.setattr(ResearchSettingsRepository, "snapshot", lambda *_args, **_kwargs: pytest.fail("retry read mutable defaults"))
    assert routes._queue_settings_preparation(saved, body, **args) == plan


def _canonical_search_intent():
    return {"schema": "canonical-local-development-search/1", "enabled": True,
            "axes": [{"node_id": "rising", "parameter_id": "window",
                      "step": "1", "minimum": "1", "maximum": "3"}]}


def test_research_settings_v3_pins_search_without_rewriting_v2():
    from app.ir.hashing import canonical_json
    from research.domain.settings import V2_DEFAULTS, _document, _view, resolve_snapshot, validate_snapshot
    workspace = _view(_document("owner", None, 0, 0, None, V2_DEFAULTS, True,
                                schema="research-settings-revision/2"))
    old_strategy = _view(_document("owner", "graph", 0, 0, None, {}, True,
                                   schema="research-settings-revision/2"))
    old = resolve_snapshot(owner_id="owner", graph_identifier="graph", workspace=workspace,
                           strategy=old_strategy, run_overrides={})
    old_bytes = canonical_json(old)
    strategy = _view(_document("owner", "graph", 1, 0, str(uuid.uuid4()),
                              {"optimization": _canonical_search_intent()}, True))
    new = resolve_snapshot(owner_id="owner", graph_identifier="graph", workspace=workspace,
                           strategy=strategy, run_overrides={})
    assert new["schema"] == "research-settings-snapshot/3"
    assert new["values"]["optimization"] == _canonical_search_intent()
    assert new["sources"]["optimization"] == "strategy"
    assert canonical_json(validate_snapshot(old, owner_id="owner", graph_identifier="graph")) == old_bytes
    assert "optimization" not in old["values"]
    with pytest.raises(ValueError):
        resolve_snapshot(owner_id="owner", graph_identifier="graph", workspace=workspace,
                         strategy=strategy, run_overrides={}, schema="research-settings-snapshot/2")


def test_optimization_settings_are_strategy_intent_and_refused_at_workspace(client):
    from research.domain.settings import PLATFORM_DEFAULTS
    project = _project(client)
    _create(client, project, "optimization-settings")
    path = f"/api/ir/projects/{project}/graphs/optimization-settings/research-settings"
    body = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "enabled": True,
            "values": {"optimization": _canonical_search_intent()}}
    saved = client.put(path, json=body)
    assert saved.status_code == 200
    assert saved.json()["schema"] == "research-settings-revision/3"
    assert client.put(path, json=body).json() == saved.json()
    assert client.get(path).json()["values"]["optimization"] == _canonical_search_intent()
    workspace = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
                 "values": {**PLATFORM_DEFAULTS, "optimization": _canonical_search_intent()}}
    assert client.put("/api/research-settings", json=workspace).status_code == 422


@pytest.mark.parametrize("fault", ["unknown", "boolean", "duplicate", "five", "decimal", "disabled_work"])
def test_search_intent_shape_is_closed_and_bounded(fault):
    from research.domain.settings import validate_values
    intent = _canonical_search_intent()
    if fault == "unknown": intent["account_capital"] = 123
    elif fault == "boolean": intent["enabled"] = 1
    elif fault == "duplicate": intent["axes"] *= 2
    elif fault == "five": intent["axes"] = [{**intent["axes"][0], "node_id": str(i)} for i in range(5)]
    elif fault == "decimal": intent["axes"][0]["step"] = "1.0"
    else: intent["enabled"] = False
    with pytest.raises(ValueError):
        validate_values({"optimization": intent}, sparse=True)


def test_search_queue_refuses_bad_axes_before_enqueue_and_retries_frozen_intent(registry_publication_store, monkeypatch):
    from types import SimpleNamespace
    from app.api import ir_experiment_routes as routes
    from app.ir.library import REGISTRY
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for
    from research_tests.test_v2_graph_experiment_bridge import _saved_v2_boolean_graph
    from research.orchestrator.v2_operation import V2OperationRefusal
    _, sessions = registry_publication_store
    monkeypatch.setattr(routes, "SessionLocal", sessions)
    monkeypatch.setattr(routes, "_existing_preparation", lambda *_: None)
    queued = []
    monkeypatch.setattr(routes, "_enqueue_preparation", lambda plan, *_: queued.append(plan) or plan)
    document = canonical_document(_saved_v2_boolean_graph(REGISTRY), REGISTRY)
    saved = {"document": document, "content_address": content_address_for(document, REGISTRY),
             "graph_address": graph_address_for(document, REGISTRY), "registry_snapshot_address": REGISTRY.registry_snapshot_address}
    body = routes.V2SettingsResearchPreparationRequest(request_id=str(uuid.uuid4()),
        dataset_manifest_address="sha256:" + "c" * 64, dataset_as_of="2026-09-01T00:00:00Z",
        hypothesis="Canonical development search", expected_workspace_revision=0, expected_strategy_revision=0,
        run_overrides={"optimization": _canonical_search_intent()})
    args = dict(owner_id="publication-owner", project_id="publication-project", identifier="publication-graph", version=1)
    invalid = body.model_copy(deep=True)
    invalid.run_overrides["optimization"]["axes"][0]["parameter_id"] = "max_daily_loss"
    with pytest.raises(V2OperationRefusal, match="parameter"):
        routes._queue_settings_preparation(saved, invalid, **args)
    assert queued == []
    plan = routes._queue_settings_preparation(saved, body, **args)
    assert "optimization" not in plan["v2_graphs"][0]["experiment"]
    assert plan["v2_graphs"][0]["settings_snapshot"]["schema"] == "research-settings-snapshot/3"
    monkeypatch.setattr(routes, "_existing_preparation", lambda *_: SimpleNamespace(plan=plan))
    monkeypatch.setattr(routes, "_check_canonical_search", lambda *_: pytest.fail("retry must not recheck mutable registry"))
    assert routes._queue_settings_preparation(saved, body, **args) == plan
