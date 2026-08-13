"""Structural causal admission rejects incomplete evidence before parity."""
from __future__ import annotations

import dataclasses
import json
from types import MappingProxyType

import pandas as pd
import numpy as np
import pytest

from app.ir.causal import HistoryBound, causal_contract
from app.ir.contributors.generated_blocks import BLOCK_COMPONENTS, REGISTRATIONS
from app.ir.hashing import canonical_json, content_address
from app.ir.library import REGISTRY
from app.ir.registry import DependencyBoundary, KernelRegistration, PlatformRegistry
from app.ir.resolve import BOUNDARY_INPUT, BOUNDARY_OUTPUT
from app.ir.strategies.expanding_z import GRAPH
from app.strategy.registry.expanding_z_v4 import ExpandingZImpulseV4
from app.strategy.admission import (
    AdmittedKernelIdentity,
    AdmissionRefusalCode,
    AdmissionRefused,
    HandwrittenAdapterInput,
    IRGraphAdmissionInput,
    InputProvenance,
    ParityEvidence,
    ResolvedComponentIdentity,
    SourceEvidence,
    StructuralAdmission,
    admitted_artifact,
    canonical_decisions,
    inspect_strategy,
)


def test_refusal_vocabulary_is_closed_and_stable():
    assert {code.value for code in AdmissionRefusalCode} == {
        "IR_INVALID",
        "RESOLUTION_FAILED",
        "CONTRACT_MISSING",
        "CONTRACT_INVALID",
        "COMPONENT_QUARANTINED",
        "INPUT_UNDECLARED",
        "CONTEXT_UNDECLARED",
        "EXTERNAL_SERIES_UNRESOLVED",
        "IMPURE_KERNEL",
        "IMPLEMENTATION_UNIDENTIFIED",
        "IMPLEMENTATION_STALE",
        "HISTORY_INVALID",
        "OUTPUT_DELAY_INVALID",
        "OUTPUT_MAPPING_INVALID",
        "STREAMING_DIVERGENCE",
        "VECTOR_EVALUATION_FAILED",
        "REFERENCE_EVALUATION_FAILED",
        "OWNER_SCOPE_INVALID",
        "ARTEFACT_MISMATCH",
        "RECEIPT_STALE",
    }


def _structural(owner_id: str) -> StructuralAdmission:
    return StructuralAdmission(
        owner_id=owner_id,
        source="ir_graph",
        source_evidence=SourceEvidence("ir_graph", "graph.test", "1", None, None),
        graph_identifier="graph.test",
        graph_version=1,
        graph_address="sha256:" + "1" * 64,
        resolved_components=(ResolvedComponentIdentity(
            "n", "indicator.test", 1, "sha256:" + "2" * 64, {"length": 2}),),
        input_provenance=(InputProvenance(
            "n", "source", ("close",), (("$input.close", "n.source"),)),),
        bound_parameters={"length": 2},
        kernels=(AdmittedKernelIdentity(
            "sha256:" + "2" * 64,
            "sha256:" + "3" * 64,
            {"history": {"mode": "bounded", "constant": 2, "terms": []}},
            2,
        ),),
        canonical_mapping={"longEntry": "signal"},
        declared_warmup=2,
        risk_model=None,
    )


def test_owner_is_hashed_and_canonical_evidence_is_deeply_immutable():
    first = admitted_artifact(
        _structural("owner-a"),
        ParityEvidence("sha256:" + "4" * 64,
                       "sha256:" + "5" * 64, "sha256:" + "5" * 64),
    )
    second = admitted_artifact(
        _structural("owner-b"),
        ParityEvidence("sha256:" + "4" * 64,
                       "sha256:" + "5" * 64, "sha256:" + "5" * 64),
    )

    assert first.admission_address != second.admission_address
    assert first.to_dict()["owner_id"] == "owner-a"
    with pytest.raises(TypeError):
        first.bound_parameters["length"] = 99
    with pytest.raises(TypeError):
        first.kernels[0].causal_contract["history"]["constant"] = 99


def test_unequal_parity_addresses_refuse_without_hashing_exception_text():
    with pytest.raises(AdmissionRefused) as raised:
        admitted_artifact(
            _structural("owner-a"),
            ParityEvidence("sha256:" + "4" * 64,
                           "sha256:" + "5" * 64, "sha256:" + "6" * 64),
        )
    assert raised.value.code is AdmissionRefusalCode.STREAMING_DIVERGENCE
    assert "detail" not in _structural("owner-a").to_dict()


def test_direct_final_artifact_construction_cannot_bypass_parity_equality():
    artifact = admitted_artifact(
        _structural("owner-a"),
        ParityEvidence("sha256:" + "4" * 64,
                       "sha256:" + "5" * 64, "sha256:" + "5" * 64),
    )

    with pytest.raises(AdmissionRefused) as raised:
        dataclasses.replace(artifact, vector_decision_address="sha256:" + "6" * 64)
    assert raised.value.code is AdmissionRefusalCode.STREAMING_DIVERGENCE


def test_canonical_decisions_bind_utc_timestamps_and_fixed_boolean_columns():
    index = pd.DatetimeIndex([
        "2026-08-13 09:15:00+05:30", "2026-08-13 09:20:00+05:30"])
    frame = pd.DataFrame({
        "shortExit": [False, True], "longEntry": [True, False],
        "longExit": [False, False], "shortEntry": [False, True],
    }, index=index)

    assert canonical_decisions(frame) == canonical_decisions(
        frame[["shortEntry", "longExit", "longEntry", "shortExit"]])
    assert canonical_decisions(frame).decode() == (
        '[[1786592700000000000,true,false,false,false],'
        '[1786593000000000000,false,true,false,true]]')

    with pytest.raises(AdmissionRefused) as raised:
        canonical_decisions(frame.reset_index(drop=True))
    assert raised.value.code is AdmissionRefusalCode.ARTEFACT_MISMATCH


def _wire(value: str) -> dict:
    return {"value": value, "structure": "series",
            "domain": {"instrument": "*", "timeframe": "*"}}


def _socket(name: str, direction: str, value: str) -> dict:
    return {"item": "socket", "identifier": name, "display_name": name,
            "direction": direction, "wire_type": _wire(value)}


def _node(instance: str, identifier: str, overrides=None) -> dict:
    return {"instance_id": instance,
            "component": {"identifier": identifier, "version": 1},
            "overrides": overrides or {}}


def _edge(source: str, source_socket: str, target: str, target_socket: str) -> dict:
    return {"source": {"instance": source, "socket": source_socket},
            "target": {"instance": target, "socket": target_socket}}


@pytest.fixture(scope="module")
def nested_case():
    block = BLOCK_COMPONENTS["roc_gt"]
    body = {
        "format_version": 1, "kind": "graph", "identifier": "nested.body",
        "version": 1, "display_name": "Nested body",
        "interface": [_socket("close", "input", "float"),
                      _socket("signal", "output", "bool")],
        "nodes": [_node("io_in", BOUNDARY_INPUT),
                  _node("z", "block.roc_gt", {"length": 2, "thr": 0.0}),
                  _node("io_out", BOUNDARY_OUTPUT)],
        "edges": [_edge("io_in", "close", "z", "close"),
                  _edge("z", "out", "io_out", "signal")],
        "groups": [],
    }
    body_ref = content_address(body)
    nested = {
        "format_version": 1, "kind": "component", "identifier": "nested.signal",
        "version": 1, "display_name": "Nested signal", "interface": body["interface"],
        "body": {"body": "graph", "ref": body_ref},
    }
    graph = {
        "format_version": 1, "kind": "graph", "identifier": "strategy.nested",
        "version": 1, "display_name": "Nested strategy",
        "interface": [_socket("close", "input", "float"),
                      _socket("longEntry", "output", "bool")],
        "nodes": [_node("io_in", BOUNDARY_INPUT), _node("nested", "nested.signal"),
                  _node("io_out", BOUNDARY_OUTPUT)],
        "edges": [_edge("io_in", "close", "nested", "close"),
                  _edge("nested", "signal", "io_out", "longEntry")],
        "groups": [],
    }
    registration = REGISTRATIONS[block.body_ref]
    registry = PlatformRegistry(
        components={("block.roc_gt", 1): block.definition,
                    ("nested.signal", 1): nested},
        bodies={body_ref: body}, registrations={block.body_ref: registration})
    return graph, registry, registration


def _replace_registration(registry: PlatformRegistry, old: KernelRegistration,
                          replacement: KernelRegistration) -> PlatformRegistry:
    return PlatformRegistry(
        components=registry.library.components,
        bodies=registry.library.bodies,
        registrations={old.body_ref: replacement},
    )


def test_structural_inspection_derives_nested_provenance_from_real_registry(nested_case):
    graph, registry, _ = nested_case
    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=registry)

    assert decision.refusal_code is None
    structural = decision.structural
    assert structural is not None
    assert structural.graph_address == content_address(graph)
    assert structural.canonical_mapping == {"longEntry": "longEntry"}
    source = next(item for item in structural.input_provenance
                  if item.node_path == "nested/z" and item.socket == "close")
    assert source.root_market_inputs == ("close",)
    assert source.source_paths == (("$input.close", "nested.input", "nested/z.close"),)


def test_reached_nested_body_must_validate_against_its_published_interface(nested_case):
    graph, registry, registration = nested_case
    body = json.loads(canonical_json(next(iter(registry.library.bodies.values()))))
    body["interface"][0]["wire_type"]["value"] = "bool"
    body_ref = content_address(body)
    nested = json.loads(canonical_json(
        registry.library.components[("nested.signal", 1)]))
    nested["body"]["ref"] = body_ref
    changed = PlatformRegistry(
        components={
            ("block.roc_gt", 1): BLOCK_COMPONENTS["roc_gt"].definition,
            ("nested.signal", 1): nested,
        },
        bodies={body_ref: body},
        registrations={registration.body_ref: registration},
    )

    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=changed)

    assert decision.structural is None
    assert decision.refusal_code is AdmissionRefusalCode.IR_INVALID


def test_nested_graph_body_address_is_bound_into_structural_evidence(nested_case):
    graph, registry, registration = nested_case
    body = json.loads(canonical_json(next(iter(registry.library.bodies.values()))))
    body["display_name"] = "Same semantics, new immutable body"
    body_ref = content_address(body)
    nested = json.loads(canonical_json(
        registry.library.components[("nested.signal", 1)]))
    nested["body"]["ref"] = body_ref
    changed = PlatformRegistry(
        components={
            ("block.roc_gt", 1): BLOCK_COMPONENTS["roc_gt"].definition,
            ("nested.signal", 1): nested,
        },
        bodies={body_ref: body},
        registrations={registration.body_ref: registration},
    )

    original = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=registry).structural
    revised = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=changed).structural

    assert original is not None and revised is not None
    original_nested = next(item for item in original.resolved_components
                           if item.node_path == "nested")
    revised_nested = next(item for item in revised.resolved_components
                          if item.node_path == "nested")
    assert original_nested.body_ref != revised_nested.body_ref
    assert original.to_dict() != revised.to_dict()


def test_self_referential_graph_component_refuses_as_resolution_cycle():
    body = {
        "format_version": 1, "kind": "graph", "identifier": "cycle.body",
        "version": 1, "display_name": "Cycle body", "interface": [],
        "nodes": [_node("again", "cycle.component")], "edges": [], "groups": [],
    }
    body_ref = content_address(body)
    component = {
        "format_version": 1, "kind": "component", "identifier": "cycle.component",
        "version": 1, "display_name": "Cycle component", "interface": [],
        "body": {"body": "graph", "ref": body_ref},
    }
    graph = {
        "format_version": 1, "kind": "graph", "identifier": "strategy.cycle",
        "version": 1, "display_name": "Cyclic strategy", "interface": [],
        "nodes": [_node("cycle", "cycle.component")], "edges": [], "groups": [],
    }
    registry = PlatformRegistry(
        components={("cycle.component", 1): component},
        bodies={body_ref: body}, registrations={})

    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=registry)

    assert decision.structural is None
    assert decision.refusal_code is AdmissionRefusalCode.RESOLUTION_FAILED


def test_missing_contract_refuses_before_parity(nested_case):
    graph, registry, registration = nested_case
    missing = dataclasses.replace(
        registration, spec=dataclasses.replace(registration.spec, causal=None))
    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=_replace_registration(registry, registration, missing))

    assert decision.structural is None
    assert decision.refusal_code is AdmissionRefusalCode.CONTRACT_MISSING


@pytest.mark.parametrize(
    "sockets, expected",
    [((), AdmissionRefusalCode.INPUT_UNDECLARED),
     (("close", "ghost"), AdmissionRefusalCode.CONTRACT_INVALID)],
)
def test_missing_or_extra_contract_socket_refuses(nested_case, sockets, expected):
    graph, registry, registration = nested_case
    changed_contract = causal_contract(
        node_input_sockets=sockets, history=HistoryBound("bounded", constant=1,
                                                         terms=registration.spec.causal.history.terms))
    changed = dataclasses.replace(
        registration, spec=dataclasses.replace(registration.spec, causal=changed_contract))
    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=_replace_registration(registry, registration, changed))

    assert decision.structural is None
    assert decision.refusal_code is expected


def test_stale_registration_refuses_before_parity(nested_case):
    graph, registry, registration = nested_case

    def changed_kernel(params, node_inputs, context_inputs):
        return {"out": node_inputs["close"] > 0}

    stale = dataclasses.replace(
        registration,
        implementation=changed_kernel,
        dependency_boundary=DependencyBoundary("declared_objects"),
    )
    object.__setattr__(registry, "_registrations", MappingProxyType({
        registration.body_ref: stale}))
    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=registry)

    assert decision.structural is None
    assert decision.refusal_code is AdmissionRefusalCode.IMPLEMENTATION_STALE
    object.__setattr__(registry, "_registrations", MappingProxyType({
        registration.body_ref: registration}))


def test_shipped_expanding_z_graph_reaches_structural_admission():
    decision = inspect_strategy(
        owner_id="owner-a", source_input=IRGraphAdmissionInput(GRAPH, {}, None),
        registry=REGISTRY)

    assert decision.refusal_code is None
    assert decision.structural is not None
    assert decision.structural.graph_identifier == GRAPH["identifier"]
    assert decision.structural.declared_warmup > 0


def test_handwritten_adapter_cannot_claim_another_key_or_version():
    decision = inspect_strategy(
        owner_id="owner-a",
        source_input=HandwrittenAdapterInput(
            strategy_key="another_strategy",
            strategy_version="not-the-v4-version",
            adapter_implementation=ExpandingZImpulseV4,
            adapter_dependencies=DependencyBoundary("defining_module", (np, pd)),
            equivalent_ir=IRGraphAdmissionInput(GRAPH, {}, None),
        ),
        registry=REGISTRY,
    )

    assert decision.structural is None
    assert decision.refusal_code is AdmissionRefusalCode.ARTEFACT_MISMATCH


def test_handwritten_adapter_records_exact_executable_identity_and_equivalent_ir():
    adapter = ExpandingZImpulseV4()
    decision = inspect_strategy(
        owner_id="owner-a",
        source_input=HandwrittenAdapterInput(
            strategy_key=adapter.key,
            strategy_version=adapter.version,
            adapter_implementation=ExpandingZImpulseV4,
            adapter_dependencies=DependencyBoundary("defining_module", (np, pd)),
            equivalent_ir=IRGraphAdmissionInput(GRAPH, {}, None),
        ),
        registry=REGISTRY,
    )

    assert decision.refusal_code is None
    assert decision.structural is not None
    assert decision.structural.source == "handwritten_adapter"
    assert decision.structural.source_evidence.strategy_key == adapter.key
    assert decision.structural.source_evidence.strategy_version == adapter.version
    assert decision.structural.source_evidence.adapter_implementation_address.startswith(
        "sha256:")
    assert decision.structural.graph_address == content_address(GRAPH)
