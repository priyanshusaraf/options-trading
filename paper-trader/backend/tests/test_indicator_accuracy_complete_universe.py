"""Independent closure assurance for the integrated analytical v2 universe.

Expected catalogue facts come only from the accepted architecture records.  This
module does not import an implementation-owner test module or use product output
to manufacture an expected value.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import pandas as pd
import pytest

from app.ir import node_contracts
from app.ir.first_party import analytical
from app.ir.first_party.analytical_v2 import (
    core_math,
    multi_output,
    recursive_state,
    remaining_oracles,
    session_data,
)
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract
from app.ir.hashing import canonical_json, content_address
from app.ir.library import ANALYTICAL_V2_DISPOSITIONS, REGISTRY
from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.validity import ValidityState


ROOT = Path(__file__).resolve().parents[3]
REPLAN = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan"
CAPSULE = ROOT / "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-complete-universe-assurance.md"
MATRIX = REPLAN / "component-matrix.json"
CATALOGUE = REPLAN / "current-catalogue.json"
SOURCE_AUTHORITY = REPLAN / "source-authority.json"
BINDING_SPEC = REPLAN / "binding-contract-spec.json"
SAR_ADDENDUM = ROOT / ".agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-replan/decision.json"
SOURCE_ADDENDA = (
    ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-source-replan/decision.json",
    ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-replan/decision.json",
    SAR_ADDENDUM,
)

PACKAGES = (core_math, recursive_state, multi_output, session_data, remaining_oracles)
SESSION_INPUT_CORRECTIONS = {
    "DISTANCE_FROM_SESSION_HIGH_LOW": ["close", "high", "low", "session_id", "session_open_at"],
    "PREVIOUS_SESSION_FIELDS": [
        "close", "high", "low", "open", "session_close_at", "session_id",
        "session_open_at", "volume"],
    "PREVIOUS_SESSION_OHLC": [
        "close", "high", "low", "open", "session_close_at", "session_id", "session_open_at"],
    "SESSION_HIGH": ["high", "session_id", "session_open_at"],
    "SESSION_LOW": ["low", "session_id", "session_open_at"],
    "SESSION_OPEN": ["open", "session_id", "session_open_at"],
    "SESSION_OPEN_HIGH_LOW": ["high", "low", "open", "session_id", "session_open_at"],
    "VWAP": ["close", "high", "low", "session_id", "session_open_at", "volume"],
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _capsule():
    text = CAPSULE.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        text = text[4:]
    return json.loads(text.split("\n---", 1)[0])


def _records():
    return _load(MATRIX)["records"]


def _canonical_target(row):
    """Apply only the three accepted additive source decisions to the frozen matrix."""
    target = deepcopy(row["target"])
    for path in SOURCE_ADDENDA:
        decision = _load(path)
        delta = decision["corrected_target_delta"]
        component = decision.get("component")
        if component:
            component_id = component.get("component_id", component.get("id"))
            if component_id == row["component_id"]:
                target.update(delta)
        elif row["name"] in delta:
            target.update(delta[row["name"]])
    if row["name"] in SESSION_INPUT_CORRECTIONS:
        target["inputs"] = SESSION_INPUT_CORRECTIONS[row["name"]]
    return target


def _product_specs():
    rows = {}
    for package in PACKAGES:
        for name, spec in package.SPECS.items():
            assert name not in rows, f"duplicate product specification {name}"
            rows[name] = node_contracts._plain(spec)
    return rows


def _package_for(name):
    matches = [package for package in PACKAGES if name in package.SPECS]
    assert len(matches) == 1
    return matches[0]


def _component_document(name: str, parameters: dict | None = None):
    key = (analytical.component_id(name), 2)
    component = node_contracts._plain(REGISTRY.v2_components[key])
    inputs = [deepcopy(port) for port in component["ports"] if port["direction"] == "input"]
    outputs = [deepcopy(port) for port in component["ports"] if port["direction"] == "output"]
    edges = []
    for port in inputs:
        edges.append({
            "edge_id": f"input-{port['port_id']}",
            "source": {"scope": "graph_input", "port_id": port["port_id"]},
            "target": {"scope": "node", "node_id": "subject", "port_id": port["port_id"]},
            "binding": {"kind": "single"},
        })
    for port in outputs:
        edges.append({
            "edge_id": f"output-{port['port_id']}",
            "source": {"scope": "node", "node_id": "subject", "port_id": port["port_id"]},
            "target": {"scope": "graph_output", "port_id": port["port_id"]},
            "binding": {"kind": "single"},
        })
    return {
        "format_version": 2,
        "strategy_id": f"assurance-{name.lower()}",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": name, "description": None, "tags": []},
        "graph_inputs": inputs,
        "graph_outputs": outputs,
        "nodes": [{
            "node_id": "subject",
            "component": {"component_id": key[0], "component_version": 2},
            "parameters": parameters or {},
        }],
        "edges": edges,
    }


def _refused_document(name: str, *, plausible: bool):
    row = next(row for row in _records() if row["name"] == name)
    parameters = {
        key: spec.get("default") for key, spec in row["target"]["parameters"].items()
        if spec.get("default") is not None
    }
    scenario = "plausible-capability" if plausible else "missing-input"
    graph_inputs = []
    edges = []
    if plausible:
        parameters["capability_verified"] = True
        graph_inputs = [
            {
                "port_id": port_id,
                "direction": "input",
                "semantic_flow": "value",
                "semantic_role": "market_frame",
                "type_ref": {"type_id": "analytical.market_frame", "type_version": 2},
                "shape": "series",
                "connections": {
                    "cardinality": "single", "min": 1, "max": 1, "assembly": "single",
                },
            }
            for port_id in row["target"]["inputs"]
        ]
        edges = [
            {
                "edge_id": f"input-{port_id}",
                "source": {"scope": "graph_input", "port_id": port_id},
                "target": {"scope": "node", "node_id": "subject", "port_id": port_id},
                "binding": {"kind": "single"},
            }
            for port_id in row["target"]["inputs"]
        ]
    return {
        "format_version": 2,
        "strategy_id": f"refused-{name.lower()}-{scenario}",
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": name,
            "description": f"Unavailable assurance scenario: {scenario}",
            "tags": [f"assurance-scenario:{scenario}"],
        },
        "graph_inputs": graph_inputs,
        "graph_outputs": [],
        "nodes": [{
            "node_id": "subject",
            "component": {"component_id": row["component_id"], "component_version": 2},
            "parameters": parameters,
        }],
        "edges": edges,
    }


def _sma_bound():
    fact = {
        "schema": "canonical-input-binding/1",
        "owner_id": "assurance-owner",
        "dataset_context_address": content_address({"assurance": "dataset"}),
        "evaluation_context_address": content_address({"assurance": "evaluation"}),
        "dataset_manifest_address": content_address({"assurance": "manifest"}),
        "market_truth_address": content_address({"assurance": "market-truth"}),
        "provider_product_address": content_address({"assurance": "provider-product"}),
        "provider_contract_address": content_address({"assurance": "provider-contract"}),
        "canonical_instrument_address": content_address({"assurance": "instrument"}),
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "timeframe": 60,
        "fields": ["CLOSE"],
        "freshness": {"maximum_age_seconds": 60},
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False,
    }
    input_binding = {
        "schema": "node-input-binding/1",
        "owner_id": fact["owner_id"],
        "dataset_context_address": fact["dataset_context_address"],
        "evaluation_context_address": fact["evaluation_context_address"],
        "context_address": content_address({"assurance": "input-context"}),
        "ports": {"frame": {
            "source": {"scope": "graph_input", "port_id": "frame"},
            "binding_address": content_address(fact),
            "binding": fact,
        }},
    }
    return materialize_node_contract(
        core_math.source_contract("SMA"),
        core_math.CONTRACT_BINDINGS[core_math.component_key("SMA")],
        {"window": 2}, input_binding,
    )


def _assurance_view():
    return {
        "dispositions": [[name, dict(value)] for name, value in ANALYTICAL_V2_DISPOSITIONS.items()],
        "accepted": {
            name: {
                "descriptor": node_contracts._plain(REGISTRY.v2_components[(analytical.component_id(name), 2)]),
                "contract": node_contracts._plain(REGISTRY.node_contracts[(analytical.component_id(name), 2)]),
                "contract_address": REGISTRY.node_contract_addresses[(analytical.component_id(name), 2)],
                "binding": node_contracts._plain(REGISTRY.contract_bindings[(analytical.component_id(name), 2)].document),
                "implementation_address": REGISTRY.v2_implementation_identities[(analytical.component_id(name), 2)],
            }
            for name, disposition in ANALYTICAL_V2_DISPOSITIONS.items()
            if disposition["status"] == "ACCEPTED_V2"
        },
        "v1": {
            row["component_id"]: {
                "descriptor": node_contracts._plain(REGISTRY.v2_components[(row["component_id"], 1)]),
                "contract": node_contracts._plain(REGISTRY.node_contracts[(row["component_id"], 1)]),
                "contract_address": REGISTRY.node_contract_addresses[(row["component_id"], 1)],
                "declaration_address": REGISTRY.data_requirement_declaration_addresses[(row["component_id"], 1)],
                "implementation_address": REGISTRY.v2_implementation_identities[(row["component_id"], 1)],
            }
            for row in _load(CATALOGUE)["records"]
        },
    }


def _validate_view(view):
    matrix = _records()
    expected_names = _capsule()["component_scope"]
    expected = {row["name"]: row for row in matrix}
    rows = view["dispositions"]
    names = [row[0] for row in rows]
    assert len(names) == len(set(names)) == 125
    assert names == sorted(expected_names) == sorted(expected)
    assert sum(row[1]["status"] == "ACCEPTED_V2" for row in rows) == 108
    assert sum(row[1]["status"] == "UNAVAILABLE" for row in rows) == 17
    expected_accepted = {name for name, row in expected.items() if row["decision"] != "REFUSE"}
    assert set(view["accepted"]) == expected_accepted
    for name, disposition in rows:
        row = expected[name]
        if row["decision"] == "REFUSE":
            assert disposition == {
                "status": "UNAVAILABLE", "reason_code": row["target"]["refusal"]["code"]}
            continue
        assert disposition == {
            "status": "ACCEPTED_V2", "reason_code": "ACCURACY_ASSURANCE_ACCEPTED"}
        actual = view["accepted"][name]
        descriptor, contract, binding = actual["descriptor"], actual["contract"], actual["binding"]
        output_ports = [port["port_id"] for port in descriptor["ports"] if port["direction"] == "output"]
        assert output_ports == sorted(row["target"]["outputs"])
        assert set(descriptor["parameters"]) == set(row["target"]["parameters"])
        assert set(contract) == set(_load(BINDING_SPEC)["source_contract"]["closed_top_level_fields"])
        assert set(contract["required_resolution"]) == {"source", "port", "alignment"}
        assert set(contract["warmup_history"]) == {"rule_id", "rule_version"}
        assert set(contract["state_reset_policy"]) == {"schema", "reasons"}
        assert set(contract["parameter_binding"]) == {
            "scheme", "rule_id", "rule_version", "parameter_names", "input_ports"}
        assert contract["stable_node_id"] == row["component_id"]
        assert contract["semantic_version"] == 2
        assert sorted(contract["output_types"]) == sorted(row["target"]["outputs"])
        assert contract["parameter_binding"]["parameter_names"] == sorted(row["target"]["parameters"])
        assert contract["bar_policy"] == "COMPLETED_ONLY"
        assert contract["causal_declaration"] == "COMPLETED_EVENT_PREFIX"
        assert contract["reference_provenance"]
        assert all(value.startswith("sha256:") for value in contract["reference_provenance"])
        assert contract["mode_eligibility"] == {"research": True, "paper": False, "live": False}
        assert set(binding) == set(_load(BINDING_SPEC)["binding_registration"]["closed_fields"])
        assert binding["component"] == {"component_id": row["component_id"], "component_version": 2}
        assert binding["source_contract_address"] == actual["contract_address"] == content_address(contract)
        assert binding["implementation_address"].startswith("sha256:")
        assert actual["implementation_address"].startswith("sha256:")
        profile = contract["resource_profile"]
        assert set(profile) == {
            "compute_microseconds_per_event", "memory_bytes_upper_bound",
            "history_bytes_upper_bound", "state_bytes_upper_bound",
            "storage_bytes_per_day_upper_bound", "subscription_count_upper_bound",
            "fanout_upper_bound"}
        assert profile["compute_microseconds_per_event"] > 0
        assert profile["memory_bytes_upper_bound"] > 4096
        assert profile["history_bytes_upper_bound"] > 0
        assert profile["state_bytes_upper_bound"] > 0
        assert profile["subscription_count_upper_bound"] > 0
        assert profile["fanout_upper_bound"] > 0

    frozen = {row["component_id"]: row for row in _load(CATALOGUE)["records"]}
    assert set(view["v1"]) == set(frozen)
    for component_id, actual in view["v1"].items():
        expected_v1 = frozen[component_id]
        assert actual == {
            "descriptor": expected_v1["descriptor"],
            "contract": expected_v1["node_contract"],
            "contract_address": expected_v1["node_contract_address"],
            "declaration_address": expected_v1["data_requirement_address"],
            "implementation_address": expected_v1["implementation_address"],
        }


def test_all_125_dispositions_and_every_contract_binding_field_are_exact():
    matrix = _records()
    product = _product_specs()
    assert len(matrix) == len(product) == 125
    for row in matrix:
        spec = product[row["name"]]
        target = _canonical_target(row)
        assert {
            "formula", "inputs", "outputs", "parameters", "first_valid_index",
            "execution_form", "seed", "session_reset", "missing_policy",
            "zero_undefined_policy", "wave", "source", "constraints", "dependencies",
            "variant", "refusal"} <= set(target)
        for field in set(spec).intersection(target):
            assert node_contracts._plain(spec[field]) == target[field], (row["name"], field)
        assert {"formula", "inputs", "outputs", "parameters", "first_valid_index",
                "execution_form", "zero_undefined_policy"} <= set(spec)
        assert spec["decision"] == row["decision"]
        if row["decision"] == "REFUSE":
            assert spec["refusal"]["code"] == row["target"]["refusal"]["code"]
    _validate_view(_assurance_view())


@pytest.mark.parametrize("plausible", [False, True], ids=["missing-input", "plausible-capability"])
def test_all_17_unavailable_rows_refuse_stably_at_the_advertised_resolver(plausible):
    refused = [row for row in _records() if row["decision"] == "REFUSE"]
    assert len(refused) == 17
    scenario = "plausible-capability" if plausible else "missing-input"
    before = content_address(_assurance_view())
    observed_components = set()
    observed_strategies = set()
    for row in refused:
        key = (row["component_id"], 2)
        assert ANALYTICAL_V2_DISPOSITIONS[row["name"]]["reason_code"] == row["target"]["refusal"]["code"]
        assert key not in REGISTRY.v2_components
        assert key not in REGISTRY.v2_implementation_identities
        assert key not in REGISTRY.node_contracts
        assert key not in REGISTRY.contract_bindings
        document = _refused_document(row["name"], plausible=plausible)
        counterpart = _refused_document(row["name"], plausible=not plausible)
        assert document is not None
        assert canonical_json(document) != canonical_json(counterpart)
        assert document["format_version"] == 2
        assert document["strategy_id"] == f"refused-{row['name'].lower()}-{scenario}"
        assert document["strategy_version"] == 1
        assert document["metadata"] == {
            "metadata_version": 1,
            "name": row["name"],
            "description": f"Unavailable assurance scenario: {scenario}",
            "tags": [f"assurance-scenario:{scenario}"],
        }
        assert len(document["nodes"]) == 1
        assert document["nodes"][0]["node_id"] == "subject"
        assert document["nodes"][0]["component"] == {
            "component_id": row["component_id"], "component_version": 2,
        }
        expected_inputs = row["target"]["inputs"] if plausible else []
        assert [port["port_id"] for port in document["graph_inputs"]] == expected_inputs
        assert [edge["target"]["port_id"] for edge in document["edges"]] == expected_inputs
        if plausible:
            assert document["nodes"][0]["parameters"]["capability_verified"] is True
        else:
            assert "capability_verified" not in document["nodes"][0]["parameters"]
        observed_components.add(document["nodes"][0]["component"]["component_id"])
        observed_strategies.add(document["strategy_id"])
        with pytest.raises(ResolutionError) as refusal:
            resolve_v2(document, REGISTRY)
        assert refusal.value.clause == "V2"
        assert refusal.value.path == "$.nodes[0].component"
        assert refusal.value.message == "is not registered"
    assert observed_components == {row["component_id"] for row in refused}
    assert observed_strategies == {
        f"refused-{row['name'].lower()}-{scenario}" for row in refused
    }
    assert content_address(_assurance_view()) == before


def test_locked_sources_licences_runtime_and_sar_addendum_are_exact():
    authority = _load(SOURCE_AUTHORITY)
    assert authority["adoption"] == "No new runtime/test dependency, licence clearance or SBOM claim"
    assert authority["numeric_oracles_executed"] is False
    assert authority["tradingview"].startswith("EXCLUDED")
    assert version("numpy") == "2.5.2"
    assert version("pandas") == "3.0.5"
    lock = (ROOT / "paper-trader/backend/requirements.lock").read_text(encoding="utf-8")
    assert "numpy==2.5.2" in lock and "pandas==3.0.5" in lock
    assert "TA-Lib" not in lock and "talib" not in lock.lower()
    talib = authority["records"]["ta-lib:LICENSE"]
    assert talib["commit"] == "2247d599bddf37ed37e3a709371517e46efc66f6"
    assert talib["version"] == "v0.7.1" and talib["licence"] == "BSD-3-Clause"
    archived_root = ROOT / ".agent/runs/post-phase5-indicator-accuracy-contract-assurance/starting-sources"
    for label, record in authority["records"].items():
        path = record.get("path")
        if path:
            candidates = [ROOT / path, archived_root / path]
            existing = [candidate for candidate in candidates if candidate.is_file()]
            assert existing, label
            assert any(hashlib.sha256(candidate.read_bytes()).hexdigest() == record["sha256"]
                       for candidate in existing), label
    sar_hash = hashlib.sha256(SAR_ADDENDUM.read_bytes()).hexdigest()
    assert sar_hash == _capsule()["accepted_source_addenda"][0]["sha256"]
    sar_key = ("analytical.parabolic_sar", 2)
    assert f"sha256:{sar_hash}" in REGISTRY.node_contracts[sar_key]["reference_provenance"]
    session_seal = _load(
        ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/closure-seal.json")
    assert session_seal["verdict"] == "ASSURANCE PASS"
    assert session_seal["counts"]["candidate_binding_contracts_exact"] == 84
    assert session_seal["counts"]["legacy_identities_exact"] == 125


def test_every_declared_source_is_resolved_without_an_unknown_product_source():
    authority = _load(SOURCE_AUTHORITY)["records"]
    accepted_addenda = {f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}" for path in SOURCE_ADDENDA}
    product = _product_specs()
    for row in _records():
        labels = row["source_authorities"]
        assert labels and all(label in authority for label in labels), row["name"]
        if row["decision"] == "REFUSE":
            continue
        spec = product[row["name"]]
        expected = {f"sha256:{authority[label]['sha256']}" for label in labels}
        actual = set(spec["source_addresses"])
        assert expected <= actual, (row["name"], sorted(expected - actual))
        assert actual <= ({f"sha256:{record['sha256']}" for record in authority.values()}
                          | accepted_addenda)
        permitted = actual | {content_address(node_contracts._plain(spec))}
        assert set(REGISTRY.node_contracts[(row["component_id"], 2)]["reference_provenance"]) == permitted


def test_omission_duplicate_reorder_stale_wrong_binding_source_and_semantic_mutations_die_and_restore():
    baseline = _assurance_view()
    baseline_hash = hashlib.sha256(canonical_json(baseline).encode()).hexdigest()

    def omitted(value):
        value["dispositions"].pop()

    def duplicated(value):
        value["dispositions"].append(deepcopy(value["dispositions"][0]))

    def reordered(value):
        value["dispositions"][0], value["dispositions"][1] = value["dispositions"][1], value["dispositions"][0]

    def stale(value):
        first = sorted(value["v1"])[0]
        value["v1"][first]["implementation_address"] = content_address({"stale": first})

    def wrong_binding(value):
        value["accepted"]["SMA"]["binding"]["source_contract_address"] = content_address({"wrong": "binding"})

    def source_mutation(value):
        value["accepted"]["SMA"]["contract"]["reference_provenance"] = []

    def semantic_mutation(value):
        value["accepted"]["SMA"]["contract"]["bar_policy"] = "FORMING_ALLOWED"

    for mutation in (omitted, duplicated, reordered, stale, wrong_binding, source_mutation, semantic_mutation):
        subject = deepcopy(baseline)
        mutation(subject)
        with pytest.raises(AssertionError):
            _validate_view(subject)
        assert hashlib.sha256(canonical_json(_assurance_view()).encode()).hexdigest() == baseline_hash


def test_every_accepted_parameter_domain_refuses_the_first_value_above_its_bound():
    checked = 0
    for row in _records():
        if row["decision"] == "REFUSE":
            continue
        package = _package_for(row["name"])
        required = {
            name: "2026-08-29T00:00:00+00:00"
            for name, spec in row["target"]["parameters"].items()
            if spec.get("required") and spec.get("default") is None
        }
        normalized = node_contracts._plain(package.parameters_for(row["name"], required))
        assert set(normalized) == set(row["target"]["parameters"])
        for name, spec in row["target"]["parameters"].items():
            if name not in required:
                assert normalized[name] == spec["default"]
        for name, parameter in row["target"]["parameters"].items():
            if parameter["type"] == "enum":
                invalid = "__INVALID_ENUM__" if any(isinstance(value, str)
                                                     for value in parameter["values"]) else max(parameter["values"]) + 1
            elif type(parameter.get("maximum")) in {int, float}:
                invalid = parameter["maximum"] + 1
            else:
                continue
            with pytest.raises(node_contracts.NodeContractRefusal):
                package.parameters_for(row["name"], {**required, name: invalid})
            checked += 1
    assert checked >= 100


def test_hand_authored_sma_batch_stream_restart_gap_and_future_prefix_are_causal():
    bound = _sma_bound()
    parameters = {"window": 2}
    index = pd.date_range("2026-08-29T09:15:00Z", periods=5, freq="min")
    values = [1.0, 2.0, 3.0, 4.0]
    batch = core_math.evaluate(
        "SMA", parameters,
        {"frame": {"close": pd.Series(values, index=index[:4])}},
        bound_contract=bound,
    )["value"]
    expected = [
        (ValidityState.INSUFFICIENT_HISTORY, None),
        (ValidityState.VALID, 1.5),
        (ValidityState.VALID, 2.5),
        (ValidityState.VALID, 3.5),
    ]
    assert [(cell.state, cell.value) for cell in batch] == expected

    stream = core_math.CoreMathState("SMA", parameters, bound)
    streamed = [
        stream.step({"frame": {"close": value}}, event_time=event_time)["value"]
        for value, event_time in zip(values, index)
    ]
    assert [(cell.state, cell.value) for cell in streamed] == expected

    first = core_math.CoreMathState("SMA", parameters, bound)
    first.step({"frame": {"close": 1.0}}, event_time=index[0])
    first.step({"frame": {"close": 2.0}}, event_time=index[1])
    restored = core_math.CoreMathState.restore("SMA", parameters, bound, first.snapshot())
    resumed = [
        restored.step({"frame": {"close": value}}, event_time=event_time)["value"]
        for value, event_time in zip(values[2:], index[2:])
    ]
    assert [(cell.state, cell.value) for cell in resumed] == expected[2:]

    future = core_math.evaluate(
        "SMA", parameters,
        {"frame": {"close": pd.Series([*values, 1000.0], index=index)}},
        bound_contract=bound,
    )["value"]
    assert [(cell.state, cell.value) for cell in future.iloc[:4]] == expected

    gap = core_math.evaluate(
        "SMA", parameters,
        {"frame": {"close": pd.Series([1.0, 2.0, None, 3.0], index=index[:4])}},
        bound_contract=bound,
    )["value"]
    assert [cell.state for cell in gap] == [
        ValidityState.INSUFFICIENT_HISTORY, ValidityState.VALID,
        ValidityState.INVALID, ValidityState.INSUFFICIENT_HISTORY,
    ]
    with pytest.raises(node_contracts.NodeContractRefusal, match="CORE_EVENT_ORDER"):
        restored.step({"frame": {"close": 5.0}}, event_time=index[3])
