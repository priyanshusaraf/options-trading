"""Independent exact-decimal expectations for the multi-output 9/19 wave.

This module deliberately imports no Strategy OS product code and no earlier oracle.
Its formulas are transcribed from the sealed semantic/source decisions named in the
active assurance capsule.  Generate the immutable expectation bundle before any
inspection of the corrected implementation or predecessor expected-value code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


PRECISION = 90
D = Decimal
COMPONENT_PORTS = {
    "BOLLINGER_BANDS": ("lower", "middle", "upper"),
    "BOLLINGER_BANDWIDTH": ("value",),
    "BOLLINGER_PERCENT_B": ("value",),
    "DONCHIAN_CHANNELS": ("lower", "middle", "upper"),
    "KELTNER_CHANNELS": ("lower", "middle", "upper"),
    "MACD": ("histogram", "macd", "signal"),
    "PPO": ("value",),
    "STOCHASTIC": ("d", "k"),
    "STOCH_RSI": ("d", "k"),
}
SOURCE_DECISION_SHA256 = (
    "2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1"
)
SOURCE_IDENTITIES = {
    "BOLLINGER_BANDS": "SPEC:bollinger_bands-mathematical-v2",
    "PPO": "SPEC:ppo-mathematical-v2",
}


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, D(0)) / D(len(values))


def _rolling_mean(values: Sequence[Decimal], window: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    total = D(0)
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        if index >= window - 1:
            out[index] = total / D(window)
    return out


def _rolling_population_std(
    values: Sequence[Decimal], window: int
) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    total = D(0)
    total_sq = D(0)
    for index, value in enumerate(values):
        total += value
        total_sq += value * value
        if index >= window:
            old = values[index - window]
            total -= old
            total_sq -= old * old
        if index >= window - 1:
            mean = total / D(window)
            variance = total_sq / D(window) - mean * mean
            if variance < 0 and abs(variance) < D("1e-70"):
                variance = D(0)
            out[index] = variance.sqrt()
    return out


def _rolling_extreme(
    values: Sequence[Decimal], window: int, *, minimum: bool
) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    indexes: deque[int] = deque()
    for index, value in enumerate(values):
        while indexes and indexes[0] <= index - window:
            indexes.popleft()
        while indexes:
            prior = values[indexes[-1]]
            if (minimum and prior >= value) or (not minimum and prior <= value):
                indexes.pop()
            else:
                break
        indexes.append(index)
        if index >= window - 1:
            out[index] = values[indexes[0]]
    return out


def _sma_seeded_ema(values: Sequence[Decimal], length: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    if len(values) < length:
        return out
    alpha = D(2) / D(length + 1)
    current = _mean(values[:length])
    out[length - 1] = current
    for index in range(length, len(values)):
        current = current + alpha * (values[index] - current)
        out[index] = current
    return out


def _aligned_macd_ema(
    values: Sequence[Decimal], fast: int, slow: int
) -> tuple[list[Decimal | None], list[Decimal | None]]:
    fast_out: list[Decimal | None] = [None] * len(values)
    slow_out: list[Decimal | None] = [None] * len(values)
    if len(values) < slow:
        return fast_out, slow_out
    fast_alpha = D(2) / D(fast + 1)
    slow_alpha = D(2) / D(slow + 1)
    fast_value = _mean(values[slow - fast : slow])
    slow_value = _mean(values[:slow])
    fast_out[slow - 1] = fast_value
    slow_out[slow - 1] = slow_value
    for index in range(slow, len(values)):
        fast_value = fast_value + fast_alpha * (values[index] - fast_value)
        slow_value = slow_value + slow_alpha * (values[index] - slow_value)
        fast_out[index] = fast_value
        slow_out[index] = slow_value
    return fast_out, slow_out


def _rolling_valid_mean(
    values: Sequence[Decimal | None], window: int
) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    valid_run: list[Decimal] = []
    for index, value in enumerate(values):
        if value is None:
            valid_run.clear()
            continue
        valid_run.append(value)
        if len(valid_run) > window:
            valid_run.pop(0)
        if len(valid_run) == window:
            out[index] = _mean(valid_run)
    return out


def _rolling_valid_extreme(
    values: Sequence[Decimal | None], window: int, *, minimum: bool
) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    run: list[Decimal] = []
    for index, value in enumerate(values):
        if value is None:
            run.clear()
            continue
        run.append(value)
        if len(run) > window:
            run.pop(0)
        if len(run) == window:
            out[index] = min(run) if minimum else max(run)
    return out


def _bollinger(
    close: Sequence[Decimal], window: int, deviations: Decimal
) -> dict[str, list[Decimal | None]]:
    middle = _rolling_mean(close, window)
    std = _rolling_population_std(close, window)
    lower: list[Decimal | None] = [None] * len(close)
    upper: list[Decimal | None] = [None] * len(close)
    for index, (mean, scale) in enumerate(zip(middle, std, strict=True)):
        if mean is not None and scale is not None:
            lower[index] = mean - deviations * scale
            upper[index] = mean + deviations * scale
    return {"lower": lower, "middle": middle, "upper": upper}


def _bollinger_bandwidth(
    close: Sequence[Decimal], window: int, deviations: Decimal
) -> dict[str, list[Decimal | None]]:
    bands = _bollinger(close, window, deviations)
    out: list[Decimal | None] = [None] * len(close)
    for index, (lower, middle, upper) in enumerate(
        zip(bands["lower"], bands["middle"], bands["upper"], strict=True)
    ):
        if lower is not None and middle not in (None, D(0)) and upper is not None:
            out[index] = D(100) * (upper - lower) / middle
    return {"value": out}


def _bollinger_percent_b(
    close: Sequence[Decimal], window: int, deviations: Decimal
) -> dict[str, list[Decimal | None]]:
    bands = _bollinger(close, window, deviations)
    out: list[Decimal | None] = [None] * len(close)
    for index, (price, lower, upper) in enumerate(
        zip(close, bands["lower"], bands["upper"], strict=True)
    ):
        if lower is not None and upper is not None and upper != lower:
            out[index] = (price - lower) / (upper - lower)
    return {"value": out}


def _donchian(
    high: Sequence[Decimal], low: Sequence[Decimal], window: int
) -> dict[str, list[Decimal | None]]:
    lower = _rolling_extreme(low, window, minimum=True)
    upper = _rolling_extreme(high, window, minimum=False)
    middle: list[Decimal | None] = [None] * len(high)
    for index, (lo, hi) in enumerate(zip(lower, upper, strict=True)):
        if lo is not None and hi is not None:
            middle[index] = (lo + hi) / D(2)
    return {"lower": lower, "middle": middle, "upper": upper}


def _atr(
    high: Sequence[Decimal], low: Sequence[Decimal], close: Sequence[Decimal], length: int
) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(close)
    if len(close) <= length:
        return out
    true_ranges: list[Decimal | None] = [None]
    for index in range(1, len(close)):
        true_ranges.append(
            max(
                high[index] - low[index],
                abs(high[index] - close[index - 1]),
                abs(low[index] - close[index - 1]),
            )
        )
    current = _mean([value for value in true_ranges[1 : length + 1] if value is not None])
    out[length] = current
    for index in range(length + 1, len(close)):
        value = true_ranges[index]
        assert value is not None
        current = (current * D(length - 1) + value) / D(length)
        out[index] = current
    return out


def _keltner(
    high: Sequence[Decimal],
    low: Sequence[Decimal],
    close: Sequence[Decimal],
    window: int,
    atr_length: int,
    multiplier: Decimal,
    basis_type: str,
) -> dict[str, list[Decimal | None]]:
    middle = (
        _sma_seeded_ema(close, window)
        if basis_type == "EMA"
        else _rolling_mean(close, window)
    )
    atr = _atr(high, low, close, atr_length)
    lower: list[Decimal | None] = [None] * len(close)
    upper: list[Decimal | None] = [None] * len(close)
    for index, (mean, range_value) in enumerate(zip(middle, atr, strict=True)):
        if mean is not None and range_value is not None:
            lower[index] = mean - multiplier * range_value
            upper[index] = mean + multiplier * range_value
        else:
            middle[index] = None
    return {"lower": lower, "middle": middle, "upper": upper}


def _selected_source(inputs: Mapping[str, Sequence[Decimal]], source: str) -> list[Decimal]:
    if source in inputs:
        return list(inputs[source])
    if source == "hl2":
        return [(h + l) / D(2) for h, l in zip(inputs["high"], inputs["low"], strict=True)]
    if source == "hlc3":
        return [
            (h + l + c) / D(3)
            for h, l, c in zip(inputs["high"], inputs["low"], inputs["close"], strict=True)
        ]
    if source == "ohlc4":
        return [
            (o + h + l + c) / D(4)
            for o, h, l, c in zip(
                inputs["open"], inputs["high"], inputs["low"], inputs["close"], strict=True
            )
        ]
    raise AssertionError(f"unknown source: {source}")


def _macd(
    source_values: Sequence[Decimal], fast: int, slow: int, signal_length: int
) -> dict[str, list[Decimal | None]]:
    fast_ema, slow_ema = _aligned_macd_ema(source_values, fast, slow)
    macd_raw: list[Decimal | None] = [None] * len(source_values)
    for index, (fast_value, slow_value) in enumerate(zip(fast_ema, slow_ema, strict=True)):
        if fast_value is not None and slow_value is not None:
            macd_raw[index] = fast_value - slow_value
    aligned_macd = [value for value in macd_raw if value is not None]
    aligned_signal = _sma_seeded_ema(aligned_macd, signal_length)
    signal: list[Decimal | None] = [None] * len(source_values)
    signal[slow - 1 :] = aligned_signal
    macd: list[Decimal | None] = [None] * len(source_values)
    histogram: list[Decimal | None] = [None] * len(source_values)
    for index, signal_value in enumerate(signal):
        if signal_value is not None:
            value = macd_raw[index]
            assert value is not None
            macd[index] = value
            histogram[index] = value - signal_value
    return {"histogram": histogram, "macd": macd, "signal": signal}


def _ppo(
    close: Sequence[Decimal], fast: int, slow: int, moving_average_type: str
) -> dict[str, list[Decimal | None]]:
    if moving_average_type == "EMA":
        fast_ma = _sma_seeded_ema(close, fast)
        slow_ma = _sma_seeded_ema(close, slow)
    else:
        fast_ma = _rolling_mean(close, fast)
        slow_ma = _rolling_mean(close, slow)
    out: list[Decimal | None] = [None] * len(close)
    for index, (fast_value, slow_value) in enumerate(zip(fast_ma, slow_ma, strict=True)):
        if fast_value is not None and slow_value not in (None, D(0)):
            out[index] = D(100) * (fast_value - slow_value) / slow_value
    return {"value": out}


def _stochastic(
    high: Sequence[Decimal],
    low: Sequence[Decimal],
    close: Sequence[Decimal],
    k_length: int,
    k_smoothing: int,
    d_smoothing: int,
) -> dict[str, list[Decimal | None]]:
    lows = _rolling_extreme(low, k_length, minimum=True)
    highs = _rolling_extreme(high, k_length, minimum=False)
    raw: list[Decimal | None] = [None] * len(close)
    for index, (lo, hi) in enumerate(zip(lows, highs, strict=True)):
        if lo is not None and hi is not None:
            raw[index] = D(0) if hi == lo else D(100) * (close[index] - lo) / (hi - lo)
    k_raw = _rolling_valid_mean(raw, k_smoothing)
    d = _rolling_valid_mean(k_raw, d_smoothing)
    k: list[Decimal | None] = [None] * len(close)
    for index, d_value in enumerate(d):
        if d_value is not None:
            k[index] = k_raw[index]
    return {"d": d, "k": k}


def _rsi(close: Sequence[Decimal], length: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(close)
    if len(close) <= length:
        return out
    gains = [max(close[index] - close[index - 1], D(0)) for index in range(1, len(close))]
    losses = [max(close[index - 1] - close[index], D(0)) for index in range(1, len(close))]
    average_gain = _mean(gains[:length])
    average_loss = _mean(losses[:length])

    def value() -> Decimal:
        if average_loss == 0:
            return D(0) if average_gain == 0 else D(100)
        if average_gain == 0:
            return D(0)
        return D(100) - D(100) / (D(1) + average_gain / average_loss)

    out[length] = value()
    for index in range(length + 1, len(close)):
        gain = gains[index - 1]
        loss = losses[index - 1]
        average_gain = (average_gain * D(length - 1) + gain) / D(length)
        average_loss = (average_loss * D(length - 1) + loss) / D(length)
        out[index] = value()
    return out


def _stoch_rsi(
    close: Sequence[Decimal],
    rsi_length: int,
    stochastic_length: int,
    k_smoothing: int,
    d_smoothing: int,
) -> dict[str, list[Decimal | None]]:
    rsi = _rsi(close, rsi_length)
    lows = _rolling_valid_extreme(rsi, stochastic_length, minimum=True)
    highs = _rolling_valid_extreme(rsi, stochastic_length, minimum=False)
    raw: list[Decimal | None] = [None] * len(close)
    for index, (value, lo, hi) in enumerate(zip(rsi, lows, highs, strict=True)):
        if value is not None and lo is not None and hi is not None:
            raw[index] = D(0) if hi == lo else D(100) * (value - lo) / (hi - lo)
    k_raw = _rolling_valid_mean(raw, k_smoothing)
    d = _rolling_valid_mean(k_raw, d_smoothing)
    k: list[Decimal | None] = [None] * len(close)
    for index, d_value in enumerate(d):
        if d_value is not None:
            k[index] = k_raw[index]
    return {"d": d, "k": k}


def _split_valid_segments(
    inputs: Mapping[str, Sequence[Decimal | None]],
    evaluator: Callable[[Mapping[str, Sequence[Decimal]]], dict[str, list[Decimal | None]]],
    ports: Sequence[str],
) -> dict[str, list[Decimal | None]]:
    length = len(next(iter(inputs.values())))
    out = {port: [None] * length for port in ports}
    start = 0
    while start < length:
        while start < length and any(values[start] is None for values in inputs.values()):
            start += 1
        if start >= length:
            break
        end = start
        while end < length and all(values[end] is not None for values in inputs.values()):
            end += 1
        segment = {
            name: [value for value in values[start:end] if value is not None]
            for name, values in inputs.items()
        }
        segment_out = evaluator(segment)
        for port in ports:
            out[port][start:end] = segment_out[port]
        start = end
    return out


def _fixture(kind: str, length: int, gap: int | None = None) -> dict[str, list[Decimal | None]]:
    close: list[Decimal] = []
    for index in range(length):
        if kind == "mixed":
            value = D(100) + D((index * 17) % 23 - 11) / D(7) + D(index) / D(19)
        elif kind == "zero":
            value = D(0)
        elif kind == "tiny":
            value = D("1e-9") + D((index * 7) % 11 - 5) * D("1e-13")
        elif kind == "large":
            value = D("1000000000000") + D((index * 5) % 17 - 8) / D(8)
        elif kind == "flat":
            value = D(7)
        else:
            raise AssertionError(kind)
        close.append(value)
    if kind in {"zero", "flat"}:
        spread = D(0)
    elif kind == "tiny":
        spread = D("3e-13")
    elif kind == "large":
        spread = D("0.5")
    else:
        spread = D("1.25")
    high = [value + spread + D(index % 3) * spread / D(10) for index, value in enumerate(close)]
    low = [value - spread - D(index % 2) * spread / D(10) for index, value in enumerate(close)]
    open_ = [(value + lo + hi) / D(3) for value, lo, hi in zip(close, low, high, strict=True)]
    result: dict[str, list[Decimal | None]] = {
        "open": list(open_),
        "high": list(high),
        "low": list(low),
        "close": list(close),
    }
    if gap is not None:
        for values in result.values():
            values[gap] = None
    return result


def _parameter_sets(component: str) -> list[tuple[str, str, int, dict[str, object], int | None]]:
    common = {
        "BOLLINGER_BANDS": (
            {"window": 2, "deviations": "0.000001"},
            {"window": 14, "deviations": "2"},
            {"window": 5, "deviations": "1.25"},
            {"window": 4096, "deviations": "20"},
        ),
        "BOLLINGER_BANDWIDTH": (
            {"window": 2, "deviations": "0.000001"},
            {"window": 14, "deviations": "2"},
            {"window": 5, "deviations": "1.25"},
            {"window": 4096, "deviations": "20"},
        ),
        "BOLLINGER_PERCENT_B": (
            {"window": 2, "deviations": "0.000001"},
            {"window": 14, "deviations": "2"},
            {"window": 5, "deviations": "1.25"},
            {"window": 4096, "deviations": "20"},
        ),
        "DONCHIAN_CHANNELS": (
            {"window": 2}, {"window": 14}, {"window": 5}, {"window": 4096}
        ),
        "KELTNER_CHANNELS": (
            {"window": 2, "atr_length": 2, "multiplier": "0.000001", "basis_type": "SMA"},
            {"window": 14, "atr_length": 14, "multiplier": "2", "basis_type": "EMA"},
            {"window": 5, "atr_length": 3, "multiplier": "1.25", "basis_type": "SMA"},
            {"window": 4096, "atr_length": 4096, "multiplier": "20", "basis_type": "EMA"},
        ),
        "MACD": (
            {"fast_length": 2, "slow_length": 3, "signal_length": 1, "source": "close"},
            {"fast_length": 12, "slow_length": 26, "signal_length": 9, "source": "close"},
            {"fast_length": 3, "slow_length": 7, "signal_length": 4, "source": "hlc3"},
            {"fast_length": 4095, "slow_length": 4096, "signal_length": 4096, "source": "ohlc4"},
        ),
        "PPO": (
            {"fast_length": 2, "slow_length": 3, "moving_average_type": "SMA"},
            {"fast_length": 12, "slow_length": 26, "moving_average_type": "EMA"},
            {"fast_length": 3, "slow_length": 7, "moving_average_type": "SMA"},
            {"fast_length": 4095, "slow_length": 4096, "moving_average_type": "EMA"},
        ),
        "STOCHASTIC": (
            {"k_length": 2, "k_smoothing": 1, "d_smoothing": 1},
            {"k_length": 14, "k_smoothing": 3, "d_smoothing": 3},
            {"k_length": 5, "k_smoothing": 2, "d_smoothing": 4},
            {"k_length": 4096, "k_smoothing": 4096, "d_smoothing": 4096},
        ),
        "STOCH_RSI": (
            {"rsi_length": 2, "stochastic_length": 2, "k_smoothing": 1, "d_smoothing": 1},
            {"rsi_length": 14, "stochastic_length": 14, "k_smoothing": 3, "d_smoothing": 3},
            {"rsi_length": 5, "stochastic_length": 4, "k_smoothing": 2, "d_smoothing": 4},
            {"rsi_length": 4096, "stochastic_length": 4096, "k_smoothing": 4096, "d_smoothing": 4096},
        ),
    }
    minimum, default, nondefault, maximum = common[component]
    if component == "MACD":
        maximum_length = 8194
    elif component in {"STOCHASTIC", "STOCH_RSI"}:
        maximum_length = 16388 if component == "STOCH_RSI" else 12292
    else:
        maximum_length = 4100
    return [
        ("minimum", "mixed", 24, minimum, None),
        ("default_gap", "mixed", 96, default, 47),
        ("tiny_nonzero", "tiny", 72, nondefault, None),
        ("zero", "zero", 96, default, None),
        ("maximum", "flat", maximum_length, maximum, None),
    ]


def _evaluate_component(
    component: str,
    inputs: Mapping[str, Sequence[Decimal]],
    parameters: Mapping[str, object],
) -> dict[str, list[Decimal | None]]:
    if component == "BOLLINGER_BANDS":
        return _bollinger(inputs["close"], int(parameters["window"]), D(str(parameters["deviations"])))
    if component == "BOLLINGER_BANDWIDTH":
        return _bollinger_bandwidth(inputs["close"], int(parameters["window"]), D(str(parameters["deviations"])))
    if component == "BOLLINGER_PERCENT_B":
        return _bollinger_percent_b(inputs["close"], int(parameters["window"]), D(str(parameters["deviations"])))
    if component == "DONCHIAN_CHANNELS":
        return _donchian(inputs["high"], inputs["low"], int(parameters["window"]))
    if component == "KELTNER_CHANNELS":
        return _keltner(
            inputs["high"], inputs["low"], inputs["close"],
            int(parameters["window"]), int(parameters["atr_length"]),
            D(str(parameters["multiplier"])), str(parameters["basis_type"]),
        )
    if component == "MACD":
        return _macd(
            _selected_source(inputs, str(parameters["source"])),
            int(parameters["fast_length"]), int(parameters["slow_length"]),
            int(parameters["signal_length"]),
        )
    if component == "PPO":
        return _ppo(
            inputs["close"], int(parameters["fast_length"]), int(parameters["slow_length"]),
            str(parameters["moving_average_type"]),
        )
    if component == "STOCHASTIC":
        return _stochastic(
            inputs["high"], inputs["low"], inputs["close"],
            int(parameters["k_length"]), int(parameters["k_smoothing"]),
            int(parameters["d_smoothing"]),
        )
    if component == "STOCH_RSI":
        return _stoch_rsi(
            inputs["close"], int(parameters["rsi_length"]),
            int(parameters["stochastic_length"]), int(parameters["k_smoothing"]),
            int(parameters["d_smoothing"]),
        )
    raise AssertionError(component)


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def build_expectation_bundle() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    with localcontext() as context:
        context.prec = PRECISION
        for component, ports in COMPONENT_PORTS.items():
            for label, fixture_kind, length, parameters, gap in _parameter_sets(component):
                inputs = _fixture(fixture_kind, length, gap)
                outputs = _split_valid_segments(
                    inputs,
                    lambda segment, c=component, p=parameters: _evaluate_component(c, segment, p),
                    ports,
                )
                serialized_outputs = {}
                for port in ports:
                    values = outputs[port]
                    serialized_outputs[port] = {
                        "values": [_decimal_text(value) for value in values],
                        "valid": [value is not None for value in values],
                    }
                cases.append(
                    {
                        "id": f"{component}-{label}",
                        "component": component,
                        "ports": list(ports),
                        "fixture": fixture_kind,
                        "gap_index": gap,
                        "parameters": parameters,
                        "inputs": {
                            name: [_decimal_text(value) for value in values]
                            for name, values in inputs.items()
                        },
                        "outputs": serialized_outputs,
                    }
                )
    return {
        "schema": "independent-multi-output-expected-vectors/1",
        "independence": {
            "product_imports": 0,
            "prior_oracle_imports": 0,
            "authorship_order": "sealed before protected implementation and prior expected-value inspection",
            "decimal_precision": PRECISION,
        },
        "source_decision_sha256": SOURCE_DECISION_SHA256,
        "new_source_identities": SOURCE_IDENTITIES,
        "components": list(COMPONENT_PORTS),
        "ports": {component: list(ports) for component, ports in COMPONENT_PORTS.items()},
        "case_count": len(cases),
        "cases": cases,
    }


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_sealed_expectations(output_dir: Path, *, adjudicated: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = build_expectation_bundle()
    vector_path = output_dir / "fresh-expected-vectors.json"
    vector_path.write_bytes(_canonical_bytes(bundle))
    oracle_path = Path(__file__).resolve()
    oracle_sha = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    vector_sha = hashlib.sha256(vector_path.read_bytes()).hexdigest()
    complete_values = 0
    valid_values = 0
    for case in bundle["cases"]:
        for output in case["outputs"].values():
            complete_values += len(output["values"])
            valid_values += sum(output["valid"])
    seal = {
        "schema": "independent-multi-output-expectation-seal/1",
        "verdict": (
            "SOURCE_CONTRACT_ADJUDICATION_SEALED_AFTER_INITIAL_RED"
            if adjudicated
            else "FRESH_EXPECTATIONS_SEALED_BEFORE_PRODUCT_INSPECTION"
        ),
        "oracle": str(oracle_path),
        "oracle_sha256": oracle_sha,
        "vectors": str(vector_path),
        "vectors_sha256": vector_sha,
        "source_decision_sha256": SOURCE_DECISION_SHA256,
        "components": len(COMPONENT_PORTS),
        "ports": sum(len(ports) for ports in COMPONENT_PORTS.values()),
        "cases": bundle["case_count"],
        "complete_output_positions": complete_values,
        "valid_output_positions": valid_values,
        "fixture_classes": ["mixed", "missing-gap", "tiny-nonzero", "zero", "maximum-flat"],
        "parameter_classes": ["minimum", "default", "nondefault", "maximum"],
        "product_source_inspected": adjudicated,
        "correction_test_inspected": adjudicated,
        "producer_or_helper_inspected": adjudicated,
        "older_expected_code_inspected": adjudicated,
    }
    (output_dir / "fresh-expectation-seal.json").write_bytes(_canonical_bytes(seal))


def test_independent_bundle_covers_exact_9_components_and_19_ports() -> None:
    bundle = build_expectation_bundle()
    assert bundle["components"] == list(COMPONENT_PORTS)
    assert sum(len(ports) for ports in bundle["ports"].values()) == 19
    assert bundle["case_count"] == 45
    assert all(len(case["outputs"]) == len(COMPONENT_PORTS[case["component"]]) for case in bundle["cases"])


def test_independent_bundle_has_complete_values_and_matching_masks() -> None:
    bundle = build_expectation_bundle()
    for case in bundle["cases"]:
        input_length = len(case["inputs"]["close"])
        for output in case["outputs"].values():
            assert len(output["values"]) == input_length
            assert len(output["valid"]) == input_length
            assert output["valid"] == [value is not None for value in output["values"]]


def test_independent_bundle_exercises_seed_zero_tiny_gap_and_maximum() -> None:
    bundle = build_expectation_bundle()
    ids = {case["id"] for case in bundle["cases"]}
    for component in COMPONENT_PORTS:
        assert f"{component}-minimum" in ids
        assert f"{component}-default_gap" in ids
        assert f"{component}-tiny_nonzero" in ids
        assert f"{component}-zero" in ids
        assert f"{component}-maximum" in ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--adjudicated", action="store_true")
    arguments = parser.parse_args()
    write_sealed_expectations(arguments.output_dir, adjudicated=arguments.adjudicated)


if __name__ == "__main__":
    main()
