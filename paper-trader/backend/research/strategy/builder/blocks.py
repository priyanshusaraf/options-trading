"""The primitive block library — the entire vocabulary a generated strategy may use.

Each block is a pure function `(df, *numeric_params) -> pd.Series[bool]`, indexed like
`df`. The math mirrors the conventions of the hand-written strategies
(`app/strategy/signals.py`): EMA via `ewm(adjust=False)`, POPULATION stdev
(`std(ddof=0)`), Wilder ATR. Every block is warmup-safe by construction: rolling
windows produce NaN during warmup, and a comparison against NaN yields **False** (a
clean bool), never a NaN and never a spurious True — so `&`/`|` composition can never
leak a phantom signal.

`BLOCKS` is the name→spec registry. The builder references blocks ONLY by these names
with bounded numeric args; it never writes indicator math, so a generated strategy is
auditable down to this vetted file. Adding a block here (with a test) widens the
grammar; nothing else needs to change.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable

import numpy as np
import pandas as pd


# ── indicator helpers (shared, pure) ─────────────────────────────────────────
def _ema(close: pd.Series, length: int) -> pd.Series:
    return close.ewm(span=length, adjust=False).mean()


def _zscore(close: pd.Series, length: int) -> pd.Series:
    """(close − EMA) ÷ population stdev; 0 where stdev is undefined/zero (warmup)."""
    ema = _ema(close, length)
    std = close.rolling(length).std(ddof=0)
    z = np.where(std.to_numpy() > 0, (close - ema) / std, 0.0)
    return pd.Series(z, index=close.index)


def _atr(df: pd.DataFrame, length: int) -> pd.Series:
    """Wilder's ATR (ewm alpha=1/length, adjust=False) of the true range."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def _b(series) -> pd.Series:
    """Coerce a comparison result to a clean df-indexed bool Series (NaN → False)."""
    return pd.Series(series).fillna(False).astype(bool)


# ── trend ────────────────────────────────────────────────────────────────────
def ema_slope_up(df, length, lookback):
    ema = _ema(df["close"], length)
    return _b(ema > ema.shift(lookback))


def ema_slope_down(df, length, lookback):
    ema = _ema(df["close"], length)
    return _b(ema < ema.shift(lookback))


def price_above_ema(df, length):
    return _b(df["close"] > _ema(df["close"], length))


def price_below_ema(df, length):
    return _b(df["close"] < _ema(df["close"], length))


# ── momentum ─────────────────────────────────────────────────────────────────
def zscore_gt(df, length, thr):
    return _b(_zscore(df["close"], length) > thr)


def zscore_lt(df, length, thr):
    return _b(_zscore(df["close"], length) < thr)


def zscore_cross_up(df, length, thr):
    z = _zscore(df["close"], length)
    return _b((z.shift(1) < thr) & (z > thr))


def zscore_cross_down(df, length, thr):
    z = _zscore(df["close"], length)
    return _b((z.shift(1) > -thr) & (z < -thr))


def roc_gt(df, length, thr):
    roc = df["close"].pct_change(length)
    return _b(roc > thr)


def roc_lt(df, length, thr):
    roc = df["close"].pct_change(length)
    return _b(roc < thr)


# ── volatility (quality / quiet-bar gates) ───────────────────────────────────
def atr_pct_lt(df, length, max_pct):
    atr_pct = (_atr(df, length) / df["close"]) * 100.0
    return _b(atr_pct < max_pct)


def range_atr_lt(df, length, mult):
    return _b((df["high"] - df["low"]) < mult * _atr(df, length))


# ── confirmation ─────────────────────────────────────────────────────────────
def still_expanding_z(df, length):
    z = _zscore(df["close"], length).abs()
    return _b(z > z.shift(1))


# ── registry ─────────────────────────────────────────────────────────────────
@dataclasses.dataclass(frozen=True)
class BlockSpec:
    fn: Callable
    params: tuple          # ((name, kind), ...) kind ∈ {length, thr, pct, mult}
    warmup: Callable       # (args) -> int  bars needed before the block is meaningful
    sample_args: tuple     # a representative valid arg tuple (tests + search seeds)
    group: str             # trend | momentum | volatility | confirmation


def _len_plus(extra=0):
    return lambda args: int(args[0]) + extra


BLOCKS: dict[str, BlockSpec] = {
    "ema_slope_up":     BlockSpec(ema_slope_up, (("length", "length"), ("lookback", "length")),
                                  lambda a: int(a[0]) + int(a[1]), (50, 5), "trend"),
    "ema_slope_down":   BlockSpec(ema_slope_down, (("length", "length"), ("lookback", "length")),
                                  lambda a: int(a[0]) + int(a[1]), (50, 5), "trend"),
    "price_above_ema":  BlockSpec(price_above_ema, (("length", "length"),),
                                  _len_plus(), (50,), "trend"),
    "price_below_ema":  BlockSpec(price_below_ema, (("length", "length"),),
                                  _len_plus(), (50,), "trend"),
    "zscore_gt":        BlockSpec(zscore_gt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (50, 0.0), "momentum"),
    "zscore_lt":        BlockSpec(zscore_lt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (50, 0.0), "momentum"),
    "zscore_cross_up":  BlockSpec(zscore_cross_up, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (50, 1.0), "momentum"),
    "zscore_cross_down": BlockSpec(zscore_cross_down, (("length", "length"), ("thr", "thr")),
                                   _len_plus(1), (50, 1.0), "momentum"),
    "roc_gt":           BlockSpec(roc_gt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (10, 0.0), "momentum"),
    "roc_lt":           BlockSpec(roc_lt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (10, 0.0), "momentum"),
    "atr_pct_lt":       BlockSpec(atr_pct_lt, (("length", "length"), ("max_pct", "pct")),
                                  _len_plus(), (14, 5.0), "volatility"),
    "range_atr_lt":     BlockSpec(range_atr_lt, (("length", "length"), ("mult", "mult")),
                                  _len_plus(), (14, 2.5), "volatility"),
    "still_expanding_z": BlockSpec(still_expanding_z, (("length", "length"),),
                                   _len_plus(1), (50,), "confirmation"),
}


def block_names() -> frozenset:
    """The whitelist of callable names an emitted `compute` may reference."""
    return frozenset(BLOCKS)
