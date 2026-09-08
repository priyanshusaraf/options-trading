"""Construction cases for the v2 registry and compound declarations.

These tests exercise the registry boundary only.  A v2 declaration is not an
evaluation or admission artefact; its references and parameter bindings must
be closed before a registry can expose it.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from app.ir.registry import PlatformRegistry


TYPE_REF = {"type_id": "number", "type_version": 1}


def _type_descriptor() -> dict[str, object]:
    return {
        "type_id": "number",
        "type_version": 1,
        "shapes": ["scalar"],
        "runtime_representation": "float",
    }


def _parameter() -> dict[str, object]:
    return {
        "type": "float",
        "required": True,
        "default": None,
        "enum": None,
        "domain": None,
        "units": "value",
        "serialization": "canonical-float",
    }


def _port(port_id: str = "value", *, direction: str = "input") -> dict[str, object]:
    port = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "value",
        "type_ref": dict(TYPE_REF),
        "shape": "scalar",
    }
    if direction == "input":
        port["connections"] = {
            "cardinality": "optional",
            "assembly": "single",
            "min": 0,
            "max": 1,
        }
    return port


def _component(component_id: str, *, parameter: bool = True) -> dict[str, object]:
    return {
        "component_id": component_id,
        "component_version": 1,
        "domain_family": "transform",
        "structural_role": "transform",
        "ports": [_port("value"), _port("result", direction="output")],
        "parameters": {"length": _parameter()} if parameter else {},
    }


def _registry(components: dict[tuple[str, int], dict[str, object]]) -> PlatformRegistry:
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types={("number", 1): _type_descriptor()},
        v2_components=components,
    )


def test_registry_constructs_and_freezes_exact_v2_type_and_classification():
    registry = _registry({("indicator.scale", 1): _component("indicator.scale")})

    assert registry.v2_types[("number", 1)]["type_id"] == "number"
    assert registry.v2_components[("indicator.scale", 1)]["domain_family"] == "transform"
    with pytest.raises(TypeError):
        registry.v2_components[("indicator.scale", 1)]["domain_family"] = "risk"


@pytest.mark.parametrize(
    ("types", "components", "message"),
    [
        (
            {("number", 1): {**_type_descriptor(), "type_id": "other"}},
            {("indicator.scale", 1): _component("indicator.scale")},
            "conflicts with descriptor",
        ),
        (
            {("number", 1): _type_descriptor()},
            {("indicator.scale", 1): {**_component("indicator.scale"), "domain_family": "unregistered"}},
            "unregistered classification",
        ),
        (
            {("number", 1): _type_descriptor()},
            {("indicator.scale", 1): {**_component("indicator.scale"), "ports": [{**_port(), "type_ref": {"type_id": "missing", "type_version": 1}}]}},
            "unknown type",
        ),
        (
            {("number", 1): _type_descriptor()},
            {("indicator.scale", 1): {**_component("indicator.scale"), "ports": [{**_port(), "shape": "series"}]}},
            "shape conflicts",
        ),
    ],
)
def test_registry_closes_type_descriptor_and_classification(
    types: dict[tuple[str, int], dict[str, object]],
    components: dict[tuple[str, int], dict[str, object]],
    message: str,
):
    with pytest.raises(ValueError, match=message):
        PlatformRegistry(
            components={}, bodies={}, registrations={},
            v2_types=types, v2_components=components,
        )


def _compound(*, bindings: list[dict[str, object]]) -> dict[str, object]:
    value = _component("indicator.bundle")
    value["ports"] = [
        _port("value"),
        _port("result", direction="output"),
    ]
    value["compound"] = {
        "body": {
            "graph_inputs": [port for port in value["ports"] if port["direction"] == "input"],
            "graph_outputs": [port for port in value["ports"] if port["direction"] == "output"],
            "nodes": [{
                "node_id": "scale",
                "component": {"component_id": "indicator.scale", "component_version": 1},
                "parameters": {},
            }],
            "edges": [
                {
                    "edge_id": "input-to-scale",
                    "source": {"scope": "graph_input", "port_id": "value"},
                    "target": {"scope": "node", "node_id": "scale", "port_id": "value"},
                    "binding": {"kind": "single"},
                },
                {
                    "edge_id": "scale-to-output",
                    "source": {"scope": "node", "node_id": "scale", "port_id": "result"},
                    "target": {"scope": "graph_output", "port_id": "result"},
                    "binding": {"kind": "single"},
                },
            ],
        },
        "parameter_bindings": bindings,
    }
    return value


def _valid_components(compound: dict[str, object]) -> dict[tuple[str, int], dict[str, object]]:
    return {
        ("indicator.scale", 1): _component("indicator.scale"),
        ("indicator.bundle", 1): compound,
    }


def test_registry_constructs_compound_with_direct_one_to_many_parameter_binding():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [
            {"node_id": "scale", "parameter_id": "length"},
        ],
    }])

    registry = _registry(_valid_components(compound))

    stored = registry.v2_components[("indicator.bundle", 1)]["compound"]
    assert stored["parameter_bindings"][0]["targets"][0]["node_id"] == "scale"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_public", "duplicate public parameter binding"),
        ("duplicate_target", "duplicate or invalid parameter target"),
        ("extra_target_key", "target is not direct"),
        ("transform", "binding must be closed and transform-free"),
    ],
)
def test_registry_rejects_ambiguous_or_transform_compound_bindings(mutation: str, message: str):
    binding = {"parameter_id": "length", "targets": [{"node_id": "scale", "parameter_id": "length"}]}
    bindings: list[dict[str, object]] = [binding]
    if mutation == "duplicate_public":
        bindings.append(deepcopy(binding))
    elif mutation == "duplicate_target":
        compound = _compound(bindings=[binding, {"parameter_id": "other", "targets": [{"node_id": "scale", "parameter_id": "length"}]}])
        compound["parameters"] = {"length": _parameter(), "other": _parameter()}
        with pytest.raises(ValueError, match=message):
            _registry({("indicator.scale", 1): _component("indicator.scale"), ("indicator.bundle", 1): compound})
        return
    elif mutation == "extra_target_key":
        bindings[0]["targets"] = [{"node_id": "scale", "parameter_id": "length", "transform": "identity"}]
    else:
        bindings[0]["transform"] = "identity"

    with pytest.raises(ValueError, match=message):
        _registry(_valid_components(_compound(bindings=bindings)))


def test_registry_rejects_compound_public_parameter_without_exactly_one_binding():
    with pytest.raises(ValueError, match="binding"):
        _registry(_valid_components(_compound(bindings=[])))


def test_registry_requires_complete_ordinary_v2_compound_body():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    del compound["compound"]["body"]["edges"]

    with pytest.raises(ValueError, match="body|graph|closed|complete"):
        _registry(_valid_components(compound))


def test_registry_rejects_compound_body_non_mapping_edge_with_structured_object_path():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    compound["compound"]["body"]["edges"][0] = None

    with pytest.raises(ValueError, match=r"V2_OBJECT:\$\.edges\[0\]"):
        _registry(_valid_components(compound))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("dangling", "does not name a node"),
        ("malformed", "not in the v2 grammar"),
    ],
)
def test_registry_rejects_dangling_or_malformed_compound_body_graph(mutation: str, message: str):
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    edge = compound["compound"]["body"]["edges"][0]
    if mutation == "dangling":
        edge["target"]["node_id"] = "missing"
    else:
        edge["unexpected"] = True

    with pytest.raises(ValueError, match=message):
        _registry(_valid_components(compound))


def test_registry_rejects_duplicate_internal_semantic_edge_tuple():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    duplicate = deepcopy(compound["compound"]["body"]["edges"][0])
    duplicate["edge_id"] = "same-semantic-tuple-different-id"
    compound["compound"]["body"]["edges"].append(duplicate)

    with pytest.raises(ValueError, match="duplicates an existing source-target-binding tuple"):
        _registry(_valid_components(compound))


def test_registry_accepts_exact_body_boundary_mapping_and_rejects_drift():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    compound["ports"] = [
        {**_port("in"), "direction": "input"},
        _port("out", direction="output"),
    ]
    body = compound["compound"]["body"]
    body["graph_inputs"] = [compound["ports"][0]]
    body["graph_outputs"] = [compound["ports"][1]]
    body["edges"][0]["source"]["port_id"] = "in"
    body["edges"][1]["target"]["port_id"] = "out"
    registry = _registry(_valid_components(compound))
    assert registry.v2_components[("indicator.bundle", 1)]["compound"]["body"]["graph_inputs"] == (compound["ports"][0],)

    drifted = deepcopy(compound)
    drifted["compound"]["body"]["graph_outputs"][0] = {
        **drifted["compound"]["body"]["graph_outputs"][0],
        "port_id": "different",
    }
    with pytest.raises(ValueError, match="boundary|port"):
        _registry(_valid_components(drifted))


def test_registry_rejects_literal_and_public_binding_collision():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    compound["compound"]["body"]["nodes"][0]["parameters"] = {"length": 7.0}

    with pytest.raises(ValueError, match="literal|bound|parameter"):
        _registry(_valid_components(compound))


def test_registry_requires_pinned_nested_component_for_recursive_lowering():
    compound = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "nested", "parameter_id": "length"}],
    }])
    compound["compound"]["body"]["nodes"] = [{
        "node_id": "nested",
        "component": {"component_id": "compound.missing", "component_version": 1},
        "parameters": {},
    }]

    with pytest.raises(ValueError, match="unknown|missing|component|closure"):
        _registry(_valid_components(compound))


def test_registry_rejects_transitive_missing_nested_component_closure():
    leaf = _component("indicator.scale")
    nested = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    nested["component_id"] = "compound.nested"
    nested["compound"]["body"]["nodes"][0]["component"] = {
        "component_id": "component.missing",
        "component_version": 1,
    }
    outer = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    outer["component_id"] = "compound.outer"
    outer["compound"]["body"]["nodes"][0]["component"] = {
        "component_id": "compound.nested",
        "component_version": 1,
    }

    with pytest.raises(ValueError, match="closure|missing|component"):
        _registry({
            ("indicator.scale", 1): leaf,
            ("compound.nested", 1): nested,
            ("compound.outer", 1): outer,
        })


def test_registry_rejects_compound_reference_cycle():
    first = _compound(bindings=[{
        "parameter_id": "length",
        "targets": [{"node_id": "scale", "parameter_id": "length"}],
    }])
    first["component_id"] = "compound.first"
    second = deepcopy(first)
    second["component_id"] = "compound.second"
    first["compound"]["body"]["nodes"][0]["component"] = {
        "component_id": "compound.second", "component_version": 1,
    }
    second["compound"]["body"]["nodes"][0]["component"] = {
        "component_id": "compound.first", "component_version": 1,
    }

    with pytest.raises(ValueError, match="cycle"):
        _registry({
            ("compound.first", 1): first,
            ("compound.second", 1): second,
        })


@pytest.mark.parametrize("preset,fields", [
    ("trend_impulse_v3", {"CLOSE"}), ("expanding_z_v4", {"CLOSE", "HIGH", "LOW"}),
])
def test_original_presets_bind_canonical_data_and_research_only_contracts(preset, fields):
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.resolve import resolve_v2
    from app.market_data.requirements import compile_data_requirement_plan, DataRequirementRefusal
    from tests.test_strategy_registry import _original_preset_registry
    from tests.test_indicator_accuracy_contract_assurance import context, input_facts

    registry = _original_preset_registry()
    document = instantiate_preset(preset, "bound-original")
    graph = resolve_v2(document, registry)
    fact = input_facts()["price_feed"]
    fact["fields"] = sorted(fields)
    fact["timeframe"] = 86400
    bindings = context({"frame": fact})
    plan = compile_data_requirement_plan(graph, registry=registry, input_bindings=bindings)
    assert {row["requirement"]["field"] for row in plan.requirements} == fields
    assert {row["requirement"]["timeframe"] for row in plan.requirements} == {86400}
    assert all(node.declaration_address for node in graph.nodes)
    assert all(registry.node_contracts[node.component]["mode_eligibility"] == {
        "research": True, "paper": False, "live": False} for node in graph.nodes)
    with pytest.raises(DataRequirementRefusal):
        compile_data_requirement_plan(graph, registry=registry)
    copy = instantiate_preset(preset, "another-original")
    copy["nodes"][0]["parameters"]["ema_length"] = 10
    assert instantiate_preset(preset, "fresh")["nodes"][0]["parameters"]["ema_length"] == 50


@pytest.mark.parametrize("preset", ["trend_impulse_v3", "expanding_z_v4"])
def test_original_presets_existing_incremental_prefix_path_matches_batch(preset):
    from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract
    from app.ir.incremental_runtime import CancellationToken, _evaluate_cancellable_prefixes
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.market_data.requirements import compile_data_requirement_plan
    from tests.test_strategy_registry import _original_preset_registry, _synthetic
    from tests.test_indicator_accuracy_contract_assurance import context, input_facts

    registry = _original_preset_registry()
    document = instantiate_preset(preset, "prefix-original")
    parameters = document["nodes"][0]["parameters"]
    parameters.update({"ema_length": 3, "z_length": 3, "slope_lookback": 1})
    if preset == "expanding_z_v4":
        parameters.update({"adapt_length": 5, "atr_length": 3})
    graph = resolve_v2(document, registry)
    fact = input_facts()["price_feed"]
    fact["fields"] = ["CLOSE", "HIGH", "LOW", "OPEN"]
    plan = compile_data_requirement_plan(graph, registry=registry, input_bindings=context({"frame": fact}))
    receipts = {tuple(row["lowered_path"]): row["node_contract_binding"]
                for row in plan.parameter_binding_provenance if "node_contract_binding" in row}

    def source_context(node, inputs):
        row = receipts.get(tuple(node.lowered_path))
        return None if row is None else {"bound_contract": ResolvedNodeContract(row, row["bound_contract_address"])}

    frame = _synthetic(24).set_index("date")
    inputs = {"frame": dict(frame.items())}
    batch = evaluate_v2(graph, inputs, registry, evaluation_context_resolver=source_context)
    incremental = _evaluate_cancellable_prefixes(graph, inputs, registry, CancellationToken(), frame.index,
                                                 evaluation_context_resolver=source_context)
    assert {name: values.tolist() for name, values in batch.items()} == {
        name: values.tolist() for name, values in incremental.items()}


@pytest.mark.parametrize("preset,fanout", [("trend_impulse_v3", 7), ("expanding_z_v4", 10)])
def test_original_presets_compile_real_research_resource_admission(preset, fanout):
    from app.ir.incremental_runtime import accept_research_resource_plan
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.resolve import resolve_v2
    from app.market_data.requirements import compile_data_requirement_plan
    from tests.test_strategy_registry import _original_preset_registry
    from tests.test_indicator_accuracy_contract_assurance import context, input_facts
    registry = _original_preset_registry()
    graph = resolve_v2(instantiate_preset(preset, "original-resource-plan"), registry)
    fact = input_facts()["price_feed"]
    fact["fields"] = ["CLOSE", "HIGH", "LOW", "OPEN"]
    binding = context({"frame": fact})
    data = compile_data_requirement_plan(graph, registry=registry, input_bindings=binding)
    admitted = accept_research_resource_plan(graph, data, registry, input_bindings=binding)
    assert admitted.plan.document["maximum_single_output_fanout"] == fanout
    assert admitted.plan.document["lowered_node_count"] == len(graph.nodes)
    assert admitted.plan.document["mode_support"] == {"research": True, "paper": False, "live": False}


def _shared_original_output(readers):
    from app.ir import original_strategy_presets as presets
    document = presets.instantiate_preset("trend_impulse_v3", "bounded-shared-output")
    document["nodes"] = [presets._node("close", "close")]
    document["edges"] = [presets._edge("input", "$input", "frame", "close", "frame")]
    document["graph_outputs"] = []
    for index in range(readers):
        name = f"reader{index}"
        document["nodes"].append(presets._node(name, "abs"))
        document["edges"].extend([
            presets._edge(name + ".input", "close", "value", name, "source"),
            presets._edge(name + ".output", name, "value", "$output", name),
        ])
        document["graph_outputs"].append({
            **presets._port(presets._primitive("abs"), "value"), "port_id": name,
        })
    return document


@pytest.mark.parametrize("readers", [31, 32, 33])
def test_original_output_fanout_bound_is_enforced_and_shared_values_are_unchanged(readers):
    from app.ir.incremental_runtime import accept_research_resource_plan, IncrementalRuntimeRefusal
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.market_data.requirements import compile_data_requirement_plan
    from app.ir.first_party.analytical_v2 import contracts
    from tests.test_strategy_registry import _original_preset_registry, _synthetic
    from tests.test_indicator_accuracy_contract_assurance import context, input_facts
    registry = _original_preset_registry()
    graph = resolve_v2(_shared_original_output(readers), registry)
    binding = context({"frame": input_facts()["price_feed"]})
    data = compile_data_requirement_plan(graph, registry=registry, input_bindings=binding)
    if readers == 33:
        with pytest.raises(IncrementalRuntimeRefusal, match="ResourcePlan inputs did not compile"):
            accept_research_resource_plan(graph, data, registry, input_bindings=binding)
        return
    admitted = accept_research_resource_plan(graph, data, registry, input_bindings=binding)
    assert admitted.plan.document["maximum_single_output_fanout"] == readers
    bound = {tuple(row["lowered_path"]): row["node_contract_binding"]
             for row in data.parameter_binding_provenance if "node_contract_binding" in row}
    def source_context(node, _inputs):
        value = bound.get(tuple(node.lowered_path))
        return None if value is None else {"bound_contract": contracts.ResolvedNodeContract(value, value["bound_contract_address"])}
    frame = _synthetic(8).set_index("date")
    outputs = evaluate_v2(graph, {"frame": dict(frame.items())}, registry, evaluation_context_resolver=source_context)
    assert len(outputs) == readers
    for output in outputs.values():
        assert [cell.value for cell in output] == frame["close"].abs().tolist()
