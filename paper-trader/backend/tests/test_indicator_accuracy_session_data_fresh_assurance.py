"""Historical fresh-assurance evidence and current session-data contracts."""
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
from research_tests import test_indicator_accuracy_session_data_fresh_oracle as independent


ROOT = Path(__file__).resolve().parents[3]
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"
TRANSITION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/identity-transition.json"
F01_NAMES = frozenset({
    "DISTANCE_FROM_SESSION_HIGH_LOW", "PREVIOUS_SESSION_FIELDS", "PREVIOUS_SESSION_OHLC",
    "SESSION_HIGH", "SESSION_LOW", "SESSION_OPEN", "SESSION_OPEN_HIGH_LOW", "VWAP",
})
EXPECTED_PRODUCT_SHA = "7dd508c41cb267f7fe571b60fef414c3244b6c3373178c043226811213a4b897"
NOT_READY = ValidityState.INSUFFICIENT_HISTORY


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [plain(item) for item in value]
    return value


def mark(label):
    return hashing.content_address({"fresh_session_assurance": label})


def params(name, *, field="close"):
    if name == "ANCHORED_VWAP":
        return {"anchor_at": "2026-01-02T23:00:00+00:00"}
    if name == "OPENING_RANGE":
        return {"range_minutes": 60}
    if name == "PREVIOUS_SESSION_FIELDS":
        return {"field": field}
    return {}


def fixture_inputs(name, *, field="close"):
    source = independent.columns()
    index = pd.DatetimeIndex(pd.to_datetime(source["event_time"], utc=True))
    values = {
        "open": source["open"], "high": source["high"], "low": source["low"],
        "close": source["close"], "volume": source["volume"], "session_id": source["session_id"],
        "session_open_at": tuple(pd.Timestamp(value) for value in source["session_open_at"]),
        "session_close_at": tuple(pd.Timestamp(value) for value in source["session_close_at"]),
    }
    result = {}
    for port, fields in subject.fields_by_port(name, params(name, field=field)).items():
        result[port] = {}
        for declared in fields:
            key = declared.lower()
            column = values[key]
            if key in subject.NUMERIC_FIELDS:
                column = tuple(float(Decimal(item)) for item in column)
            result[port][key] = pd.Series(column, index=index)
    return result


def binding_fact(name, port, fields):
    primary = subject.source_contract(name)["required_resolution"]["port"]
    role = "primary" if port == primary else port
    return {
        "schema": "canonical-input-binding/1",
        "owner_id": "org.fresh-session-assurance",
        "dataset_context_address": mark("dataset"),
        "evaluation_context_address": mark("evaluation"),
        "dataset_manifest_address": mark("manifest"),
        "market_truth_address": mark("market-truth"),
        "provider_product_address": mark("provider-product"),
        "provider_contract_address": mark("provider-contract"),
        "canonical_instrument_address": mark("instrument:" + role),
        "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": 1800,
        "fields": sorted(fields),
        "freshness": {"maximum_age_seconds": 1800},
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": port == "session",
    }


def one_component_registry(name):
    key = subject.component_key(name)
    return PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=subject.V2_TYPES,
        v2_components={key: subject.V2_COMPONENTS[key]}, node_contracts={key: subject.NODE_CONTRACTS[key]},
        contract_bindings={key: subject.CONTRACT_BINDINGS[key]},
        v2_implementations={key: subject.V2_IMPLEMENTATIONS[key]},
    )


def graph(name, *, field="close"):
    key = subject.component_key(name)
    ports = plain(subject.V2_COMPONENTS[key]["ports"])
    inputs = [deepcopy(port) for port in ports if port["direction"] == "input"]
    outputs = [deepcopy(port) for port in ports if port["direction"] == "output"]
    return {
        "format_version": 2, "strategy_id": "fresh-session-assurance", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Fresh session assurance", "description": None, "tags": []},
        "graph_inputs": inputs, "graph_outputs": outputs,
        "nodes": [{"node_id": "candidate", "component": {"component_id": key[0], "component_version": 2},
                   "parameters": params(name, field=field)}],
        "edges": [
            {"edge_id": "in:" + port["port_id"], "source": {"scope": "graph_input", "port_id": port["port_id"]},
             "target": {"scope": "node", "node_id": "candidate", "port_id": port["port_id"]},
             "binding": {"kind": "single"}} for port in inputs
        ] + [
            {"edge_id": "out:" + port["port_id"],
             "source": {"scope": "node", "node_id": "candidate", "port_id": port["port_id"]},
             "target": {"scope": "graph_output", "port_id": port["port_id"]},
             "binding": {"kind": "single"}} for port in outputs
        ],
    }


def compiled(name, *, field="close"):
    parameters = params(name, field=field)
    facts = {port: binding_fact(name, port, fields) for port, fields in subject.fields_by_port(name, parameters).items()}
    context = canonical_input_bindings(
        owner_id="org.fresh-session-assurance", dataset_context_address=mark("dataset"),
        evaluation_context_address=mark("evaluation"), bindings=facts,
        expected_source_addresses={port: hashing.content_address(fact) for port, fact in facts.items()},
    )
    registry = one_component_registry(name)
    resolved = resolve_v2(graph(name, field=field), registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)
    receipt = plan.parameter_binding_provenance[0]["node_contract_binding"]
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    return registry, resolved, context, plan, bound


def consumer_result(name, *, field="close"):
    registry, resolved, _, _, bound = compiled(name, field=field)
    result = evaluate_v2(
        resolved, fixture_inputs(name, field=field), registry,
        evaluation_context_resolver=lambda _node, _inputs: {"bound_contract": bound},
    )
    return result, bound


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
        if wanted != 0:
            assert absolute / abs(wanted) <= 1e-9, position


def test_all_31_decisions_are_closed_without_placeholder_execution():
    candidates = set(independent.EXPECTED) | {"PREVIOUS_SESSION_FIELDS"}
    assert set(subject.ALL_NAMES) == candidates | set(independent.REFUSALS)
    assert set(subject.NAMES) == candidates and len(subject.NAMES) == 17
    assert set(subject.REFUSED_NAMES) == set(independent.REFUSALS) and len(subject.REFUSED_NAMES) == 14
    for key in subject.V2_COMPONENTS:
        assert_current_registry_identity(subject, key)
    for name, code in independent.REFUSALS.items():
        refusal = subject.refusal_for(name)
        assert refusal["code"] == code and refusal["executable"] is False
        assert ("analytical." + name.lower(), 2) not in subject.V2_COMPONENTS
        assert ("analytical." + name.lower(), 2) not in DEFAULT_REGISTRY.v2_components
        with pytest.raises(node_contracts.NodeContractRefusal, match=code):
            subject.component_key(name)


@pytest.mark.parametrize("name", sorted(independent.EXPECTED))
def test_complete_arrays_masks_and_real_consumers(name):
    outputs, _ = consumer_result(name)
    assert set(outputs) == set(independent.EXPECTED[name])
    for port, expected in independent.EXPECTED[name].items():
        assert_complete(outputs[port], expected)


@pytest.mark.parametrize("field", ("open", "high", "low", "close", "volume"))
def test_every_previous_session_field_array(field):
    outputs, _ = consumer_result("PREVIOUS_SESSION_FIELDS", field=field)
    assert_complete(outputs["value"], independent.previous_field(field))


@pytest.mark.parametrize("name", subject.NAMES)
def test_batch_prefix_stream_restart_and_cold_replay_agree(name):
    batch, bound = consumer_result(name)
    selected = fixture_inputs(name)
    parameters = params(name)
    declared = subject.fields_by_port(name, parameters)
    state = subject.SessionDataState(name, parameters, bound)
    index = next(iter(next(iter(selected.values())).values())).index
    for position, event_time in enumerate(index):
        prefix = {port: {field.lower(): selected[port][field.lower()].iloc[:position + 1] for field in fields}
                  for port, fields in declared.items()}
        cold = subject.evaluate(name, parameters, prefix, bound_contract=bound)
        row = {port: {field.lower(): selected[port][field.lower()].iloc[position] for field in fields}
               for port, fields in declared.items()}
        streamed = state.step(row, event_time=event_time)
        for port in batch:
            assert cold[port].tolist() == batch[port].iloc[:position + 1].tolist()
            assert streamed[port] == batch[port].iloc[position]
        state = subject.SessionDataState.restore(name, parameters, bound, json.loads(json.dumps(state.snapshot())))


def test_prior_f01_historical_fallback_is_reproduced_but_current_eight_must_refuse_second_slot():
    accepted = []
    missing_open_evidence = []
    for name in sorted(F01_NAMES):
        # Isolated historical path: the old contract omitted session_open_at, so
        # _session_context inferred a synthetic open exactly one bar earlier.
        historical = object.__new__(subject.SessionDataState)
        historical.timeframe = 1800
        historical._last_time = None
        historical._clear()
        event_time = pd.Timestamp("2026-01-02T23:00:00Z")
        historical._session_context(
            {"session_id": "OVERNIGHT", "session_close_at": pd.Timestamp("2026-01-02T23:30:00Z")},
            event_time, require_prefix=True,
        )
        assert historical._session_open == pd.Timestamp("2026-01-02T22:30:00Z")

        declared = {field for fields in subject.fields_by_port(name, params(name)).values() for field in fields}
        if "SESSION_OPEN_AT" not in declared:
            missing_open_evidence.append(name)
        _, bound = consumer_result(name)
        selected = fixture_inputs(name)
        suffix = {port: {field: series.iloc[1:] for field, series in values.items()} for port, values in selected.items()}
        try:
            subject.evaluate(name, params(name), suffix, bound_contract=bound)
        except node_contracts.NodeContractRefusal:
            continue
        accepted.append(name)
    assert missing_open_evidence == [], f"canonical session-open evidence absent: {missing_open_evidence}"
    assert accepted == [], f"second-slot suffix accepted: {accepted}"


@pytest.mark.parametrize("name", sorted(subject.SESSION_PREFIX_NAMES))
def test_missing_internal_slot_is_never_row_compressed(name):
    _, bound = consumer_result(name)
    selected = fixture_inputs(name)
    missing = {port: {field: series.drop(series.index[1]) for field, series in values.items()}
               for port, values in selected.items()}
    with pytest.raises(node_contracts.NodeContractRefusal, match="MISSING_SESSION_SLOT"):
        subject.evaluate(name, params(name), missing, bound_contract=bound)


def test_incomplete_prior_session_can_never_be_exposed_as_previous_aggregate():
    for name in ("PREVIOUS_SESSION_FIELDS", "PREVIOUS_SESSION_OHLC"):
        _, bound = consumer_result(name)
        selected = fixture_inputs(name)
        # Start the first session at its second slot, include its declared close,
        # then include the next session. A complete-prefix guard must reject.
        positions = [1, 2, 3, 4]
        incomplete = {port: {field: series.iloc[positions] for field, series in values.items()}
                      for port, values in selected.items()}
        with pytest.raises(node_contracts.NodeContractRefusal, match="INCOMPLETE_SESSION_PREFIX"):
            subject.evaluate(name, params(name), incomplete, bound_contract=bound)


def test_parameter_anchor_state_and_first_above_resource_domains_refuse():
    assert subject.parameters_for("OPENING_RANGE", {"range_minutes": 1})["range_minutes"] == 1
    assert subject.parameters_for("OPENING_RANGE", {"range_minutes": 240})["range_minutes"] == 240
    for value in (0, 241, True, 1.0, None):
        with pytest.raises(node_contracts.NodeContractRefusal):
            subject.parameters_for("OPENING_RANGE", {"range_minutes": value})
    for value in (None, pd.Timestamp("2026-01-02T23:00:00Z"), "2026-01-02T23:00:00Z", "2026-01-02"):
        with pytest.raises(node_contracts.NodeContractRefusal):
            subject.parameters_for("ANCHORED_VWAP", {"anchor_at": value})

    for name, counter, code in (
        ("SESSION_HIGH", "_session_count", "SESSION_PREFIX_LIMIT"),
        ("ANCHORED_VWAP", "_anchor_count", "ANCHOR_HISTORY_LIMIT"),
    ):
        _, bound = consumer_result(name)
        state = subject.SessionDataState(name, params(name), bound)
        selected = fixture_inputs(name)
        index = next(iter(next(iter(selected.values())).values())).index
        first = 0 if name == "SESSION_HIGH" else 1
        row = {port: {field: series.iloc[first] for field, series in values.items()} for port, values in selected.items()}
        state.step(row, event_time=index[first])
        setattr(state, counter, 100000)
        second = first + 1
        row = {port: {field: series.iloc[second] for field, series in values.items()} for port, values in selected.items()}
        with pytest.raises(node_contracts.NodeContractRefusal, match=code):
            state.step(row, event_time=index[second])
        forged = state.snapshot()
        forged[counter.removeprefix("_")] = 100001
        body = {key: value for key, value in forged.items() if key != "payload_address"}
        forged["payload_address"] = hashing.content_address(body)
        with pytest.raises(node_contracts.NodeContractRefusal, match="STATE_COUNTER"):
            subject.SessionDataState.restore(name, params(name), bound, forged)


def test_wrong_role_session_identity_alignment_and_derived_local_fail_consumers():
    name = "BARS_SINCE_SESSION_OPEN"
    registry, resolved, context, plan, _ = compiled(name)
    mutations = (
        ("instrument", {"role": "peer", "type": "PHYSICAL"}),
        ("session", "CONTINUOUS"),
        ("derived_local", False),
        ("alignment", {"kind": "AS_OF", "maximum_skew_seconds": 1}),
    )
    for field, value in mutations:
        document = plain(context.document)
        binding = document["inputs"]["session"]["binding"]
        binding[field] = value
        row = document["inputs"]["session"]
        row["binding_address"] = hashing.content_address(binding)
        row["source_address"] = row["binding_address"]
        with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
            forged = type(context)(document, hashing.content_address(document))
            verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=forged)


def assert_current_registry_identity(wave, key):
    """Published registrations must retain the current module's exact authority."""
    contract = plain(wave.NODE_CONTRACTS[key])
    assert plain(DEFAULT_REGISTRY.v2_components[key]) == plain(wave.V2_COMPONENTS[key])
    assert plain(DEFAULT_REGISTRY.node_contracts[key]) == contract
    assert DEFAULT_REGISTRY.node_contract_addresses[key] == hashing.content_address(contract)
    assert DEFAULT_REGISTRY.contract_bindings[key] == wave.CONTRACT_BINDINGS[key]
    assert DEFAULT_REGISTRY.contract_bindings[key].source_contract_address == hashing.content_address(contract)
    assert DEFAULT_REGISTRY.v2_implementation_registrations[key] == wave.V2_IMPLEMENTATIONS[key]
    assert DEFAULT_REGISTRY.v2_implementation_identities[key] == wave.V2_IMPLEMENTATIONS[key].implementation_address


def test_legacy_125_and_accepted_84_source_facts_and_current_registrations_are_exact():
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

    transition = json.loads(TRANSITION.read_text())["records"]
    current = {}
    for wave in (core_math, recursive_state, multi_output):
        for key in sorted(wave.V2_COMPONENTS):
            current[f"{key[0]}@{key[1]}"] = {
                "component_address": hashing.content_address(plain(wave.V2_COMPONENTS[key])),
                "source_contract_address": hashing.content_address(plain(wave.NODE_CONTRACTS[key])),
                "binding_source_contract_address": wave.CONTRACT_BINDINGS[key].source_contract_address,
            }
            assert_current_registry_identity(wave, key)
    assert len(current) == 84
    # The historical source facts remain exact. Later role handling changes the
    # executable closures, whose current authority is checked against the registry.
    fields = ("component_address", "source_contract_address", "binding_source_contract_address")
    assert current == {marker: {field: record["after"][field] for field in fields}
                       for marker, record in transition.items()}


def test_session_identity_closure_and_research_only_registry_integration():
    identities = {}
    for name in subject.NAMES:
        key = subject.component_key(name)
        identities[name] = {
            "component": hashing.content_address(plain(subject.V2_COMPONENTS[key])),
            "source": hashing.content_address(plain(subject.NODE_CONTRACTS[key])),
            "binding_source": subject.CONTRACT_BINDINGS[key].source_contract_address,
            "binding_implementation": subject.CONTRACT_BINDINGS[key].implementation_address,
            "implementation": subject.V2_IMPLEMENTATIONS[key].implementation_address,
        }
        assert subject.NODE_CONTRACTS[key]["mode_eligibility"] == {"research": True, "paper": False, "live": False}
        assert subject.NODE_CONTRACTS[key]["provider_requirements"] == ()
        assert_current_registry_identity(subject, key)
    assert len(identities) == 17 and len({row["implementation"] for row in identities.values()}) == 17


def test_historical_product_and_rejection_hashes_and_unchanged_controls_are_exact():
    expected = {
        "paper-trader/backend/tests/fixtures/indicator_accuracy/historical_sources/session_data_before_prefix_correction.py": EXPECTED_PRODUCT_SHA,
        "paper-trader/backend/tests/test_indicator_accuracy_session_data.py": "6b7924a0ea1a3d5aaf768aec9c72b2023ffcd81a6677fda785413841815cc714",
        ".agent/runs/post-phase5-indicator-accuracy-session-data/closure-seal.json": "6de01a2b59e4a07eee68bd5c58777d8d0152d3f62063f5e7c36d6e35750454ec",
        ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/report.md": "747e0ec93508e18a21ccf1685f9411e9cf7121533154a0804fab47be1949bfb4",
        ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/findings.json": "44ee328a8218044b31c66da37fa6c1c179db1e82e4531cccee31aba58cf9ddf0",
        ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/closure-seal.json": "4c04161d7d390914981f8f8fe56eee549faf0cca854267d4fbcb61e21e2b91ef",
        "paper-trader/backend/app/ir/registry.py": "4c1d83e9f8714d9e8a11e571426cde6b7a896fe47aec3d3fe1a44b4f58bf120f",
        "paper-trader/backend/app/ir/node_contracts.py": "a1e16b735cd8decfcad4356aa82c10a20d65c5129f25d78ae7931ad9596af284",
        "paper-trader/backend/app/market_data/requirements.py": "d1d0a4b278a4d2d503667197c384ee07b0d58c790fa1726ada8e9bfbea8354d4",
    }
    for relative, wanted in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == wanted
