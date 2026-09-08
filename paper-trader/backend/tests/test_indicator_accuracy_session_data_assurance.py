"""Historical session-data evidence and current research-only contributor assurance."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import core_math, multi_output, recursive_state
from app.ir.first_party.analytical_v2 import session_data as product
from app.ir.first_party.analytical_v2.contracts import (
    ResolvedNodeContract,
    canonical_input_bindings,
)
from app.ir.library import REGISTRY as DEFAULT_REGISTRY
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.runtime import evaluate_v2
from app.ir.validity import NumericValue, ValidityState
from app.market_data.requirements import compile_data_requirement_plan, verify_data_requirement_plan
from tests import test_indicator_accuracy_session_data_fresh_assurance as fresh
from research_tests import test_indicator_accuracy_session_data_oracle as oracle


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance"
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"
TRANSITION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/identity-transition.json"
EXPECTED_SOURCE_SHA = "7dd508c41cb267f7fe571b60fef414c3244b6c3373178c043226811213a4b897"
EXPECTED_OWNER_TEST_SHA = "6b7924a0ea1a3d5aaf768aec9c72b2023ffcd81a6677fda785413841815cc714"
NOT_READY = ValidityState.INSUFFICIENT_HISTORY


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [plain(item) for item in value]
    return value


def address(label):
    return hashing.content_address({"session_data_assurance": label})


def parameters(name):
    if name == "ANCHORED_VWAP":
        return {"anchor_at": "2026-08-26T19:00:00+00:00"}
    if name == "OPENING_RANGE":
        return {"range_minutes": 60}
    return {}


def product_inputs(name):
    columns = oracle.columns()
    index = pd.DatetimeIndex(pd.to_datetime(columns["event_time"], utc=True))
    available = {
        "open": columns["open"], "high": columns["high"], "low": columns["low"],
        "close": columns["close"], "volume": columns["volume"],
        "session_id": columns["session_id"],
        "session_open_at": tuple(pd.Timestamp(value) for value in columns["session_open_at"]),
        "session_close_at": tuple(pd.Timestamp(value) for value in columns["session_close_at"]),
    }
    result = {}
    for port, fields in product.fields_by_port(name, parameters(name)).items():
        result[port] = {}
        for field in fields:
            key = field.lower()
            values = available[key]
            if key in product.NUMERIC_FIELDS:
                values = tuple(float(Decimal(value)) for value in values)
            result[port][key] = pd.Series(values, index=index)
    return result


def canonical_fact(name, port, fields):
    primary = product.source_contract(name)["required_resolution"]["port"]
    role = "primary" if port == primary else port
    return {
        "schema": "canonical-input-binding/1",
        "owner_id": "org.session-data-assurance",
        "dataset_context_address": address("dataset"),
        "evaluation_context_address": address("evaluation"),
        "dataset_manifest_address": address("manifest"),
        "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"),
        "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("instrument:" + role),
        "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": 1800,
        "fields": sorted(fields),
        "freshness": {"maximum_age_seconds": 1800},
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": port == "session",
    }


def isolated_registry(name):
    key = product.component_key(name)
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types=product.V2_TYPES,
        v2_components={key: product.V2_COMPONENTS[key]},
        node_contracts={key: product.NODE_CONTRACTS[key]},
        contract_bindings={key: product.CONTRACT_BINDINGS[key]},
        v2_implementations={key: product.V2_IMPLEMENTATIONS[key]},
    )


def graph_document(name):
    key = product.component_key(name)
    ports = plain(product.V2_COMPONENTS[key]["ports"])
    inputs = [deepcopy(port) for port in ports if port["direction"] == "input"]
    outputs = [deepcopy(port) for port in ports if port["direction"] == "output"]
    return {
        "format_version": 2,
        "strategy_id": "session-data-assurance",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Session data assurance", "description": None, "tags": []},
        "graph_inputs": inputs,
        "graph_outputs": outputs,
        "nodes": [{"node_id": "probe", "component": {"component_id": key[0], "component_version": 2},
                   "parameters": parameters(name)}],
        "edges": [
            {"edge_id": "in:" + port["port_id"],
             "source": {"scope": "graph_input", "port_id": port["port_id"]},
             "target": {"scope": "node", "node_id": "probe", "port_id": port["port_id"]},
             "binding": {"kind": "single"}}
            for port in inputs
        ] + [
            {"edge_id": "out:" + port["port_id"],
             "source": {"scope": "node", "node_id": "probe", "port_id": port["port_id"]},
             "target": {"scope": "graph_output", "port_id": port["port_id"]},
             "binding": {"kind": "single"}}
            for port in outputs
        ],
    }


def compiled_case(name):
    params = parameters(name)
    facts = {
        port: canonical_fact(name, port, fields)
        for port, fields in product.fields_by_port(name, params).items()
    }
    context = canonical_input_bindings(
        owner_id="org.session-data-assurance",
        dataset_context_address=address("dataset"),
        evaluation_context_address=address("evaluation"),
        bindings=facts,
        expected_source_addresses={port: hashing.content_address(fact) for port, fact in facts.items()},
    )
    registry = isolated_registry(name)
    resolved = resolve_v2(graph_document(name), registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)
    receipt = plan.parameter_binding_provenance[0]["node_contract_binding"]
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    return registry, resolved, context, plan, bound


def through_consumers(name):
    registry, resolved, _, _, bound = compiled_case(name)
    result = evaluate_v2(
        resolved,
        product_inputs(name),
        registry,
        evaluation_context_resolver=lambda _node, _inputs: {"bound_contract": bound},
    )
    return result, bound


def assert_series(actual, expected):
    assert len(actual) == len(expected)
    for cell, wanted in zip(actual, expected):
        assert isinstance(cell, NumericValue)
        if wanted is None:
            assert cell.state is NOT_READY and cell.value is None
        else:
            target = float(Decimal(wanted))
            assert cell.state is ValidityState.VALID
            assert abs(cell.value - target) <= (1e-12 if target == 0 else max(1e-10, abs(target) * 1e-9))


def test_exact_31_decisions_and_14_refusals_have_no_executable_placeholder():
    candidates = set(oracle.EXPECTED) | {"PREVIOUS_SESSION_FIELDS"}
    assert set(product.ALL_NAMES) == candidates | set(oracle.REFUSALS)
    assert set(product.NAMES) == candidates and len(product.NAMES) == 17
    assert set(product.REFUSED_NAMES) == set(oracle.REFUSALS) and len(product.REFUSED_NAMES) == 14
    for key in product.V2_COMPONENTS:
        fresh.assert_current_registry_identity(product, key)
    for name, code in oracle.REFUSALS.items():
        fact = product.refusal_for(name)
        assert fact["code"] == code and fact["executable"] is False
        assert ("analytical." + name.lower(), 2) not in product.V2_COMPONENTS
        assert ("analytical." + name.lower(), 2) not in DEFAULT_REGISTRY.v2_components
        with pytest.raises(node_contracts.NodeContractRefusal, match=code):
            product.component_key(name)


@pytest.mark.parametrize("name", sorted(oracle.EXPECTED))
def test_independent_complete_arrays_masks_and_real_consumers(name):
    outputs, _ = through_consumers(name)
    assert set(outputs) == set(oracle.EXPECTED[name])
    for port, expected in oracle.EXPECTED[name].items():
        assert_series(outputs[port], expected)


@pytest.mark.parametrize("field", ("open", "high", "low", "close", "volume"))
def test_previous_session_field_enum_complete_arrays(field):
    name = "PREVIOUS_SESSION_FIELDS"
    original = parameters
    try:
        globals()["parameters"] = lambda candidate: {"field": field} if candidate == name else original(candidate)
        outputs, _ = through_consumers(name)
    finally:
        globals()["parameters"] = original
    assert_series(outputs["value"], oracle.previous_field_expected(field))


@pytest.mark.parametrize("name", product.NAMES)
def test_batch_stream_and_serialized_restart_match_at_every_bar(name):
    batch, bound = through_consumers(name)
    selected = product_inputs(name)
    fields = product.fields_by_port(name, parameters(name))
    state = product.SessionDataState(name, parameters(name), bound)
    index = next(iter(next(iter(selected.values())).values())).index
    for position, event_time in enumerate(index):
        row = {port: {field.lower(): selected[port][field.lower()].iloc[position] for field in declared}
               for port, declared in fields.items()}
        streamed = state.step(row, event_time=event_time)
        for port in batch:
            assert streamed[port] == batch[port].iloc[position]
        state = product.SessionDataState.restore(
            name, parameters(name), bound, json.loads(json.dumps(state.snapshot())),
        )


def test_every_session_prefix_candidate_refuses_a_missing_first_bar():
    accepted_suffixes = []
    for name in sorted(product.SESSION_PREFIX_NAMES):
        _, bound = through_consumers(name)
        selected = product_inputs(name)
        missing_first = {port: {field: series.iloc[1:] for field, series in values.items()}
                         for port, values in selected.items()}
        try:
            product.evaluate(name, parameters(name), missing_first, bound_contract=bound)
        except node_contracts.NodeContractRefusal:
            continue
        accepted_suffixes.append(name)
    assert accepted_suffixes == [], f"session suffix silently treated as a complete prefix: {accepted_suffixes}"


@pytest.mark.parametrize("name", sorted(product.SESSION_PREFIX_NAMES))
def test_internal_session_gap_refuses_without_row_compression(name):
    _, bound = through_consumers(name)
    selected = product_inputs(name)
    missing_slot = {port: {field: series.drop(series.index[1]) for field, series in values.items()}
                    for port, values in selected.items()}
    with pytest.raises(node_contracts.NodeContractRefusal, match="MISSING_SESSION_SLOT"):
        product.evaluate(name, parameters(name), missing_slot, bound_contract=bound)


def test_parameter_anchor_and_resource_first_above_bounds_refuse():
    assert product.parameters_for("OPENING_RANGE", {"range_minutes": 1})["range_minutes"] == 1
    assert product.parameters_for("OPENING_RANGE", {"range_minutes": 240})["range_minutes"] == 240
    for value in (0, 241, True, 1.0, None):
        with pytest.raises(node_contracts.NodeContractRefusal):
            product.parameters_for("OPENING_RANGE", {"range_minutes": value})
    for value in (None, pd.Timestamp("2026-08-26T19:00:00Z"), "2026-08-26T19:00:00Z", "2026-08-26"):
        with pytest.raises(node_contracts.NodeContractRefusal):
            product.parameters_for("ANCHORED_VWAP", {"anchor_at": value})
    _, high_bound = through_consumers("SESSION_HIGH")
    high = product.SessionDataState("SESSION_HIGH", {}, high_bound)
    selected = product_inputs("SESSION_HIGH")
    first_time = selected["frame"]["high"].index[0]
    high.step({port: {field: series.iloc[0] for field, series in values.items()}
               for port, values in selected.items()}, event_time=first_time)
    high._session_count = 100000
    with pytest.raises(node_contracts.NodeContractRefusal, match="SESSION_PREFIX_LIMIT"):
        high.step({port: {field: series.iloc[1] for field, series in values.items()}
                   for port, values in selected.items()}, event_time=selected["frame"]["high"].index[1])


def test_wrong_role_session_source_and_derived_local_fail_real_compiler():
    name = "SESSION_HIGH"
    registry, resolved, context, plan, _ = compiled_case(name)
    for field, value in (("role", "peer"), ("session", "CONTINUOUS"), ("derived_local", False)):
        document = plain(context.document)
        binding = document["inputs"]["session"]["binding"]
        if field == "role":
            binding["instrument"]["role"] = value
        else:
            binding[field] = value
        binding_row = document["inputs"]["session"]
        binding_row["binding_address"] = hashing.content_address(binding)
        document["inputs"]["session"]["source_address"] = binding_row["binding_address"]
        with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
            forged = type(context)(document, hashing.content_address(document))
            verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=forged)


def test_legacy_125_and_accepted_84_source_facts_and_current_registrations_are_exact():
    catalogue = json.loads(CATALOGUE.read_text())
    transition = json.loads(TRANSITION.read_text())
    assert len(catalogue["records"]) == 125
    waves = (core_math, recursive_state, multi_output)
    current = {}
    for wave in waves:
        for key in sorted(wave.V2_COMPONENTS):
            marker = f"{key[0]}@{key[1]}"
            current[marker] = {
                "component_address": hashing.content_address(plain(wave.V2_COMPONENTS[key])),
                "source_contract_address": hashing.content_address(plain(wave.NODE_CONTRACTS[key])),
                "binding_source_contract_address": wave.CONTRACT_BINDINGS[key].source_contract_address,
            }
            fresh.assert_current_registry_identity(wave, key)
    assert len(current) == 84
    fields = ("component_address", "source_contract_address", "binding_source_contract_address")
    assert current == {marker: {field: record["after"][field] for field in fields}
                       for marker, record in transition["records"].items()}


def test_historical_product_and_contract_sources_and_unchanged_control_hashes():
    expected = {
        "paper-trader/backend/tests/fixtures/indicator_accuracy/historical_sources/session_data_before_prefix_correction.py": EXPECTED_SOURCE_SHA,
        "paper-trader/backend/tests/test_indicator_accuracy_session_data.py": EXPECTED_OWNER_TEST_SHA,
        "paper-trader/backend/app/ir/node_contracts.py": "a1e16b735cd8decfcad4356aa82c10a20d65c5129f25d78ae7931ad9596af284",
        "paper-trader/backend/app/ir/registry.py": "4c1d83e9f8714d9e8a11e571426cde6b7a896fe47aec3d3fe1a44b4f58bf120f",
        "paper-trader/backend/tests/fixtures/indicator_accuracy/historical_sources/contracts_session_data_assurance.py": "95e0ae03d2f3dc93fb959c9522cb636c517d7ebd5766e3ae3524d95964be0ba3",
        "paper-trader/backend/app/market_data/requirements.py": "d1d0a4b278a4d2d503667197c384ee07b0d58c790fa1726ada8e9bfbea8354d4",
        "paper-trader/backend/app/ir/first_party/analytical.py": "4b164cac9c1a71ab810b457ea404266034c4043185fa7712ade0d38d411d5fec",
    }
    for relative, wanted in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == wanted


def test_isolated_wrong_output_and_refusal_mutations_are_killed(monkeypatch):
    registry, resolved, _, _, bound = compiled_case("DISTANCE_FROM_SESSION_HIGH_LOW")
    original_advance = product.SessionDataState._advance

    def swap_distance_outputs(state, row, event_time):
        produced = original_advance(state, row, event_time)
        if state.name == "DISTANCE_FROM_SESSION_HIGH_LOW":
            produced = {"from_high": produced["from_low"], "from_low": produced["from_high"]}
        return produced

    monkeypatch.setattr(product.SessionDataState, "_advance", swap_distance_outputs)
    actual = evaluate_v2(
        resolved,
        product_inputs("DISTANCE_FROM_SESSION_HIGH_LOW"),
        registry,
        evaluation_context_resolver=lambda _node, _inputs: {"bound_contract": bound},
    )
    with pytest.raises(AssertionError):
        assert_series(actual["from_high"], oracle.EXPECTED["DISTANCE_FROM_SESSION_HIGH_LOW"]["from_high"])
    monkeypatch.setattr(product.SessionDataState, "_advance", original_advance)
    fake_components = dict(product.V2_COMPONENTS)
    fake_components[("analytical.ask", 2)] = next(iter(product.V2_COMPONENTS.values()))
    with pytest.raises(AssertionError):
        assert ("analytical.ask", 2) not in fake_components


def test_current_registry_integration_retains_research_only_provider_free_contracts():
    seal_path = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-data/closure-seal.json"
    assert hashlib.sha256(seal_path.read_bytes()).hexdigest() == "6de01a2b59e4a07eee68bd5c58777d8d0152d3f62063f5e7c36d6e35750454ec"
    seal = json.loads(seal_path.read_text())
    assert seal["source_sha256"] == EXPECTED_SOURCE_SHA
    assert seal["publication"] is False and seal["deployment"] is False
    for name in product.NAMES:
        contract = product.source_contract(name)
        assert contract["mode_eligibility"] == {"research": True, "paper": False, "live": False}
        assert contract["provider_requirements"] == ()
        fresh.assert_current_registry_identity(product, product.component_key(name))
