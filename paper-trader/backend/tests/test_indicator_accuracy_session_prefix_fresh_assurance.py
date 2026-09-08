"""Fresh independent assurance for the corrected SESSION_OPEN_AT wave."""
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
from app.ir.first_party.analytical_v2 import session_data as subject
from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract, canonical_input_bindings
from app.ir.library import REGISTRY as DEFAULT_REGISTRY
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.runtime import evaluate_v2
from app.ir.validity import NumericValue, ValidityState
from app.market_data.requirements import compile_data_requirement_plan, verify_data_requirement_plan
from tests import test_indicator_accuracy_session_data_fresh_assurance as fresh
from research_tests import test_indicator_accuracy_session_prefix_fresh_oracle as oracle


ROOT = Path(__file__).resolve().parents[3]
TRANSITION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/identity-transition.json"
PRIOR_IDENTITIES = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/candidate-identities.json"
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"
ACCEPTED_V2 = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/identity-transition.json"
F01_NAMES = frozenset({
    "DISTANCE_FROM_SESSION_HIGH_LOW", "PREVIOUS_SESSION_FIELDS", "PREVIOUS_SESSION_OHLC",
    "SESSION_HIGH", "SESSION_LOW", "SESSION_OPEN", "SESSION_OPEN_HIGH_LOW", "VWAP",
})
PARAMETERS = {
    "ANCHORED_VWAP": {"anchor_at": "2026-02-14T00:30:00+00:00"},
    "OPENING_RANGE": {"range_minutes": 60},
    "PREVIOUS_SESSION_FIELDS": {"field": "close"},
}
NOT_READY = ValidityState.INSUFFICIENT_HISTORY


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [plain(item) for item in value]
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker(label: str) -> str:
    return hashing.content_address({"fresh_session_prefix_assurance": label})


def parameters(name: str, *, field: str = "close") -> dict:
    if name == "PREVIOUS_SESSION_FIELDS":
        return {"field": field}
    return dict(PARAMETERS.get(name, {}))


def fixture_inputs(name: str, *, field: str = "close") -> dict:
    source = oracle.columns()
    index = pd.DatetimeIndex(pd.to_datetime(source["event_time"], utc=True))
    columns = {
        "open": source["open"], "high": source["high"], "low": source["low"],
        "close": source["close"], "volume": source["volume"], "session_id": source["session_id"],
        "session_open_at": tuple(pd.Timestamp(value) for value in source["session_open_at"]),
        "session_close_at": tuple(pd.Timestamp(value) for value in source["session_close_at"]),
    }
    selected = {}
    for port, fields in subject.fields_by_port(name, parameters(name, field=field)).items():
        selected[port] = {}
        for declared in fields:
            key = declared.lower()
            values = columns[key]
            if key in subject.NUMERIC_FIELDS:
                values = tuple(float(Decimal(value)) for value in values)
            selected[port][key] = pd.Series(values, index=index)
    return selected


def binding_fact(name: str, port: str, fields: tuple[str, ...]) -> dict:
    primary = subject.source_contract(name)["required_resolution"]["port"]
    role = "primary" if port == primary else port
    return {
        "schema": "canonical-input-binding/1",
        "owner_id": "org.fresh-prefix-assurance",
        "dataset_context_address": marker("dataset"),
        "evaluation_context_address": marker("evaluation"),
        "dataset_manifest_address": marker("manifest"),
        "market_truth_address": marker("market-truth"),
        "provider_product_address": marker("provider-product"),
        "provider_contract_address": marker("provider-contract"),
        "canonical_instrument_address": marker("instrument:" + role),
        "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": 1800,
        "fields": sorted(fields),
        "freshness": {"maximum_age_seconds": 1800},
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": port == "session",
    }


def registry_for(name: str) -> PlatformRegistry:
    key = subject.component_key(name)
    return PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=subject.V2_TYPES,
        v2_components={key: subject.V2_COMPONENTS[key]},
        node_contracts={key: subject.NODE_CONTRACTS[key]},
        contract_bindings={key: subject.CONTRACT_BINDINGS[key]},
        v2_implementations={key: subject.V2_IMPLEMENTATIONS[key]},
    )


def graph(name: str, *, field: str = "close") -> dict:
    key = subject.component_key(name)
    ports = plain(subject.V2_COMPONENTS[key]["ports"])
    inputs = [deepcopy(port) for port in ports if port["direction"] == "input"]
    outputs = [deepcopy(port) for port in ports if port["direction"] == "output"]
    return {
        "format_version": 2, "strategy_id": "fresh-prefix-assurance", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Fresh prefix assurance", "description": None, "tags": []},
        "graph_inputs": inputs, "graph_outputs": outputs,
        "nodes": [{"node_id": "candidate", "component": {"component_id": key[0], "component_version": 2},
                   "parameters": parameters(name, field=field)}],
        "edges": [
            {"edge_id": "in:" + port["port_id"],
             "source": {"scope": "graph_input", "port_id": port["port_id"]},
             "target": {"scope": "node", "node_id": "candidate", "port_id": port["port_id"]},
             "binding": {"kind": "single"}} for port in inputs
        ] + [
            {"edge_id": "out:" + port["port_id"],
             "source": {"scope": "node", "node_id": "candidate", "port_id": port["port_id"]},
             "target": {"scope": "graph_output", "port_id": port["port_id"]},
             "binding": {"kind": "single"}} for port in outputs
        ],
    }


def compiled(name: str, *, field: str = "close"):
    declared = subject.fields_by_port(name, parameters(name, field=field))
    facts = {port: binding_fact(name, port, fields) for port, fields in declared.items()}
    context = canonical_input_bindings(
        owner_id="org.fresh-prefix-assurance",
        dataset_context_address=marker("dataset"),
        evaluation_context_address=marker("evaluation"),
        bindings=facts,
        expected_source_addresses={port: hashing.content_address(fact) for port, fact in facts.items()},
    )
    registry = registry_for(name)
    resolved = resolve_v2(graph(name, field=field), registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)
    materialized = plan.parameter_binding_provenance[0]["node_contract_binding"]
    bound = ResolvedNodeContract(materialized, materialized["bound_contract_address"])
    return registry, resolved, context, plan, bound


def consumer_result(name: str, *, field: str = "close"):
    registry, resolved, _, _, bound = compiled(name, field=field)
    outputs = evaluate_v2(
        resolved,
        fixture_inputs(name, field=field),
        registry,
        evaluation_context_resolver=lambda _node, _inputs: {"bound_contract": bound},
    )
    return outputs, bound


def assert_complete(actual, expected):
    assert len(actual) == len(expected)
    for position, (cell, text) in enumerate(zip(actual, expected)):
        assert isinstance(cell, NumericValue), position
        if text is None:
            assert cell.state is NOT_READY and cell.value is None, position
            continue
        wanted = float(Decimal(text))
        assert cell.state is ValidityState.VALID, position
        absolute = abs(cell.value - wanted)
        assert absolute <= (1e-12 if wanted == 0 else 1e-10), position
        if wanted:
            assert absolute / abs(wanted) <= 1e-9, position


def row_at(name: str, position: int, *, field: str = "close"):
    selected = fixture_inputs(name, field=field)
    declared = subject.fields_by_port(name, parameters(name, field=field))
    index = next(iter(next(iter(selected.values())).values())).index
    row = {
        port: {item.lower(): selected[port][item.lower()].iloc[position] for item in fields}
        for port, fields in declared.items()
    }
    return selected, index, row


def current_identities() -> dict:
    result = {}
    for name in subject.NAMES:
        key = subject.component_key(name)
        result[name] = {
            "component_address": hashing.content_address(plain(subject.V2_COMPONENTS[key])),
            "source_contract_address": hashing.content_address(plain(subject.NODE_CONTRACTS[key])),
            "binding_source_contract_address": subject.CONTRACT_BINDINGS[key].source_contract_address,
            "binding_implementation_address": subject.CONTRACT_BINDINGS[key].implementation_address,
            "implementation_address": subject.V2_IMPLEMENTATIONS[key].implementation_address,
        }
    return result


def test_complete_31_decisions_17_candidates_14_refusals_and_parameters():
    candidates = set(oracle.EXPECTED) | {"PREVIOUS_SESSION_FIELDS"}
    assert set(subject.ALL_NAMES) == candidates | set(oracle.REFUSALS)
    assert set(subject.NAMES) == candidates and len(subject.NAMES) == 17
    assert set(subject.REFUSED_NAMES) == set(oracle.REFUSALS) and len(subject.REFUSED_NAMES) == 14
    assert {name: set(subject.SPECS[name]["parameters"]) for name in subject.NAMES} == {
        name: set(PARAMETERS.get(name, {})) for name in subject.NAMES
    }
    assert subject.parameters_for("OPENING_RANGE", {}) == {"range_minutes": 15}
    assert subject.parameters_for("PREVIOUS_SESSION_FIELDS", {}) == {"field": "close"}
    for name, code in oracle.REFUSALS.items():
        refusal = subject.refusal_for(name)
        assert refusal["code"] == code and refusal["executable"] is False
        assert subject.SPECS[name]["decision"] == "REFUSE"
        assert ("analytical." + name.lower(), 2) not in subject.V2_COMPONENTS
        assert ("analytical." + name.lower(), 2) not in DEFAULT_REGISTRY.v2_components
        with pytest.raises(node_contracts.NodeContractRefusal, match=code):
            subject.component_key(name)


@pytest.mark.parametrize("name", sorted(oracle.EXPECTED))
def test_independent_complete_arrays_masks_and_real_consumers(name):
    outputs, _ = consumer_result(name)
    assert set(outputs) == set(oracle.EXPECTED[name])
    for port, expected in oracle.EXPECTED[name].items():
        assert_complete(outputs[port], expected)


@pytest.mark.parametrize("field", ("open", "high", "low", "close", "volume"))
def test_all_previous_session_field_arrays_and_masks(field):
    outputs, _ = consumer_result("PREVIOUS_SESSION_FIELDS", field=field)
    assert_complete(outputs["value"], oracle.previous_field(field))


@pytest.mark.parametrize("name", subject.NAMES)
def test_batch_future_prefix_stream_snapshot_restart_and_cold_replay(name):
    batch, bound = consumer_result(name)
    selected = fixture_inputs(name)
    declared = subject.fields_by_port(name, parameters(name))
    state = subject.SessionDataState(name, parameters(name), bound)
    index = next(iter(next(iter(selected.values())).values())).index
    for position, event_time in enumerate(index):
        prefix = {
            port: {field.lower(): selected[port][field.lower()].iloc[:position + 1] for field in fields}
            for port, fields in declared.items()
        }
        cold = subject.evaluate(name, parameters(name), prefix, bound_contract=bound)
        row = {
            port: {field.lower(): selected[port][field.lower()].iloc[position] for field in fields}
            for port, fields in declared.items()
        }
        streamed = state.step(row, event_time=event_time)
        for port in batch:
            assert cold[port].tolist() == batch[port].iloc[:position + 1].tolist()
            assert streamed[port] == batch[port].iloc[position]
        state = subject.SessionDataState.restore(
            name, parameters(name), bound, json.loads(json.dumps(state.snapshot()))
        )


@pytest.mark.parametrize("name", sorted(F01_NAMES))
def test_all_eight_require_derived_exact_session_open_and_refuse_second_slot_without_mutation(name):
    registry, resolved, context, plan, bound = compiled(name)
    fields = subject.fields_by_port(name, parameters(name))
    assert fields["session"].count("SESSION_OPEN_AT") == 1
    assert "session.session_open_at" in subject.source_contract(name)["required_market_fields"]
    fact = bound.document["input_binding"]["ports"]["session"]["binding"]
    assert fact["instrument"] == {"role": "session", "type": "PHYSICAL"}
    assert fact["session"] == "INSTRUMENT_CALENDAR"
    assert fact["alignment"] == {"kind": "EXACT", "maximum_skew_seconds": 0}
    assert fact["derived_local"] is True
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)

    selected, index, second = row_at(name, 1)
    state = subject.SessionDataState(name, parameters(name), bound)
    before = state.snapshot()
    with pytest.raises(node_contracts.NodeContractRefusal, match="INCOMPLETE_SESSION_PREFIX"):
        state.step(second, event_time=index[1])
    assert state.snapshot() == before
    missing = {
        port: {field: series for field, series in values.items() if field != "session_open_at"}
        for port, values in selected.items()
    }
    with pytest.raises(node_contracts.NodeContractRefusal):
        subject.evaluate(name, parameters(name), missing, bound_contract=bound)


@pytest.mark.parametrize("name", sorted(F01_NAMES))
def test_all_eight_reject_session_open_identity_change_and_skipped_slot_before_mutation(name):
    _, _, _, _, bound = compiled(name)
    _, index, first = row_at(name, 0)
    _, _, second = row_at(name, 1)
    state = subject.SessionDataState(name, parameters(name), bound)
    state.step(first, event_time=index[0])
    established = state.snapshot()
    wrong_identity = deepcopy(second)
    wrong_identity["session"]["session_open_at"] = pd.Timestamp("2026-02-13T23:00:00Z")
    with pytest.raises(node_contracts.NodeContractRefusal, match="SESSION_IDENTITY_CHANGED"):
        state.step(wrong_identity, event_time=index[1])
    assert state.snapshot() == established
    with pytest.raises(node_contracts.NodeContractRefusal, match="MISSING_SESSION_SLOT"):
        state.step(second, event_time=index[2])
    assert state.snapshot() == established


@pytest.mark.parametrize("name", sorted(subject.SESSION_PREFIX_NAMES))
def test_internal_gap_is_not_compressed(name):
    _, bound = consumer_result(name)
    selected = fixture_inputs(name)
    missing = {
        port: {field: series.drop(series.index[1]) for field, series in values.items()}
        for port, values in selected.items()
    }
    with pytest.raises(node_contracts.NodeContractRefusal, match="MISSING_SESSION_SLOT"):
        subject.evaluate(name, parameters(name), missing, bound_contract=bound)


def test_incomplete_previous_session_never_becomes_an_aggregate_and_anchor_requires_history():
    for name in ("PREVIOUS_SESSION_FIELDS", "PREVIOUS_SESSION_OHLC"):
        _, bound = consumer_result(name)
        selected = fixture_inputs(name)
        incomplete = {
            port: {field: series.iloc[[1, 2, 3]] for field, series in values.items()}
            for port, values in selected.items()
        }
        with pytest.raises(node_contracts.NodeContractRefusal, match="INCOMPLETE_SESSION_PREFIX"):
            subject.evaluate(name, parameters(name), incomplete, bound_contract=bound)

    name = "ANCHORED_VWAP"
    _, bound = consumer_result(name)
    selected = fixture_inputs(name)
    suffix = {port: {field: series.iloc[2:] for field, series in values.items()} for port, values in selected.items()}
    with pytest.raises(node_contracts.NodeContractRefusal, match="ANCHOR_HISTORY_INCOMPLETE"):
        subject.evaluate(name, parameters(name), suffix, bound_contract=bound)


def test_parameter_domains_resource_profiles_and_first_above_guards_are_exact():
    assert subject.parameters_for("OPENING_RANGE", {"range_minutes": 1}) == {"range_minutes": 1}
    assert subject.parameters_for("OPENING_RANGE", {"range_minutes": 240}) == {"range_minutes": 240}
    for invalid in (0, 241, True, 1.0, None):
        with pytest.raises(node_contracts.NodeContractRefusal):
            subject.parameters_for("OPENING_RANGE", {"range_minutes": invalid})
    for invalid in (None, pd.Timestamp("2026-02-14T00:30:00Z"), "2026-02-14T00:30:00Z", "2026-02-14"):
        with pytest.raises(node_contracts.NodeContractRefusal):
            subject.parameters_for("ANCHORED_VWAP", {"anchor_at": invalid})
    for invalid in ("price", 1, True, None):
        with pytest.raises(node_contracts.NodeContractRefusal):
            subject.parameters_for("PREVIOUS_SESSION_FIELDS", {"field": invalid})

    for name in subject.NAMES:
        resource = subject.source_contract(name)["resource_profile"]
        assert resource == {
            "compute_microseconds_per_event": 250000,
            "fanout_upper_bound": 1,
            "history_bytes_upper_bound": 2097152,
            "memory_bytes_upper_bound": 33554432,
            "state_bytes_upper_bound": 4194304,
            "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": 1,
        }
    for name, counter, code, first in (
        ("SESSION_HIGH", "_session_count", "SESSION_PREFIX_LIMIT", 0),
        ("ANCHORED_VWAP", "_anchor_count", "ANCHOR_HISTORY_LIMIT", 1),
    ):
        _, bound = consumer_result(name)
        _, index, row = row_at(name, first)
        state = subject.SessionDataState(name, parameters(name), bound)
        state.step(row, event_time=index[first])
        setattr(state, counter, 100000)
        _, _, following = row_at(name, first + 1)
        with pytest.raises(node_contracts.NodeContractRefusal, match=code):
            state.step(following, event_time=index[first + 1])


def test_real_plan_verifier_rejects_wrong_session_role_alignment_freshness_and_identity():
    name = "SESSION_OPEN"
    registry, resolved, context, plan, _ = compiled(name)
    mutations = (
        ("instrument", {"role": "primary", "type": "PHYSICAL"}),
        ("alignment", {"kind": "AS_OF", "maximum_skew_seconds": 1}),
        ("derived_local", False),
        ("session", "CONTINUOUS"),
        ("freshness", {"maximum_age_seconds": 3600}),
    )
    for field, value in mutations:
        document = plain(context.document)
        binding = document["inputs"]["session"]["binding"]
        binding[field] = value
        item = document["inputs"]["session"]
        item["binding_address"] = hashing.content_address(binding)
        item["source_address"] = item["binding_address"]
        with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
            forged = type(context)(document, hashing.content_address(document))
            verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=forged)


def test_original_identity_transition_source_facts_and_current_registration_closure():
    receipt = json.loads(TRANSITION.read_text())
    assert receipt["affected_components"] == sorted(F01_NAMES)
    assert receipt["decision"] == "F01-FRESH"
    assert receipt["summary"] == {
        "binding_implementation_addresses_moved": 17,
        "binding_source_contract_addresses_moved": 8,
        "component_addresses_moved": 0,
        "implementation_addresses_moved": 17,
        "published": False,
        "source_contract_addresses_moved": 8,
    }
    current = current_identities()
    assert set(current) == set(receipt["records"]) == set(subject.NAMES)
    for name, record in receipt["records"].items():
        # Keep historical source facts separate from maintained executable closures.
        fields = ("component_address", "source_contract_address", "binding_source_contract_address")
        assert {field: current[name][field] for field in fields} == {field: record["after"][field] for field in fields}
        assert record["after"]["component_address"] == record["before"]["component_address"]
        if name in F01_NAMES:
            assert record["changed_fields"] == [
                "binding_implementation_address", "binding_source_contract_address",
                "implementation_address", "source_contract_address",
            ]
        else:
            assert record["changed_fields"] == ["binding_implementation_address", "implementation_address"]
        fresh.assert_current_registry_identity(subject, subject.component_key(name))


def test_125_legacy_and_84_earlier_accepted_v2_source_facts_and_current_registrations_are_exact():
    catalogue = json.loads(CATALOGUE.read_text())["records"]
    assert len(catalogue) == 125
    for row in catalogue:
        key = (row["component_id"], 1)
        assert plain(DEFAULT_REGISTRY.v2_components[key]) == row["descriptor"]
        assert plain(DEFAULT_REGISTRY.node_contracts[key]) == row["node_contract"]
        assert plain(DEFAULT_REGISTRY.data_requirement_declarations[key]) == row["data_requirement"]
        assert DEFAULT_REGISTRY.node_contract_addresses[key] == row["node_contract_address"]
        assert DEFAULT_REGISTRY.data_requirement_declaration_addresses[key] == row["data_requirement_address"]
        assert DEFAULT_REGISTRY.v2_implementation_registrations[key].implementation_address == row["implementation_address"]

    current = {}
    for wave in (core_math, recursive_state, multi_output):
        for key in sorted(wave.V2_COMPONENTS):
            current[f"{key[0]}@{key[1]}"] = {
                "component_address": hashing.content_address(plain(wave.V2_COMPONENTS[key])),
                "source_contract_address": hashing.content_address(plain(wave.NODE_CONTRACTS[key])),
                "binding_source_contract_address": wave.CONTRACT_BINDINGS[key].source_contract_address,
            }
            fresh.assert_current_registry_identity(wave, key)
    accepted = json.loads(ACCEPTED_V2.read_text())["records"]
    assert len(current) == 84
    fields = ("component_address", "source_contract_address", "binding_source_contract_address")
    assert current == {name: {field: record["after"][field] for field in fields}
                       for name, record in accepted.items()}


def test_historical_rejections_and_original_correction_source_bytes_remain_exact():
    expected = {
        "paper-trader/backend/tests/fixtures/indicator_accuracy/historical_sources/session_data_prefix_correction.py": "3592d4478cf9494c196b415c468438d3ee9d9e157b2d2104922373e9f2eb534f",
        "paper-trader/backend/tests/test_indicator_accuracy_session_data.py": "6b7924a0ea1a3d5aaf768aec9c72b2023ffcd81a6677fda785413841815cc714",
        ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/report.md": "747e0ec93508e18a21ccf1685f9411e9cf7121533154a0804fab47be1949bfb4",
        ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/findings.json": "44ee328a8218044b31c66da37fa6c1c179db1e82e4531cccee31aba58cf9ddf0",
        ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/report.md": "0dd77b7b138419b815bbd4b7d44b24d5d14cc4bd2cd9edb3550928f22f4a71ec",
        ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/closure-seal.json": "0f7b86f8b4f1124c56073adb80bb730d702a7a0adcaffb0871beea300f1d2361",
        ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/report.md": "4076e85c867bb1e65b2878f4f4cce1fca846a753dd9a660cb6e9c36878167ecf",
        ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/identity-transition.json": "7c674e3be8a8b134333fd2df3cca0a15354cb10acc6f514143172238dd169725",
        ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/closure-seal.json": "fba09d80ed688718524a4d7797adc58ab6e9a29b6b9f16ecf777a52a1217a380",
    }
    for relative, wanted in expected.items():
        assert digest(ROOT / relative) == wanted, relative
