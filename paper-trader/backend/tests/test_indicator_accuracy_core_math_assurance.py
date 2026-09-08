"""Different-owner assurance of unpublished core math and its real boundaries."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import tracemalloc

import pandas as pd
import pytest

from research_tests import test_indicator_accuracy_core_math_oracle as oracle
from app.ir.first_party.analytical_v2 import core_math as core
from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract, canonical_input_bindings
from app.ir.node_contracts import NodeContractRefusal
from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.validity import NumericValue, ValidityState
from app.market_data.requirements import compile_data_requirement_plan

RUN = oracle.RUN
ROOT = Path(__file__).resolve().parents[3]
NAMES = oracle.NAMES


def plain(value):
    if isinstance(value, Mapping): return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [plain(item) for item in value]
    return value


def address(value):
    wire = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(wire.encode()).hexdigest()


def mark(name):
    return address({"core_math_independent_fixture": name})


def record(kind, value):
    if os.environ.get("CORE_ASSURANCE_RECORD") == "1":
        label = os.environ.get("CORE_ASSURANCE_LABEL", "unlabelled")
        with (RUN / (label + "-" + kind + ".jsonl")).open("a") as output:
            output.write(json.dumps(value, allow_nan=False, sort_keys=True) + "\n")


def fields(name):
    result = {"frame": sorted(field for field in oracle.declared_inputs(name) if field != "peer")}
    if "peer" in oracle.declared_inputs(name): result["peer"] = ["close"]
    return result


def port(name):
    return {"port_id": name, "direction": "input", "semantic_flow": "value", "semantic_role": "market_frame",
            "type_ref": {"type_id": "analytical.market_frame", "type_version": 2}, "shape": "series",
            "connections": {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}}


@lru_cache(maxsize=None)
def candidate_registry(name):
    key = ("analytical." + name.lower(), 2)
    return PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=core.V2_TYPES,
                            v2_components={key: core.V2_COMPONENTS[key]}, node_contracts={key: core.NODE_CONTRACTS[key]},
                            v2_implementations={key: core.V2_IMPLEMENTATIONS[key]}, contract_bindings={key: core.CONTRACT_BINDINGS[key]})


def input_facts(name, *, owner="assurance-owner", timeframe=300, market="market-truth", provider="offline-data-product"):
    return {role: {"schema": "canonical-input-binding/1", "owner_id": owner,
                   "dataset_context_address": mark("dataset"), "evaluation_context_address": mark("evaluation"),
                   "dataset_manifest_address": mark("manifest-" + role), "market_truth_address": mark(market),
                   "provider_product_address": mark(provider), "provider_contract_address": mark("provider-contract"),
                   "canonical_instrument_address": mark("instrument-" + role),
                   "instrument": {"role": "primary" if role == "frame" else role, "type": "PHYSICAL"},
                   "timeframe": timeframe, "fields": [field.upper() for field in columns],
                   "freshness": {"maximum_age_seconds": 600}, "depth": {"kind": "NONE", "levels": None},
                   "session": "INSTRUMENT_CALENDAR", "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
                   "derived_local": True} for role, columns in fields(name).items()}


@lru_cache(maxsize=None)
def _bound(name, serialized_parameters, owner, timeframe, market, provider):
    parameters = json.loads(serialized_parameters)
    registry = candidate_registry(name)
    key = ("analytical." + name.lower(), 2)
    graph = {"format_version": 2, "strategy_id": "independent-core-math", "strategy_version": 1,
             "metadata": {"metadata_version": 1, "name": "Independent core math", "description": None, "tags": []},
             "graph_inputs": [port(role) for role in fields(name)], "graph_outputs": [],
             "nodes": [{"node_id": "subject", "component": {"component_id": key[0], "component_version": 2}, "parameters": parameters}],
             "edges": [{"edge_id": role, "source": {"scope": "graph_input", "port_id": role},
                        "target": {"scope": "node", "node_id": "subject", "port_id": role}, "binding": {"kind": "single"}} for role in fields(name)]}
    resolved = resolve_v2(graph, registry)
    facts = input_facts(name, owner=owner, timeframe=timeframe, market=market, provider=provider)
    context = canonical_input_bindings(owner_id=owner, dataset_context_address=mark("dataset"),
                                       evaluation_context_address=mark("evaluation"), bindings=facts,
                                       expected_source_addresses={role: address(fact) for role, fact in facts.items()})
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    value = plan.parameter_binding_provenance[0]["node_contract_binding"]
    return ResolvedNodeContract(value, value["bound_contract_address"])


def binding(name, parameters=None, *, owner="assurance-owner", timeframe=300, market="market-truth", provider="offline-data-product"):
    return _bound(name, json.dumps(parameters or {}, sort_keys=True), owner, timeframe, market, provider)


def index_for(length):
    return pd.date_range("2026-08-27T23:40:00Z", periods=length, freq="5min")


def actual_cell(value):
    if isinstance(value, oracle.Cell):
        return NumericValue(ValidityState(value.state), value.value, tuple(ValidityState(cause) for cause in value.causes))
    return value


def inputs_for(name, rows, index=None):
    index = index_for(len(rows)) if index is None else index
    return {role: {field: pd.Series([actual_cell(row["peer" if role == "peer" else field]) for row in rows], index=index, dtype=object)
                   for field in columns} for role, columns in fields(name).items()}


def row_inputs(name, row):
    return {role: {field: actual_cell(row["peer" if role == "peer" else field]) for field in columns} for role, columns in fields(name).items()}


def compare(name, actual, expected, index, *, case, parameters=None):
    assert set(actual) == set(expected) == set(oracle.declared_outputs(name)), (name, case, "output closure")
    maximum_absolute = maximum_relative = 0.0
    valid_count = 0
    for output, cells in expected.items():
        series = actual[output]
        assert isinstance(series, pd.Series) and series.index.equals(index) and series.name == output
        assert len(series) == len(cells)
        for bar, (got, want) in enumerate(zip(series, cells)):
            identity = (name, output, bar, case, parameters)
            assert isinstance(got, NumericValue), identity
            assert got.state.value == want.state, (identity, got.state.value, want.state)
            assert tuple(cause.value for cause in got.causes) == want.causes, identity
            if want.state == "VALID":
                valid_count += 1
                if type(want.value) is not bool:
                    absolute = abs(got.value - want.value)
                    maximum_absolute = max(maximum_absolute, absolute)
                    if want.value != 0: maximum_relative = max(maximum_relative, absolute / abs(want.value))
                assert oracle.error_within(got.value, want.value, exact=name in oracle.EXACT), (identity, "number", got.value, want.value)
            else:
                assert got.value is None, identity
    record("comparisons", {"name": name, "case": case, "parameters": parameters or {}, "bars": len(index),
                            "outputs": list(expected), "valid_cells": valid_count,
                            "max_absolute_error": maximum_absolute, "max_relative_error": maximum_relative, "verdict": "PASS"})


def evaluate_compare(name, rows, parameters=None, *, case="specified", resets=None, index=None):
    index = index_for(len(rows)) if index is None else index
    expected = oracle.scalar_series(name, rows, parameters, resets)
    actual = core.evaluate(name, parameters or {}, inputs_for(name, rows, index), bound_contract=binding(name, parameters), resets=resets)
    compare(name, actual, expected, index, case=case, parameters=parameters)
    return actual, expected


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", ["jagged", "ramp", "reversal", "ties", "flat", "zero"])
def test_complete_arrays_against_independent_specification(name, kind):
    evaluate_compare(name, oracle.fixture_rows(kind=kind), case=kind)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("choice", ["minimum", "maximum", "nondefault"])
def test_parameter_endpoints_and_nondefaults_against_specification(name, choice):
    parameters = {}
    for key, spec in oracle.parameter_specs(name).items():
        if spec["type"] == "enum": parameters[key] = spec["values"][0 if choice == "minimum" else -1]
        else: parameters[key] = spec["minimum"] if choice == "minimum" else spec["maximum"] if choice == "maximum" else 37.5 if key == "q" else 7
    length = max(31, oracle.first_valid(name, parameters) + 4)
    evaluate_compare(name, oracle.fixture_rows(length), parameters, case=choice)


@pytest.mark.parametrize("name", NAMES)
def test_every_declared_input_invalidates_and_restarts_full_warmup(name):
    for field in oracle.declared_inputs(name):
        for invalid in (None, float("nan"), float("inf"), float("-inf"), True, oracle.Cell("STALE")):
            rows = oracle.fixture_rows(43)
            rows[18][field] = invalid
            evaluate_compare(name, rows, case="invalid-" + field + "-" + str(invalid))


@pytest.mark.parametrize("name", NAMES)
def test_causal_prefix_streaming_and_restart(name):
    rows = oracle.fixture_rows(45, "reversal")
    rows[19][oracle.declared_inputs(name)[0]] = None
    resets = [()] * len(rows); resets[32] = ("DATA_GAP",)
    _, expected = evaluate_compare(name, rows, resets=resets, case="stream-reset")
    idx = index_for(len(rows)); bound = binding(name)
    for stop in (1, oracle.first_valid(name) + 1, 30):
        prefix = core.evaluate(name, {}, inputs_for(name, rows[:stop], idx[:stop]), bound_contract=bound, resets=resets[:stop])
        compare(name, prefix, {port: cells[:stop] for port, cells in expected.items()}, idx[:stop], case="prefix-" + str(stop))
    state = core.CoreMathState(name, {}, bound)
    streamed = {port: [] for port in expected}
    checkpoints = {0, max(0, oracle.first_valid(name) - 1), oracle.first_valid(name), 19, 20, 31, 32}
    for bar, row in enumerate(rows):
        produced = state.step(row_inputs(name, row), event_time=idx[bar], reset_reasons=resets[bar])
        assert set(produced) == set(streamed)
        for output in streamed: streamed[output].append(produced[output])
        if bar in checkpoints:
            state = core.CoreMathState.restore(name, {}, bound, json.loads(json.dumps(state.snapshot())))
    compare(name, {output: pd.Series(values, index=idx, name=output) for output, values in streamed.items()}, expected, idx, case="restored-stream")


@pytest.mark.parametrize("name", NAMES)
def test_component_parameter_output_role_history_closure_and_refusals(name):
    key = ("analytical." + name.lower(), 2)
    descriptor = plain(core.V2_COMPONENTS[key])
    assert set(descriptor["parameters"]) == set(oracle.parameter_specs(name))
    assert {p["port_id"] for p in descriptor["ports"] if p["direction"] == "input"} == set(fields(name))
    assert {p["port_id"] for p in descriptor["ports"] if p["direction"] == "output"} == set(oracle.declared_outputs(name))
    assert dict(core.parameters_for(name)) == oracle.defaults(name)
    bound = binding(name)
    assert bound.document["resolved_contract"]["warmup_history"] == oracle.first_valid(name)
    assert dict(bound.document["resolved_contract"]["output_warmup"]) == {output: oracle.first_valid(name) for output in oracle.declared_outputs(name)}
    assert {row["instrument"]["role"] for row in bound.document["bound_requirements"]} == {"primary" if p == "frame" else p for p in fields(name)}
    for row in bound.document["bound_requirements"]:
        assert row["timeframe"] == 300 and row["history"]["warmup_bars"] == oracle.first_valid(name)
    for parameter, spec in oracle.parameter_specs(name).items():
        bad_values = [True, None, float("nan"), float("inf"), "14"]
        bad_values += [max(spec["values"]) + 1] if spec["type"] == "enum" else [spec["minimum"] - 1, spec["maximum"] + 1]
        for bad in bad_values:
            with pytest.raises(NodeContractRefusal):
                core.parameters_for(name, {parameter: bad})
            # NaN/infinity cannot be canonical JSON and may be refused by the
            # existing serializer before resolution reaches the node boundary.
            with pytest.raises((ValueError, ResolutionError)):
                candidate = binding(name, {parameter: bad})
                core.evaluate(name, {parameter: bad}, inputs_for(name, oracle.fixture_rows(2)), bound_contract=candidate)
    with pytest.raises((NodeContractRefusal, ResolutionError)):
        binding(name, {"unexpected": 1})
    for role, required in fields(name).items():
        for field in required:
            inputs = inputs_for(name, oracle.fixture_rows(3)); del inputs[role][field]
            with pytest.raises(NodeContractRefusal): core.evaluate(name, {}, inputs, bound_contract=bound)
        inputs = inputs_for(name, oracle.fixture_rows(3)); del inputs[role]
        with pytest.raises(NodeContractRefusal): core.evaluate(name, {}, inputs, bound_contract=bound)


def test_complete_universe_and_legacy_identity_are_unpublished_and_unchanged():
    assert tuple(core.NAMES) == NAMES
    expected = {("analytical." + name.lower(), 2) for name in NAMES}
    for collection in (core.V2_COMPONENTS, core.NODE_CONTRACTS, core.CONTRACT_BINDINGS, core.V2_IMPLEMENTATIONS):
        assert set(collection) == expected
    assert sum(len(oracle.declared_outputs(name)) for name in NAMES) == 60
    from app.ir.library import REGISTRY
    assert REGISTRY.registry_snapshot_address == "sha256:bef51d976101e495d3666fb89e3a6f0be4ea6dbe87ad7a0d4f2f1c075a9812d0"
    catalogue = json.loads((ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json").read_text())
    assert len(catalogue["records"]) == 125
    for row in catalogue["records"]:
        key = (row["component_id"], 1)
        assert plain(REGISTRY.v2_components[key]) == row["descriptor"]
        assert plain(REGISTRY.node_contracts[key]) == row["node_contract"]
        assert plain(REGISTRY.data_requirement_declarations[key]) == row["data_requirement"]
        assert REGISTRY.v2_implementation_registrations[key].implementation_address == row["implementation_address"]
        assert REGISTRY.node_contract_addresses[key] == row["node_contract_address"]
        assert REGISTRY.data_requirement_declaration_addresses[key] == row["data_requirement_address"]
    assert not expected.intersection(REGISTRY.v2_components)


def test_output_binding_guard():
    name = "ROLLING_REGRESSION"
    rows = oracle.fixture_rows(29)
    evaluate_compare(name, rows, case="output-guard")


def test_state_identity_guard():
    name = "SMA"; bound = binding(name)
    state = core.CoreMathState(name, {}, bound)
    for i, row in enumerate(oracle.fixture_rows(16)):
        state.step(row_inputs(name, row), event_time=index_for(16)[i])
    saved = state.snapshot()
    forged = deepcopy(saved); forged["bound_contract_address"] = mark("wrong-state-binding")
    forged["payload_address"] = address({key: value for key, value in forged.items() if key != "payload_address"})
    with pytest.raises(NodeContractRefusal, match="CORE_STATE_IDENTITY"):
        core.CoreMathState.restore(name, {}, bound, forged)
    assert core.CoreMathState.restore(name, {}, bound, saved).snapshot() == saved


@pytest.mark.parametrize("name", ["SMA", "BETA", "ROLLING_REGRESSION", "RATIO", "MFI"])
def test_actual_evaluation_rejects_forged_binding_and_input_clock(name):
    bound = binding(name); rows = oracle.fixture_rows(20); inputs = inputs_for(name, rows)
    for field in ("source_contract_address", "binding_implementation_address"):
        document = plain(bound.document); document[field] = mark("forged-" + field)
        document["bound_contract_address"] = address({key: value for key, value in document.items() if key != "bound_contract_address"})
        with pytest.raises(NodeContractRefusal):
            core.evaluate(name, {}, inputs, bound_contract=ResolvedNodeContract(document, document["bound_contract_address"]))
    for kind in ("naive", "duplicate", "reversed"):
        index = index_for(20)
        if kind == "naive": index = index.tz_localize(None)
        elif kind == "duplicate": index = index[:1].append(index[:19])
        else: index = index[::-1]
        with pytest.raises(NodeContractRefusal): core.evaluate(name, {}, inputs_for(name, rows, index), bound_contract=bound)
    if "peer" in fields(name):
        changed = inputs_for(name, rows)
        changed["peer"]["close"].index += pd.Timedelta(seconds=1)
        with pytest.raises(NodeContractRefusal, match="ALIGNMENT"):
            core.evaluate(name, {}, changed, bound_contract=bound)
    state = core.CoreMathState(name, {}, bound)
    with pytest.raises(NodeContractRefusal, match="COMPLETED"):
        state.step(row_inputs(name, rows[0]), event_time=index_for(1)[0], event_kind="forming_bar")
    state.step(row_inputs(name, rows[0]), event_time=index_for(1)[0])
    with pytest.raises(NodeContractRefusal, match="ORDER"):
        state.step(row_inputs(name, rows[0]), event_time=index_for(1)[0])


@pytest.mark.parametrize("changed", ["owner", "timeframe", "market", "provider", "parameters"])
def test_state_refuses_changed_canonical_context(changed):
    name = "SMA"; state = core.CoreMathState(name, {}, binding(name))
    saved = state.snapshot()
    kwargs = {changed: 900 if changed == "timeframe" else "different"}
    parameters = {"window": 2} if changed == "parameters" else {}
    if changed == "parameters": kwargs = {}
    with pytest.raises(NodeContractRefusal, match="CORE_STATE_IDENTITY"):
        core.CoreMathState.restore(name, parameters, binding(name, parameters, **kwargs), saved)


def deep_bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen: return 0
    seen.add(id(value)); size = sys.getsizeof(value)
    if isinstance(value, dict): size += sum(deep_bytes(key, seen) + deep_bytes(item, seen) for key, item in value.items())
    elif isinstance(value, (list, tuple)): size += sum(deep_bytes(item, seen) for item in value)
    return size


@pytest.mark.parametrize("name", NAMES)
def test_measured_resource_bounds_at_default_minimum_and_maximum(name):
    choices = [{}]
    for limit in ("minimum", "maximum"):
        choices.append({key: (min(spec["values"]) if limit == "minimum" else max(spec["values"])) if spec["type"] == "enum" else spec[limit]
                        for key, spec in oracle.parameter_specs(name).items()})
    for parameters in choices:
        bound = binding(name, parameters)
        state = core.CoreMathState(name, parameters, bound)
        capacity = oracle.first_valid(name, parameters) + 1
        rows = oracle.fixture_rows(capacity + 4); idx = index_for(len(rows))
        for i, row in enumerate(rows[:capacity]): state.step(row_inputs(name, row), event_time=idx[i])
        tracemalloc.start()
        durations = []
        for i in range(capacity, len(rows)):
            started = time.perf_counter_ns()
            state.step(row_inputs(name, rows[i]), event_time=idx[i])
            durations.append((time.perf_counter_ns() - started) / 1000)
        _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        saved = state.snapshot()
        state_size = deep_bytes(saved)
        encoded = len(json.dumps(saved, separators=(",", ":")).encode())
        history_size = deep_bytes(saved["rows"])
        profile = bound.document["resolved_contract"]["resource_profile"]
        assert len(saved["rows"]) == capacity
        assert all(len(row) == len(oracle.declared_inputs(name)) for row in saved["rows"])
        assert max(durations) <= profile["compute_microseconds_per_event"], (name, parameters, durations)
        assert max(state_size, encoded) <= profile["state_bytes_upper_bound"], (name, parameters, state_size)
        assert history_size <= profile["history_bytes_upper_bound"]
        assert state_size + peak <= profile["memory_bytes_upper_bound"]
        record("resources", {"name": name, "parameters": parameters, "capacity": capacity, "max_event_us": max(durations),
                             "history_bytes": history_size, "state_bytes": state_size, "encoded_bytes": encoded,
                             "allocation_peak_bytes": peak, "declared_profile": plain(profile), "verdict": "PASS"})


def test_percentile_explicit_float_math_does_not_hide_default_binding_rejection():
    name = "PERCENTILE"
    for q in (0.0, 37.5, 50.0, 100.0):
        for kind in ("jagged", "ties", "flat", "zero"):
            evaluate_compare(name, oracle.fixture_rows(39, kind), {"q": q}, case="explicit-float-" + kind)
    for window in (2, 14, 4096):
        evaluate_compare(name, oracle.fixture_rows(window + 3), {"q": 50.0, "window": window}, case="explicit-float-window")
    rows = oracle.fixture_rows(47)
    rows[17]["close"] = None; rows[21]["close"] = float("inf")
    resets = [()] * len(rows); resets[33] = ("DATA_GAP",)
    _, expected = evaluate_compare(name, rows, {"q": 50.0}, resets=resets, case="explicit-float-validity")
    bound = binding(name, {"q": 50.0}); state = core.CoreMathState(name, {"q": 50.0}, bound)
    streamed = []
    idx = index_for(len(rows))
    for i, row in enumerate(rows):
        streamed.append(state.step(row_inputs(name, row), event_time=idx[i], reset_reasons=resets[i])["value"])
        if i in (0, 12, 13, 17, 21, 33): state = core.CoreMathState.restore(name, {"q": 50.0}, bound, state.snapshot())
    compare(name, {"value": pd.Series(streamed, index=idx, name="value")}, expected, idx, case="explicit-float-state")


REFERENCE_CASES = json.loads((RUN / "reference-cases.json").read_text())["cases"] if (RUN / "reference-cases.json").exists() else []


@pytest.mark.parametrize("case", REFERENCE_CASES, ids=lambda case: case["id"])
def test_pinned_native_and_independent_exact_specification(case):
    native = {row["id"]: row for row in json.loads((RUN / "native-results.json").read_text())["results"]}[case["id"]]["values"]
    actual, expected = evaluate_compare(case["name"], case["rows"], case["parameters"], case=case["id"])
    failures = []
    exact_zero_residuals = []
    for bar, (cell, reference, truth) in enumerate(zip(actual["value"], native, expected["value"])):
        if cell.state is not ValidityState.VALID:
            if reference != "NaN": failures.append({"bar": bar, "state": cell.state.value, "native": reference})
            continue
        if type(reference) not in {int, float} or not oracle.error_within(cell.value, reference, exact=case["name"] in oracle.EXACT):
            failures.append({"bar": bar, "product": cell.value, "native": reference, "mathematical_expected": truth.value})
        if truth.value == 0 and type(reference) in {int, float} and reference != 0:
            assert abs(reference) <= 1e-12
            exact_zero_residuals.append({"bar": bar, "native": reference, "product": cell.value})
    record("native-comparisons", {"id": case["id"], "name": case["name"], "parameters": case["parameters"],
                                   "product_vs_specification": "PASS", "product_vs_raw_native": "FAIL" if failures else "PASS",
                                   "failures": failures, "native_residuals_at_exact_zero": exact_zero_residuals})
    if case["classification"] == "default_non_degenerate": assert not failures, (case["id"], failures[:3])
    if case["classification"] == "fraction_identity_two_points":
        for i in range(1, len(case["rows"])):
            rows = case["rows"][i - 1:i + 1]
            fraction = oracle.two_point_fraction_correlation([row["peer"] for row in rows], [row["close"] for row in rows])
            assert expected["value"][i].value == fraction


def test_native_evidence_and_required_reference_cases_are_complete():
    assert len(REFERENCE_CASES) == 39
    assert sum(case["classification"] == "default_non_degenerate" for case in REFERENCE_CASES) == 26
    document = json.loads((RUN / "native-results.json").read_text())
    assert document["compatibility"] == 0 and all(value == 0 for value in document["unstable_periods"].values())
    assert document["wrapper_version"] == "0.7.1"
    assert document["reference_receipt_sha256"] == "4009d26ff3949641700d59b33ec8a55d284eaa86ae759bc25a694a8e9396153a"


@pytest.mark.parametrize("name", ["PERCENT_RETURN", "ROLLING_RETURN", "ROC", "LOG_RETURN", "BETA", "ALPHA"])
@pytest.mark.parametrize("window_choice", ["minimum", "default"])
def test_small_nonzero_returns_keep_strict_relative_accuracy(name, window_choice):
    # Fresh finite inputs exercise nonzero relative accuracy, separately from
    # exact-zero native residuals. Decimal/Fraction truth uses exact input floats.
    rows = oracle.fixture_rows(37)
    for i, row in enumerate(rows):
        row["close"] = 100.0 + (((i * 7) % 19) + i) / 100000000
        row["peer"] = 200.0 + (((i * 11) % 23) + 2 * i) / 100000000
    parameters = {"window": oracle.parameter_specs(name)["window"][window_choice]}
    evaluate_compare(name, rows, parameters, case="small-nonzero-returns-" + window_choice)
