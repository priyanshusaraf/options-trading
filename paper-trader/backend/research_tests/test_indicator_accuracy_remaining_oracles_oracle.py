"""Independent remaining-oracles expected-value logic.

This module deliberately imports no Strategy OS product module, evaluator, helper,
fixture, or generated product output.  Its decisions, parameter surfaces, named
outputs, and equations are transcribed from the sealed required specification.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import math


ALL_NAMES = tuple(
    "EWMA_VOLATILITY GARMAN_KLASS ICHIMOKU_COMPONENTS PARKINSON "
    "REALIZED_VOLATILITY ROGERS_SATCHELL SUPERTREND "
    "VOLATILITY_PERCENTILE VOLATILITY_RANK YANG_ZHANG".split()
)
DECISIONS = {
    "EWMA_VOLATILITY": "REPLACE_V2",
    "GARMAN_KLASS": "REFUSE",
    "ICHIMOKU_COMPONENTS": "REFUSE",
    "PARKINSON": "REPLACE_V2",
    "REALIZED_VOLATILITY": "KEEP",
    "ROGERS_SATCHELL": "REPLACE_V2",
    "SUPERTREND": "REFUSE",
    "VOLATILITY_PERCENTILE": "REPLACE_V2",
    "VOLATILITY_RANK": "REPLACE_V2",
    "YANG_ZHANG": "REPLACE_V2",
}
NAMES = tuple(name for name in ALL_NAMES if DECISIONS[name] != "REFUSE")
REFUSED = tuple(name for name in ALL_NAMES if DECISIONS[name] == "REFUSE")
REFUSAL_CODES = {
    "GARMAN_KLASS": "PRIMARY_GK_VARIANT_UNVERIFIED",
    "ICHIMOKU_COMPONENTS": "NUMERICAL_CONVENTION_UNVERIFIED",
    "SUPERTREND": "NUMERICAL_CONVENTION_UNVERIFIED",
}
INPUTS = {
    "EWMA_VOLATILITY": ("close",),
    "GARMAN_KLASS": ("open", "high", "low", "close"),
    "ICHIMOKU_COMPONENTS": ("high", "low", "close"),
    "PARKINSON": ("high", "low"),
    "REALIZED_VOLATILITY": ("close",),
    "ROGERS_SATCHELL": ("open", "high", "low", "close"),
    "SUPERTREND": ("high", "low", "close"),
    "VOLATILITY_PERCENTILE": ("close",),
    "VOLATILITY_RANK": ("close",),
    "YANG_ZHANG": ("open", "high", "low", "close"),
}
OUTPUTS = {
    name: {"value": {"dtype": "float64_series", "units": "decimal_volatility"}}
    for name in ALL_NAMES
}
OUTPUTS["ICHIMOKU_COMPONENTS"] = {
    port: {"dtype": "float64_series", "units": "input_units"}
    for port in ("chikou", "kijun", "senkou_a", "senkou_b", "tenkan")
}
OUTPUTS["SUPERTREND"] = {
    "direction": {"dtype": "nullable_signed_direction_series", "units": "direction_minus1_plus1"},
    "value": {"dtype": "float64_series", "units": "input_units"},
}
OUTPUTS["VOLATILITY_PERCENTILE"] = {
    "value": {"dtype": "float64_series", "units": "percentile_0_to_100"},
}
OUTPUTS["VOLATILITY_RANK"] = {
    "value": {"dtype": "float64_series", "units": "range_rank_0_to_100"},
}
PARAMETERS = {
    "EWMA_VOLATILITY": {
        "decay": ("finite_number", 0.000001, 0.999999, 0.94),
        "periods_per_year": ("finite_number", 1, 1_000_000, 1),
        "seed_window": ("exact_integer", 2, 4096, 14),
    },
    "GARMAN_KLASS": {
        "periods_per_year": ("finite_number", 1, 1_000_000, 1),
        "window": ("exact_integer", 2, 4096, 14),
    },
    "ICHIMOKU_COMPONENTS": {
        "base_length": ("exact_integer", 2, 4096, 26),
        "conversion_length": ("exact_integer", 2, 4096, 9),
        "displacement": ("exact_integer", 0, 4096, 26),
        "span_b_length": ("exact_integer", 2, 4096, 52),
    },
    "PARKINSON": {
        "periods_per_year": ("finite_number", 1, 1_000_000, 1),
        "window": ("exact_integer", 2, 4096, 14),
    },
    "REALIZED_VOLATILITY": {
        "periods_per_year": ("finite_number", 1, 1_000_000, 1),
        "window": ("exact_integer", 2, 4096, 14),
    },
    "ROGERS_SATCHELL": {
        "periods_per_year": ("finite_number", 1, 1_000_000, 1),
        "window": ("exact_integer", 2, 4096, 14),
    },
    "SUPERTREND": {
        "atr_length": ("exact_integer", 2, 4096, 14),
        "factor": ("finite_number", 0.000001, 20, 3),
    },
    "VOLATILITY_PERCENTILE": {
        "rank_window": ("exact_integer", 2, 4096, 14),
        "vol_window": ("exact_integer", 2, 4096, 14),
    },
    "VOLATILITY_RANK": {
        "rank_window": ("exact_integer", 2, 4096, 14),
        "vol_window": ("exact_integer", 2, 4096, 14),
    },
    "YANG_ZHANG": {
        "periods_per_year": ("finite_number", 1, 1_000_000, 1),
        "window": ("exact_integer", 2, 4096, 14),
    },
}


@dataclass(frozen=True)
class Cell:
    state: str
    value: float | None = None


def defaults(name):
    return {key: spec[3] for key, spec in PARAMETERS[name].items()}


def small_parameters(name):
    values = defaults(name)
    if "window" in values:
        values["window"] = 3
    if "seed_window" in values:
        values.update(seed_window=3, decay=0.8, periods_per_year=252)
    if "vol_window" in values:
        values.update(vol_window=3, rank_window=4)
    if "periods_per_year" in values:
        values["periods_per_year"] = 252
    return values


def first_valid(name, parameters):
    if name in REFUSED:
        return None
    if name in {"EWMA_VOLATILITY"}:
        return parameters["seed_window"]
    if name in {"REALIZED_VOLATILITY", "YANG_ZHANG"}:
        return parameters["window"]
    if name in {"PARKINSON", "ROGERS_SATCHELL"}:
        return parameters["window"] - 1
    return parameters["vol_window"] + parameters["rank_window"] - 1


def fixture_rows(count):
    rows = []
    for i in range(count):
        close = 101.0 + i * 0.29 + ((i * 7) % 11 - 5) * 0.43 + (i % 3) * 0.17
        opening = close + (-0.37 if i % 2 else 0.21)
        rows.append({
            "open": opening,
            "high": max(opening, close) + 0.71 + (i % 4) * 0.09,
            "low": min(opening, close) - 0.63 - (i % 5) * 0.04,
            "close": close,
        })
    return rows


def _d(value):
    return Decimal.from_float(float(value))


def _population_volatility(changes, periods_per_year=1):
    mean = sum(changes, Decimal(0)) / len(changes)
    variance = sum(((value - mean) ** 2 for value in changes), Decimal(0)) / len(changes)
    radicand = variance * _d(periods_per_year)
    return None if radicand < 0 else radicand.sqrt()


def _row_is_valid(name, row):
    try:
        values = [float(row[field]) for field in INPUTS[name]]
    except (KeyError, TypeError, ValueError):
        return False
    if any(not math.isfinite(value) or value <= 0 for value in values):
        return False
    if "high" in INPUTS[name] and "low" in INPUTS[name] and row["high"] < row["low"]:
        return False
    if "open" in INPUTS[name] and not row["low"] <= row["open"] <= row["high"]:
        return False
    if "close" in INPUTS[name] and "high" in INPUTS[name] and not row["low"] <= row["close"] <= row["high"]:
        return False
    return True


def expected(name, parameters, rows, resets=None):
    """Return every expected state/value without calling any product code."""
    if name not in NAMES:
        raise ValueError("numeric oracle requested for a refused component")
    resets = [()] * len(rows) if resets is None else resets
    result = []
    segment = []
    variance = None
    volatilities = []
    with localcontext() as context:
        context.prec = 120
        context.Emin = -999999
        context.Emax = 999999
        for row, reasons in zip(rows, resets):
            if reasons:
                segment, variance, volatilities = [], None, []
            if not _row_is_valid(name, row):
                result.append(Cell("INVALID"))
                segment, variance, volatilities = [], None, []
                continue
            segment.append({field: _d(row[field]) for field in INPUTS[name]})
            number = None
            if name == "EWMA_VOLATILITY":
                length = parameters["seed_window"]
                if len(segment) == length + 1:
                    changes = [(b["close"] - a["close"]) / a["close"] for a, b in zip(segment, segment[1:])]
                    variance = sum((change * change for change in changes), Decimal(0)) / length
                elif len(segment) > length + 1:
                    previous, current = segment[-2]["close"], segment[-1]["close"]
                    change = (current - previous) / previous
                    decay = _d(parameters["decay"])
                    variance = decay * variance + (1 - decay) * change * change
                if variance is not None:
                    number = (variance * _d(parameters["periods_per_year"])).sqrt()
            elif name == "PARKINSON":
                length = parameters["window"]
                if len(segment) >= length:
                    terms = [(row["high"].ln() - row["low"].ln()) ** 2 for row in segment[-length:]]
                    number = (sum(terms, Decimal(0)) / length / (4 * Decimal(2).ln())
                              * _d(parameters["periods_per_year"])).sqrt()
            elif name == "ROGERS_SATCHELL":
                length = parameters["window"]
                if len(segment) >= length:
                    terms = []
                    for item in segment[-length:]:
                        o, h, low, close = (item[key] for key in ("open", "high", "low", "close"))
                        terms.append((h.ln() - o.ln()) * (h.ln() - close.ln())
                                     + (low.ln() - o.ln()) * (low.ln() - close.ln()))
                    radicand = sum(terms, Decimal(0)) / length * _d(parameters["periods_per_year"])
                    number = None if radicand < 0 else radicand.sqrt()
            elif name in {"REALIZED_VOLATILITY", "VOLATILITY_PERCENTILE", "VOLATILITY_RANK"}:
                length = parameters.get("window", parameters.get("vol_window"))
                if len(segment) > length:
                    sample = segment[-(length + 1):]
                    changes = [(b["close"] - a["close"]) / a["close"] for a, b in zip(sample, sample[1:])]
                    volatility = _population_volatility(changes, parameters.get("periods_per_year", 1))
                    if name == "REALIZED_VOLATILITY":
                        number = volatility
                    else:
                        volatilities.append(volatility)
                        rank = parameters["rank_window"]
                        if len(volatilities) >= rank:
                            values = volatilities[-rank:]
                            current = values[-1]
                            if name == "VOLATILITY_PERCENTILE":
                                less = sum(value < current for value in values)
                                equal = sum(value == current for value in values)
                                number = Decimal(100) * (Decimal(less) + (Decimal(equal) + 1) / 2) / rank
                            else:
                                low, high = min(values), max(values)
                                number = None if high == low else Decimal(100) * (current - low) / (high - low)
            else:
                length = parameters["window"]
                if len(segment) > length:
                    sample = segment[-(length + 1):]
                    overnight, intraday, rs = [], [], []
                    for prior, item in zip(sample, sample[1:]):
                        o, h, low, close = (item[key] for key in ("open", "high", "low", "close"))
                        overnight.append(o.ln() - prior["close"].ln())
                        intraday.append(close.ln() - o.ln())
                        rs.append((h.ln() - o.ln()) * (h.ln() - close.ln())
                                  + (low.ln() - o.ln()) * (low.ln() - close.ln()))

                    def sample_variance(values):
                        mean = sum(values, Decimal(0)) / length
                        return sum(((value - mean) ** 2 for value in values), Decimal(0)) / (length - 1)

                    k = Decimal("0.34") / (Decimal("1.34") + Decimal(length + 1) / (length - 1))
                    radicand = (sample_variance(overnight) + k * sample_variance(intraday)
                                + (1 - k) * sum(rs, Decimal(0)) / length) * _d(parameters["periods_per_year"])
                    number = None if radicand < 0 else radicand.sqrt()

            first = first_valid(name, parameters)
            if len(segment) - 1 < first:
                result.append(Cell("INSUFFICIENT_HISTORY"))
            elif number is None or not math.isfinite(float(number)):
                result.append(Cell("MATHEMATICALLY_UNDEFINED"))
            else:
                result.append(Cell("VALID", float(number)))
    return result


def test_oracle_scope_is_closed_and_self_consistent():
    assert len(ALL_NAMES) == 10
    assert len(NAMES) == 7
    assert len(REFUSED) == 3
    assert set(DECISIONS) == set(INPUTS) == set(OUTPUTS) == set(PARAMETERS)
    for name in NAMES:
        params = small_parameters(name)
        cells = expected(name, params, fixture_rows(first_valid(name, params) + 4))
        assert cells[first_valid(name, params)].state in {"VALID", "MATHEMATICALLY_UNDEFINED"}
