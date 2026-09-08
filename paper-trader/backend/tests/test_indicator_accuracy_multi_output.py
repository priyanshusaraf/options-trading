"""Implementation-owner proof from independent algebra; separate assurance required.

Expected recurrences use exact rational convolution, not candidate helpers/state.
Native reference comparisons and independent-owner acceptance remain separate facts.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import json
import math

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import multi_output as multi
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract
from app.ir.validity import NumericValue, ValidityState

NAMES = tuple("BOLLINGER_BANDS BOLLINGER_BANDWIDTH BOLLINGER_PERCENT_B DONCHIAN_CHANNELS KELTNER_CHANNELS MACD PPO STOCHASTIC STOCH_RSI".split())
PORTS = {name: tuple("lower middle upper".split()) if name in {"BOLLINGER_BANDS", "DONCHIAN_CHANNELS", "KELTNER_CHANNELS"}
         else ("histogram", "macd", "signal") if name == "MACD" else ("d", "k") if name in {"STOCHASTIC", "STOCH_RSI"} else ("value",) for name in NAMES}
DEFAULTS = {
    "BOLLINGER_BANDS": {"window": 14, "deviations": 2}, "BOLLINGER_BANDWIDTH": {"window": 14, "deviations": 2},
    "BOLLINGER_PERCENT_B": {"window": 14, "deviations": 2}, "DONCHIAN_CHANNELS": {"window": 14},
    "KELTNER_CHANNELS": {"window": 14, "basis_type": "EMA", "atr_length": 14, "multiplier": 2},
    "MACD": {"fast_length": 12, "slow_length": 26, "signal_length": 9, "source": "close"},
    "PPO": {"fast_length": 12, "slow_length": 26, "moving_average_type": "EMA"},
    "STOCHASTIC": {"k_length": 14, "k_smoothing": 3, "d_smoothing": 3},
    "STOCH_RSI": {"rsi_length": 14, "stochastic_length": 14, "k_smoothing": 3, "d_smoothing": 3},
}
H, U, I, M = (ValidityState.INSUFFICIENT_HISTORY, ValidityState.MATHEMATICALLY_UNDEFINED, ValidityState.INVALID, ValidityState.MISSING)


def parameters(name, kind="small"):
    p = dict(DEFAULTS[name])
    if kind == "default":
        return p
    for key, value in list(p.items()):
        if key in {"window", "atr_length", "rsi_length", "stochastic_length", "k_length"}:
            p[key] = 4096 if kind == "maximum" else 2 if kind == "minimum" else 3
        elif key in {"k_smoothing", "d_smoothing", "signal_length"}:
            p[key] = 4096 if kind == "maximum" else 1 if kind == "minimum" else 2
    if name in {"MACD", "PPO"}:
        p.update(fast_length=4095 if kind == "maximum" else 2,
                 slow_length=4096 if kind == "maximum" else 3 if kind == "minimum" else 5)
    return p


def first(name, p):
    if name.startswith("BOLLINGER_") or name == "DONCHIAN_CHANNELS":
        return p["window"] - 1
    if name == "KELTNER_CHANNELS":
        return max(p["window"] - 1, p["atr_length"])
    if name == "MACD":
        return p["slow_length"] + p["signal_length"] - 2
    if name == "PPO":
        return p["slow_length"] - 1
    if name == "STOCHASTIC":
        return p["k_length"] + p["k_smoothing"] + p["d_smoothing"] - 3
    return p["rsi_length"] + p["stochastic_length"] + p["k_smoothing"] + p["d_smoothing"] - 3


def fields(name, p):
    if name == "MACD":
        return {"hl2": ("high", "low"), "hlc3": ("high", "low", "close"), "ohlc4": ("open", "high", "low", "close")}.get(p["source"], (p["source"],))
    return ("high", "low", "close") if name in {"KELTNER_CHANNELS", "STOCHASTIC"} else ("high", "low") if name == "DONCHIAN_CHANNELS" else ("close",)


def address(value):
    return hashing.content_address({"multi_output_test": value})


def binding(name, p=None, *, timeframe=900):
    p = dict(DEFAULTS[name]) if p is None else p
    fact = {"schema": "canonical-input-binding/1", "owner_id": "org.multi",
        "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
        "dataset_manifest_address": address("manifest"), "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"), "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("primary"), "instrument": {"role": "primary", "type": "PHYSICAL"},
        "timeframe": timeframe, "fields": sorted(f.upper() for f in fields(name, p)),
        "freshness": {"maximum_age_seconds": 900}, "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR", "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": False}
    ports = {"frame": {"source": {"scope": "graph_input", "port_id": "frame"}, "binding": fact, "binding_address": hashing.content_address(fact)}}
    context = {"schema": "node-input-binding/1", "owner_id": "org.multi", "dataset_context_address": address("dataset"),
        "evaluation_context_address": address("evaluation"), "context_address": hashing.content_address(ports), "ports": ports}
    return materialize_node_contract(multi.source_contract(name), multi.CONTRACT_BINDINGS[("analytical." + name.lower(), 2)], p, context)


def frame(count=50, *, level=None):
    close = [float(level)] * count if level is not None else [float((i * 7) % 19 + 5) for i in range(count)]
    index = pd.date_range("2025-01-02T10:00:00Z", periods=count, freq="15min")
    return {"frame": {"close": pd.Series(close, index=index),
        "open": pd.Series(close if level is not None else [v + .5 for v in close], index=index),
        "high": pd.Series(close if level is not None else [v + 2 for v in close], index=index),
        "low": pd.Series(close if level is not None else [v - 1 for v in close], index=index)}}


def exact_mean(values, length):
    result = [None] * len(values)
    for i in range(length - 1, len(values)):
        window = values[i + 1 - length:i + 1]
        if all(v is not None for v in window):
            result[i] = sum(window, F(0)) / length
    return result


def convolution(values, period, *, start=0, alpha=None):
    """Closed rational weights from the seed, not a copy of streaming updates."""
    result = [None] * len(values)
    seed_at = start + period - 1
    if seed_at >= len(values):
        return result
    seed = sum(values[start:seed_at + 1], F(0)) / period
    alpha = F(2, period + 1) if alpha is None else alpha
    decay = 1 - alpha
    for i in range(seed_at, len(values)):
        result[i] = decay ** (i - seed_at) * seed + sum((alpha * decay ** (i - j) * values[j] for j in range(seed_at + 1, i + 1)), F(0))
    return result


def dec(value):
    return Decimal(value.numerator) / Decimal(value.denominator) if isinstance(value, F) else Decimal(value)


def expected(name, p, data):
    rows = {k: [F(float(v)) for v in values] for k, values in data["frame"].items()}
    close, count = rows["close"], len(rows["close"])
    output = {port: [None] * count for port in PORTS[name]}
    warmup = first(name, p)
    with localcontext() as context:
        context.prec = 120
        if name.startswith("BOLLINGER_"):
            w = p["window"]
            for i in range(w - 1, count):
                window = close[i + 1 - w:i + 1]
                mean = sum(window, F(0)) / w
                variance = sum(((v - mean) ** 2 for v in window), F(0)) / w
                width = dec(variance).sqrt() * dec(F(p["deviations"]))
                low, high = dec(mean) - width, dec(mean) + width
                if name == "BOLLINGER_BANDS":
                    output["lower"][i], output["middle"][i], output["upper"][i] = low, dec(mean), high
                elif name == "BOLLINGER_BANDWIDTH":
                    output["value"][i] = (high - low) / dec(mean) * 100 if mean else None
                else:
                    output["value"][i] = (dec(close[i]) - low) / (high - low) if high != low else None
        elif name == "DONCHIAN_CHANNELS":
            for i in range(p["window"] - 1, count):
                low, high = min(rows["low"][i + 1 - p["window"]:i + 1]), max(rows["high"][i + 1 - p["window"]:i + 1])
                output["lower"][i], output["middle"][i], output["upper"][i] = low, (low + high) / 2, high
        elif name == "KELTNER_CHANNELS":
            basis = exact_mean(close, p["window"]) if p["basis_type"] == "SMA" else convolution(close, p["window"])
            true_range = [max(rows["high"][i] - rows["low"][i], abs(rows["high"][i] - close[i - 1]), abs(rows["low"][i] - close[i - 1])) for i in range(1, count)]
            atr = [None] + convolution(true_range, p["atr_length"], alpha=F(1, p["atr_length"]))
            for i in range(warmup, count):
                width = F(p["multiplier"]) * atr[i]
                output["lower"][i], output["middle"][i], output["upper"][i] = basis[i] - width, basis[i], basis[i] + width
        elif name in {"MACD", "PPO"}:
            selected = fields(name, p)
            values = [sum((rows[k][i] for k in selected), F(0)) / len(selected) for i in range(count)] if name == "MACD" else close
            f, s = p["fast_length"], p["slow_length"]
            if name == "PPO" and p["moving_average_type"] == "SMA":
                fast, slow = exact_mean(values, f), exact_mean(values, s)
            else:
                fast, slow = convolution(values, f, start=s - f if name == "MACD" else 0), convolution(values, s)
            if name == "PPO":
                for i in range(s - 1, count):
                    output["value"][i] = 100 * (fast[i] - slow[i]) / slow[i] if slow[i] else None
            else:
                difference = [fast[i] - slow[i] for i in range(s - 1, count)]
                signal = convolution(difference, p["signal_length"])
                for i in range(warmup, count):
                    value, smooth = difference[i - s + 1], signal[i - s + 1]
                    output["macd"][i], output["signal"][i], output["histogram"][i] = value, smooth, value - smooth
        else:
            if name == "STOCH_RSI":
                w = p["rsi_length"]
                changes = [b - a for a, b in zip(close, close[1:])]
                gains = convolution([max(v, 0) for v in changes], w, alpha=F(1, w))
                losses = convolution([max(-v, 0) for v in changes], w, alpha=F(1, w))
                oscillator = [None] * w + [100 * g / (g + loss) if g + loss else F(0) for g, loss in zip(gains[w - 1:], losses[w - 1:])]
                highs = lows = oscillator
                k_length, base = p["stochastic_length"], w
            else:
                highs, lows, oscillator = rows["high"], rows["low"], close
                k_length, base = p["k_length"], 0
            raw = [None] * count
            for i in range(base + k_length - 1, count):
                low, high = min(lows[i + 1 - k_length:i + 1]), max(highs[i + 1 - k_length:i + 1])
                raw[i] = 100 * (oscillator[i] - low) / (high - low) if high != low else F(0)
            output["k"] = exact_mean(raw, p["k_smoothing"])
            output["d"] = exact_mean(output["k"], p["d_smoothing"])
        for port, values in output.items():
            output[port] = [H if i < warmup else U if value is None or not math.isfinite(float(value)) else float(value) for i, value in enumerate(values)]
    return output


def compare(actual, wanted, index, name):
    assert set(actual) == set(PORTS[name]) == set(wanted)
    recursive = name in {"KELTNER_CHANNELS", "MACD", "PPO", "STOCH_RSI"}
    for port in PORTS[name]:
        assert actual[port].index.equals(index) and actual[port].name == port
        assert len(actual[port]) == len(wanted[port])
        for i, (got, want) in enumerate(zip(actual[port], wanted[port])):
            assert isinstance(got, NumericValue)
            if isinstance(want, ValidityState):
                assert got.state is want and got.value is None, (name, port, i, got, want)
            else:
                assert got.state is ValidityState.VALID, (name, port, i, got, want)
                error = abs(got.value - want)
                assert error <= (1e-12 if want == 0 else 1e-10), (name, port, i, got.value, want)
                if want:
                    assert error / abs(want) <= (1e-8 if recursive else 1e-9)


def evaluate(name, p, data, **kwargs):
    return multi.evaluate(name, p, data, bound_contract=binding(name, p), **kwargs)


def through_runtime(name, p, data, *, tamper=None, omitted_defaults=False):
    from app.ir.registry import PlatformRegistry
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings, ResolvedNodeContract
    from app.market_data.requirements import compile_data_requirement_plan, verify_data_requirement_plan
    key = ("analytical." + name.lower(), 2)
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=multi.V2_TYPES,
        v2_components={key: multi.V2_COMPONENTS[key]}, node_contracts={key: multi.NODE_CONTRACTS[key]},
        contract_bindings={key: multi.CONTRACT_BINDINGS[key]}, v2_implementations={key: multi.V2_IMPLEMENTATIONS[key]})
    ports = node_contracts._plain(multi.V2_COMPONENTS[key]["ports"])
    document = {"format_version": 2, "strategy_id": "multi-output-proof", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Multi-output proof", "description": None, "tags": []},
        "graph_inputs": [port for port in ports if port["direction"] == "input"],
        "graph_outputs": [port for port in ports if port["direction"] == "output"],
        "nodes": [{"node_id": "n", "component": {"component_id": key[0], "component_version": 2}, "parameters": {} if omitted_defaults else p}],
        "edges": [{"edge_id": "input", "source": {"scope": "graph_input", "port_id": "frame"},
                   "target": {"scope": "node", "node_id": "n", "port_id": "frame"}, "binding": {"kind": "single"}}] +
                 [{"edge_id": "output_" + port, "source": {"scope": "node", "node_id": "n", "port_id": port},
                   "target": {"scope": "graph_output", "port_id": port}, "binding": {"kind": "single"}} for port in PORTS[name]]}
    fact = node_contracts._plain(binding(name, p).document["input_binding"]["ports"]["frame"]["binding"])
    context = canonical_input_bindings(owner_id=fact["owner_id"], dataset_context_address=fact["dataset_context_address"],
        evaluation_context_address=fact["evaluation_context_address"], bindings={"frame": fact}, expected_source_addresses={"frame": hashing.content_address(fact)})
    graph = resolve_v2(document, registry)
    plan = compile_data_requirement_plan(graph, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, graph, registry=registry, input_bindings=context)
    receipt = node_contracts._plain(plan.parameter_binding_provenance[0]["node_contract_binding"])
    if tamper:
        tamper(receipt)
        # A self-consistent checksum is not registry authority. Readdress the
        # forged document so these cases reach replay, not merely digest parsing.
        receipt["bound_contract_address"] = hashing.content_address({key: value for key, value in receipt.items() if key != "bound_contract_address"})
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    result = evaluate_v2(graph, data, registry, evaluation_context_resolver=lambda node, inputs: {"bound_contract": bound})
    return result, receipt


def test_complete_scope_unpublished():
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS
    assert multi.NAMES == NAMES
    assert sum(len(PORTS[n]) for n in NAMES) == 19
    assert multi not in V2_CONTRIBUTORS
    assert set(multi.V2_COMPONENTS) == {("analytical." + name.lower(), 2) for name in NAMES}
    assert all(("analytical." + n.lower(), 2) not in REGISTRY.v2_components for n in NAMES)
    for name in NAMES:
        assert dict(multi.parameters_for(name)) == DEFAULTS[name]
        assert set(multi.SPECS[name]["outputs"]) == set(PORTS[name])


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", ["minimum", "small", "default"])
def test_complete_arrays_from_rational_convolution(name, kind):
    p, data = parameters(name, kind), frame(64)
    compare(evaluate(name, p, data), expected(name, p, data), data["frame"]["close"].index, name)


@pytest.mark.parametrize("source", ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"])
def test_macd_selected_fields(source):
    p, data = parameters("MACD"), frame(40)
    p["source"] = source
    wanted = expected("MACD", p, data)
    data["frame"] = {key: data["frame"][key] for key in fields("MACD", p)}
    compare(evaluate("MACD", p, data), wanted, next(iter(data["frame"].values())).index, "MACD")
    bound = binding("MACD", p, timeframe=3600)
    assert set(bound.document["resolved_contract"]["required_market_fields"]) == set(fields("MACD", p))
    assert all(row["timeframe"] == 3600 for row in bound.document["bound_requirements"])


@pytest.mark.parametrize("name,knob", [("KELTNER_CHANNELS", "basis_type"), ("PPO", "moving_average_type")])
def test_sma_variants(name, knob):
    p, data = parameters(name), frame(40)
    p[knob] = "SMA"
    compare(evaluate(name, p, data), expected(name, p, data), data["frame"]["close"].index, name)


@pytest.mark.parametrize("name,key", [("BOLLINGER_BANDS", "deviations"), ("BOLLINGER_BANDWIDTH", "deviations"),
                                     ("BOLLINGER_PERCENT_B", "deviations"), ("KELTNER_CHANNELS", "multiplier")])
@pytest.mark.parametrize("scale", [1e-6, 20])
def test_finite_parameter_endpoint_arrays(name, key, scale):
    p, data = parameters(name), frame(32)
    p[key] = scale
    compare(evaluate(name, p, data), expected(name, p, data), data["frame"]["close"].index, name)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("level", [0., 6., 1e-300, 1e300])
@pytest.mark.parametrize("kind", ["minimum", "default", "maximum"])
def test_analytic_constant_parameter_extremes(name, level, kind):
    p = parameters(name, kind)
    start = first(name, p)
    data = frame(start + 3, level=level)
    target = level if name in {"BOLLINGER_BANDS", "DONCHIAN_CHANNELS", "KELTNER_CHANNELS"} else 0.
    if name == "BOLLINGER_PERCENT_B" or level == 0 and name in {"PPO", "BOLLINGER_BANDWIDTH"}:
        target = U
    wanted = {port: [H] * start + [target] * 3 for port in PORTS[name]}
    compare(evaluate(name, p, data), wanted, data["frame"]["close"].index, name)


@pytest.mark.parametrize("name", NAMES)
def test_prefix_streaming_and_serialized_restart(name):
    p, data = parameters(name), frame(24)
    bound = binding(name, p)
    batch = multi.evaluate(name, p, data, bound_contract=bound)
    index = data["frame"]["close"].index
    for end in range(1, len(index) + 1):
        prefix = {"frame": {key: values.iloc[:end] for key, values in data["frame"].items()}}
        actual = multi.evaluate(name, p, prefix, bound_contract=bound)
        for port in PORTS[name]:
            assert actual[port].tolist() == batch[port].iloc[:end].tolist()
    state = multi.MultiOutputState(name, p, bound)
    for i, timestamp in enumerate(index):
        row = {"frame": {key: values.iloc[i] for key, values in data["frame"].items()}}
        got = state.step(row, event_time=timestamp)
        assert got == {port: batch[port].iloc[i] for port in PORTS[name]}
        state = multi.MultiOutputState.restore(name, p, bound, json.loads(json.dumps(state.snapshot())))


@pytest.mark.parametrize("name", NAMES)
def test_parameter_binding_and_state_guards(name):
    p = parameters(name)
    with pytest.raises(node_contracts.NodeContractRefusal):
        multi.parameters_for(name, {**p, "unused": 1})
    for key, value in p.items():
        invalid = [None, True, False, "not-a-choice"]
        if isinstance(value, str):
            invalid += [1]
        else:
            spec = multi.SPECS[name]["parameters"][key]
            invalid += [float("nan"), float("inf"), spec["minimum"] - 1, spec["maximum"] + 1]
            if spec["type"] == "exact_integer":
                invalid += [2.0, 2.5]
        for candidate in invalid:
            with pytest.raises(node_contracts.NodeContractRefusal):
                multi.parameters_for(name, {**p, key: candidate})
    if name in {"MACD", "PPO"}:
        with pytest.raises(node_contracts.NodeContractRefusal):
            multi.parameters_for(name, {**p, "fast_length": p["slow_length"]})
    bound = binding(name, p)
    state = multi.MultiOutputState(name, p, bound)
    state.step({"frame": {field: 4. for field in fields(name, p)}}, event_time="2025-01-02T10:00Z")
    snapshot = state.snapshot()
    for change in [lambda d: d.update(seen=True), lambda d: d.update(extra=1), lambda d: d.update(bound_contract_address=address("wrong")),
                   lambda d: d["history"].update(wrong=[]), lambda d: d.update(payload_address=address("forged"))]:
        corrupt = deepcopy(snapshot); change(corrupt)
        with pytest.raises(node_contracts.NodeContractRefusal):
            multi.MultiOutputState.restore(name, p, bound, corrupt)
    with pytest.raises(node_contracts.NodeContractRefusal):
        multi.MultiOutputState.restore(name, p, binding(name, p, timeframe=3600), snapshot)
    with pytest.raises(node_contracts.NodeContractRefusal):
        state.step({"frame": {f: 4. for f in fields(name, p)}}, event_time="2025-01-02T10:00Z")
    with pytest.raises(node_contracts.NodeContractRefusal):
        state.step({"frame": {f: 4. for f in fields(name, p)}}, event_time="2025-01-02T10:15Z", reset_reasons=["SESSION"])


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("invalid,state", [(None, M), (float("nan"), I), (float("inf"), I)])
def test_missing_invalid_and_explicit_gap_resets(name, invalid, state):
    p = parameters(name)
    split = first(name, p) + 2
    data = frame(split + first(name, p) + 4, level=4.)
    field = fields(name, p)[0]
    data["frame"][field] = data["frame"][field].astype(object)
    data["frame"][field].iloc[split] = invalid
    got = evaluate(name, p, data)
    for port in PORTS[name]:
        assert got[port].iloc[split].state is state
        assert all(v.state is H for v in got[port].iloc[split + 1:split + first(name, p) + 1])
    clean = frame(split + first(name, p) + 4, level=4.)
    resets = [()] * len(clean["frame"]["close"]); resets[split] = ("DATA_GAP",)
    reset = evaluate(name, p, clean, resets=resets)
    tail = {"frame": {key: series.iloc[split:] for key, series in clean["frame"].items()}}
    replay = evaluate(name, p, tail)
    for port in PORTS[name]:
        assert reset[port].iloc[split:].tolist() == replay[port].tolist()


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", ["minimum", "default", "maximum"])
def test_actual_resolver_compiler_runtime(name, kind):
    p = parameters(name, kind)
    data = frame(first(name, p) + 3, level=4.) if kind == "maximum" else frame(64)
    actual, receipt = through_runtime(name, p, data, omitted_defaults=kind == "default")
    if kind == "maximum":
        target = 4. if name in {"BOLLINGER_BANDS", "DONCHIAN_CHANNELS", "KELTNER_CHANNELS"} else U if name == "BOLLINGER_PERCENT_B" else 0.
        wanted = {port: [H] * first(name, p) + [target] * 3 for port in PORTS[name]}
    else:
        wanted = expected(name, p, data)
    compare(actual, wanted, data["frame"]["close"].index, name)
    assert receipt["parameters"] == p
    assert hashing.content_address(receipt["parameters"]) == hashing.content_address(p)
    assert receipt["resolved_contract"]["output_warmup"] == {port: first(name, p) for port in PORTS[name]}


@pytest.mark.parametrize("field", ["source_contract_address", "binding_implementation_address", "resolved_history", "extra"])
def test_real_runtime_rejects_any_forged_receipt_fact(field):
    def forge(document):
        if field == "resolved_history":
            document["resolved_contract"]["warmup_history"] = 0
        else:
            document[field] = address("forged")
    with pytest.raises((node_contracts.NodeContractRefusal, ValueError)):
        through_runtime("MACD", parameters("MACD"), frame(24), tamper=forge)


@pytest.mark.parametrize("impossible", ["1E+600", "1E-600"])
def test_restart_refuses_non_binary64_raw_history_even_with_consistent_digest(impossible):
    p = parameters("BOLLINGER_BANDS", "minimum")
    bound = binding("BOLLINGER_BANDS", p)
    state = multi.MultiOutputState("BOLLINGER_BANDS", p, bound)
    for minute, value in enumerate((4., 5.)):
        state.step({"frame": {"close": value}}, event_time=pd.Timestamp("2025-01-02T10:00Z") + pd.Timedelta(minutes=minute))
    document = state.snapshot()
    document["history"]["close"][0] = impossible
    values = [F(Decimal(value)) for value in document["history"]["close"]]
    total, squares = sum(values, F(0)), sum((value * value for value in values), F(0))
    document["fractions"] = [[str(value.numerator), str(value.denominator)] for value in (total, squares)]
    with localcontext() as context:
        context.prec = 1536
        document["sums"]["close"] = str(dec(total))
    document["payload_address"] = hashing.content_address({key: value for key, value in document.items() if key != "payload_address"})
    with pytest.raises(node_contracts.NodeContractRefusal):
        multi.MultiOutputState.restore("BOLLINGER_BANDS", p, bound, document)
