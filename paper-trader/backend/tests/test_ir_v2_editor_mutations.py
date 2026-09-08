"""Focused RED/GREEN contract for canonical Component IR v2 editor commands."""
from __future__ import annotations

import copy
from types import SimpleNamespace
import json
import time
import tracemalloc

import pytest


def _port(port_id: str, direction: str) -> dict[str, object]:
    value: dict[str, object] = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "value",
        "type_ref": {"type_id": "number", "type_version": 1},
        "shape": "scalar",
    }
    if direction == "input":
        value["connections"] = {
            "cardinality": "single", "min": 1, "max": 1, "assembly": "single",
        }
    return value


def _registry() -> SimpleNamespace:
    source = {
        "component_id": "source", "component_version": 2,
        "domain_family": "source", "structural_role": "source",
        "ports": [_port("out", "output")], "parameters": {"value": {"default": "1"}},
    }
    sink = {
        "component_id": "sink", "component_version": 2,
        "domain_family": "sink", "structural_role": "sink",
        "ports": [_port("in", "input"), _port("out", "output")], "parameters": {},
    }
    return SimpleNamespace(
        v2_types={("number", 1): {"type_id": "number", "type_version": 1,
                                  "shapes": ["scalar"], "runtime_representation": "decimal"}},
        v2_components={("source", 2): source, ("sink", 2): sink},
        v2_implementation_identities={}, contract_bindings={},
        data_requirement_declarations={}, data_requirement_declaration_addresses={},
        node_contract_addresses={}, registry_snapshot_address=None,
        registry_snapshot_payload=None,
    )


def _empty() -> dict[str, object]:
    return {
        "format_version": 2, "strategy_id": "graph-a", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Graph A", "description": "", "tags": []},
        "graph_inputs": [], "graph_outputs": [], "nodes": [], "edges": [],
    }


def _sealed_semantic_receipt(commands, opposite_commands):
    from app.editor.v2_mutations import (
        NONAUTHORITY, seal_semantic_receipt,
    )

    address = "sha256:" + "1" * 64
    return seal_semantic_receipt({
        "schema": "strategy-os-v2-semantic-receipt/2",
        "receipt_class": "SEALED_EDITOR_INVERSE",
        "owner_id": "owner", "project_id": "project", "graph_identifier": "graph",
        "format_version": 2, "intent": "EDIT", "source_receipt_address": None,
        "registry_snapshot_address": address,
        "base_semantic_revision": 0, "result_semantic_revision": 1,
        "base_content_address": address, "result_content_address": address,
        "base_graph_address": address, "result_graph_address": address,
        "current_version": None, "next_candidate_version": 1,
        "forward_commands": list(opposite_commands), "inverse_commands": list(commands),
        "resolved_topology_address": address, "commit_state": "DRAFT_COMMITTED",
        "nonauthority": NONAUTHORITY,
    })


def _receipt_material(
        document, commands, opposite_commands, registry, catalogue_identities,
        target_document):
    from app.editor.v2_mutations import (
        NONAUTHORITY, seal_semantic_receipt,
    )
    from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for
    from app.ir.hashing import content_address
    from app.ir.resolve import resolve_v2

    if registry.registry_snapshot_address is None:
        registry.registry_snapshot_payload = {"schema": "pure-receipt-registry/1"}
        registry.registry_snapshot_address = content_address(registry.registry_snapshot_payload)
    canonical_target = dict(canonical_document(target_document, registry))
    target_content = content_address_for(canonical_target, registry)
    target_graph = graph_address_for(canonical_target, registry)
    current_content = content_address_for(document, registry)
    current_graph = graph_address_for(document, registry)
    receipt = seal_semantic_receipt({
        "schema": "strategy-os-v2-semantic-receipt/2",
        "receipt_class": "SEALED_EDITOR_INVERSE",
        "owner_id": "owner", "project_id": "project", "graph_identifier": "graph",
        "format_version": 2, "intent": "EDIT", "source_receipt_address": None,
        "registry_snapshot_address": registry.registry_snapshot_address,
        "base_semantic_revision": 0, "result_semantic_revision": 1,
        "base_content_address": target_content,
        "result_content_address": current_content,
        "base_graph_address": target_graph, "result_graph_address": current_graph,
        "current_version": None, "next_candidate_version": 1,
        "forward_commands": list(opposite_commands), "inverse_commands": list(commands),
        "resolved_topology_address": resolve_v2(canonical_target, registry).resolved_graph_address,
        "commit_state": "DRAFT_COMMITTED", "nonauthority": NONAUTHORITY,
    })
    return receipt, target_content, target_graph


def _receipt_invocation(
        document, commands, opposite_commands, registry, catalogue_identities,
        target_document):
    from app.editor.v2_mutations import _new_receipt_restore_invocation

    receipt, target_content, target_graph = _receipt_material(
        document, commands, opposite_commands, registry, catalogue_identities,
        target_document)
    return _new_receipt_restore_invocation(
        receipt, document, commands, opposite_commands=opposite_commands,
        registry=registry, catalogue_identities=catalogue_identities,
        owner_id="owner", project_id="project", graph_identifier="graph",
        current_version=None, base_revision=1, requested_intent="UNDO",
        target_content=target_content, target_graph=target_graph)


def test_closed_batch_derives_edges_outputs_addresses_and_exact_inverse():
    from app.editor.v2_mutations import apply_semantic_commands

    commands = [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
        {"command": "bind_output", "output_id": "result",
         "source": {"node_id": "b", "port_id": "out"}, "semantic_role": "result"},
    ]
    result = apply_semantic_commands(
        _empty(), commands, registry=_registry(),
        catalogue_identities=frozenset({("source", 2), ("sink", 2)}),
    )
    assert result.document["edges"][0]["edge_id"].startswith("edge.")
    assert result.content_address.startswith("sha256:")
    assert result.graph_address.startswith("sha256:")
    assert result.resolved_address.startswith("sha256:")
    restored = apply_semantic_commands(
        result.document, result.inverse_commands, registry=_registry(),
        catalogue_identities=frozenset({("source", 2), ("sink", 2)}),
    )
    assert restored.document == _empty()


def test_private_receipt_restore_preserves_arbitrary_imported_edge_identity():
    from app.editor.v2_mutations import apply_semantic_commands

    registry = _registry()
    from app.ir.formats.v2 import content_address_for, graph_address_for

    allowed = frozenset({("source", 2), ("sink", 2)})
    created = apply_semantic_commands(
        _empty(),
        [
            {"command": "add_node", "node_id": "a", "component_id": "source",
             "component_version": 2, "parameters": {"value": "2"}},
            {"command": "add_node", "node_id": "b", "component_id": "sink",
             "component_version": 2, "parameters": {}},
            {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
             "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
        ],
        registry=registry,
        catalogue_identities=allowed,
    )
    imported = json.loads(json.dumps(created.document))
    imported["edges"][0]["edge_id"] = "caller.edge.identity.\u00e9." + "x" * 129
    expected_content = content_address_for(imported, registry)
    expected_graph = graph_address_for(imported, registry)
    removed = apply_semantic_commands(
        imported,
        [{"command": "remove_node", "node_id": "b"}],
        registry=registry,
        catalogue_identities=allowed,
    )
    assert removed.inverse_commands[1] == {
        "command": "restore_edge_from_receipt",
        "mode": "insert_or_replace_graph_output",
        "edge": imported["edges"][0],
        "graph_output_descriptor": None,
    }
    restored = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, imported).invoke()
    assert restored.document == imported
    assert restored.content_address == expected_content
    assert restored.graph_address == expected_graph


def test_receipt_restore_capability_is_one_shot_and_document_bound():
    from app.editor.v2_mutations import (
        EditorRefusal, _new_receipt_restore_invocation, apply_semantic_commands,
    )

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    created = apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
    ], registry=registry, catalogue_identities=allowed).document
    created["edges"][0]["edge_id"] = "caller.edge.identity"
    removed = apply_semantic_commands(
        created, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    invocation = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)
    first = invocation.invoke()
    assert first.document == created
    with pytest.raises(EditorRefusal) as reused:
        invocation.invoke()
    assert reused.value.code == "RECEIPT_CAPABILITY_INVALID"

    foreign = copy.deepcopy(removed.document)
    foreign["strategy_id"] = "graph-b"
    foreign["metadata"]["name"] = "Graph B"
    foreign_invocation = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)
    with pytest.raises(TypeError):
        foreign_invocation.invoke(foreign)
    receipt, target_content, target_graph = _receipt_material(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)
    with pytest.raises(EditorRefusal) as cross_lineage:
        _new_receipt_restore_invocation(
            receipt, foreign, removed.inverse_commands,
            opposite_commands=removed.forward_commands, registry=registry,
            catalogue_identities=allowed, owner_id="owner-b", project_id="project-b",
            graph_identifier="graph-b", current_version=None, base_revision=1,
            requested_intent="UNDO", target_content=target_content,
            target_graph=target_graph)
    assert cross_lineage.value.code == "RECEIPT_CAPABILITY_INVALID"
    with pytest.raises(EditorRefusal) as direct_private:
        apply_semantic_commands(
            foreign, removed.inverse_commands, registry=registry,
            catalogue_identities=allowed)
    assert direct_private.value.code == "REQUEST_SCHEMA_INVALID"


def test_receipt_restore_invocation_refuses_manual_copy_serialization_and_altered_commands():
    import inspect
    import pickle

    import app.editor.v2_mutations as mutations
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    created = apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
    ], registry=registry, catalogue_identities=allowed).document
    created["edges"][0]["edge_id"] = "caller.edge.identity"
    removed = apply_semantic_commands(
        created, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    invocation = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)
    assert not hasattr(mutations, "_RECEIPT_CAPABILITY_MARKER")
    assert not hasattr(mutations, "_receipt_invocation_creator")
    assert not hasattr(mutations, "_new_receipt_restore_invocation_impl")
    assert not hasattr(mutations, "_apply_semantic_commands_core")
    assert "private" not in str(inspect.signature(mutations.apply_semantic_commands))
    assert "_apply_private" not in str(
        inspect.signature(mutations._new_receipt_restore_invocation))
    assert mutations.apply_semantic_commands.__closure__ is None
    assert mutations.apply_semantic_commands.__defaults__ is None
    assert all(
        not callable(value)
        for value in (mutations.apply_semantic_commands.__kwdefaults__ or {}).values()
    )
    reachable_globals = {
        name: mutations.apply_semantic_commands.__globals__[name]
        for name in mutations.apply_semantic_commands.__code__.co_names
        if name in mutations.apply_semantic_commands.__globals__
        and callable(mutations.apply_semantic_commands.__globals__[name])
    }
    assert "_ReceiptRestoreInvocation" not in reachable_globals
    assert "_new_receipt_restore_invocation" not in reachable_globals
    with pytest.raises(EditorRefusal) as manual:
        mutations._ReceiptRestoreInvocation(
            {}, removed.document, removed.inverse_commands,
            opposite_commands=removed.forward_commands,
            registry=registry, catalogue_identities=allowed,
            owner_id="owner", project_id="project", graph_identifier="graph",
            current_version=None, base_revision=1, requested_intent="UNDO",
            target_content=removed.content_address, target_graph=removed.graph_address,
        )
    assert manual.value.code in {"RECEIPT_ADDRESS_INVALID", "RECEIPT_CAPABILITY_INVALID"}
    forged = object.__new__(mutations._ReceiptRestoreInvocation)
    with pytest.raises(EditorRefusal) as uninitialized:
        forged.invoke()
    assert uninitialized.value.code == "RECEIPT_CAPABILITY_INVALID"
    with pytest.raises(TypeError):
        copy.copy(invocation)
    with pytest.raises(TypeError):
        copy.deepcopy(invocation)
    with pytest.raises(TypeError):
        pickle.dumps(invocation)
    with pytest.raises(TypeError):
        json.dumps(invocation)
    assert "caller.edge.identity" not in repr(invocation)
    assert not hasattr(invocation, "__dict__")

    altered = copy.deepcopy(removed.inverse_commands)
    altered[1]["edge"]["edge_id"] = "attacker.edge"
    with pytest.raises(EditorRefusal) as refused:
        apply_semantic_commands(
            removed.document, altered, registry=registry, catalogue_identities=allowed)
    assert refused.value.code == "REQUEST_SCHEMA_INVALID"
    assert invocation.invoke().document == created


def test_receipt_restore_invocation_concurrent_use_has_one_winner():
    from concurrent.futures import ThreadPoolExecutor

    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    created = apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
    ], registry=registry, catalogue_identities=allowed).document
    created["edges"][0]["edge_id"] = "caller.edge.identity"
    removed = apply_semantic_commands(
        created, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    invocation = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)

    def invoke():
        try:
            return "won", invocation.invoke().document
        except EditorRefusal as exc:
            return exc.code, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: invoke(), range(2)))
    assert [state for state, _document in outcomes].count("won") == 1
    assert [state for state, _document in outcomes].count("RECEIPT_CAPABILITY_INVALID") == 1
    assert next(document for state, document in outcomes if state == "won") == created


def test_receipt_restore_invocation_consumes_before_exception(monkeypatch):
    import app.editor.v2_mutations as mutations

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    created = mutations.apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
    ], registry=registry, catalogue_identities=allowed).document
    created["edges"][0]["edge_id"] = "caller.edge.identity"
    removed = mutations.apply_semantic_commands(
        created, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    invocation = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected private restore failure")

    monkeypatch.setattr(mutations, "_apply_public_semantic_command", fail)
    with pytest.raises(RuntimeError, match="injected private restore failure"):
        invocation.invoke()
    with pytest.raises(mutations.EditorRefusal) as consumed:
        invocation.invoke()
    assert consumed.value.code == "RECEIPT_CAPABILITY_INVALID"


def test_receipt_restore_invocation_reauthenticates_receipt_and_context_on_invoke(monkeypatch):
    import app.editor.v2_mutations as mutations

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    created = mutations.apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
    ], registry=registry, catalogue_identities=allowed).document
    created["edges"][0]["edge_id"] = "caller.edge.identity"
    removed = mutations.apply_semantic_commands(
        created, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    invocation = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)
    real_validate = mutations.validate_semantic_receipt
    calls = 0

    def refuse_on_second_validation(receipt):
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_validate(receipt)
        raise mutations.EditorRefusal("RECEIPT_SEAL_INVALID", "injected server MAC refusal")

    monkeypatch.setattr(mutations, "validate_semantic_receipt", refuse_on_second_validation)
    # Reconstruct under the wrapper so construction is the first validation and
    # invocation proves that the closed receipt and server MAC are checked again.
    receipt, target_content, target_graph = _receipt_material(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry, allowed, created)
    invocation = mutations._new_receipt_restore_invocation(
        receipt, removed.document, removed.inverse_commands,
        opposite_commands=removed.forward_commands, registry=registry,
        catalogue_identities=allowed, owner_id="owner", project_id="project",
        graph_identifier="graph", current_version=None, base_revision=1,
        requested_intent="UNDO", target_content=target_content,
        target_graph=target_graph)
    with pytest.raises(mutations.EditorRefusal) as rechecked:
        invocation.invoke()
    assert rechecked.value.code == "RECEIPT_SEAL_INVALID"
    assert calls == 2
    with pytest.raises(mutations.EditorRefusal) as consumed:
        invocation.invoke()
    assert consumed.value.code == "RECEIPT_CAPABILITY_INVALID"


def test_private_inverse_and_sealed_receipt_enforce_exact_byte_ceilings():
    from app.editor.v2_mutations import (
        MAX_BATCH_BYTES, MAX_RECEIPT_BYTES, EditorRefusal, apply_semantic_commands,
    )
    from app.ir.hashing import canonical_json

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    created = apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
    ], registry=registry, catalogue_identities=allowed).document
    probe_document = copy.deepcopy(created)
    probe_document["edges"][0]["edge_id"] = "x"
    probe = apply_semantic_commands(
        probe_document, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    probe_size = len(canonical_json(probe.inverse_commands).encode("utf-8"))
    exact_document = copy.deepcopy(probe_document)
    exact_document["edges"][0]["edge_id"] = "x" * (1 + MAX_BATCH_BYTES - probe_size)
    exact = apply_semantic_commands(
        exact_document, [{"command": "remove_node", "node_id": "b"}],
        registry=registry, catalogue_identities=allowed)
    assert len(canonical_json(exact.inverse_commands).encode("utf-8")) == MAX_BATCH_BYTES
    first_over_document = copy.deepcopy(exact_document)
    first_over_document["edges"][0]["edge_id"] += "x"
    with pytest.raises(EditorRefusal) as first_over:
        apply_semantic_commands(
            first_over_document, [{"command": "remove_node", "node_id": "b"}],
            registry=registry, catalogue_identities=allowed)
    assert first_over.value.code == "EDITOR_RESOURCE_LIMIT"
    assert first_over_document["edges"][0]["edge_id"].endswith("xx")

    private = probe.inverse_commands[1]
    opposite = probe.forward_commands
    receipt_probe = _sealed_semantic_receipt([private], opposite)
    receipt_probe_size = len(canonical_json(receipt_probe).encode("utf-8"))
    exact_private = copy.deepcopy(private)
    exact_private["edge"]["edge_id"] += "x" * (MAX_RECEIPT_BYTES - receipt_probe_size)
    exact_receipt = _sealed_semantic_receipt([exact_private], opposite)
    assert len(canonical_json(exact_receipt).encode("utf-8")) == MAX_RECEIPT_BYTES
    first_over_private = copy.deepcopy(exact_private)
    first_over_private["edge"]["edge_id"] += "x"
    with pytest.raises(EditorRefusal) as receipt_over:
        _sealed_semantic_receipt([first_over_private], opposite)
    assert receipt_over.value.code == "EDITOR_RESOURCE_LIMIT"


def test_private_receipt_restore_covers_disconnect_unbind_and_replacement_output():
    from app.editor.v2_mutations import apply_semantic_commands

    registry = _registry()
    allowed = frozenset({("source", 2), ("sink", 2)})
    base = apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "a", "component_id": "source",
         "component_version": 2, "parameters": {"value": "2"}},
        {"command": "add_node", "node_id": "b", "component_id": "sink",
         "component_version": 2, "parameters": {}},
        {"command": "connect", "source": {"node_id": "a", "port_id": "out"},
         "target": {"node_id": "b", "port_id": "in"}, "binding": {"kind": "single"}},
        {"command": "bind_output", "output_id": "result",
         "source": {"node_id": "b", "port_id": "out"}, "semantic_role": "result"},
    ], registry=registry, catalogue_identities=allowed).document
    derived_base = copy.deepcopy(base)
    base["edges"][0]["edge_id"] = "caller.node.edge"
    base["edges"][1]["edge_id"] = "caller.output.edge"

    unbound = apply_semantic_commands(base, [
        {"command": "unbind_output", "output_id": "result"},
    ], registry=registry, catalogue_identities=allowed)
    restored_unbind = _receipt_invocation(
        unbound.document, unbound.inverse_commands, unbound.forward_commands,
        registry, allowed, base).invoke()
    assert restored_unbind.document == base

    replaced = apply_semantic_commands(base, [{
        "command": "bind_output", "output_id": "result",
        "source": {"node_id": "a", "port_id": "out"}, "semantic_role": "replacement",
    }], registry=registry, catalogue_identities=allowed)
    restored_replacement = _receipt_invocation(
        replaced.document, replaced.inverse_commands, replaced.forward_commands,
        registry, allowed, base).invoke()
    assert restored_replacement.document == base

    same_edge_id_replacement = apply_semantic_commands(derived_base, [{
        "command": "bind_output", "output_id": "result",
        "source": {"node_id": "b", "port_id": "out"}, "semantic_role": "changed-role",
    }], registry=registry, catalogue_identities=allowed)
    restored_same_edge_id = _receipt_invocation(
        same_edge_id_replacement.document,
        same_edge_id_replacement.inverse_commands,
        same_edge_id_replacement.forward_commands,
        registry, allowed, derived_base).invoke()
    assert restored_same_edge_id.document == derived_base


def test_private_restore_refuses_without_capability_and_canonical_cycle_still_refuses():
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    registry = _resource_registry()
    allowed = frozenset({("resource.target", 2)})
    base = apply_semantic_commands(_empty(), [
        {"command": "add_node", "node_id": "b", "component_id": "resource.target",
         "component_version": 2, "parameters": {}},
    ], registry=registry, catalogue_identities=allowed)
    private = {
        "command": "restore_edge_from_receipt",
        "mode": "insert_or_replace_graph_output",
        "edge": {"edge_id": "forged", "source": {
            "scope": "node", "node_id": "b", "port_id": "out"}, "target": {
            "scope": "node", "node_id": "b", "port_id": "members"},
            "binding": {"kind": "keyed", "key": "self"}},
        "graph_output_descriptor": None,
    }
    with pytest.raises(EditorRefusal) as unverified:
        apply_semantic_commands(
            base.document, [private], registry=registry, catalogue_identities=allowed)
    assert unverified.value.code == "REQUEST_SCHEMA_INVALID"
    with pytest.raises(EditorRefusal) as cycle:
        _receipt_invocation(
            base.document, [private], [{"command": "remove_node", "node_id": "b"}],
            registry, allowed, base.document).invoke()
    assert cycle.value.code == "CYCLE_INVALID"


def test_invalid_final_candidate_is_atomic_and_typed():
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    original = _empty()
    try:
        apply_semantic_commands(
            original,
            [{"command": "add_node", "node_id": "b", "component_id": "sink",
              "component_version": 2, "parameters": {}}],
            registry=_registry(), catalogue_identities=frozenset({("sink", 2)}),
        )
    except EditorRefusal as exc:
        assert exc.code in {"CARDINALITY_INVALID", "SEMANTIC_INVALID"}
    else:
        raise AssertionError("incomplete required input was accepted")
    assert original == _empty()


def test_v1_document_refuses_without_mapping():
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    try:
        apply_semantic_commands({**_empty(), "format_version": 1}, [], registry=_registry(),
                                catalogue_identities=frozenset())
    except EditorRefusal as exc:
        assert exc.code == "V1_LEGACY_ONLY"
    else:
        raise AssertionError("v1 crossed into the v2 editor")


def test_exact_243_catalogue_identities_are_the_only_add_authority():
    from app.editor.v2_catalogue import CATALOGUE_DOCUMENT
    from app.editor.v2_mutations import EditorRefusal, _catalogue_identities, apply_semantic_commands
    from app.ir.library import REGISTRY

    projected = frozenset(
        (row["component_id"], row["component_version"])
        for group in CATALOGUE_DOCUMENT["groups"] for row in group["components"])
    assert len(projected) == 243
    assert _catalogue_identities() == projected
    exclusions = {(row["component_id"], row["component_version"])
                  for row in CATALOGUE_DOCUMENT["exclusions"]}
    assert not projected & exclusions
    base = _empty() | {"strategy_id": "catalogue-positive-controls"}
    for component_id, component_version in sorted(projected):
        result = apply_semantic_commands(base, [
            {"command": "add_node", "node_id": "candidate", "component_id": component_id,
             "component_version": component_version, "parameters": {}},
            {"command": "remove_node", "node_id": "candidate"},
        ], registry=REGISTRY)
        assert result.document == base
    for row in CATALOGUE_DOCUMENT["exclusions"]:
        try:
            apply_semantic_commands(base, [{
                "command": "add_node", "node_id": "excluded",
                "component_id": row["component_id"],
                "component_version": row["component_version"], "parameters": {},
            }], registry=REGISTRY)
        except EditorRefusal as exc:
            assert exc.code == "COMPONENT_NOT_IN_V0_CATALOGUE"
            assert row["reason_code"] in str(exc)
        else:
            raise AssertionError(f"excluded catalogue row was accepted: {row}")


def test_shared_logic_ids_keep_v2_ports_and_never_translate_to_v1_sockets():
    from app.ir.library import LIBRARY, REGISTRY

    for component_id in ("logic.and", "logic.or"):
        v2 = REGISTRY.v2_components[(component_id, 1)]
        assert [port["port_id"] for port in v2["ports"]] == ["input", "value"]
        legacy = LIBRARY.components[(component_id, 1)]
        assert {socket["identifier"] for socket in legacy["interface"]
                if socket["direction"] == "input"} == {"left", "right"}
        assert {socket["identifier"] for socket in legacy["interface"]
                if socket["direction"] == "output"} == {"out"}


def test_shared_logic_command_resolves_only_v2_input_and_value_ports():
    from app.editor.v2_mutations import apply_semantic_commands
    from app.ir.library import REGISTRY

    document = _empty() | {"strategy_id": "logic-v2-collision"}
    result = apply_semantic_commands(document, [
        {"command": "add_node", "node_id": "left", "component_id": "logic.and",
         "component_version": 1, "parameters": {}},
        {"command": "add_node", "node_id": "right", "component_id": "logic.and",
         "component_version": 1, "parameters": {}},
        {"command": "connect", "source": {"node_id": "left", "port_id": "value"},
         "target": {"node_id": "right", "port_id": "input"},
         "binding": {"kind": "single"}},
    ], registry=REGISTRY)
    assert result.document["edges"][0]["source"]["port_id"] == "value"
    assert result.document["edges"][0]["target"]["port_id"] == "input"


def _resource_registry() -> SimpleNamespace:
    output = _port("out", "output")
    source = {
        "component_id": "resource.source", "component_version": 2,
        "domain_family": "test", "structural_role": "source",
        "ports": [output], "parameters": {},
    }
    target_input = _port("members", "input")
    target_input["connections"] = {
        "cardinality": "variadic", "min": 0, "max": None, "assembly": "keyed",
    }
    target = {
        "component_id": "resource.target", "component_version": 2,
        "domain_family": "test", "structural_role": "transform",
        "ports": [target_input, output], "parameters": {},
    }
    implementation = "sha256:" + "1" * 64
    return SimpleNamespace(
        v2_types={("number", 1): {"type_id": "number", "type_version": 1,
                                  "shapes": ["scalar"], "runtime_representation": "decimal"}},
        v2_components={("resource.source", 2): source, ("resource.target", 2): target},
        v2_implementation_identities={
            ("resource.source", 2): implementation, ("resource.target", 2): implementation,
        },
        contract_bindings={}, data_requirement_declarations={},
        data_requirement_declaration_addresses={}, node_contract_addresses={},
        registry_snapshot_address=None, registry_snapshot_payload=None,
    )


def _resource_document(node_count: int, edge_count: int) -> dict[str, object]:
    sources = node_count - 1
    nodes = [{"node_id": f"source-{index}",
              "component": {"component_id": "resource.source", "component_version": 2},
              "parameters": {}} for index in range(sources)]
    nodes.append({"node_id": "target",
                  "component": {"component_id": "resource.target", "component_version": 2},
                  "parameters": {}})
    edges = [{
        "edge_id": f"edge-{index}",
        "source": {"scope": "node", "node_id": f"source-{index % sources}", "port_id": "out"},
        "target": {"scope": "node", "node_id": "target", "port_id": "members"},
        "binding": {"kind": "keyed", "key": f"member-{index}"},
    } for index in range(edge_count)]
    return {
        "format_version": 2, "strategy_id": f"resource-{node_count}-{edge_count}",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Resource", "description": "", "tags": []},
        "graph_inputs": [], "graph_outputs": [], "nodes": nodes, "edges": edges,
    }


@pytest.mark.parametrize("assembly", ["keyed", "ordered", "unordered"])
def test_private_restore_preserves_valid_multi_edge_identity_and_order(assembly):
    from app.editor.v2_mutations import apply_semantic_commands
    from app.ir.formats.v2 import canonical_document

    registry = _resource_registry()
    registry.v2_components[("resource.target", 2)]["ports"][0]["connections"]["assembly"] = assembly
    document = _resource_document(4, 3)
    for index, edge in enumerate(document["edges"]):
        edge["edge_id"] = f"caller.{assembly}.{2 - index}"
        edge["binding"] = (
            {"kind": "keyed", "key": f"member-{index}"} if assembly == "keyed"
            else {"kind": "ordered", "position": index} if assembly == "ordered"
            else {"kind": "unordered"}
        )
    document = dict(canonical_document(document, registry))
    first = document["edges"][0]
    disconnected = apply_semantic_commands(document, [{
        "command": "disconnect",
        "source": {key: value for key, value in first["source"].items() if key != "scope"},
        "target": {key: value for key, value in first["target"].items() if key != "scope"},
        "binding": first["binding"],
    }], registry=registry,
       catalogue_identities=frozenset({("resource.source", 2), ("resource.target", 2)}))
    restored_disconnect = _receipt_invocation(
        disconnected.document, disconnected.inverse_commands,
        disconnected.forward_commands, registry,
        frozenset({("resource.source", 2), ("resource.target", 2)}), document).invoke()
    assert restored_disconnect.document == document
    removed = apply_semantic_commands(
        document, [{"command": "remove_node", "node_id": "target"}],
        registry=registry,
        catalogue_identities=frozenset({("resource.source", 2), ("resource.target", 2)}),
    )
    restored = _receipt_invocation(
        removed.document, removed.inverse_commands, removed.forward_commands,
        registry,
        frozenset({("resource.source", 2), ("resource.target", 2)}), document).invoke()
    assert restored.document == document


@pytest.mark.parametrize("node_count,edge_count,seconds,peak_bytes", [
    (300, 600, 10.0, 96 * 1024 * 1024),
    (2000, 10000, 60.0, 384 * 1024 * 1024),
])
def test_fixed_resource_workloads_resolve_with_bounded_time_and_peak_memory(
        node_count, edge_count, seconds, peak_bytes):
    from app.editor.v2_mutations import apply_semantic_commands, seal_receipt

    document = _resource_document(node_count, edge_count)
    registry = _resource_registry()
    tracemalloc.start()
    started = time.perf_counter()
    result = apply_semantic_commands(document, [
        {"command": "add_node", "node_id": "temporary", "component_id": "resource.source",
         "component_version": 2, "parameters": {}},
        {"command": "remove_node", "node_id": "temporary"},
    ], registry=registry,
       catalogue_identities=frozenset({("resource.source", 2), ("resource.target", 2)}))
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    receipt = seal_receipt({
        "schema": "resource-editor-receipt/1", "nodes": node_count, "edges": edge_count,
        "forward_commands": list(result.forward_commands),
        "inverse_commands": list(result.inverse_commands),
        "content_address": result.content_address, "graph_address": result.graph_address,
        "resolved_address": result.resolved_address,
    })
    receipt_bytes = len(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    print(json.dumps({"nodes": node_count, "edges": edge_count, "seconds": elapsed,
                      "peak_bytes": peak, "receipt_bytes": receipt_bytes}, sort_keys=True))
    assert result.document["strategy_id"] == document["strategy_id"]
    assert len(result.document["nodes"]) == node_count
    assert len(result.document["edges"]) == edge_count
    assert elapsed < seconds
    assert peak < peak_bytes
    assert receipt_bytes < 1 * 1024 * 1024


def test_forward_edit_refuses_first_inverse_above_durable_command_limit():
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    registry = _resource_registry()
    document = _resource_document(2, 32)
    try:
        apply_semantic_commands(
            document, [{"command": "remove_node", "node_id": "target"}],
            registry=registry,
            catalogue_identities=frozenset({("resource.source", 2), ("resource.target", 2)}),
        )
    except EditorRefusal as exc:
        assert exc.code == "EDITOR_RESOURCE_LIMIT"
    else:
        raise AssertionError("forward edit returned an inverse above the durable command limit")


def test_registry_owned_unit_contract_refusal_and_canonical_value_control():
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands
    from app.ir.library import REGISTRY

    base = _empty() | {"strategy_id": "unit-contract"}
    add = {"command": "add_node", "node_id": "stop",
           "component_id": "intent.fixed_stop_percent", "component_version": 2,
           "parameters": {"rate": "0.1"}}
    try:
        apply_semantic_commands(base, [
            add,
            {"command": "set_parameter", "node_id": "stop", "parameter_id": "rate",
             "value": {"value": "0.2", "unit": "PERCENT"}},
            {"command": "remove_node", "node_id": "stop"},
        ], registry=REGISTRY)
    except EditorRefusal as exc:
        assert exc.code == "UNIT_CONTRACT_REFUSED"
    else:
        raise AssertionError("caller-supplied unit wrapper crossed the registry contract")
    accepted = apply_semantic_commands(base, [
        add,
        {"command": "set_parameter", "node_id": "stop", "parameter_id": "rate",
         "value": "0.2"},
        {"command": "remove_node", "node_id": "stop"},
    ], registry=REGISTRY)
    assert accepted.document == base


def test_output_binding_refusal_and_bind_unbind_control_are_typed():
    from app.editor.v2_mutations import EditorRefusal, apply_semantic_commands

    registry = _registry()
    base = _empty() | {"strategy_id": "output-contract"}
    try:
        apply_semantic_commands(base, [
            {"command": "unbind_output", "output_id": "missing"},
        ], registry=registry, catalogue_identities=frozenset())
    except EditorRefusal as exc:
        assert exc.code == "OUTPUT_BINDING_INVALID"
    else:
        raise AssertionError("missing output unbind was accepted")
    accepted = apply_semantic_commands(base, [
        {"command": "add_node", "node_id": "source", "component_id": "source",
         "component_version": 2, "parameters": {}},
        {"command": "bind_output", "output_id": "result",
         "source": {"node_id": "source", "port_id": "out"}, "semantic_role": "result"},
        {"command": "unbind_output", "output_id": "result"},
        {"command": "remove_node", "node_id": "source"},
    ], registry=registry, catalogue_identities=frozenset({("source", 2)}))
    assert accepted.document == base
