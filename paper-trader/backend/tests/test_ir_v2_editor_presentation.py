"""Presentation revision stays independent of semantic and immutable identity."""
from __future__ import annotations

from app.editor.v2_mutations import apply_presentation_commands, empty_presentation


def test_presentation_commands_are_closed_reversible_and_nonsemantic():
    identifiers = {
        "nodes": frozenset({"node-a"}), "edges": frozenset(), "outputs": frozenset(),
    }
    result = apply_presentation_commands(empty_presentation(), [
        {"command": "set_position", "node_id": "node-a", "x": 12, "y": 24},
        {"command": "put_group", "group_id": "group-a", "x": 0, "y": 0,
         "width": 200, "height": 100, "members": ["node-a"]},
        {"command": "set_viewport", "x": 1, "y": 2, "zoom": 1.5},
        {"command": "set_selection", "nodes": ["node-a"], "edges": [], "outputs": []},
    ], semantic_ids=identifiers)
    assert result.presentation_address.startswith("sha256:")
    restored = apply_presentation_commands(
        result.document, result.inverse_commands, semantic_ids=identifiers)
    assert restored.document == empty_presentation()


def test_persisted_presentation_never_changes_semantic_identity_and_reports_orphans():
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import (
        create_graph, mutate_presentation, mutate_semantic, read_graph, read_presentation,
    )

    init_db(reset=True)
    project = create_project("Presentation", owner_id="owner")
    create_graph(project.project_id, "presentation-v2", "Presentation", "", owner_id="owner")
    edit = mutate_semantic(
        project.project_id, "presentation-v2", base_revision=0, intent="EDIT",
        commands=[{"command": "add_node", "node_id": "node-a",
                   "component_id": "logic.and", "component_version": 1,
                   "parameters": {}}], source_receipt=None, owner_id="owner")
    semantic_before = read_graph(project.project_id, "presentation-v2", owner_id="owner")
    receipt = mutate_presentation(
        project.project_id, "presentation-v2", base_semantic_revision=1,
        base_presentation_revision=0,
        commands=[{"command": "set_position", "node_id": "node-a", "x": 1, "y": 2}],
        owner_id="owner")
    semantic_after = read_graph(project.project_id, "presentation-v2", owner_id="owner")
    assert receipt["identity_class"] == "NOT_EXECUTABLE_IDENTITY"
    assert semantic_after == semantic_before

    mutate_semantic(
        project.project_id, "presentation-v2", base_revision=1, intent="UNDO",
        commands=edit["inverse_commands"], source_receipt=edit, owner_id="owner")
    projected = read_presentation(project.project_id, "presentation-v2", owner_id="owner")
    assert projected["presentation"]["positions"] == {}
    assert projected["orphaned_references"]["positions"] == ["node-a"]
    assert projected["presentation_revision"] == 1


def test_http_presentation_receipt_drives_exact_undo_and_redo():
    from fastapi.testclient import TestClient
    from app.db.session import init_db
    from app.main import app
    from tests.test_ir_v2_editor_api import _batch, _create, _logic_node, _project

    init_db(reset=True)
    with TestClient(app) as client:
        project = _project(client)
        _create(client, project)
        path = f"/api/ir/projects/{project}/graphs/editor-v2/v2"
        assert client.post(path + "/semantic-batches",
                           json=_batch(base=0, commands=[_logic_node()])).status_code == 200
        edit = client.post(path + "/presentation-batches", json={
            "schema": "strategy-os-v2-presentation-batch/1", "format_version": 2,
            "base_semantic_revision": 1, "base_presentation_revision": 0,
            "intent": "EDIT", "source_receipt": None,
            "commands": [{"command": "set_position", "node_id": "logic", "x": 1, "y": 2}],
        })
        assert edit.status_code == 200, edit.text
        undo = client.post(path + "/presentation-batches", json={
            "schema": "strategy-os-v2-presentation-batch/1", "format_version": 2,
            "base_semantic_revision": 1, "base_presentation_revision": 1,
            "intent": "UNDO", "source_receipt": edit.json(),
            "commands": edit.json()["inverse_commands"],
        })
        assert undo.status_code == 200, undo.text
        assert client.get(path + "/presentation").json()["presentation"]["positions"] == {}
        redo = client.post(path + "/presentation-batches", json={
            "schema": "strategy-os-v2-presentation-batch/1", "format_version": 2,
            "base_semantic_revision": 1, "base_presentation_revision": 2,
            "intent": "REDO", "source_receipt": undo.json(),
            "commands": undo.json()["inverse_commands"],
        })
        assert redo.status_code == 200, redo.text
        assert client.get(path + "/presentation").json()["presentation"]["positions"] == {
            "logic": {"x": 1.0, "y": 2.0}}


def test_presentation_receipt_tamper_stale_and_replay_after_undo_are_atomic():
    import json
    import subprocess
    import sys
    from app.db.session import init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import (
        create_graph, mutate_presentation, mutate_semantic, read_presentation,
    )
    from app.editor.v2_mutations import EditorRefusal, seal_receipt
    from tests.test_ir_v2_editor_api import _logic_node

    init_db(reset=True)
    project = create_project("Presentation receipts", owner_id="owner")
    create_graph(project.project_id, "receipt-presentation", "Receipt", "", owner_id="owner")
    mutate_semantic(project.project_id, "receipt-presentation", base_revision=0, intent="EDIT",
                    commands=[_logic_node()], source_receipt=None, owner_id="owner")
    edit = mutate_presentation(
        project.project_id, "receipt-presentation", base_semantic_revision=1,
        base_presentation_revision=0,
        commands=[{"command": "set_position", "node_id": "logic", "x": 1, "y": 2}],
        owner_id="owner")
    forged = seal_receipt({**{k: v for k, v in edit.items() if k != "receipt_address"},
                           "project_id": "project.foreign"})
    unsealed = dict(edit)
    unsealed.pop("receipt_address")
    for source, base, code in ((unsealed, 1, "RECEIPT_ADDRESS_INVALID"),
                               (forged, 1, "RECEIPT_LINEAGE_INVALID"),
                               (edit, 0, "PRESENTATION_REVISION_CONFLICT")):
        try:
            mutate_presentation(
                project.project_id, "receipt-presentation", base_semantic_revision=1,
                base_presentation_revision=base, commands=edit["inverse_commands"],
                owner_id="owner", intent="UNDO", source_receipt=source)
        except EditorRefusal as exc:
            assert exc.code == code
        else:
            raise AssertionError("tampered or stale presentation receipt was accepted")
    undo = mutate_presentation(
        project.project_id, "receipt-presentation", base_semantic_revision=1,
        base_presentation_revision=1, commands=edit["inverse_commands"],
        owner_id="owner", intent="UNDO", source_receipt=edit)
    script = r'''import json,sys
from app.editor.v2_editor_store import mutate_presentation,read_presentation
receipt=json.loads(sys.argv[2])
result=mutate_presentation(sys.argv[1],"receipt-presentation",base_semantic_revision=1,
 base_presentation_revision=2,commands=receipt["forward_commands"],owner_id="owner",
 intent="REPLAY",source_receipt=receipt)
state=read_presentation(sys.argv[1],"receipt-presentation",owner_id="owner")
print(json.dumps({"commit":result["commit_state"],"result":result["result_presentation_address"],"revision":state["presentation_revision"]}))'''
    cold = subprocess.run(
        [sys.executable, "-c", script, project.project_id, json.dumps(edit)],
        check=True, capture_output=True, text=True)
    replay = json.loads(cold.stdout.strip())
    assert replay == {"commit": "DRY_RUN_ROLLED_BACK",
                      "result": edit["result_presentation_address"], "revision": 2}
    assert read_presentation(project.project_id, "receipt-presentation",
                             owner_id="owner")["presentation_revision"] == 2
    assert undo["source_receipt_address"] == edit["receipt_address"]


def test_presentation_receipt_cannot_cross_owner_same_identifier_lineage():
    from app.db.models import Organization
    from app.db.session import SessionLocal, init_db
    from app.editor.graph_artifacts import create_project
    from app.editor.v2_editor_store import create_graph, mutate_presentation, mutate_semantic
    from app.editor.v2_mutations import EditorRefusal
    from tests.test_ir_v2_editor_api import _logic_node

    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="owner-b", name="Owner B"))
    projects = {
        "owner": create_project("A", owner_id="owner"),
        "owner-b": create_project("B", owner_id="owner-b"),
    }
    receipts = {}
    for owner, project in projects.items():
        create_graph(project.project_id, "same-presentation", "Same", "", owner_id=owner)
        mutate_semantic(project.project_id, "same-presentation", base_revision=0, intent="EDIT",
                        commands=[_logic_node()], source_receipt=None, owner_id=owner)
        receipts[owner] = mutate_presentation(
            project.project_id, "same-presentation", base_semantic_revision=1,
            base_presentation_revision=0,
            commands=[{"command": "set_position", "node_id": "logic", "x": 1, "y": 2}],
            owner_id=owner)
    try:
        mutate_presentation(
            projects["owner-b"].project_id, "same-presentation", base_semantic_revision=1,
            base_presentation_revision=1, commands=receipts["owner"]["inverse_commands"],
            owner_id="owner-b", intent="UNDO", source_receipt=receipts["owner"])
    except EditorRefusal as exc:
        assert exc.code == "RECEIPT_LINEAGE_INVALID"
    else:
        raise AssertionError("foreign-owner presentation receipt crossed lineages")
