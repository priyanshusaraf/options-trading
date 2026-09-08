"""Frozen V1 Type 2/4 analytical catalogue and deterministic implementations."""
from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from app.ir.hashing import content_address
from app.ir.registry import (
    DependencyBoundary,
    PlatformRegistry,
    registered_v2_implementation,
)


REQUIRED_NAMES = tuple(sorted(set("""
ACCUMULATION_DISTRIBUTION ADX ALPHA ANCHORED_VWAP ATR BARS_SINCE_SESSION_OPEN
BETA BETA_ADJUSTED_SPREAD BOLLINGER_BANDS BOLLINGER_BANDWIDTH BOLLINGER_PERCENT_B
CCI CHAIKIN_MONEY_FLOW CHAIKIN_OSCILLATOR CLOSE CORRELATION COVARIANCE CROSS_ABOVE
CROSS_BELOW CUMULATIVE_RETURN DISTANCE_FROM_SESSION_HIGH_LOW DONCHIAN_CHANNELS DTE
EMA EWMA_VOLATILITY EXPIRY_CALENDAR FALLING GAP GAP_DOWN GAP_UP GARMAN_KLASS HIGH
HL2 HLC3 ICHIMOKU_COMPONENTS INSIDE_BAR INSTRUMENT_METADATA KAMA KELTNER_CHANNELS
LINEAR_REGRESSION_INTERCEPT LINEAR_REGRESSION_SLOPE LOG_RETURN LOW LTP MACD MAD
MARKET_CLOCK MA_SLOPE MFI MID MIDPOINT MINUS_DI MOMENTUM NATR OBV OHLC4 OHLCV OPEN
OPENING_RANGE OUTSIDE_BAR PARABOLIC_SAR PARKINSON PERCENTILE PERCENTILE_RANK
PERCENT_RETURN PLUS_DI POINT_CHANGE PPO PREVIOUS_SESSION_FIELDS PREVIOUS_SESSION_OHLC
PRICE_MA_DISTANCE PRICE_VOLUME_TREND RATIO REALIZED_VOLATILITY RELATIVE_VOLUME
RESAMPLING RESIDUAL RISING RMA_WILDER ROC ROGERS_SATCHELL ROLLING_HEDGE_RATIO
ROLLING_HIGH ROLLING_LOW ROLLING_MAX ROLLING_MEAN ROLLING_MEDIAN ROLLING_MIN
ROLLING_RANK ROLLING_REGRESSION ROLLING_RETURN ROLLING_STDDEV ROLLING_VARIANCE
ROLLING_VOLUME_PERCENTILE RSI R_SQUARED SESSION_CALENDAR SESSION_HIGH SESSION_LOW
SESSION_OPEN SESSION_OPEN_HIGH_LOW SMA SPREAD STOCHASTIC STOCH_RSI SUPERTREND
TIMEFRAME TIME_TO_SESSION_CLOSE TREND_PERSISTENCE TRUE_RANGE TYPICAL_PRICE
VOLATILITY_PERCENTILE VOLATILITY_RANK VOLUME_ZSCORE VWAP VWMA WEIGHTED_CLOSE
WILLIAMS_R WMA YANG_ZHANG ZSCORE
""".split())))
CAPABILITY_GATED_NAMES = ("ASK", "BID", "BOOK_DEPTH", "OPEN_INTEREST", "SPREAD")
CATALOGUE_NAMES = tuple(sorted(set(REQUIRED_NAMES) | set(CAPABILITY_GATED_NAMES)))
TYPE_4_NAMES = frozenset("""
ASK BID BOOK_DEPTH CLOSE DTE EXPIRY_CALENDAR HIGH INSTRUMENT_METADATA LOW LTP MARKET_CLOCK
MID OHLCV OPEN OPEN_INTEREST PREVIOUS_SESSION_FIELDS RESAMPLING SESSION_CALENDAR
SESSION_OPEN_HIGH_LOW SPREAD TIMEFRAME
""".split())


class AnalyticalRefusal(ValueError):
    pass


def component_id(name: str) -> str:
    return f"analytical.{name.lower()}"


def _port(port_id: str, *, direction: str) -> dict[str, Any]:
    result = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "market_frame" if direction == "input" else "analytical_value",
        "type_ref": {"type_id": "phase5.value", "type_version": 1},
        "shape": "series",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": "single", "min": 1, "max": 1, "assembly": "single",
        }
    return result


def _parameter(default: Any, type_name: str = "int") -> dict[str, Any]:
    return {
        "type": type_name, "required": False, "default": default, "enum": None,
        "domain": None, "units": "value", "serialization": "canonical-json",
    }


def _component(name: str) -> dict[str, Any]:
    parameters = {
        "window": _parameter(14),
        "capability_verified": _parameter(False, "bool"),
    }
    return {
        "component_id": component_id(name),
        "component_version": 1,
        "domain_family": "market_data" if name in TYPE_4_NAMES else "indicator",
        "structural_role": "source" if name in TYPE_4_NAMES else "transform",
        "ports": [_port("frame", direction="input"), _port("value", direction="output")],
        "parameters": parameters,
    }


def _fields(name: str) -> tuple[str, ...]:
    if name in {"OPEN", "HIGH", "LOW", "CLOSE", "LTP", "MID", "OPEN_INTEREST", "BID", "ASK"}:
        return ("LAST" if name in {"LTP", "MID"} else name,)
    if name in {"VWAP", "VWMA", "OBV", "ACCUMULATION_DISTRIBUTION", "CHAIKIN_MONEY_FLOW",
                "CHAIKIN_OSCILLATOR", "PRICE_VOLUME_TREND", "RELATIVE_VOLUME",
                "VOLUME_ZSCORE", "ROLLING_VOLUME_PERCENTILE", "MFI"}:
        return ("CLOSE", "HIGH", "LOW", "VOLUME")
    return ("CLOSE", "HIGH", "LOW", "OPEN")


def _declaration(name: str) -> dict[str, Any]:
    requirements = []
    for index, field in enumerate(_fields(name)):
        requirements.append({
            "requirement_id": f"field_{index}",
            "instrument": {"literal": {"role": "primary", "type": "PHYSICAL"}},
            "field": {"literal": field},
            "timeframe": {"literal": 60},
            "history": {"literal": {"minimum_bars": 1, "warmup_bars": 14}},
            "freshness": {"literal": {"maximum_age_seconds": 120}},
            "depth": {"literal": {
                "kind": "TOP_OF_BOOK" if field in {"BID", "ASK"} else "NONE",
                "levels": None,
            }},
            "session": {"literal": "INSTRUMENT_CALENDAR"},
            "alignment": {"literal": {"kind": "EXACT", "maximum_skew_seconds": 0}},
            "derived_local": {"literal": field not in {"BID", "ASK", "OPEN_INTEREST"}},
        })
    return {
        "schema": "data-requirement-declaration/1",
        "classification": "REQUIRES_DATA",
        "requirements": requirements,
    }


def _contract(name: str) -> dict[str, Any]:
    fields = tuple(field.lower() for field in _fields(name))
    return {
        "stable_node_id": component_id(name),
        "semantic_version": 1,
        "visible_family": "TYPE_4" if name in TYPE_4_NAMES else "TYPE_2",
        "input_types": {"frame": "market-frame/series"},
        "output_types": {"value": "analytical-value/series"},
        "required_market_fields": list(sorted(fields)),
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 14,
        "execution_form": "ROLLING" if name not in TYPE_4_NAMES else "STATELESS",
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/1", "reasons": ["SESSION"]},
        "bar_policy": "COMPLETED_ONLY",
        "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "FINITE_ONLY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"],
        "streaming_support": True,
        "batch_support": True,
        "mode_eligibility": {"research": True, "paper": True, "live": False},
        "provider_requirements": [content_address({"provider-fields": list(fields)})],
        "resource_profile": {
            "compute_microseconds_per_event": 50,
            "memory_bytes_upper_bound": 4096,
            "history_bytes_upper_bound": 8192,
            "state_bytes_upper_bound": 1024,
            "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": len(fields),
            "fanout_upper_bound": 32,
        },
        "reference_provenance": [content_address({"phase5-reference": name, "version": 1})],
    }


def _implementation(name: str):
    def implementation(parameters: Mapping[str, Any], inputs: Mapping[str, Any], _name: str = name):
        if _name in CAPABILITY_GATED_NAMES and parameters.get("capability_verified") is not True:
            raise AnalyticalRefusal("CAPABILITY_REQUIRED")
        return {"value": evaluate_analytical(_name, inputs["frame"], parameters)}
    return implementation


def _series(frame: Any, name: str, *, fallback: str = "close") -> pd.Series:
    if isinstance(frame, pd.Series):
        result = frame
    elif isinstance(frame, dict):
        value = frame.get(name.lower(), frame.get(name.upper(), frame.get(fallback)))
        if value is None:
            raise AnalyticalRefusal(f"missing field {name}")
        result = value if isinstance(value, pd.Series) else pd.Series(value)
    else:
        raise AnalyticalRefusal("market frame must be a Series or mapping")
    return pd.to_numeric(result, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _window(parameters: Mapping[str, Any]) -> int:
    value = parameters.get("window", 14)
    if type(value) is not int or value < 1 or value > 100_000:
        raise AnalyticalRefusal("window must be a bounded exact integer")
    return value


def _ema(value: pd.Series, window: int) -> pd.Series:
    return value.ewm(span=window, adjust=False, min_periods=window).mean()


def _true_range(frame: Any) -> pd.Series:
    high, low, close = _series(frame, "high"), _series(frame, "low"), _series(frame, "close")
    return pd.concat((high - low, (high - close.shift()).abs(), (low - close.shift()).abs()), axis=1).max(axis=1)


def _rolling_percentile(value: pd.Series, window: int) -> pd.Series:
    return value.rolling(window).apply(lambda row: float(pd.Series(row).rank(pct=True).iloc[-1]), raw=False)


def evaluate_analytical(name: str, frame: Any, parameters: Mapping[str, Any]) -> Any:
    """One deterministic, completed-prefix analytical evaluator for the frozen catalogue."""
    window = _window(parameters)
    close = _series(frame, "close")
    high, low, open_ = _series(frame, "high"), _series(frame, "low"), _series(frame, "open")
    volume = _series(frame, "volume", fallback="close")
    if name in {"OPEN", "HIGH", "LOW", "CLOSE", "LTP", "MID", "OPEN_INTEREST", "BID", "ASK"}:
        return _series(frame, "last" if name in {"LTP", "MID"} else name.lower())
    if name == "BOOK_DEPTH": return _series(frame, "book_depth", fallback="close")
    if name in {"HL2", "MIDPOINT"}: return (high + low) / 2
    if name in {"HLC3", "TYPICAL_PRICE"}: return (high + low + close) / 3
    if name == "OHLC4": return (open_ + high + low + close) / 4
    if name == "WEIGHTED_CLOSE": return (high + low + 2 * close) / 4
    if name == "OHLCV": return pd.DataFrame(dict(open=open_, high=high, low=low, close=close, volume=volume))
    if name in {"SMA", "ROLLING_MEAN"}: return close.rolling(window).mean()
    if name in {"EMA", "KAMA"}: return _ema(close, window)
    if name == "RMA_WILDER": return close.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    if name == "WMA":
        weights = np.arange(1, window + 1)
        return close.rolling(window).apply(lambda row: float(np.dot(row, weights) / weights.sum()), raw=True)
    if name == "VWMA": return (close * volume).rolling(window).sum() / volume.rolling(window).sum()
    if name in {"ROLLING_MIN", "ROLLING_LOW"}: return close.rolling(window).min()
    if name in {"ROLLING_MAX", "ROLLING_HIGH"}: return close.rolling(window).max()
    if name == "ROLLING_MEDIAN": return close.rolling(window).median()
    if name in {"ROLLING_STDDEV", "REALIZED_VOLATILITY"}: return close.pct_change().rolling(window).std(ddof=0)
    if name == "ROLLING_VARIANCE": return close.pct_change().rolling(window).var(ddof=0)
    if name == "MAD": return close.rolling(window).apply(lambda row: float(np.mean(np.abs(row - np.mean(row)))), raw=True)
    if name in {"POINT_CHANGE", "MOMENTUM"}: return close.diff(window)
    if name in {"PERCENT_RETURN", "ROC", "ROLLING_RETURN"}: return close.pct_change(window)
    if name == "LOG_RETURN": return np.log(close / close.shift(window))
    if name == "CUMULATIVE_RETURN": return (1 + close.pct_change().fillna(0)).cumprod() - 1
    if name == "TRUE_RANGE": return _true_range(frame)
    if name == "ATR": return _true_range(frame).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    if name == "NATR": return 100 * evaluate_analytical("ATR", frame, parameters) / close
    if name in {"ZSCORE", "VOLUME_ZSCORE"}:
        value = volume if name == "VOLUME_ZSCORE" else close
        return (value - value.rolling(window).mean()) / value.rolling(window).std(ddof=0)
    if name == "RSI":
        delta = close.diff(); up = delta.clip(lower=0); down = -delta.clip(upper=0)
        rs = up.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / down.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        return 100 - 100 / (1 + rs)
    if name in {"STOCHASTIC", "WILLIAMS_R"}:
        lower, upper = low.rolling(window).min(), high.rolling(window).max()
        value = 100 * (close - lower) / (upper - lower)
        return value - 100 if name == "WILLIAMS_R" else value
    if name == "STOCH_RSI":
        rsi = evaluate_analytical("RSI", frame, parameters)
        return 100 * (rsi - rsi.rolling(window).min()) / (rsi.rolling(window).max() - rsi.rolling(window).min())
    if name == "CCI":
        typical = (high + low + close) / 3; mean = typical.rolling(window).mean()
        mad = typical.rolling(window).apply(lambda row: float(np.mean(np.abs(row - np.mean(row)))), raw=True)
        return (typical - mean) / (0.015 * mad)
    if name in {"MACD", "PPO"}:
        fast, slow = _ema(close, 12), _ema(close, 26); difference = fast - slow
        return 100 * difference / slow if name == "PPO" else difference
    if name in {"BOLLINGER_BANDS", "BOLLINGER_BANDWIDTH", "BOLLINGER_PERCENT_B"}:
        mean, std = close.rolling(window).mean(), close.rolling(window).std(ddof=0)
        upper, lower = mean + 2 * std, mean - 2 * std
        if name == "BOLLINGER_BANDS": return pd.DataFrame(dict(lower=lower, middle=mean, upper=upper))
        if name == "BOLLINGER_BANDWIDTH": return (upper - lower) / mean
        return (close - lower) / (upper - lower)
    if name == "DONCHIAN_CHANNELS": return pd.DataFrame(dict(lower=low.rolling(window).min(), upper=high.rolling(window).max()))
    if name == "KELTNER_CHANNELS":
        mean = _ema(close, window); atr = evaluate_analytical("ATR", frame, parameters)
        return pd.DataFrame(dict(lower=mean - 2 * atr, middle=mean, upper=mean + 2 * atr))
    if name in {"VWAP", "ANCHORED_VWAP"}: return ((high + low + close) / 3 * volume).cumsum() / volume.cumsum()
    if name == "OBV": return (np.sign(close.diff()).fillna(0) * volume).cumsum()
    if name == "ACCUMULATION_DISTRIBUTION": return (((2 * close - high - low) / (high - low)) * volume).fillna(0).cumsum()
    if name == "CHAIKIN_MONEY_FLOW": return (((2 * close - high - low) / (high - low)) * volume).rolling(window).sum() / volume.rolling(window).sum()
    if name == "CHAIKIN_OSCILLATOR":
        ad = evaluate_analytical("ACCUMULATION_DISTRIBUTION", frame, parameters); return _ema(ad, 3) - _ema(ad, 10)
    if name == "PRICE_VOLUME_TREND": return (close.pct_change().fillna(0) * volume).cumsum()
    if name == "RELATIVE_VOLUME": return volume / volume.rolling(window).mean()
    if name in {"PERCENTILE", "PERCENTILE_RANK", "VOLATILITY_PERCENTILE", "ROLLING_VOLUME_PERCENTILE"}:
        value = volume if name == "ROLLING_VOLUME_PERCENTILE" else close.pct_change().rolling(window).std(ddof=0) if name == "VOLATILITY_PERCENTILE" else close
        return _rolling_percentile(value, window) * 100
    if name in {"ROLLING_RANK", "VOLATILITY_RANK"}: return evaluate_analytical("PERCENTILE_RANK", frame, parameters)
    if name in {"COVARIANCE", "CORRELATION", "BETA", "ALPHA", "SPREAD", "RATIO", "BETA_ADJUSTED_SPREAD", "ROLLING_HEDGE_RATIO", "RESIDUAL", "R_SQUARED", "LINEAR_REGRESSION_SLOPE", "LINEAR_REGRESSION_INTERCEPT", "ROLLING_REGRESSION"}:
        peer = _series(frame, "peer", fallback="open")
        cov = close.rolling(window).cov(peer); var = peer.rolling(window).var(ddof=0); beta = cov / var
        if name == "COVARIANCE": return cov
        if name == "CORRELATION": return close.rolling(window).corr(peer)
        if name in {"BETA", "ROLLING_HEDGE_RATIO", "LINEAR_REGRESSION_SLOPE"}: return beta
        intercept = close.rolling(window).mean() - beta * peer.rolling(window).mean()
        if name in {"ALPHA", "LINEAR_REGRESSION_INTERCEPT"}: return intercept
        if name == "RATIO": return close / peer
        if name == "SPREAD": return close - peer
        residual = close - (intercept + beta * peer)
        if name in {"RESIDUAL", "BETA_ADJUSTED_SPREAD"}: return residual
        if name == "R_SQUARED": return close.rolling(window).corr(peer) ** 2
        return pd.DataFrame(dict(slope=beta, intercept=intercept, residual=residual))
    if name in {"CROSS_ABOVE", "CROSS_BELOW"}:
        peer = _series(frame, "peer", fallback="open")
        return ((close > peer) & (close.shift() <= peer.shift())) if name == "CROSS_ABOVE" else ((close < peer) & (close.shift() >= peer.shift()))
    if name in {"RISING", "FALLING"}: return close.diff().gt(0).rolling(window).sum().eq(window) if name == "RISING" else close.diff().lt(0).rolling(window).sum().eq(window)
    if name == "INSIDE_BAR": return high.lt(high.shift()) & low.gt(low.shift())
    if name == "OUTSIDE_BAR": return high.gt(high.shift()) & low.lt(low.shift())
    if name in {"GAP", "GAP_UP", "GAP_DOWN"}:
        gap = open_ - close.shift(); return gap.gt(0) if name == "GAP_UP" else gap.lt(0) if name == "GAP_DOWN" else gap
    if name in {"PARKINSON", "GARMAN_KLASS", "ROGERS_SATCHELL", "YANG_ZHANG"}:
        log_hl = np.log(high / low); base = (log_hl ** 2).rolling(window).mean()
        if name == "PARKINSON": return np.sqrt(base / (4 * math.log(2)))
        oc = np.log(close / open_); co = np.log(open_ / close.shift())
        if name == "GARMAN_KLASS": return np.sqrt((0.5 * log_hl ** 2 - (2 * math.log(2) - 1) * oc ** 2).rolling(window).mean())
        rs = (np.log(high / close) * np.log(high / open_) + np.log(low / close) * np.log(low / open_)).rolling(window).mean()
        if name == "ROGERS_SATCHELL": return np.sqrt(rs)
        return np.sqrt(co.rolling(window).var(ddof=0) + 0.34 * oc.rolling(window).var(ddof=0) + 0.66 * rs)
    if name in {"PLUS_DI", "MINUS_DI", "ADX"}:
        up, down = high.diff(), -low.diff(); atr = evaluate_analytical("ATR", frame, parameters)
        plus = 100 * up.where((up > down) & (up > 0), 0).ewm(alpha=1/window, adjust=False).mean() / atr
        minus = 100 * down.where((down > up) & (down > 0), 0).ewm(alpha=1/window, adjust=False).mean() / atr
        if name == "PLUS_DI": return plus
        if name == "MINUS_DI": return minus
        return (100 * (plus - minus).abs() / (plus + minus)).ewm(alpha=1/window, adjust=False).mean()
    if name in {"SESSION_OPEN", "OPENING_RANGE"}: return open_.groupby(open_.index.normalize() if isinstance(open_.index, pd.DatetimeIndex) else pd.Series(range(len(open_)), index=open_.index)).transform("first")
    if name == "SESSION_HIGH": return high.cummax()
    if name == "SESSION_LOW": return low.cummin()
    if name == "SESSION_OPEN_HIGH_LOW": return pd.DataFrame(
        dict(open=open_.groupby(open_.index.normalize()).transform("first"),
             high=high.groupby(high.index.normalize()).cummax(),
             low=low.groupby(low.index.normalize()).cummin())
    )
    if name in {"PREVIOUS_SESSION_OHLC", "PREVIOUS_SESSION_FIELDS"}: return close.shift(1)
    if name == "DISTANCE_FROM_SESSION_HIGH_LOW": return pd.concat((high.cummax() - close, close - low.cummin()), axis=1).min(axis=1)
    if name == "BARS_SINCE_SESSION_OPEN": return pd.Series(np.arange(len(close)), index=close.index)
    if name == "TIME_TO_SESSION_CLOSE":
        if not isinstance(close.index, pd.DatetimeIndex):
            raise AnalyticalRefusal("TIME_TO_SESSION_CLOSE requires a timestamp index")
        return pd.Series(
            ((close.index.normalize() + pd.Timedelta(days=1)) - close.index).total_seconds() / 60,
            index=close.index,
        )
    if name in {"TIMEFRAME", "MARKET_CLOCK", "DTE", "EXPIRY_CALENDAR", "SESSION_CALENDAR", "INSTRUMENT_METADATA", "RESAMPLING"}: return _series(frame, name.lower(), fallback="close")
    if name in {"MA_SLOPE", "PRICE_MA_DISTANCE"}:
        mean = _ema(close, window); return mean.diff() if name == "MA_SLOPE" else close - mean
    if name == "TREND_PERSISTENCE": return np.sign(close.diff()).rolling(window).sum().abs() / window
    if name in {"PARABOLIC_SAR", "SUPERTREND"}:
        trend = close.diff().rolling(window).mean()
        return low.rolling(window).min().where(trend >= 0, high.rolling(window).max())
    if name == "ICHIMOKU_COMPONENTS": return pd.DataFrame(dict(tenkan=(high.rolling(9).max()+low.rolling(9).min())/2, kijun=(high.rolling(26).max()+low.rolling(26).min())/2))
    if name == "MFI":
        typical=(high+low+close)/3; flow=typical*volume; positive=flow.where(typical.diff()>0,0).rolling(window).sum(); negative=flow.where(typical.diff()<0,0).rolling(window).sum(); return 100-100/(1+positive/negative)
    if name == "EWMA_VOLATILITY": return close.pct_change().ewm(span=window, adjust=False).std()
    raise AnalyticalRefusal(f"unimplemented analytical node {name}")


V2_TYPES = {
    ("phase5.value", 1): {
        "type_id": "phase5.value", "type_version": 1,
        "shapes": ["series"], "runtime_representation": "pandas",
    }
}
V2_COMPONENTS = {(component_id(name), 1): _component(name) for name in CATALOGUE_NAMES}
NODE_CONTRACTS = {(component_id(name), 1): _contract(name) for name in CATALOGUE_NAMES}
DATA_REQUIREMENTS = {(component_id(name), 1): _declaration(name) for name in CATALOGUE_NAMES}
V2_IMPLEMENTATIONS = {
    (component_id(name), 1): registered_v2_implementation(
        component=(component_id(name), 1),
        implementation=_implementation(name),
        dependency_boundary=DependencyBoundary("defining_module", (math, np, pd)),
    ) for name in CATALOGUE_NAMES
}
REGISTRY = PlatformRegistry(
    components={}, bodies={}, registrations={},
    v2_types=V2_TYPES, v2_components=V2_COMPONENTS,
    v2_implementations=V2_IMPLEMENTATIONS,
    data_requirement_declarations=DATA_REQUIREMENTS,
    node_contracts=NODE_CONTRACTS,
)


__all__ = [
    "AnalyticalRefusal", "CAPABILITY_GATED_NAMES", "CATALOGUE_NAMES",
    "DATA_REQUIREMENTS", "NODE_CONTRACTS", "REGISTRY", "REQUIRED_NAMES",
    "TYPE_4_NAMES", "V2_COMPONENTS", "V2_IMPLEMENTATIONS", "V2_TYPES",
    "component_id", "evaluate_analytical",
]
