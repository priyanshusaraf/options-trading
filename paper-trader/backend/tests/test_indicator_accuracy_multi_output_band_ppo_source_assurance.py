"""Independent assurance for the corrected BOLLINGER_BANDS/PPO source identities."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import tracemalloc

import pandas as pd
import pytest

from app.ir import node_contracts
from app.ir.first_party.analytical_v2 import multi_output as product
from app.ir.validity import ValidityState


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance"
CORRECTION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-correction"
DECISION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-replan/decision.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


oracle = _load(
    "fresh_band_ppo_source_oracle",
    ROOT / "paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_band_ppo_source_oracle.py",
)
baseline = _load(
    "preserved_multi_output_consumer_harness",
    ROOT / "paper-trader/backend/tests/test_indicator_accuracy_multi_output_assurance.py",
)
source_contract_check = _load(
    "preserved_band_ppo_source_contract_check",
    ROOT / "paper-trader/backend/tests/test_indicator_accuracy_multi_output_band_ppo_source_contract.py",
)
INITIAL_SEAL = json.loads((RUN / "fresh-expectation-seal.json").read_text())
SEAL = json.loads((RUN / "adjudicated/fresh-expectation-seal.json").read_text())
BUNDLE = json.loads((RUN / "adjudicated/fresh-expected-vectors.json").read_text())
RAW_CASES = {case["id"]: case for case in BUNDLE["cases"]}


def _parameters(raw: dict[str, object]) -> dict[str, object]:
    return {
        key: float(value) if key in {"deviations", "multiplier"} else value
        for key, value in raw.items()
    }


def _case(case_id: str) -> dict[str, object]:
    raw = RAW_CASES[case_id]
    expected = {
        port: [None if value is None else float(value) for value in output["values"]]
        for port, output in raw["outputs"].items()
    }
    data = {
        field: [None if value is None else float(value) for value in values]
        for field, values in raw["inputs"].items()
    }
    threshold = (
        "NONRECURSIVE"
        if raw["component"]
        in {
            "BOLLINGER_BANDS",
            "BOLLINGER_BANDWIDTH",
            "BOLLINGER_PERCENT_B",
            "DONCHIAN_CHANNELS",
            "STOCHASTIC",
        }
        else "RECURSIVE"
    )
    return {
        "id": case_id,
        "component": raw["component"],
        "parameters": _parameters(raw["parameters"]),
        "data": data,
        "expected": expected,
        "threshold": threshold,
    }


CASES = {case_id: _case(case_id) for case_id in RAW_CASES}


def _comparison(result, case: dict[str, object]) -> dict[str, object]:
    report = baseline.comparison(result, case["expected"], case)
    path = RUN / "comparisons" / f"fresh-{case['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def _required_fields(name: str, parameters: dict[str, object]) -> tuple[str, ...]:
    return tuple(field.lower() for field in product.fields_by_port(name, parameters)["frame"])


def _direct_frame(case: dict[str, object]) -> dict[str, dict[str, pd.Series]]:
    index = pd.date_range("2026-02-01T03:45:00Z", periods=len(case["data"]["close"]), freq="5min")
    return {
        "frame": {
            field: pd.Series(case["data"][field], index=index, dtype=object)
            for field in _required_fields(case["component"], case["parameters"])
        }
    }


def _index(data: dict[str, dict[str, pd.Series]]) -> pd.DatetimeIndex:
    return next(iter(data["frame"].values())).index


def test_fresh_expectation_seal_is_exact_and_preinspection_independent() -> None:
    oracle_path = ROOT / "paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_band_ppo_source_oracle.py"
    initial_oracle_path = RUN / "initial-oracle.py"
    initial_vector_path = RUN / "fresh-expected-vectors.json"
    vector_path = RUN / "adjudicated/fresh-expected-vectors.json"
    assert hashlib.sha256(initial_oracle_path.read_bytes()).hexdigest() == INITIAL_SEAL["oracle_sha256"]
    assert hashlib.sha256(initial_vector_path.read_bytes()).hexdigest() == INITIAL_SEAL["vectors_sha256"]
    assert hashlib.sha256(oracle_path.read_bytes()).hexdigest() == SEAL["oracle_sha256"]
    assert hashlib.sha256(vector_path.read_bytes()).hexdigest() == SEAL["vectors_sha256"]
    assert INITIAL_SEAL["verdict"] == "FRESH_EXPECTATIONS_SEALED_BEFORE_PRODUCT_INSPECTION"
    adjudication = json.loads((RUN / "oracle-adjudication.json").read_text())
    assert adjudication["initial_oracle_sha256"] == INITIAL_SEAL["oracle_sha256"]
    assert adjudication["initial_vectors_sha256"] == INITIAL_SEAL["vectors_sha256"]
    assert adjudication["corrected_oracle_sha256"] == SEAL["oracle_sha256"]
    assert adjudication["corrected_vectors_sha256"] == SEAL["vectors_sha256"]
    assert adjudication["changed_contract"] == "MACD signal: SMA seed followed by EMA recurrence"
    assert not any(
        INITIAL_SEAL[key]
        for key in (
            "product_source_inspected",
            "correction_test_inspected",
            "producer_or_helper_inspected",
            "older_expected_code_inspected",
        )
    )
    tree = ast.parse(oracle_path.read_text())
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not ({"app", "tests", "research_tests", "pandas", "numpy"} & imports)
    assert INITIAL_SEAL["components"] == SEAL["components"] == 9
    assert INITIAL_SEAL["ports"] == SEAL["ports"] == 19
    assert INITIAL_SEAL["cases"] == SEAL["cases"] == 45
    assert INITIAL_SEAL["complete_output_positions"] == SEAL["complete_output_positions"] == 136614


def test_exact_source_delta_and_all_identity_invariants() -> None:
    before = json.loads((CORRECTION / "before/identities.json").read_text())
    decision_digest = hashlib.sha256(DECISION.read_bytes()).hexdigest()
    decision = json.loads(DECISION.read_text())
    assert decision_digest == oracle.SOURCE_DECISION_SHA256
    assert set(decision["corrected_target_delta"]) == {"BOLLINGER_BANDS", "PPO"}
    for name, old in before["multi"].items():
        key = product.component_key(name)
        expected = deepcopy(old["spec"])
        if name in decision["corrected_target_delta"]:
            expected.update(decision["corrected_target_delta"][name])
            expected["source_addresses"].append("sha256:" + decision_digest)
            assert product.CONTRACT_BINDINGS[key].source_contract_address != old["source"]
        else:
            assert product.CONTRACT_BINDINGS[key].source_contract_address == old["source"]
        assert node_contracts._plain(product.SPECS[name]) == expected
        assert product.CONTRACT_BINDINGS[key].implementation_address != old["binding"]
        assert product.V2_IMPLEMENTATIONS[key].implementation_address != old["implementation"]
    source_contract_check.test_all_function_class_bytes_and_nonmetadata_module_bytes_preserved()
    source_contract_check.test_legacy_core_recursive_and_default_registry_remain_unpublished_exact()


@pytest.mark.parametrize("case_id", list(CASES))
def test_fresh_complete_arrays_masks_and_actual_consumers(case_id: str) -> None:
    case = CASES[case_id]
    result, receipt = baseline.through_consumer(case)
    report = _comparison(result, case)
    assert not report.get("identity_error")
    assert not report["failing_ports"], report
    expected_ports = set(oracle.COMPONENT_PORTS[case["component"]])
    assert set(result) == expected_ports
    assert receipt["parameters"] == case["parameters"]
    assert receipt["source_contract_address"] == product.CONTRACT_BINDINGS[
        product.component_key(case["component"])
    ].source_contract_address
    assert receipt["resolved_contract"]["warmup_history"] == product.first_valid_index(
        case["component"], case["parameters"]
    )
    assert receipt["resolved_contract"]["output_warmup"] == dict.fromkeys(
        expected_ports, product.first_valid_index(case["component"], case["parameters"])
    )


@pytest.mark.parametrize("name", list(oracle.COMPONENT_PORTS))
def test_default_gap_prefix_stream_serialized_restart_and_cold_reset(name: str) -> None:
    case = CASES[f"{name}-default_gap"]
    parameters = case["parameters"]
    bound = baseline.bind(name, parameters)
    data = _direct_frame(case)
    batch = product.evaluate(name, parameters, data, bound_contract=bound)
    first = product.first_valid_index(name, parameters)
    event_index = _index(data)
    checkpoints = sorted({1, max(1, first - 1), first, first + 1, 46, 47, 48, len(event_index) - 2})
    state = product.MultiOutputState(name, parameters, bound)
    streamed = {port: [] for port in oracle.COMPONENT_PORTS[name]}
    for index, event_time in enumerate(event_index):
        row = {"frame": {field: series.iloc[index] for field, series in data["frame"].items()}}
        values = state.step(row, event_time=event_time)
        for port in streamed:
            streamed[port].append(values[port])
        if index in checkpoints:
            state = product.MultiOutputState.restore(
                name, parameters, bound, json.loads(json.dumps(state.snapshot()))
            )
            prefix = {
                "frame": {field: series.iloc[: index + 1] for field, series in data["frame"].items()}
            }
            prefix_result = product.evaluate(name, parameters, prefix, bound_contract=bound)
            for port in streamed:
                assert prefix_result[port].tolist() == streamed[port]
    for port in streamed:
        assert streamed[port] == batch[port].tolist()
    reset_at = 60
    resets: list[tuple[str, ...]] = [()] * len(event_index)
    resets[reset_at] = ("EXPLICIT",)
    reset = product.evaluate(name, parameters, data, bound_contract=bound, resets=resets)
    tail = {"frame": {field: series.iloc[reset_at:] for field, series in data["frame"].items()}}
    cold = product.evaluate(name, parameters, tail, bound_contract=bound)
    for port in streamed:
        assert reset[port].iloc[reset_at:].tolist() == cold[port].tolist()


@pytest.mark.parametrize("name", list(oracle.COMPONENT_PORTS))
def test_zero_states_and_tiny_nonzero_outputs_are_distinct(name: str) -> None:
    zero = CASES[f"{name}-zero"]
    tiny = CASES[f"{name}-tiny_nonzero"]
    zero_result = product.evaluate(name, zero["parameters"], _direct_frame(zero), bound_contract=baseline.bind(name, zero["parameters"]))
    tiny_result = product.evaluate(name, tiny["parameters"], _direct_frame(tiny), bound_contract=baseline.bind(name, tiny["parameters"]))
    first = product.first_valid_index(name, zero["parameters"])
    undefined = name in {"BOLLINGER_BANDWIDTH", "BOLLINGER_PERCENT_B", "PPO"}
    for port in oracle.COMPONENT_PORTS[name]:
        assert all(cell.state is ValidityState.INSUFFICIENT_HISTORY for cell in zero_result[port].iloc[:first])
        wanted = ValidityState.MATHEMATICALLY_UNDEFINED if undefined else ValidityState.VALID
        assert all(cell.state is wanted for cell in zero_result[port].iloc[first:])
        assert any(cell.state is ValidityState.VALID for cell in tiny_result[port])


def test_real_consumer_refuses_forged_source_output_state_and_event_order() -> None:
    baseline.test_runtime_rejects_self_readdressed_forgery("source_contract_address")
    baseline.test_runtime_rejects_self_readdressed_forgery("output")
    case = CASES["PPO-default_gap"]
    parameters = case["parameters"]
    bound = baseline.bind("PPO", parameters)
    data = _direct_frame(case)
    state = product.MultiOutputState("PPO", parameters, bound)
    for index in range(30):
        state.step(
            {"frame": {field: series.iloc[index] for field, series in data["frame"].items()}},
            event_time=data["frame"]["close"].index[index],
        )
    snapshot = json.loads(json.dumps(state.snapshot()))
    snapshot["bound_contract_address"] = baseline.addr("stale-source-state")
    snapshot["payload_address"] = baseline.hashing.content_address(
        {key: value for key, value in snapshot.items() if key != "payload_address"}
    )
    with pytest.raises(node_contracts.NodeContractRefusal):
        product.MultiOutputState.restore("PPO", parameters, bound, snapshot)
    event_time = data["frame"]["close"].index[29]
    row = {"frame": {field: series.iloc[29] for field, series in data["frame"].items()}}
    with pytest.raises(node_contracts.NodeContractRefusal):
        state.step(row, event_time=event_time)


def test_minimum_default_maximum_resources_and_restart() -> None:
    points = []
    for name in oracle.COMPONENT_PORTS:
        for regime in ("minimum", "default_gap", "maximum"):
            case = CASES[f"{name}-{regime}"]
            parameters = case["parameters"]
            bound = baseline.bind(name, parameters)
            data = _direct_frame(case)
            state = product.MultiOutputState(name, parameters, bound)
            maximum_step_us = 0.0
            tracemalloc.start()
            event_index = _index(data)
            for index, event_time in enumerate(event_index):
                row = {"frame": {field: series.iloc[index] for field, series in data["frame"].items()}}
                started = time.perf_counter_ns()
                state.step(row, event_time=event_time)
                maximum_step_us = max(maximum_step_us, (time.perf_counter_ns() - started) / 1000)
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            snapshot = json.loads(json.dumps(state.snapshot()))
            state_bytes = len(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())
            history_bytes = len(json.dumps(snapshot["history"], sort_keys=True, separators=(",", ":")).encode())
            restored = product.MultiOutputState.restore(name, parameters, bound, snapshot)
            next_time = event_index[-1] + pd.Timedelta(minutes=5)
            row = {"frame": {field: series.iloc[-1] for field, series in data["frame"].items()}}
            original_next = state.step(row, event_time=next_time)
            restored_next = restored.step(row, event_time=next_time)
            profile = node_contracts._plain(product.source_contract(name))["resource_profile"]
            checks = {
                "compute": maximum_step_us <= profile["compute_microseconds_per_event"],
                "memory": peak_bytes <= profile["memory_bytes_upper_bound"],
                "state": state_bytes <= profile["state_bytes_upper_bound"],
                "history": history_bytes <= profile["history_bytes_upper_bound"],
                "restart": original_next == restored_next,
            }
            points.append(
                {
                    "component": name,
                    "regime": regime,
                    "parameters": parameters,
                    "events": len(event_index),
                    "maximum_step_us": maximum_step_us,
                    "peak_bytes": peak_bytes,
                    "state_bytes": state_bytes,
                    "history_bytes": history_bytes,
                    "profile": profile,
                    "checks": checks,
                }
            )
            assert all(checks.values()), points[-1]
    (RUN / "resources.json").write_text(json.dumps(points, indent=2, allow_nan=False) + "\n")
    assert len(points) == 27


def test_preserved_historical_red_is_exact_and_unwaived() -> None:
    receipt = json.loads((RUN / "historical-red-recheck.json").read_text())
    assert receipt["tests"] == 600
    assert receipt["passed"] == 570
    assert receipt["failed"] == 30
    assert receipt["errors"] == 0
    assert receipt["skipped"] == 0
    assert len(receipt["native_failures"]) == 20
    assert len(receipt["F03_failures"]) == 9
    assert receipt["archived_old_source_failure"] == (
        "test_corrected_source_delta_and_preserved_accepted_identities"
    )
    assert receipt["xfail_markers"] == 0
    assert receipt["waivers"] == 0
