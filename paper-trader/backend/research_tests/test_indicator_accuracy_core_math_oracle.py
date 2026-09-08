"""Independent 80-digit mathematical specification consumer.

No product import, product evaluator, implementation-owner vector or generator
is used. Definitions come from the accepted semantic-contracts.md sections.
Decimal normal equations deliberately avoid the product's floating-point
algorithm; Fraction supplies an additional two-point correlation identity.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
import os
from pathlib import Path
from typing import NamedTuple


RUN = Path(os.environ.get("CORE_ASSURANCE_RUN_ROOT", str(Path(__file__).resolve().parents[3] / ".agent/runs/post-phase5-indicator-accuracy-core-math-assurance")))
SPEC = json.loads((RUN / "semantic-specification.json").read_text())
NAMES = tuple("""ALPHA BETA BETA_ADJUSTED_SPREAD CCI CHAIKIN_MONEY_FLOW CORRELATION
COVARIANCE CROSS_ABOVE CROSS_BELOW FALLING GAP GAP_DOWN GAP_UP HL2 HLC3 INSIDE_BAR
LINEAR_REGRESSION_INTERCEPT LINEAR_REGRESSION_SLOPE LOG_RETURN MAD MFI MIDPOINT
MOMENTUM OHLC4 OUTSIDE_BAR PERCENTILE PERCENTILE_RANK PERCENT_RETURN POINT_CHANGE
RATIO RELATIVE_VOLUME RESIDUAL RISING ROC ROLLING_HEDGE_RATIO ROLLING_HIGH ROLLING_LOW
ROLLING_MAX ROLLING_MEAN ROLLING_MEDIAN ROLLING_MIN ROLLING_RANK ROLLING_REGRESSION
ROLLING_RETURN ROLLING_STDDEV ROLLING_VARIANCE ROLLING_VOLUME_PERCENTILE R_SQUARED
SMA TREND_PERSISTENCE TRUE_RANGE TYPICAL_PRICE VOLUME_ZSCORE VWMA WEIGHTED_CLOSE
WILLIAMS_R WMA ZSCORE""".split())
assert set(SPEC) == set(NAMES) and len(NAMES) == 58
EXACT = frozenset("""CROSS_ABOVE CROSS_BELOW FALLING GAP GAP_DOWN GAP_UP HL2 HLC3
INSIDE_BAR MIDPOINT MOMENTUM OHLC4 OUTSIDE_BAR POINT_CHANGE RISING ROLLING_HIGH
ROLLING_LOW ROLLING_MAX ROLLING_MIN TRUE_RANGE TYPICAL_PRICE WEIGHTED_CLOSE""".split())


class Cell(NamedTuple):
    state: str
    value: object = None
    causes: tuple[str, ...] = ()


def declared_inputs(name):
    return tuple(SPEC[name]["Inputs"].split(", "))


def declared_outputs(name):
    return tuple(sorted(json.loads(SPEC[name]["Outputs"])))


def parameter_specs(name):
    return json.loads(SPEC[name]["Parameters"])


def defaults(name, supplied=None):
    result = {key: value["default"] for key, value in parameter_specs(name).items()}
    result.update(supplied or {})
    return result


def first_valid(name, parameters=None):
    rule = SPEC[name]["First valid index"]
    if rule == "window":
        return defaults(name, parameters)["window"]
    if rule == "window - 1":
        return defaults(name, parameters)["window"] - 1
    return int(rule)


def dec(value):
    if type(value) is float:
        return Decimal.from_float(value)
    return Decimal(value)


def sumd(values):
    return sum(values, Decimal(0))


def normal_equations(x, y):
    """Exact-precision raw moments, independent of centered float accumulation."""
    n = Decimal(len(x))
    sx, sy = sumd(x), sumd(y)
    xx = n * sumd(value * value for value in x) - sx * sx
    yy = n * sumd(value * value for value in y) - sy * sy
    xy = n * sumd(a * b for a, b in zip(x, y)) - sx * sy
    return xx, yy, xy, sx / n, sy / n


def two_point_fraction_correlation(x, y):
    dx = Fraction(x[1]) - Fraction(x[0])
    dy = Fraction(y[1]) - Fraction(y[0])
    if dx == 0 or dy == 0:
        return None
    return 1 if dx * dy > 0 else -1


def scalar_number(name, window_rows, parameters):
    """One mathematical trailing-window result; never calls product helpers."""
    columns = {key: [dec(row[key]) for row in window_rows] for key in declared_inputs(name)}
    latest = {key: values[-1] for key, values in columns.items()}
    close = columns.get("close", [])
    n = len(window_rows)
    w = parameters.get("window", n)
    zero = Decimal(0)
    result = None
    if name in {"HL2", "MIDPOINT"}:
        result = (latest["high"] + latest["low"]) / 2
    elif name in {"HLC3", "TYPICAL_PRICE"}:
        result = (latest["high"] + latest["low"] + latest["close"]) / 3
    elif name == "OHLC4":
        result = sumd(latest[key] for key in ("open", "high", "low", "close")) / 4
    elif name == "WEIGHTED_CLOSE":
        result = (latest["high"] + latest["low"] + 2 * latest["close"]) / 4
    elif name == "RATIO":
        result = latest["close"] / latest["peer"]
    elif name in {"GAP", "GAP_UP", "GAP_DOWN"}:
        difference = latest["open"] - close[-2]
        result = difference if name == "GAP" else difference > 0 if name == "GAP_UP" else difference < 0
    elif name in {"CROSS_ABOVE", "CROSS_BELOW"}:
        peer = columns["peer"]
        result = (close[-1] > peer[-1] and close[-2] <= peer[-2]) if name == "CROSS_ABOVE" else (close[-1] < peer[-1] and close[-2] >= peer[-2])
    elif name in {"INSIDE_BAR", "OUTSIDE_BAR"}:
        high, low = columns["high"], columns["low"]
        result = (high[-1] < high[-2] and low[-1] > low[-2]) if name == "INSIDE_BAR" else (high[-1] > high[-2] and low[-1] < low[-2])
    elif name == "TRUE_RANGE":
        result = max(latest["high"] - latest["low"], abs(latest["high"] - close[-2]), abs(latest["low"] - close[-2]))
    elif name in {"MOMENTUM", "POINT_CHANGE"}:
        result = close[-1] - close[0]
    elif name in {"PERCENT_RETURN", "ROLLING_RETURN", "ROC"}:
        result = close[-1] / close[0] - 1
    elif name == "LOG_RETURN":
        if close[-1] <= 0 or close[0] <= 0:
            raise ArithmeticError("nonpositive log endpoint")
        result = (close[-1] / close[0]).ln()
    elif name in {"RISING", "FALLING", "TREND_PERSISTENCE"}:
        differences = [b - a for a, b in zip(close, close[1:])]
        if name == "TREND_PERSISTENCE":
            result = Decimal(abs(sum((value > 0) - (value < 0) for value in differences))) / w
        else:
            result = all(value > 0 for value in differences) if name == "RISING" else all(value < 0 for value in differences)
    elif name in {"SMA", "ROLLING_MEAN"}:
        result = sumd(close) / n
    elif name in {"ROLLING_HIGH", "ROLLING_MAX"}:
        result = max(close)
    elif name in {"ROLLING_LOW", "ROLLING_MIN"}:
        result = min(close)
    elif name == "WMA":
        result = sumd(Decimal(index + 1) * value for index, value in enumerate(close)) / Decimal(n * (n + 1) // 2)
    elif name in {"ROLLING_MEDIAN", "PERCENTILE"}:
        ordered = sorted(close)
        q = Decimal(50) if name == "ROLLING_MEDIAN" else dec(parameters["q"])
        position = Decimal(n - 1) * q / 100
        left = int(position)
        right = min(n - 1, left + 1)
        result = ordered[left] + (position - left) * (ordered[right] - ordered[left])
    elif name in {"ROLLING_RANK", "PERCENTILE_RANK", "ROLLING_VOLUME_PERCENTILE"}:
        values = columns["volume"] if name == "ROLLING_VOLUME_PERCENTILE" else close
        rank = Decimal(sum(value < values[-1] for value in values)) + Decimal(sum(value == values[-1] for value in values) + 1) / 2
        result = rank if name == "ROLLING_RANK" else 100 * rank / n
    elif name == "MAD":
        mean = sumd(close) / n
        result = sumd(abs(value - mean) for value in close) / n
    elif name in {"ROLLING_VARIANCE", "ROLLING_STDDEV", "ZSCORE", "VOLUME_ZSCORE"}:
        values = columns["volume"] if name == "VOLUME_ZSCORE" else close
        # Pairwise squared distance identity: sum_i,j (x_i-x_j)^2/(2*n)
        # reduces to n*sum(x^2)-sum(x)^2, evaluated at 80 digits.
        mean = sumd(values) / n
        variance = (Decimal(n) * sumd(value * value for value in values) - sumd(values) ** 2) / Decimal(n * (n - parameters.get("ddof", 0)))
        if name == "ROLLING_VARIANCE": result = variance
        elif name == "ROLLING_STDDEV": result = variance.sqrt()
        else: result = (values[-1] - mean) / variance.sqrt()
    elif name == "RELATIVE_VOLUME":
        result = latest["volume"] * n / sumd(columns["volume"])
    elif name == "VWMA":
        result = sumd(price * volume for price, volume in zip(close, columns["volume"])) / sumd(columns["volume"])
    elif name == "WILLIAMS_R":
        high, low = max(columns["high"]), min(columns["low"])
        result = zero if high == low else -100 * (high - close[-1]) / (high - low)
    elif name in {"CCI", "MFI"}:
        typical = [(h + l + c) / 3 for h, l, c in zip(columns["high"], columns["low"], close)]
        if name == "CCI":
            mean = sumd(typical) / n
            deviation = sumd(abs(value - mean) for value in typical) / n
            result = zero if deviation == 0 else (typical[-1] - mean) / (Decimal("0.015") * deviation)
        else:
            positive = sumd(typical[i] * columns["volume"][i] for i in range(1, n) if typical[i] > typical[i - 1])
            negative = sumd(typical[i] * columns["volume"][i] for i in range(1, n) if typical[i] < typical[i - 1])
            # The pinned TA_MFI contract specifies the 1.0 total-flow threshold.
            result = zero if positive + negative < 1 else 100 * positive / (positive + negative)
    elif name == "CHAIKIN_MONEY_FLOW":
        contributions = []
        for high, low, price, volume in zip(columns["high"], columns["low"], close, columns["volume"]):
            contributions.append(zero if high == low else (2 * price - high - low) * volume / (high - low))
        result = sumd(contributions) / sumd(columns["volume"])
    elif name in {"LINEAR_REGRESSION_SLOPE", "LINEAR_REGRESSION_INTERCEPT"}:
        xx, _, xy, meanx, meany = normal_equations([Decimal(i) for i in range(n)], close)
        slope = xy / xx
        result = slope if name.endswith("SLOPE") else meany - slope * meanx
    elif name in {"BETA", "ALPHA"}:
        x = [b / a - 1 for a, b in zip(columns["peer"], columns["peer"][1:])]
        y = [b / a - 1 for a, b in zip(close, close[1:])]
        xx, _, xy, meanx, meany = normal_equations(x, y)
        result = xy / xx if name == "BETA" else meany - (xy / xx) * meanx
    elif name in {"CORRELATION", "COVARIANCE", "R_SQUARED", "ROLLING_HEDGE_RATIO", "BETA_ADJUSTED_SPREAD", "RESIDUAL", "ROLLING_REGRESSION"}:
        xx, yy, xy, meanx, meany = normal_equations(columns["peer"], close)
        if name == "COVARIANCE": result = xy / Decimal(n * (n - parameters["ddof"]))
        elif name in {"CORRELATION", "R_SQUARED"}:
            result = xy / (xx * yy).sqrt() if name == "CORRELATION" else xy * xy / (xx * yy)
        else:
            # Rational level OLS also proves exact-zero residuals, avoiding a
            # Decimal division rounding remnant being mislabeled nonzero truth.
            xq = [Fraction(value) for value in columns["peer"]]
            yq = [Fraction(value) for value in close]
            denominator = n * sum(value * value for value in xq) - sum(xq) ** 2
            slope = (n * sum(a * b for a, b in zip(xq, yq)) - sum(xq) * sum(yq)) / denominator
            intercept = (sum(yq) - slope * sum(xq)) / n
            residual = yq[-1] - intercept - slope * xq[-1]
            if name == "ROLLING_REGRESSION":
                return {"slope": slope, "intercept": intercept, "residual": residual}
            result = {"ROLLING_HEDGE_RATIO": slope, "BETA_ADJUSTED_SPREAD": yq[-1] - slope * xq[-1], "RESIDUAL": residual}[name]
    else:
        raise AssertionError("Uncovered independent formula: " + name)
    return {"value": result}


def ingress(value):
    if isinstance(value, Cell):
        return value
    if value is None:
        return Cell("MISSING")
    if isinstance(value, bool):
        return Cell("INVALID")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return Cell("INVALID")
    return Cell("VALID", number) if math.isfinite(number) else Cell("INVALID")


def scalar_series(name, rows, parameters=None, resets=None):
    parameters = defaults(name, parameters)
    outputs = {port: [] for port in declared_outputs(name)}
    first = first_valid(name, parameters)
    start = 0
    valid_rows = []
    resets = resets if resets is not None else [()] * len(rows)
    with localcontext() as ctx:
        ctx.prec = 80
        for index, row in enumerate(rows):
            cells = {field: ingress(row[field]) for field in declared_inputs(name)}
            bad = [cell for cell in cells.values() if cell.state != "VALID"]
            values = {field: cell.value for field, cell in cells.items()}
            if not bad:
                if ("volume" in values and values["volume"] < 0) or ("high" in values and "low" in values and (values["high"] < values["low"] or "close" in values and not values["low"] <= values["close"] <= values["high"])):
                    bad = [Cell("INVALID")]
            valid_rows.append(values)
            if resets[index]:
                start = index
            if bad:
                start = index + 1
                states = tuple(sorted({cell.state for cell in bad}))
                cell = bad[0] if len(states) == 1 else Cell("INVALID", causes=states)
                produced = {port: cell for port in outputs}
            elif index - start < first:
                produced = {port: Cell("INSUFFICIENT_HISTORY") for port in outputs}
            else:
                try:
                    raw = scalar_number(name, valid_rows[index - first:index + 1], parameters)
                    produced = {port: Cell("VALID", value if type(value) is bool else float(value)) for port, value in raw.items()}
                    if any(not math.isfinite(cell.value) for cell in produced.values()):
                        raise ArithmeticError("overflow")
                except (ArithmeticError, ValueError):
                    produced = {port: Cell("MATHEMATICALLY_UNDEFINED") for port in outputs}
            assert set(produced) == set(outputs)
            for port in outputs:
                outputs[port].append(produced[port])
    return outputs


def error_within(actual, expected, *, exact=False):
    if isinstance(expected, bool):
        return type(actual) is bool and actual is expected
    if type(actual) not in {int, float} or not math.isfinite(actual):
        return False
    absolute = abs(actual - expected)
    if expected == 0 or exact:
        return absolute <= 1e-12
    return absolute <= 1e-10 and absolute / abs(expected) <= 1e-9


def fixture_rows(length=73, kind="jagged"):
    rows = []
    for index in range(length):
        price = 80 + ((index * 17) % 37) / 8 + (index % 5) / 16
        peer = 50 + ((index * 23) % 43) / 16 + (index % 11) / 8
        volume = 32 + (index * 13) % 97
        if kind == "ramp": price, peer = 32 + index / 8, 17 + index / 16 + (index % 3) / 8
        if kind == "reversal": price = 32 + min(index, length - 1 - index) / 4
        if kind == "ties": price, peer = 32 + (index // 3) % 4, 18 + (index // 2) % 7
        if kind in {"flat", "zero"}: price, peer, volume = (4, 2, 8) if kind == "flat" else (0, 0, 0)
        opening = price + ((index % 3) - 1) / 4
        high = max(opening, price) + 0.5 + (index % 7) / 32
        low = min(opening, price) - 0.75 - (index % 4) / 32
        if kind in {"flat", "zero"}: opening = high = low = price
        rows.append({"open": opening, "high": high, "low": low, "close": price, "volume": volume, "peer": peer})
    return rows


def test_oracle_hand_worked_regression_rank_quantile_and_masks():
    rows = [{"close": y, "peer": x} for x, y in [(1, 3), (2, 5), (3, 7)]]
    regression = scalar_series("ROLLING_REGRESSION", rows, {"window": 2})
    assert regression == {"intercept": [Cell("INSUFFICIENT_HISTORY"), Cell("VALID", 1.0), Cell("VALID", 1.0)],
                          "residual": [Cell("INSUFFICIENT_HISTORY"), Cell("VALID", 0.0), Cell("VALID", 0.0)],
                          "slope": [Cell("INSUFFICIENT_HISTORY"), Cell("VALID", 2.0), Cell("VALID", 2.0)]}
    assert scalar_series("PERCENTILE", [{"close": 1}, {"close": 5}], {"window": 2, "q": 25})["value"][-1] == Cell("VALID", 2.0)
    assert scalar_series("ROLLING_RANK", [{"close": 2}] * 3, {"window": 3})["value"][-1] == Cell("VALID", 2.0)
    assert scalar_series("SMA", [{"close": 1}, {"close": None}, {"close": 3}, {"close": 5}], {"window": 2})["value"] == [Cell("INSUFFICIENT_HISTORY"), Cell("MISSING"), Cell("INSUFFICIENT_HISTORY"), Cell("VALID", 4.0)]


def test_oracle_strict_conjunction_and_zero_threshold():
    assert not error_within(1.01e-12, 1e-12)
    assert not error_within(1e12 + 0.001, 1e12)
    assert error_within(1e-13, 0.0)
    assert not error_within(2e-12, 0.0)
    assert not error_within(0, False)
    assert two_point_fraction_correlation([1, 3], [7, 2]) == -1
