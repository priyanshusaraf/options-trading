"""Implementation-owner evidence; fresh independent assurance remains required.

Expected equations below are authored from the pinned specification, NIST scale
definition, and the captured Rogers-Satchell / Yang-Zhang primary equations. They
do not import candidate numerical helpers or derive expectations from its output.
"""
from __future__ import annotations

from copy import deepcopy
import decimal
from decimal import Decimal
import json
import math
import time
import tracemalloc

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import remaining_oracles as remaining
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract
from app.ir.validity import NumericValue, ValidityState


ALL_NAMES = tuple("EWMA_VOLATILITY GARMAN_KLASS ICHIMOKU_COMPONENTS PARKINSON REALIZED_VOLATILITY ROGERS_SATCHELL SUPERTREND VOLATILITY_PERCENTILE VOLATILITY_RANK YANG_ZHANG".split())
NAMES = tuple(name for name in ALL_NAMES if name not in {"GARMAN_KLASS", "ICHIMOKU_COMPONENTS", "SUPERTREND"})
REFUSED = ("GARMAN_KLASS", "ICHIMOKU_COMPONENTS", "SUPERTREND")
SOURCE_HASHES = {
    "specification": "sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb",
    "architecture": "sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482",
    "binding": "sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925",
    "source_policy": "sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994",
    "verification": "sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3",
    "nist_scale": "sha256:bad33742f059fe2dfee9b2d26139b525dbedf7a6d702d8a1e7ccabc6c71eccfe",
    "yang_zhang": "sha256:3cffec0643654ca22db333f6fdf4688ab6be836d53942b5cfd04643588e44911",
    "rogers_satchell": "sha256:22d07345c6b50edfafe30cc0efd2d06b72e277957c0857a154e05d17fe2e678b",
    "audit_refusal": "sha256:e83da220d7eb2416cc780504c346f7f5abd6dffecb54b3a01ea014d643bc9418",
}
H = ValidityState.INSUFFICIENT_HISTORY
U = ValidityState.MATHEMATICALLY_UNDEFINED
I = ValidityState.INVALID


def address(value):
    return hashing.content_address({"remaining_oracles_test": value})


def parameters(name, kind="small"):
    result = {key: spec["default"] for key, spec in remaining.SPECS[name]["parameters"].items()}
    if kind == "default":
        return result
    for key, spec in remaining.SPECS[name]["parameters"].items():
        if kind == "minimum":
            result[key] = spec["minimum"]
        elif kind == "maximum":
            result[key] = spec["maximum"]
    if kind == "small":
        if "window" in result:
            result["window"] = 3
        if "seed_window" in result:
            result.update(seed_window=3, decay=0.8, periods_per_year=252)
        if "vol_window" in result:
            result.update(vol_window=3, rank_window=4)
        if "periods_per_year" in result:
            result["periods_per_year"] = 252
    return result


def frame(count=40, *, flat=None, start="2025-01-02T09:15:00Z"):
    if flat is None:
        close = [100.0 + i * 0.37 + (i % 5 - 2) * 0.81 + (i % 3) * 0.19 for i in range(count)]
        opening = [value + (-0.31 if i % 2 else 0.23) for i, value in enumerate(close)]
        high = [max(o, c) + 0.8 + (i % 4) * 0.07 for i, (o, c) in enumerate(zip(opening, close))]
        low = [min(o, c) - 0.6 - (i % 3) * 0.05 for i, (o, c) in enumerate(zip(opening, close))]
    else:
        opening = high = low = close = [float(flat)] * count
    index = pd.date_range(start, periods=count, freq="15min")
    return {"frame": {key: pd.Series(values, index=index) for key, values in
                       {"open": opening, "high": high, "low": low, "close": close}.items()}}


def binding(name, supplied=None, *, timeframe=900, role="primary"):
    supplied = parameters(name, "default") if supplied is None else supplied
    fields = remaining.fields_by_port(name)["frame"]
    fact = {
        "schema": "canonical-input-binding/1", "owner_id": "org.remaining",
        "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
        "dataset_manifest_address": address("manifest"), "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"), "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("instrument"), "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": timeframe, "fields": list(fields), "freshness": {"maximum_age_seconds": 900},
        "depth": {"kind": "NONE", "levels": None}, "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": False,
    }
    entry = {"source": {"scope": "graph_input", "port_id": "frame"}, "binding": fact,
             "binding_address": hashing.content_address(fact)}
    ports = {"frame": entry}
    context = {
        "schema": "node-input-binding/1", "owner_id": "org.remaining",
        "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
        "context_address": hashing.content_address(ports), "ports": ports,
    }
    return materialize_node_contract(remaining.source_contract(name),
                                     remaining.CONTRACT_BINDINGS[remaining.component_key(name)], supplied, context)


def evaluate(name, supplied=None, inputs=None, resets=None):
    supplied = parameters(name, "default") if supplied is None else supplied
    inputs = frame() if inputs is None else inputs
    return remaining.evaluate(name, supplied, inputs, bound_contract=binding(name, supplied), resets=resets)["value"]


def d(value):
    return Decimal.from_float(float(value))


def independent_oracle(name, supplied, inputs):
    """Complete source-equation arrays; no candidate helper or state is called."""
    rows = inputs["frame"]
    values = {key: [d(value) for value in series.tolist()] for key, series in rows.items()}
    count = len(next(iter(values.values())))
    result = [None] * count
    with decimal.localcontext(decimal.Context(prec=120, Emin=-999999, Emax=999999)):
        returns = [(values["close"][i] - values["close"][i - 1]) / values["close"][i - 1]
                   for i in range(1, count)]
        if name == "EWMA_VOLATILITY":
            length = supplied["seed_window"]
            if len(returns) >= length:
                variance = sum((value * value for value in returns[:length]), Decimal(0)) / length
                result[length] = (variance * d(supplied["periods_per_year"])).sqrt()
                decay = d(supplied["decay"])
                for i in range(length + 1, count):
                    variance = decay * variance + (1 - decay) * returns[i - 1] ** 2
                    result[i] = (variance * d(supplied["periods_per_year"])).sqrt()
        elif name == "PARKINSON":
            terms = [(values["high"][i].ln() - values["low"][i].ln()) ** 2 for i in range(count)]
            length = supplied["window"]
            for i in range(length - 1, count):
                result[i] = (sum(terms[i + 1 - length:i + 1], Decimal(0)) / length
                             / (4 * Decimal(2).ln()) * d(supplied["periods_per_year"])).sqrt()
        elif name == "ROGERS_SATCHELL":
            terms = []
            for i in range(count):
                o, h, low, c = (values[key][i] for key in ("open", "high", "low", "close"))
                terms.append((h.ln() - o.ln()) * (h.ln() - c.ln()) + (low.ln() - o.ln()) * (low.ln() - c.ln()))
            length = supplied["window"]
            for i in range(length - 1, count):
                radicand = sum(terms[i + 1 - length:i + 1], Decimal(0)) / length * d(supplied["periods_per_year"])
                result[i] = None if radicand < 0 else radicand.sqrt()
        elif name == "REALIZED_VOLATILITY":
            length = supplied["window"]
            for i in range(length, count):
                sample = returns[i - length:i]
                mean = sum(sample, Decimal(0)) / length
                variance = sum(((value - mean) ** 2 for value in sample), Decimal(0)) / length
                result[i] = (variance * d(supplied["periods_per_year"])).sqrt()
        elif name in {"VOLATILITY_PERCENTILE", "VOLATILITY_RANK"}:
            length, rank = supplied["vol_window"], supplied["rank_window"]
            volatility = [None] * count
            for i in range(length, count):
                sample = returns[i - length:i]
                mean = sum(sample, Decimal(0)) / length
                volatility[i] = (sum(((value - mean) ** 2 for value in sample), Decimal(0)) / length).sqrt()
            for i in range(length + rank - 1, count):
                sample = volatility[i + 1 - rank:i + 1]
                current = sample[-1]
                if name == "VOLATILITY_PERCENTILE":
                    less = sum(value < current for value in sample)
                    equal = sum(value == current for value in sample)
                    result[i] = Decimal(100) * (Decimal(less) + (Decimal(equal) + 1) / 2) / rank
                else:
                    low, high = min(sample), max(sample)
                    result[i] = None if low == high else Decimal(100) * (current - low) / (high - low)
        else:
            length = supplied["window"]
            overnight, intraday, rs = [], [], []
            for i in range(1, count):
                o, h, low, c = (values[key][i] for key in ("open", "high", "low", "close"))
                overnight.append(o.ln() - values["close"][i - 1].ln())
                intraday.append(c.ln() - o.ln())
                rs.append((h.ln() - o.ln()) * (h.ln() - c.ln()) + (low.ln() - o.ln()) * (low.ln() - c.ln()))
            k = Decimal("0.34") / (Decimal("1.34") + Decimal(length + 1) / (length - 1))
            for i in range(length, count):
                offset = i - length
                os, cs, rss = overnight[offset:i], intraday[offset:i], rs[offset:i]
                def sample_variance(sample):
                    mean = sum(sample, Decimal(0)) / length
                    return sum(((value - mean) ** 2 for value in sample), Decimal(0)) / (length - 1)
                radicand = (sample_variance(os) + k * sample_variance(cs)
                            + (1 - k) * sum(rss, Decimal(0)) / length) * d(supplied["periods_per_year"])
                result[i] = None if radicand < 0 else radicand.sqrt()
    return result


def compare_complete(actual, expected, *, recursive=False):
    assert len(actual) == len(expected)
    for index, (cell, target) in enumerate(zip(actual.tolist(), expected)):
        assert isinstance(cell, NumericValue), index
        if target is None:
            expected_state = H if index < next((i for i, value in enumerate(expected) if value is not None), len(expected)) else U
            assert cell.state is expected_state, (index, cell, expected_state)
        else:
            assert cell.state is ValidityState.VALID, (index, cell)
            wanted = float(target)
            absolute = abs(cell.value - wanted)
            relative = absolute / abs(wanted) if wanted else None
            assert absolute <= (1e-12 if wanted == 0 else 1e-10), (index, absolute)
            if wanted:
                assert relative <= (1e-8 if recursive else 1e-9), (index, relative)


def test_scope_source_identity_refusals_and_no_publication():
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS
    assert remaining.ALL_NAMES == tuple(sorted(ALL_NAMES))
    assert remaining.NAMES == tuple(sorted(NAMES))
    assert remaining.REFUSED_NAMES == tuple(sorted(REFUSED))
    assert remaining not in V2_CONTRIBUTORS
    assert all(remaining.component_key(name) not in REGISTRY.v2_components for name in NAMES)
    assert set(remaining.V2_COMPONENTS) == set(remaining.NODE_CONTRACTS) == set(remaining.CONTRACT_BINDINGS) == set(remaining.V2_IMPLEMENTATIONS)
    assert len(remaining.V2_COMPONENTS) == 7 and len(remaining.REFUSALS) == 3
    for name in ALL_NAMES:
        spec = remaining.SPECS[name]
        assert SOURCE_HASHES["specification"] in spec["source_addresses"]
        assert SOURCE_HASHES["architecture"] in spec["source_addresses"]
        assert SOURCE_HASHES["binding"] in spec["source_addresses"]
        assert SOURCE_HASHES["source_policy"] in spec["source_addresses"]
        assert SOURCE_HASHES["verification"] in spec["source_addresses"]
    assert SOURCE_HASHES["nist_scale"] in remaining.SPECS["REALIZED_VOLATILITY"]["source_addresses"]
    assert SOURCE_HASHES["rogers_satchell"] in remaining.SPECS["ROGERS_SATCHELL"]["source_addresses"]
    assert SOURCE_HASHES["yang_zhang"] in remaining.SPECS["PARKINSON"]["source_addresses"]
    assert SOURCE_HASHES["yang_zhang"] in remaining.SPECS["YANG_ZHANG"]["source_addresses"]
    for name in REFUSED:
        refusal = remaining.REFUSALS[name]
        assert refusal["executable"] is False and refusal["decision"] == "REFUSE"
        assert SOURCE_HASHES["audit_refusal"] in refusal["source_addresses"]
        for inputs, capability in ((None, False), ({"frame": {}}, False), ({"frame": {"plausible": 1}}, True)):
            with pytest.raises(node_contracts.NodeContractRefusal, match=refusal["code"]):
                remaining.refuse(name, inputs=inputs, parameters={"capability_verified": capability},
                                 capability_verified=capability)
        with pytest.raises(node_contracts.NodeContractRefusal, match=refusal["code"]):
            remaining.component_key(name)
    with pytest.raises(TypeError):
        remaining.SPECS["PARKINSON"]["parameters"]["window"]["default"] = 2


@pytest.mark.parametrize("name", NAMES)
def test_contracts_cover_every_field_output_parameter_and_identity(name):
    supplied = parameters(name, "default")
    contract = remaining.source_contract(name)
    resolved = binding(name, supplied)
    assert set(remaining.fields_by_port(name)["frame"]) == {field.upper() for field in remaining.SPECS[name]["inputs"]}
    assert set(remaining.descriptor(name)["parameters"]) == set(remaining.SPECS[name]["parameters"])
    assert [port["port_id"] for port in remaining.descriptor(name)["ports"] if port["direction"] == "output"] == ["value"]
    assert tuple(contract["required_market_fields"]) == tuple(sorted(remaining.SPECS[name]["inputs"]))
    assert dict(contract["mode_eligibility"]) == {"research": True, "paper": False, "live": False}
    assert contract["bar_policy"] == "COMPLETED_ONLY" and contract["causal_declaration"] == "COMPLETED_EVENT_PREFIX"
    assert resolved.document["resolved_contract"]["warmup_history"] == remaining.first_valid_index(name, supplied)
    assert dict(resolved.document["resolved_contract"]["output_warmup"]) == {"value": remaining.first_valid_index(name, supplied)}
    assert dict(resolved.document["parameters"]) == supplied


@pytest.mark.parametrize("name", NAMES)
def test_parameter_defaults_minimum_maximum_and_first_above_refuse(name):
    assert dict(remaining.parameters_for(name)) == parameters(name, "default")
    for kind in ("minimum", "maximum"):
        supplied = parameters(name, kind)
        assert dict(remaining.parameters_for(name, supplied)) == supplied
        assert binding(name, supplied).document["resolved_contract"]["warmup_history"] == remaining.first_valid_index(name, supplied)
    with pytest.raises(node_contracts.NodeContractRefusal):
        remaining.parameters_for(name, {"unknown": 1})
    for key, spec in remaining.SPECS[name]["parameters"].items():
        for value in (True, False, None, "2", float("nan"), float("inf"), spec["minimum"] - 1, spec["maximum"] + 1):
            with pytest.raises(node_contracts.NodeContractRefusal):
                remaining.parameters_for(name, {key: value})
        if spec["type"] == "exact_integer":
            for value in (2.0, 2.5):
                with pytest.raises(node_contracts.NodeContractRefusal):
                    remaining.parameters_for(name, {key: value})


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", ("default", "small"))
def test_source_bound_independent_complete_arrays_and_masks(name, kind):
    supplied = parameters(name, kind)
    count = remaining.first_valid_index(name, supplied) + 8
    inputs = frame(count)
    expected = independent_oracle(name, supplied, inputs)
    compare_complete(evaluate(name, supplied, inputs), expected, recursive=name == "EWMA_VOLATILITY")


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", ("minimum", "maximum"))
def test_parameter_domain_flat_zero_outputs_and_complete_masks(name, kind):
    supplied = parameters(name, kind)
    count = remaining.first_valid_index(name, supplied) + 3
    actual = evaluate(name, supplied, frame(count, flat=100.0))
    first = remaining.first_valid_index(name, supplied)
    for index, cell in enumerate(actual.tolist()):
        if index < first:
            assert cell.state is H
        elif name == "VOLATILITY_RANK":
            assert cell.state is U
        elif name == "VOLATILITY_PERCENTILE":
            expected = 50 + 50 / supplied["rank_window"]
            assert cell.state is ValidityState.VALID and cell.value == pytest.approx(expected, abs=1e-12)
        else:
            assert cell.state is ValidityState.VALID and cell.value == 0


def stream(name, supplied, inputs, resets, checkpoints=()):
    bound = binding(name, supplied)
    state = remaining.RemainingOracleState(name, supplied, bound)
    result = []
    required = [field.lower() for field in remaining.fields_by_port(name)["frame"]]
    for index, event_time in enumerate(inputs["frame"][required[0]].index):
        row = {"frame": {field: inputs["frame"][field].iloc[index] for field in required}}
        result.append(state.step(row, event_time=event_time, reset_reasons=resets[index])["value"])
        if index in checkpoints:
            state = remaining.RemainingOracleState.restore(name, supplied, bound,
                                                           json.loads(json.dumps(state.snapshot())))
    return result, state


@pytest.mark.parametrize("name", NAMES)
def test_complete_prefix_batch_stream_restart_gap_reversal_and_session_carry(name):
    supplied = parameters(name, "small")
    count = remaining.first_valid_index(name, supplied) + 18
    inputs = frame(count, start="2025-01-02T22:30:00Z")
    # Reversal plus a missing bar exercise causal restart; a civil/session date
    # crossing carries because SESSION is not a declared reset reason.
    for offset, value in enumerate((111.0, 106.0, 101.0, 98.0)):
        index = count - 5 + offset
        inputs["frame"]["close"].iloc[index] = value
        inputs["frame"]["open"].iloc[index] = value + 0.2
        inputs["frame"]["high"].iloc[index] = value + 1.0
        inputs["frame"]["low"].iloc[index] = value - 1.0
    gap = remaining.first_valid_index(name, supplied) + 3
    for field in remaining.fields_by_port(name)["frame"]:
        inputs["frame"][field.lower()].iloc[gap] = float("nan")
    resets = [()] * count
    reset_at = count - 2
    resets[reset_at] = ("EXPLICIT",)
    batch = evaluate(name, supplied, inputs, resets).tolist()
    checkpoints = tuple(sorted({0, max(0, remaining.first_valid_index(name, supplied) - 1),
                                remaining.first_valid_index(name, supplied), gap, gap + 1, count - 6}))
    streamed, state = stream(name, supplied, inputs, resets, checkpoints)
    assert streamed == batch
    for length in range(1, count + 1):
        prefix = {"frame": {key: series.iloc[:length] for key, series in inputs["frame"].items()}}
        assert evaluate(name, supplied, prefix, resets[:length]).tolist() == batch[:length]
    forged = deepcopy(state.snapshot())
    forged["payload_address"] = address("forged")
    with pytest.raises(node_contracts.NodeContractRefusal, match="STATE_DIGEST"):
        remaining.RemainingOracleState.restore(name, supplied, binding(name, supplied), forged)


@pytest.mark.parametrize("name", NAMES)
def test_missing_wrong_role_alignment_nonfinite_and_zero_fail_closed(name):
    supplied = parameters(name, "small")
    inputs = frame(remaining.first_valid_index(name, supplied) + 3)
    missing = deepcopy(inputs)
    missing["frame"].pop(next(iter(field.lower() for field in remaining.fields_by_port(name)["frame"])))
    with pytest.raises(node_contracts.NodeContractRefusal):
        evaluate(name, supplied, missing)
    with pytest.raises(node_contracts.NodeContractRefusal):
        binding(name, supplied, role="peer")
    unaligned = deepcopy(inputs)
    fields = tuple(field.lower() for field in remaining.fields_by_port(name)["frame"])
    field = fields[0]
    if len(fields) == 1:
        unaligned["frame"][field].index = unaligned["frame"][field].index.tz_localize(None)
    else:
        unaligned["frame"][field] = unaligned["frame"][field].shift(freq="1min")
    with pytest.raises(node_contracts.NodeContractRefusal):
        evaluate(name, supplied, unaligned)
    for bad in (0.0, float("inf"), float("nan")):
        poisoned = deepcopy(inputs)
        for required in remaining.fields_by_port(name)["frame"]:
            poisoned["frame"][required.lower()].iloc[-1] = bad
        assert evaluate(name, supplied, poisoned).iloc[-1].state is I


@pytest.mark.parametrize("name", NAMES)
def test_maximum_domain_resource_and_state_bounds(name):
    supplied = parameters(name, "maximum")
    count = remaining.first_valid_index(name, supplied) + 2
    inputs = frame(count, flat=100.0)
    resets = [()] * count
    tracemalloc.start()
    started = time.perf_counter()
    _, state = stream(name, supplied, inputs, resets)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    profile = remaining.source_contract(name)["resource_profile"]
    assert elapsed / count * 1_000_000 < profile["compute_microseconds_per_event"]
    assert peak < profile["memory_bytes_upper_bound"]
    assert len(json.dumps(state.snapshot()).encode()) < profile["state_bytes_upper_bound"]
    assert sum(len(values) for values in state._history.values()) <= sum(state._limits.values())


def test_wrong_binding_and_state_identity_refuse():
    name = "PARKINSON"
    supplied = parameters(name, "small")
    bound = binding(name, supplied)
    with pytest.raises(node_contracts.NodeContractRefusal):
        remaining.RemainingOracleState(name, parameters(name, "default"), bound)
    state = remaining.RemainingOracleState(name, supplied, bound)
    snapshot = state.snapshot()
    other = binding(name, {**supplied, "periods_per_year": 7})
    with pytest.raises(node_contracts.NodeContractRefusal):
        remaining.RemainingOracleState.restore(name, supplied, other, snapshot)
