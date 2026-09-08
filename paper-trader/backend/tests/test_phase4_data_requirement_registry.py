from copy import deepcopy
from dataclasses import replace
from types import MappingProxyType

import pytest

from app.ir.registry import PlatformRegistry
from app.ir.library import REGISTRY as V1_REGISTRY
from app.ir.resolve import resolve_v2, resolved_v2_graph_address
from app.ir.hashing import content_address


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value
from app.market_data.requirements import DataRequirementRefusal, compile_data_requirement_plan


def component(parameter_id="bar_seconds"):
    return {"component_id": "leaf.close", "component_version": 1, "domain_family": "transform", "structural_role": "transform", "ports": [], "parameters": {parameter_id: {"type": "int", "required": True, "default": None, "enum": None, "domain": None, "units": "seconds", "serialization": "integer"}}}


def declaration():
    return {"schema": "data-requirement-declaration/1", "classification": "REQUIRES_DATA", "requirements": [{"requirement_id": "primary_close", "instrument": {"literal": {"role": "primary", "type": "PHYSICAL"}}, "field": {"literal": "CLOSE"}, "timeframe": {"parameter": "bar_seconds"}, "history": {"literal": {"minimum_bars": 1, "warmup_bars": 20}}, "freshness": {"literal": {"maximum_age_seconds": 60}}, "depth": {"literal": {"kind": "NONE", "levels": None}}, "session": {"literal": "INSTRUMENT_CALENDAR"}, "alignment": {"literal": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}}, "derived_local": {"literal": False}}]}


def no_data_declaration():
    return {"schema": "data-requirement-declaration/1", "classification": "NO_DATA", "requirements": []}


def registry(declarations):
    return PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): component()}, data_requirement_declarations=declarations)


def test_registry_freezes_and_addresses_normalized_declaration():
    raw = declaration(); first = registry({("leaf.close", 1): raw}); raw["requirements"][0]["field"] = {"literal": "OPEN"}; second = registry({("leaf.close", 1): declaration()})
    assert first.data_requirement_declarations[("leaf.close", 1)]["requirements"][0]["field"]["literal"] == "CLOSE"
    assert first.data_requirement_declaration_addresses[("leaf.close", 1)] == second.data_requirement_declaration_addresses[("leaf.close", 1)]
    assert first.registry_snapshot_address == second.registry_snapshot_address
    changed = declaration(); changed["requirements"][0]["field"] = {"literal": "OPEN"}
    assert first.registry_snapshot_address != registry({("leaf.close", 1): changed}).registry_snapshot_address
    with pytest.raises(TypeError): first.data_requirement_declarations[("leaf.close", 1)]["schema"] = "other"


def test_mixed_v1_and_v2_registry_snapshot_uses_structured_v1_entries():
    mixed = PlatformRegistry(
        components=V1_REGISTRY.library.components, bodies=V1_REGISTRY.library.bodies,
        registrations=V1_REGISTRY.registrations, v2_types={},
        v2_components={("leaf.close", 1): component()},
        data_requirement_declarations={("leaf.close", 1): declaration()},
    )
    assert mixed.registry_snapshot_address.startswith("sha256:")
    assert isinstance(mixed.registry_snapshot_payload["v1_components"], tuple)


def test_requirement_array_permutations_have_canonical_bytes_and_sorted_rows():
    first = declaration()
    second = deepcopy(first["requirements"][0]); second["requirement_id"] = "secondary_close"
    reverse = deepcopy(first); reverse["requirements"] = [second, first["requirements"][0]]
    forward = deepcopy(first); forward["requirements"] = [first["requirements"][0], second]
    left = registry({("leaf.close", 1): reverse})
    right = registry({("leaf.close", 1): forward})
    assert left.data_requirement_declaration_addresses == right.data_requirement_declaration_addresses
    assert plain(left.data_requirement_declarations) == plain(right.data_requirement_declarations)
    assert [row["requirement_id"] for row in left.data_requirement_declarations[("leaf.close", 1)]["requirements"]] == ["primary_close", "secondary_close"]


def test_duplicate_requirement_id_refuses_before_normalization():
    value = declaration(); value["requirements"].append(deepcopy(value["requirements"][0]))
    with pytest.raises(ValueError, match="duplicate requirement_id"):
        registry({("leaf.close", 1): value})


@pytest.mark.parametrize("mutate", [
    lambda value: value.__setitem__("extra", True),
    lambda value: value["requirements"][0].__setitem__("requirement_id", "Bad"),
    lambda value: value["requirements"][0].pop("derived_local"),
    lambda value: value["requirements"][0].__setitem__("field", {"literal": "unknown"}),
    lambda value: value["requirements"][0].__setitem__("history", {"literal": {"minimum_bars": {"parameter": "bar_seconds"}, "warmup_bars": 1}}),
    lambda value: value["requirements"][0].__setitem__("timeframe", {"parameter": "missing"}),
])
def test_registry_refuses_closed_or_unbound_declarations(mutate):
    value = declaration(); mutate(value)
    with pytest.raises(ValueError): registry({("leaf.close", 1): value})


def test_registry_refuses_compound_owned_declaration():
    value = component(); value["compound"] = {"body": {"graph_inputs": [], "graph_outputs": [], "nodes": [], "edges": []}, "parameter_bindings": [{"parameter_id": "bar_seconds", "targets": []}]}
    with pytest.raises(ValueError):
        PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): value}, data_requirement_declarations={("leaf.close", 1): declaration()})


def document(seconds=60):
    return {"format_version": 2, "strategy_id": "phase4-data", "strategy_version": 1, "metadata": {"metadata_version": 1, "name": "Data", "description": None, "tags": []}, "graph_inputs": [], "graph_outputs": [], "nodes": [{"node_id": "close", "component": {"component_id": "leaf.close", "component_version": 1}, "parameters": {"bar_seconds": seconds}}], "edges": []}


def test_leaf_binding_and_plan_are_identity_complete_and_deterministic():
    current = registry({("leaf.close", 1): declaration()})
    resolved = resolve_v2(document(120), current)
    leaf = resolved.nodes[0]
    assert leaf.bound_requirements[0]["timeframe"] == 120
    assert leaf.declaration_address == current.data_requirement_declaration_addresses[("leaf.close", 1)]
    assert leaf.registry_snapshot_address == current.registry_snapshot_address
    plan = compile_data_requirement_plan(resolved)
    assert plan.authored_ir_address == resolved.authored_ir_address
    assert plan.registry_snapshot_address == current.registry_snapshot_address
    assert plan.requirements[0]["requirement"]["timeframe"] == 120
    assert plan.plan_address == compile_data_requirement_plan(resolve_v2(document(120), current)).plan_address


def test_authored_identity_cannot_be_overridden_and_addresses_are_canonical():
    resolved = resolve_v2(document(), registry({("leaf.close", 1): declaration()}))
    with pytest.raises(DataRequirementRefusal, match="override"):
        compile_data_requirement_plan(resolved, authored_ir_address="sha256:" + "a" * 64)
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(resolved, resolved_graph_address="not-an-address"))


def test_missing_or_stale_declaration_refuses_plan_not_no_data():
    missing = registry({})
    with pytest.raises(DataRequirementRefusal, match="missing"):
        compile_data_requirement_plan(resolve_v2(document(), missing))
    current = registry({("leaf.close", 1): declaration()})
    resolved = resolve_v2(document(), current)
    stale = type("Stale", (), {"nodes": resolved.nodes, "registry_snapshot_address": "sha256:" + "0" * 64, "resolved_graph_address": resolved.resolved_graph_address, "implementation_closure_address": resolved.implementation_closure_address, "authored_ir_address": resolved.authored_ir_address})()
    with pytest.raises(DataRequirementRefusal, match="stale"):
        compile_data_requirement_plan(stale)


def test_explicit_no_data_compiles_while_absent_declaration_only_resolves():
    opted = registry({("leaf.close", 1): no_data_declaration()})
    plan = compile_data_requirement_plan(resolve_v2(document(), opted))
    assert plan.requirements == ()
    assert plan.declaration_addresses == (opted.data_requirement_declaration_addresses[("leaf.close", 1)],)
    unresolved_opt_in = resolve_v2(document(), registry({}))
    assert unresolved_opt_in.nodes[0].declaration_address is None
    with pytest.raises(DataRequirementRefusal, match="missing"):
        compile_data_requirement_plan(unresolved_opt_in)


def test_forged_or_stale_leaf_declaration_and_snapshot_map_refuse():
    resolved = resolve_v2(document(), registry({("leaf.close", 1): declaration()}))
    forged_node = replace(resolved.nodes[0], declaration_address="sha256:" + "f" * 64)
    forged = replace(resolved, nodes=(forged_node,))
    forged = replace(forged, resolved_graph_address=resolved_v2_graph_address(
        forged.nodes, forged.registry_snapshot_address, forged.implementation_closure_address,
        forged.registry_snapshot_payload, forged.data_requirement_declaration_closure,
    ))
    with pytest.raises(DataRequirementRefusal, match="exact leaf"):
        compile_data_requirement_plan(forged)
    bad_payload = plain(resolved.registry_snapshot_payload)
    bad_payload["data_requirement_declarations"][0]["declaration_address"] = "sha256:" + "e" * 64
    bad_snapshot = replace(resolved, registry_snapshot_payload=MappingProxyType(bad_payload), registry_snapshot_address=content_address(bad_payload))
    bad_snapshot = replace(bad_snapshot, resolved_graph_address=resolved_v2_graph_address(
        bad_snapshot.nodes, bad_snapshot.registry_snapshot_address, bad_snapshot.implementation_closure_address,
        bad_snapshot.registry_snapshot_payload, bad_snapshot.data_requirement_declaration_closure,
    ))
    with pytest.raises(DataRequirementRefusal, match="disagrees"):
        compile_data_requirement_plan(bad_snapshot)


def test_self_consistent_synthetic_closure_still_must_obey_registry_grammar():
    resolved = resolve_v2(document(), registry({("leaf.close", 1): declaration()}))
    malformed = plain(resolved.data_requirement_declaration_closure)
    malformed[0]["declaration"]["requirements"][0]["field"] = {"literal": "NOT_A_FIELD"}
    bad_payload = plain(resolved.registry_snapshot_payload)
    bad_payload["data_requirement_declarations"][0]["declaration_address"] = content_address(malformed[0]["declaration"])
    synthetic = replace(
        resolved,
        registry_snapshot_payload=MappingProxyType(bad_payload),
        data_requirement_declaration_closure=tuple(MappingProxyType(item) for item in malformed),
        registry_snapshot_address=content_address(bad_payload),
    )
    synthetic = replace(synthetic, resolved_graph_address=resolved_v2_graph_address(
        synthetic.nodes, synthetic.registry_snapshot_address, synthetic.implementation_closure_address,
        synthetic.registry_snapshot_payload, synthetic.data_requirement_declaration_closure,
    ))
    with pytest.raises(DataRequirementRefusal, match="registry grammar"):
        compile_data_requirement_plan(synthetic)


def test_repeated_leaf_instances_keep_unique_sorted_declaration_addresses():
    current = registry({("leaf.close", 1): declaration()})
    value = document(120)
    value["nodes"].append({"node_id": "another", "component": {"component_id": "leaf.close", "component_version": 1}, "parameters": {"bar_seconds": 60}})
    plan = compile_data_requirement_plan(resolve_v2(value, current))
    assert plan.declaration_addresses == (current.data_requirement_declaration_addresses[("leaf.close", 1)],)
    assert plan.plan_address == compile_data_requirement_plan(resolve_v2(value, current)).plan_address


def test_structured_attribution_avoids_slash_and_colon_collisions():
    left_component = component("b:c")
    right_component = component("c")
    left_decl = declaration(); left_decl["requirements"][0]["timeframe"] = {"parameter": "b:c"}
    right_decl = declaration(); right_decl["requirements"][0]["timeframe"] = {"parameter": "c"}
    current = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types={},
        v2_components={("leaf.left", 1): {**left_component, "component_id": "leaf.left"}, ("leaf.right", 1): {**right_component, "component_id": "leaf.right"}},
        data_requirement_declarations={("leaf.left", 1): left_decl, ("leaf.right", 1): right_decl},
    )
    value = document(); value["nodes"] = [
        {"node_id": "a:b", "component": {"component_id": "leaf.left", "component_version": 1}, "parameters": {"b:c": 60}},
        {"node_id": "a", "component": {"component_id": "leaf.right", "component_version": 1}, "parameters": {"c": 120}},
    ]
    plan = compile_data_requirement_plan(resolve_v2(value, current))
    assert {entry["authored_node_id"] for entry in plan.parameter_binding_provenance} == {"a:b", "a"}
    assert plan.requirements[0]["authored_node_id"] in {"a:b", "a"}
    assert {record["lowered_path"] for record in plan.requirements} == {("a:b",), ("a",)}


def test_forged_structured_attribution_and_joined_slash_path_collision_refuse():
    resolved = resolve_v2(document(), registry({("leaf.close", 1): declaration()}))
    forged_node = replace(resolved.nodes[0], authored_node_id="forged", lowered_path=("forged",))
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(resolved, nodes=(forged_node,)))
    first = replace(resolved.nodes[0], node_id="a/b/c", authored_node_id="a/b", lowered_path=("a/b", "c"))
    second = replace(resolved.nodes[0], node_id="a/b/c", authored_node_id="a", lowered_path=("a", "b/c"))
    collision = replace(resolved, nodes=(first, second))
    collision = replace(collision, resolved_graph_address=resolved_v2_graph_address(
        collision.nodes, collision.registry_snapshot_address, collision.implementation_closure_address,
        collision.registry_snapshot_payload, collision.data_requirement_declaration_closure,
    ))
    with pytest.raises(DataRequirementRefusal, match="collides"):
        compile_data_requirement_plan(collision)


def test_compound_lowering_binds_leaf_declaration_and_retains_target_paths():
    leaf = component()
    compound = deepcopy(component())
    compound["component_id"] = "compound.close"
    compound["compound"] = {
        "body": {"graph_inputs": [], "graph_outputs": [], "nodes": [{"node_id": "child", "component": {"component_id": "leaf.close", "component_version": 1}, "parameters": {}}], "edges": []},
        "parameter_bindings": [{"parameter_id": "bar_seconds", "targets": [{"node_id": "child", "parameter_id": "bar_seconds"}]}],
    }
    current = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): leaf, ("compound.close", 1): compound}, data_requirement_declarations={("leaf.close", 1): declaration()})
    value = document(120); value["nodes"][0]["component"]["component_id"] = "compound.close"
    resolved = resolve_v2(value, current)
    bound = resolved.nodes[0]
    assert bound.component == ("leaf.close", 1)
    assert bound.bound_requirements[0]["timeframe"] == 120
    assert bound.parameter_provenance["bar_seconds"]["target_paths"] == (("child", "bar_seconds"),)
    assert compile_data_requirement_plan(resolved).requirements[0]["lowered_path"] == ("close", "child")


def test_plan_address_includes_registry_snapshot_identity():
    current = registry({("leaf.close", 1): declaration()})
    plan = compile_data_requirement_plan(resolve_v2(document(120), current))
    record = plan.requirements[0]
    payload = {"authored_ir_address": plan.authored_ir_address, "resolved_graph_address": plan.resolved_graph_address, "implementation_closure_address": plan.implementation_closure_address, "registry_snapshot_address": plan.registry_snapshot_address, "declaration_addresses": list(plan.declaration_addresses), "requirements": [{"authored_node_id": record["authored_node_id"], "lowered_path": list(record["lowered_path"]), "leaf_component": {"component_id": record["leaf_component"][0], "component_version": record["leaf_component"][1]}, "requirement": plain(record["requirement"])}], "parameter_binding_provenance": plain(plan.parameter_binding_provenance)}
    assert plan.plan_address == content_address(payload)


@pytest.mark.parametrize("mutate", [
    lambda row: row.__setitem__("extra", True),
    lambda row: row.__setitem__("field", {"literal": "CLOSE"}),
    lambda row: row.__setitem__("history", {"minimum_bars": {"parameter": "bar_seconds"}, "warmup_bars": 1}),
])
def test_compiler_refuses_malformed_or_expression_bound_rows(mutate):
    resolved = resolve_v2(document(), registry({("leaf.close", 1): declaration()}))
    row = plain(resolved.nodes[0].bound_requirements[0]); mutate(row)
    node = replace(resolved.nodes[0], bound_requirements=(MappingProxyType(row),))
    graph = replace(resolved, nodes=(node,))
    graph = replace(graph, resolved_graph_address=resolved_v2_graph_address(
        graph.nodes, graph.registry_snapshot_address, graph.implementation_closure_address,
        graph.registry_snapshot_payload, graph.data_requirement_declaration_closure,
    ))
    with pytest.raises(DataRequirementRefusal, match="bound data requirement"):
        compile_data_requirement_plan(graph)


def test_post_binding_direct_values_are_deeply_frozen():
    resolved = resolve_v2(document(), registry({("leaf.close", 1): declaration()}))
    row = resolved.nodes[0].bound_requirements[0]
    with pytest.raises(TypeError):
        row["history"]["minimum_bars"] = 9
