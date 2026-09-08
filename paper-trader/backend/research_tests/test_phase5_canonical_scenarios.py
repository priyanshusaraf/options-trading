from __future__ import annotations

import pandas as pd
import pytest

from app.ir.first_party.conformance import reference_frame
from app.ir.hashing import content_address
from app.ir.incremental_runtime import accept_research_resource_plan
from app.ir.library import REGISTRY
from app.ir.resolve import resolve_v2
from app.market_data.requirements import compile_data_requirement_plan
from research.evaluation.phase5_runtime import (
    ResearchExecutionRefusal,
    execute_research,
    research_evaluation_policy,
)
from research_tests.test_phase5_research_execution import (
    _accepted_type3_fact,
    _boundary_port,
    _dataset_inputs,
    _plain_policy,
    _policy,
    _single_production_runtime,
)
from tests.test_phase5_canonical_scenarios import _scenario_inputs
from tests.test_phase5_state_execution_derivatives_catalogue import (
    _derivative_fact,
    _generic_input,
    _rehash_fact,
    _type5_input,
)


def _parallel_analytical_graph():
    components = (
        ("ema", ("analytical.ema", 1)),
        ("rsi", ("analytical.rsi", 1)),
        ("atr", ("analytical.atr", 1)),
    )
    input_template = next(
        port for port in REGISTRY.v2_components[components[0][1]]["ports"]
        if port["direction"] == "input"
    )
    graph_inputs = [_boundary_port("frame", "input", template=input_template)]
    graph_outputs, nodes, edges = [], [], []
    for name, key in components:
        component = REGISTRY.v2_components[key]
        input_port = next(port for port in component["ports"] if port["direction"] == "input")
        output_port = next(port for port in component["ports"] if port["direction"] == "output")
        if name != "rsi":
            graph_outputs.append(_boundary_port(
                f"{name}_value", "output", template=output_port,
            ))
        nodes.append({
            "node_id": name,
            "component": {"component_id": key[0], "component_version": key[1]},
            "parameters": {"window": 1, "capability_verified": False},
        })
        edges.extend((
            {"edge_id": f"frame-to-{name}", "source": {
                "scope": "graph_input", "port_id": "frame",
            }, "target": {"scope": "node", "node_id": name,
                           "port_id": input_port["port_id"]},
             "binding": {"kind": "single"}},
        ))
        if name != "rsi":
            edges.append({"edge_id": f"{name}-to-output", "source": {
                "scope": "node", "node_id": name, "port_id": output_port["port_id"],
            }, "target": {"scope": "graph_output", "port_id": f"{name}_value"},
             "binding": {"kind": "single"}})
    return resolve_v2({
        "format_version": 2,
        "strategy_id": "phase5-scenario-a-ema-rsi-atr",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Scenario A",
                     "description": None, "tags": ["phase5", "scenario-a"]},
        "graph_inputs": graph_inputs, "graph_outputs": graph_outputs,
        "nodes": nodes, "edges": edges,
    }, REGISTRY)


def test_scenario_a_one_immutable_ema_rsi_atr_graph_executes_batch_and_incremental():
    graph = _parallel_analytical_graph()
    roles, providers = _scenario_inputs("A")
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), REGISTRY,
        instrument_roles=roles, provider_requirements=providers,
        cache_bytes_upper_bound=128 * 1024,
        artifact_bytes_upper_bound=128 * 1024,
        queue_concurrency_upper_bound=2,
    )
    frame = reference_frame(40)
    dataset = _dataset_inputs(length=40, inputs={"frame": frame})
    policy = _policy(graph, REGISTRY, plan, dataset, maximum_events=40)
    result = execute_research(graph, REGISTRY, plan, dataset, policy)
    assert result.document["status"] == "COMPLETED"
    assert set(result.batch_outputs) == {"ema_value", "atr_value"}
    assert "analytical.rsi@1" in result.document["node_components"]
    for name in result.batch_outputs:
        pd.testing.assert_series_equal(
            result.batch_outputs[name], result.incremental_outputs[name],
        )
    assert result.document["resolved_graph_address"] == graph.resolved_graph_address
    assert result.document["resource_plan_address"] == plan.plan_address
    assert len({graph.resolved_graph_address for _role in roles}) == 1


@pytest.mark.parametrize("name", ("PCR_OPEN_INTEREST", "DEPTH_IMBALANCE"))
def test_scenario_b_weekly_option_and_order_flow_use_accepted_point_in_time_facts(name):
    fact = _accepted_type3_fact(name)
    runtime = _single_production_runtime(
        (f"derivative.{name.lower()}", 1), fact,
        parameters={"maximum_members": 3},
    )
    result = execute_research(*runtime)
    assert result.document["status"] == "COMPLETED"
    assert result.document["event_count"] == 1
    assert result.batch_outputs["value"] == result.incremental_outputs["value"]
    assert result.document["evaluation_policy_address"] == runtime[-1].policy_address


def test_scenario_b_weekday_schedule_and_broker_protection_remain_pure_intent():
    weekday = _type5_input("WEEKDAY_GATE")
    schedule_runtime = _single_production_runtime(
        ("logic.weekday_gate", 1), weekday, maximum_events=4,
    )
    schedule = execute_research(*schedule_runtime)
    assert schedule.batch_outputs["value"] == schedule.incremental_outputs["value"]
    protection_runtime = _single_production_runtime(
        ("intent.broker_resident_protection_request", 1), _generic_input(),
        parameters={"entry_blocked": False}, maximum_events=4,
    )
    protection = execute_research(*protection_runtime)
    description = protection.batch_outputs["value"]
    assert description == protection.incremental_outputs["value"]
    assert description["schema"] == "execution-intent-description/1"
    assert not any(key in description for key in ("broker_id", "order_id", "credential"))


def test_scenario_b_overwide_weekly_window_refuses_before_result():
    fact = _derivative_fact(
        "PCR_OPEN_INTEREST", members=4, maximum_members=3,
    )
    fact["event_time"] = "2026-01-01T00:01:00+00:00"
    fact["knowledge_time"] = "2026-01-01T00:02:00+00:00"
    fact["evaluation_cutoff"] = "2026-01-01T00:03:00+00:00"
    _rehash_fact(fact)
    runtime = _single_production_runtime(
        ("derivative.pcr_open_interest", 1), fact,
        parameters={"maximum_members": 3},
    )
    with pytest.raises(ResearchExecutionRefusal):
        execute_research(*runtime)


def _cross_market_graph():
    keys = (("correlation", ("analytical.correlation", 1)),
            ("ema", ("analytical.ema", 1)))
    first = REGISTRY.v2_components[keys[0][1]]
    input_port = next(port for port in first["ports"] if port["direction"] == "input")
    ema_output = next(
        port for port in REGISTRY.v2_components[keys[1][1]]["ports"]
        if port["direction"] == "output"
    )
    nodes, edges = [], []
    for name, key in keys:
        target = next(
            port for port in REGISTRY.v2_components[key]["ports"]
            if port["direction"] == "input"
        )
        nodes.append({
            "node_id": name,
            "component": {"component_id": key[0], "component_version": 1},
            "parameters": {"window": 1, "capability_verified": False},
        })
        edges.append({"edge_id": f"frame-to-{name}", "source": {
            "scope": "graph_input", "port_id": "frame",
        }, "target": {"scope": "node", "node_id": name,
                       "port_id": target["port_id"]},
         "binding": {"kind": "single"}})
    edges.append({"edge_id": "ema-to-output", "source": {
        "scope": "node", "node_id": "ema", "port_id": ema_output["port_id"],
    }, "target": {"scope": "graph_output", "port_id": "value"},
     "binding": {"kind": "single"}})
    return resolve_v2({
        "format_version": 2, "strategy_id": "phase5-scenario-c-cross-market",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Scenario C",
                     "description": None, "tags": ["phase5", "scenario-c"]},
        "graph_inputs": [_boundary_port("frame", "input", template=input_port)],
        "graph_outputs": [_boundary_port("value", "output", template=ema_output)],
        "nodes": nodes, "edges": edges,
    }, REGISTRY)


def test_scenario_c_cross_market_frame_executes_with_exact_alignment_policy():
    graph = _cross_market_graph()
    roles, providers = _scenario_inputs("C")
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), REGISTRY,
        instrument_roles=roles, provider_requirements=providers,
        queue_concurrency_upper_bound=2,
    )
    frame = {name: values.copy(deep=True) for name, values in reference_frame(40).items()}
    frame["peer"] = frame["close"].shift(1).bfill()
    dataset = _dataset_inputs(length=40, inputs={"frame": frame})
    policy = _policy(graph, REGISTRY, plan, dataset, maximum_events=40)
    result = execute_research(graph, REGISTRY, plan, dataset, policy)
    assert result.document["status"] == "COMPLETED"
    pd.testing.assert_series_equal(
        result.batch_outputs["value"], result.incremental_outputs["value"],
    )
    assert "analytical.correlation@1" in result.document["node_components"]
    assert policy.document["alignment_policy_address"] \
        == dataset.manifest.alignment_policy_address
    assert policy.document["missing_data_policy_address"] \
        == dataset.manifest.missing_data_policy_address


@pytest.mark.parametrize("mutation", ("alignment", "truth", "binding"))
def test_scenario_c_wrong_alignment_truth_or_binding_refuses(mutation):
    graph = _cross_market_graph()
    roles, providers = _scenario_inputs("C")
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), REGISTRY,
        instrument_roles=roles, provider_requirements=providers,
        queue_concurrency_upper_bound=2,
    )
    frame = {name: values.copy(deep=True) for name, values in reference_frame(20).items()}
    dataset = _dataset_inputs(length=20, inputs={"frame": frame})
    policy = _policy(graph, REGISTRY, plan, dataset, maximum_events=20)
    assert execute_research(graph, REGISTRY, plan, dataset, policy).document["status"] \
        == "COMPLETED"
    document = _plain_policy(policy.document)
    if mutation == "alignment":
        document["alignment_policy_address"] = content_address({"wrong": "alignment"})
    elif mutation == "truth":
        document["truth_snapshot_addresses"] = [content_address({"wrong": "truth"})]
    else:
        document["input_bindings"]["frame"]["instrument_address"] = \
            content_address({"wrong": "instrument"})
    document.pop("evaluation_policy_address")
    document["evaluation_policy_address"] = content_address(document)
    changed = research_evaluation_policy(document)
    with pytest.raises(ResearchExecutionRefusal):
        execute_research(graph, REGISTRY, plan, dataset, changed)
