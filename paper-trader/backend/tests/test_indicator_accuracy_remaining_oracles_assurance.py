"""Different-owner assurance for the unpublished remaining-oracles wave."""
from __future__ import annotations

from copy import deepcopy
import ast
import hashlib
import json
import math
from pathlib import Path
import time
import tracemalloc

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import remaining_oracles as subject
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract
from app.ir.validity import NumericValue, ValidityState
from research_tests import test_indicator_accuracy_remaining_oracles_oracle as oracle


ROOT = Path(__file__).resolve().parents[3]
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"
SUBJECT = ROOT / "paper-trader/backend/app/ir/first_party/analytical_v2/remaining_oracles.py"
LEGACY = ROOT / "paper-trader/backend/app/ir/first_party/analytical.py"
SOURCE_ADDRESSES = {
    "specification": "sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb",
    "architecture": "sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482",
    "binding": "sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925",
    "source_policy": "sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994",
    "verification": "sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3",
    "audit_refusal": "sha256:e83da220d7eb2416cc780504c346f7f5abd6dffecb54b3a01ea014d643bc9418",
    "nist_scale": "sha256:bad33742f059fe2dfee9b2d26139b525dbedf7a6d702d8a1e7ccabc6c71eccfe",
    "rogers_satchell": "sha256:22d07345c6b50edfafe30cc0efd2d06b72e277957c0857a154e05d17fe2e678b",
    "yang_zhang": "sha256:3cffec0643654ca22db333f6fdf4688ab6be836d53942b5cfd04643588e44911",
}
SEALED_FILE_HASHES = {
    SUBJECT: "aa0beead42fa1ee0ffc69dddcfc7fa3d83d62ec5c431138950593115261a061c",
    LEGACY: "4b164cac9c1a71ab810b457ea404266034c4043185fa7712ade0d38d411d5fec",
    CATALOGUE: "f0be00e88ca9b1c3799ec98ab14fe16359b0ccf0bd2d1c2a32f422075e17cb6f",
}


def address(value):
    return hashing.content_address({"remaining_oracles_assurance": value})


def plain(value):
    return node_contracts._plain(value)


def parameters(name, kind="small"):
    values = oracle.defaults(name)
    if kind == "small":
        return oracle.small_parameters(name)
    for key, spec in oracle.PARAMETERS[name].items():
        if kind == "minimum":
            values[key] = spec[1]
        elif kind == "maximum":
            values[key] = spec[2]
    return values


def binding(name, supplied, *, role="primary", skew=0, fields=None, timeframe=900):
    required = tuple(sorted(field.upper() for field in oracle.INPUTS[name]))
    fact = {
        "schema": "canonical-input-binding/1",
        "owner_id": "org.remaining.assurance",
        "dataset_context_address": address("dataset"),
        "evaluation_context_address": address("evaluation"),
        "dataset_manifest_address": address("manifest"),
        "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"),
        "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("instrument"),
        "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": timeframe,
        "fields": list(required if fields is None else fields),
        "freshness": {"maximum_age_seconds": 900},
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": skew},
        "derived_local": False,
    }
    ports = {"frame": {
        "source": {"scope": "graph_input", "port_id": "frame"},
        "binding": fact,
        "binding_address": hashing.content_address(fact),
    }}
    inputs = {
        "schema": "node-input-binding/1",
        "owner_id": "org.remaining.assurance",
        "dataset_context_address": address("dataset"),
        "evaluation_context_address": address("evaluation"),
        "context_address": hashing.content_address(ports),
        "ports": ports,
    }
    key = subject.component_key(name)
    return materialize_node_contract(subject.source_contract(name), subject.CONTRACT_BINDINGS[key], supplied, inputs)


def index_for(count):
    # Crosses civil midnight and a weekend without inventing a session reset.
    return pd.date_range("2025-01-03T22:45:00Z", periods=count, freq="17min")


def inputs_for(name, rows, index=None):
    index = index_for(len(rows)) if index is None else index
    return {"frame": {
        field: pd.Series([row[field] for row in rows], index=index)
        for field in oracle.INPUTS[name]
    }}


def evaluate(name, supplied, rows, resets=None):
    return subject.evaluate(
        name,
        supplied,
        inputs_for(name, rows),
        bound_contract=binding(name, supplied),
        resets=resets,
    )["value"].tolist()


def compare_complete(name, actual, expected):
    assert len(actual) == len(expected)
    recursive = name == "EWMA_VOLATILITY"
    for offset, (cell, wanted) in enumerate(zip(actual, expected)):
        assert isinstance(cell, NumericValue), offset
        assert cell.state.value == wanted.state, (name, offset, cell, wanted)
        if wanted.state != "VALID":
            assert cell.value is None, (name, offset, cell)
            continue
        assert isinstance(cell.value, float) and math.isfinite(cell.value), (name, offset, cell)
        absolute = abs(cell.value - wanted.value)
        if wanted.value == 0:
            assert absolute <= 1e-12, (name, offset, absolute)
        else:
            relative = absolute / abs(wanted.value)
            assert absolute <= 1e-10, (name, offset, absolute)
            assert relative <= (1e-8 if recursive else 1e-9), (name, offset, relative)


def assert_closed_universe():
    assert subject.ALL_NAMES == tuple(sorted(oracle.ALL_NAMES))
    assert subject.NAMES == tuple(sorted(oracle.NAMES))
    assert subject.REFUSED_NAMES == tuple(sorted(oracle.REFUSED))
    expected = {("analytical." + name.lower(), 2) for name in oracle.NAMES}
    for collection in (subject.V2_COMPONENTS, subject.NODE_CONTRACTS,
                       subject.CONTRACT_BINDINGS, subject.V2_IMPLEMENTATIONS):
        assert set(collection) == expected
    for name in oracle.NAMES:
        ports = [port["port_id"] for port in subject.descriptor(name)["ports"] if port["direction"] == "output"]
        assert ports == list(oracle.OUTPUTS[name])


def test_all_ten_decisions_seven_candidates_three_refusals_and_source_seals():
    assert_closed_universe()
    assert len(subject.SPECS) == 10 and len(subject.V2_COMPONENTS) == 7 and len(subject.REFUSALS) == 3
    for name in oracle.ALL_NAMES:
        spec = subject.SPECS[name]
        assert spec["decision"] == oracle.DECISIONS[name]
        assert tuple(spec["inputs"]) == oracle.INPUTS[name]
        assert plain(spec["outputs"]) == oracle.OUTPUTS[name]
        for key in ("specification", "architecture", "binding", "source_policy", "verification"):
            assert SOURCE_ADDRESSES[key] in spec["source_addresses"]
    assert SOURCE_ADDRESSES["nist_scale"] in subject.SPECS["REALIZED_VOLATILITY"]["source_addresses"]
    assert SOURCE_ADDRESSES["rogers_satchell"] in subject.SPECS["ROGERS_SATCHELL"]["source_addresses"]
    for name in ("PARKINSON", "YANG_ZHANG"):
        assert SOURCE_ADDRESSES["yang_zhang"] in subject.SPECS[name]["source_addresses"]
    for path, expected in SEALED_FILE_HASHES.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    oracle_tree = ast.parse(Path(oracle.__file__).read_text())
    imported = set()
    for node in ast.walk(oracle_tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name == "app" or name.startswith("app.") or name.startswith("tests")
                   or name.startswith("research_tests") for name in imported)


@pytest.mark.parametrize("name", oracle.REFUSED)
def test_three_typed_refusals_never_mint_an_executable_placeholder(name):
    record = subject.REFUSALS[name]
    assert record["schema"] == "analytical-unavailable-component/1"
    assert record["decision"] == "REFUSE" and record["executable"] is False
    assert record["code"] == oracle.REFUSAL_CODES[name]
    assert tuple(record["inputs"]) == oracle.INPUTS[name]
    assert plain(record["outputs"]) == oracle.OUTPUTS[name]
    assert SOURCE_ADDRESSES["audit_refusal"] in record["source_addresses"]
    for inputs, supplied, capability in (
        (None, None, False),
        ({"frame": {}}, {}, False),
        ({"frame": {field: 100.0 for field in oracle.INPUTS[name]}}, oracle.defaults(name), True),
    ):
        with pytest.raises(node_contracts.NodeContractRefusal, match=oracle.REFUSAL_CODES[name]):
            subject.refuse(name, inputs=inputs, parameters=supplied, capability_verified=capability)
    with pytest.raises(node_contracts.NodeContractRefusal, match=oracle.REFUSAL_CODES[name]):
        subject.component_key(name)


@pytest.mark.parametrize("name", oracle.NAMES)
def test_parameter_output_binding_and_resource_contract_closure(name):
    descriptor = subject.descriptor(name)
    contract = subject.source_contract(name)
    assert set(descriptor["parameters"]) == set(oracle.PARAMETERS[name])
    assert [port["port_id"] for port in descriptor["ports"] if port["direction"] == "output"] == ["value"]
    assert plain(contract["output_types"]) == {"value": "analytical.float64/series"}
    assert tuple(contract["required_market_fields"]) == tuple(sorted(oracle.INPUTS[name]))
    assert contract["bar_policy"] == "COMPLETED_ONLY"
    assert contract["causal_declaration"] == "COMPLETED_EVENT_PREFIX"
    assert contract["state_reset_policy"]["reasons"] == ("DATA_GAP", "EXPLICIT", "IDENTITY_CHANGE")
    assert plain(contract["mode_eligibility"]) == {"research": True, "paper": False, "live": False}
    assert contract["provider_requirements"] == ()
    assert set(contract["parameter_binding"]["parameter_names"]) == set(oracle.PARAMETERS[name])
    for key, (kind, minimum, maximum, default) in oracle.PARAMETERS[name].items():
        actual = subject.SPECS[name]["parameters"][key]
        assert (actual["type"], actual["minimum"], actual["maximum"], actual["default"]) == (
            kind, minimum, maximum, default)
    for kind in ("default", "small", "minimum", "maximum"):
        supplied = oracle.defaults(name) if kind == "default" else parameters(name, kind)
        assert plain(subject.parameters_for(name, supplied)) == supplied
        resolved = binding(name, supplied)
        first = oracle.first_valid(name, supplied)
        assert resolved.document["resolved_contract"]["warmup_history"] == first
        assert plain(resolved.document["resolved_contract"]["output_warmup"]) == {"value": first}
        assert plain(resolved.document["parameters"]) == supplied
    with pytest.raises(node_contracts.NodeContractRefusal):
        subject.parameters_for(name, {"unknown": 1})
    for key, (kind, minimum, maximum, _) in oracle.PARAMETERS[name].items():
        for bad in (True, False, None, "2", math.nan, math.inf, minimum - 1, maximum + 1):
            with pytest.raises(node_contracts.NodeContractRefusal):
                subject.parameters_for(name, {key: bad})
        if kind == "exact_integer":
            with pytest.raises(node_contracts.NodeContractRefusal):
                subject.parameters_for(name, {key: float(minimum)})


@pytest.mark.parametrize("name", oracle.NAMES)
@pytest.mark.parametrize("kind", ("default", "small", "minimum"))
def test_independent_complete_arrays_masks_validity_and_seeds(name, kind):
    supplied = oracle.defaults(name) if kind == "default" else parameters(name, kind)
    count = oracle.first_valid(name, supplied) + 9
    rows = oracle.fixture_rows(count)
    expected = oracle.expected(name, supplied, rows)
    compare_complete(name, evaluate(name, supplied, rows), expected)
    first = oracle.first_valid(name, supplied)
    assert all(cell.state == "INSUFFICIENT_HISTORY" for cell in expected[:first])
    assert expected[first].state == "VALID"


@pytest.mark.parametrize("name", oracle.NAMES)
def test_flat_zero_undefined_gap_infinity_and_contiguous_reseed(name):
    supplied = parameters(name, "small")
    first = oracle.first_valid(name, supplied)
    rows = oracle.fixture_rows(first * 2 + 9)
    gap = first + 2
    rows[gap][oracle.INPUTS[name][0]] = math.nan
    rows[-2][oracle.INPUTS[name][-1]] = math.inf
    expected = oracle.expected(name, supplied, rows)
    actual = evaluate(name, supplied, rows)
    compare_complete(name, actual, expected)
    assert expected[gap].state == "INVALID" and expected[-2].state == "INVALID"
    assert all(cell.state == "INSUFFICIENT_HISTORY" for cell in expected[gap + 1:gap + 1 + first])

    flat = [{"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}
            for _ in range(first + 3)]
    expected_flat = oracle.expected(name, supplied, flat)
    compare_complete(name, evaluate(name, supplied, flat), expected_flat)
    if name == "VOLATILITY_RANK":
        assert expected_flat[first].state == "MATHEMATICALLY_UNDEFINED"
    elif name == "VOLATILITY_PERCENTILE":
        assert expected_flat[first].value == 50 + 50 / supplied["rank_window"]
    else:
        assert expected_flat[first] == oracle.Cell("VALID", 0.0)


@pytest.mark.parametrize("name", oracle.NAMES)
def test_prefix_session_carry_explicit_reset_stream_and_restart(name):
    supplied = parameters(name, "small")
    first = oracle.first_valid(name, supplied)
    count = first * 2 + 13
    rows = oracle.fixture_rows(count)
    # Force a reversal while retaining a valid OHLC envelope.
    for offset, close in enumerate((112.0, 107.0, 103.0, 98.0)):
        item = rows[-6 + offset]
        item.update(open=close + 0.2, high=close + 1.0, low=close - 1.0, close=close)
    resets = [()] * count
    resets[first + 4] = ("EXPLICIT",)
    expected = oracle.expected(name, supplied, rows, resets)
    batch = evaluate(name, supplied, rows, resets)
    compare_complete(name, batch, expected)
    for end in (1, first, first + 1, first + 4, first + 5, count - 1, count):
        compare_complete(name, evaluate(name, supplied, rows[:end], resets[:end]), expected[:end])

    bound = binding(name, supplied)
    state = subject.RemainingOracleState(name, supplied, bound)
    streamed = []
    checkpoints = {0, max(0, first - 1), first, first + 4, first + 5, count - 7}
    required = oracle.INPUTS[name]
    times = index_for(count)
    for offset, row in enumerate(rows):
        streamed.append(state.step(
            {"frame": {field: row[field] for field in required}},
            event_time=times[offset],
            reset_reasons=resets[offset],
        )["value"])
        if offset in checkpoints:
            document = json.loads(json.dumps(state.snapshot(), allow_nan=False))
            state = subject.RemainingOracleState.restore(name, supplied, bound, document)
            assert state.snapshot() == document
    compare_complete(name, streamed, expected)
    with pytest.raises(node_contracts.NodeContractRefusal):
        state.step({"frame": {field: rows[-1][field] for field in required}},
                   event_time=times[-1] + pd.Timedelta(minutes=17), reset_reasons=("SESSION",))


@pytest.mark.parametrize("name", oracle.NAMES)
def test_missing_field_wrong_role_alignment_time_and_state_identity_refuse(name):
    supplied = parameters(name, "small")
    rows = oracle.fixture_rows(oracle.first_valid(name, supplied) + 3)
    missing = inputs_for(name, rows)
    missing["frame"].pop(oracle.INPUTS[name][0])
    with pytest.raises(node_contracts.NodeContractRefusal):
        subject.evaluate(name, supplied, missing, bound_contract=binding(name, supplied))
    for kwargs in ({"role": "peer"}, {"skew": 1}, {"fields": ()}):
        with pytest.raises((node_contracts.NodeContractRefusal, ValueError)):
            rejected = binding(name, supplied, **kwargs)
            subject.RemainingOracleState(name, supplied, rejected)
    naive = inputs_for(name, rows, index_for(len(rows)).tz_localize(None))
    with pytest.raises(node_contracts.NodeContractRefusal):
        subject.evaluate(name, supplied, naive, bound_contract=binding(name, supplied))
    bound = binding(name, supplied)
    state = subject.RemainingOracleState(name, supplied, bound)
    document = state.snapshot()
    forged = deepcopy(document)
    forged["bound_contract_address"] = address("wrong-bound-contract")
    body = {key: value for key, value in forged.items() if key != "payload_address"}
    forged["payload_address"] = hashing.content_address(body)
    with pytest.raises(node_contracts.NodeContractRefusal, match="STATE_IDENTITY"):
        subject.RemainingOracleState.restore(name, supplied, bound, forged)
    assert subject.RemainingOracleState.restore(name, supplied, bound, document).snapshot() == document


@pytest.mark.parametrize("name", oracle.NAMES)
def test_max_domain_live_history_state_memory_compute_and_first_above_bound(name):
    supplied = parameters(name, "maximum")
    first = oracle.first_valid(name, supplied)
    rows = [{"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}
            for _ in range(first + 2)]
    bound = binding(name, supplied)
    state = subject.RemainingOracleState(name, supplied, bound)
    times = index_for(len(rows))
    actual = []
    tracemalloc.start()
    started = time.perf_counter_ns()
    for offset, row in enumerate(rows):
        actual.append(state.step(
            {"frame": {field: row[field] for field in oracle.INPUTS[name]}},
            event_time=times[offset],
        )["value"])
    elapsed_ns = time.perf_counter_ns() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    profile = subject.source_contract(name)["resource_profile"]
    snapshot = state.snapshot()
    encoded = len(json.dumps(snapshot, separators=(",", ":")).encode())
    history_cells = sum(len(values) for values in snapshot["history"].values())
    expected = []
    for offset in range(len(rows)):
        if offset < first:
            expected.append(oracle.Cell("INSUFFICIENT_HISTORY"))
        elif name == "VOLATILITY_RANK":
            expected.append(oracle.Cell("MATHEMATICALLY_UNDEFINED"))
        elif name == "VOLATILITY_PERCENTILE":
            expected.append(oracle.Cell("VALID", 50 + 50 / supplied["rank_window"]))
        else:
            expected.append(oracle.Cell("VALID", 0.0))
    compare_complete(name, actual, expected)
    assert history_cells <= sum(state._limits.values())
    assert elapsed_ns / len(rows) / 1000 <= profile["compute_microseconds_per_event"]
    assert peak <= profile["memory_bytes_upper_bound"]
    assert encoded <= profile["state_bytes_upper_bound"]
    assert history_cells * 256 <= profile["history_bytes_upper_bound"]
    print(json.dumps({
        "component": name,
        "events": len(rows),
        "first_valid_index": first,
        "history_cells": history_cells,
        "snapshot_bytes": encoded,
        "tracemalloc_peak_bytes": peak,
        "microseconds_per_event": elapsed_ns / len(rows) / 1000,
        "declared_profile": plain(profile),
    }, sort_keys=True))
    for key, (_, _, maximum, _) in oracle.PARAMETERS[name].items():
        with pytest.raises(node_contracts.NodeContractRefusal, match="OUT_OF_DOMAIN"):
            subject.parameters_for(name, {key: maximum + 1})


def test_v1_catalogue_identities_and_all_accepted_shared_bytes_remain_exact():
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS

    catalogue = json.loads(CATALOGUE.read_text())["records"]
    assert len(catalogue) == 125
    for row in catalogue:
        key = (row["component_id"], row["component_version"])
        current = {
            "descriptor": plain(REGISTRY.v2_components[key]),
            "node_contract": plain(REGISTRY.node_contracts[key]),
            "node_contract_address": REGISTRY.node_contract_addresses[key],
            "data_requirement": plain(REGISTRY.data_requirement_declarations[key]),
            "data_requirement_address": REGISTRY.data_requirement_declaration_addresses[key],
            "implementation_address": REGISTRY.v2_implementation_registrations[key].implementation_address,
        }
        assert current == {field: row[field] for field in current}, row["name"]
    assert subject not in V2_CONTRIBUTORS
    assert all(subject.component_key(name) not in REGISTRY.v2_components for name in oracle.NAMES)
    accepted = {
        "contracts.py": "95e0ae03d2f3dc93fb959c9522cb636c517d7ebd5766e3ae3524d95964be0ba3",
        "common.py": "dc83bef8379e49c0ae9ced94ad755d430fa8c76ff1a2b1ee82bf1f8e4ed8c94f",
        "core_math.py": "bf8ac8d4e87e53bd96b97462a13379baa88a54b97606ba2550248fa8d4e6ccc6",
        "recursive_state.py": "dd658c9ac72c94a0df68e5bbb0aeedcb7f1e12b3a90b107b8ec51b9e44943d4c",
        "multi_output.py": "744610d2280d87edb61b032a3b02e441adc949e25039993af51ab7921d839760",
        "session_data.py": "3592d4478cf9494c196b415c468438d3ee9d9e157b2d2104922373e9f2eb534f",
    }
    base = SUBJECT.parent
    for filename, expected in accepted.items():
        assert hashlib.sha256((base / filename).read_bytes()).hexdigest() == expected


def test_genuine_omission_output_numeric_and_state_mutations_are_detected_and_restored(monkeypatch):
    source_before = hashlib.sha256(SUBJECT.read_bytes()).hexdigest()
    original_names = subject.NAMES
    original_descriptor = subject.descriptor
    original_advance = subject.RemainingOracleState._advance
    original_restore = subject.RemainingOracleState.restore.__func__

    with monkeypatch.context() as changed:
        changed.setattr(subject, "NAMES", subject.NAMES[:-1])
        with pytest.raises(AssertionError):
            assert_closed_universe()
    assert subject.NAMES is original_names

    with monkeypatch.context() as changed:
        def wrong_descriptor(name):
            value = plain(original_descriptor(name))
            value["ports"] = [port for port in value["ports"] if port["direction"] != "output"]
            return value
        changed.setattr(subject, "descriptor", wrong_descriptor)
        with pytest.raises(AssertionError):
            assert_closed_universe()
    assert subject.descriptor is original_descriptor

    name = "PARKINSON"
    supplied = parameters(name, "small")
    rows = oracle.fixture_rows(oracle.first_valid(name, supplied) + 4)
    expected = oracle.expected(name, supplied, rows)
    with monkeypatch.context() as changed:
        changed.setattr(subject.RemainingOracleState, "_advance", lambda self, row: 0)
        with pytest.raises(AssertionError):
            compare_complete(name, evaluate(name, supplied, rows), expected)
    assert subject.RemainingOracleState._advance is original_advance

    bound = binding(name, supplied)
    state = subject.RemainingOracleState(name, supplied, bound)
    forged = state.snapshot()
    forged["payload_address"] = address("forged-state")

    def state_guard_consumer():
        try:
            subject.RemainingOracleState.restore(name, supplied, bound, forged)
        except node_contracts.NodeContractRefusal as exc:
            return "STATE_DIGEST" in str(exc)
        return False

    assert state_guard_consumer()
    with monkeypatch.context() as changed:
        changed.setattr(subject.RemainingOracleState, "restore", classmethod(
            lambda cls, component, params, contract, document: cls(component, params, contract)))
        with pytest.raises(AssertionError):
            assert state_guard_consumer()
    assert subject.RemainingOracleState.restore.__func__ is original_restore
    assert state_guard_consumer()
    assert hashlib.sha256(SUBJECT.read_bytes()).hexdigest() == source_before == SEALED_FILE_HASHES[SUBJECT]
