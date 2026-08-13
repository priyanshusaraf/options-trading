"""App-owned primitive vocabulary for generated strategies.

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
import bisect
import inspect
import warnings
from collections.abc import Callable
from typing import Any, Mapping

import numpy as np
import pandas as pd

from app.ir.authoring import AuthoredComponent, component, parameter, socket, wire
from app.ir.causal import (
    BlockCausalDisposition,
    BoundTerm,
    HistoryBound,
    RecursiveStateContract,
    causal_contract,
)
from app.ir.registry import DependencyBoundary, registered_kernel
from app.ir.resolve import Library


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


# ── formula-level variation (Phase 2) ────────────────────────────────────────
# Price source and smoothing kind as PARAMETERS rather than hard-coded choices —
# the owner's "modified-RSI" ask generalised into a family of lawful variants.
#
# Encoded as bounded INTEGER codes, not strings, and that is load-bearing: the
# emitted `compute` is AST-validated against numeric literals only
# (`validate.py:53-54` rejects anything that is not an int/float). A string
# parameter would have meant opening that perimeter. A small integer keeps the
# whole safety argument intact.
#
# Code 0 is the pre-existing behaviour in both families (close, sma) so adding a
# parameter never silently re-tunes a composition that already exists.
PRICE_SOURCES = ("close", "hl2", "hlc3", "ohlc4")
SMOOTHINGS = ("sma", "ema", "wilder", "hull")


def _clamp_code(code, n: int) -> int:
    """Codes CLAMP rather than raise. A generated composition must never be able
    to crash the nightly on an arithmetic accident; out of range simply means the
    nearest lawful variant."""
    try:
        c = int(code)
    except (TypeError, ValueError):
        return 0
    return 0 if c < 0 else (n - 1 if c >= n else c)


def _source(df, code) -> pd.Series:
    """The price series a block measures: close | hl2 | hlc3 | ohlc4."""
    kind = PRICE_SOURCES[_clamp_code(code, len(PRICE_SOURCES))]
    if kind == "hl2":
        return (df["high"] + df["low"]) / 2.0
    if kind == "hlc3":
        return (df["high"] + df["low"] + df["close"]) / 3.0
    if kind == "ohlc4":
        return (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    return df["close"]


def _smooth(s: pd.Series, length: int, code) -> pd.Series:
    """Smoothing kind: sma | ema | wilder | hull.

    `ema` deliberately routes through `_ema` so the generated family agrees with
    the hand-written strategies' convention (ewm adjust=False) instead of
    inventing a second one.
    """
    kind = SMOOTHINGS[_clamp_code(code, len(SMOOTHINGS))]
    n = max(2, int(length))
    if kind == "ema":
        return _ema(s, n)
    if kind == "wilder":
        return s.ewm(alpha=1.0 / n, adjust=False).mean()
    if kind == "hull":
        half = max(1, n // 2)
        root = max(1, int(round(n ** 0.5)))
        raw = 2.0 * s.rolling(half).mean() - s.rolling(n).mean()
        return raw.rolling(root).mean()
    return s.rolling(n).mean()


def _rsi(df, length, source, smooth) -> pd.Series:
    """RSI over a chosen price source, with a chosen averaging kind.

    Wilder's RSI is the `smooth=wilder` member of this family; the others are the
    same formula with a different average, which is exactly the generalisation
    asked for."""
    src = _source(df, source)
    n = max(2, int(length))
    delta = src.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Floor the averages at zero. Gains and losses are non-negative BY
    # DEFINITION, so their average must be — but Hull smoothing
    # (2*MA(n/2) - MA(n)) can overshoot below zero, which drove RSI to -22 in
    # testing. That is an artifact of the smoother, not a reading, and an RSI
    # outside [0,100] would silently corrupt every threshold comparison built on
    # it. Clamping restores the domain rather than excluding hull from the family.
    avg_gain = _smooth(gain, n, smooth).clip(lower=0.0)
    avg_loss = _smooth(loss, n, smooth).clip(lower=0.0)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss == 0 with real gains is a maximal-strength reading, not a NaN.
    return rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)


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
# ── RSI family (formula-level variants) ──────────────────────────────────────
def rsi_gt(df, length, thr, source, smooth):
    return _b(_rsi(df, length, source, smooth) > thr)


def rsi_lt(df, length, thr, source, smooth):
    return _b(_rsi(df, length, source, smooth) < thr)


# ── volume ───────────────────────────────────────────────────────────────────
def volume_surge(df, length, mult):
    """Volume above `mult` x its rolling mean.

    A feed with no volume column reads as NO SURGE. Absent data must never
    manufacture an entry — the failure has to be silence, not a signal."""
    if "volume" not in df.columns:
        return pd.Series(False, index=df.index)
    vol = pd.to_numeric(df["volume"], errors="coerce")
    return _b(vol > (vol.rolling(max(2, int(length))).mean() * float(mult)))


# ── gaps ─────────────────────────────────────────────────────────────────────
def gap_up_pct(df, min_pct):
    prev = df["close"].shift(1)
    return _b(((df["open"] - prev) / prev * 100.0) > float(min_pct))


def gap_down_pct(df, min_pct):
    prev = df["close"].shift(1)
    return _b(((prev - df["open"]) / prev * 100.0) > float(min_pct))


# ── candle structure ─────────────────────────────────────────────────────────
def body_frac_gt(df, frac):
    """Body as a fraction of the bar's full range — a decisiveness filter. A
    zero-range bar has no body fraction and reads False."""
    rng = (df["high"] - df["low"])
    body = (df["close"] - df["open"]).abs()
    return _b((rng > 0) & ((body / rng.where(rng > 0)) > float(frac)))


# ── session awareness (Phase 2) ──────────────────────────────────────────────
# Every other block in this file is pure bar math and can be correct over a frame
# of anonymous OHLC rows. These two cannot: they need to know where a trading
# SESSION begins and what time of day a bar sits at.
#
# Both read the wall clock recorded ON THE BAR (`df["date"]`) and never call a
# clock function. That is deliberate and load-bearing: the 2026-08-01 timezone
# audit found a live stop that would have stopped firing on a rebuilt UTC droplet
# because one path fell back to naive host-local time. A time-of-day filter is
# exactly the shape of code that invites the same bug, so it is written to be
# host-independent by construction rather than by configuration.
#
# Both fail CLOSED. A frame these cannot place in time reads False everywhere,
# never True — a filter that cannot evaluate must narrow the strategy to nothing
# rather than silently removing the condition it was added to impose.


def _false(df) -> pd.Series:
    return pd.Series(False, index=df.index)


def _stamps(df) -> pd.Series | None:
    """The bar timestamps as datetimes, or None if this frame has no usable clock."""
    if "date" not in getattr(df, "columns", ()):
        return None
    col = df["date"]
    # The frame from `candles_to_df` already carries real datetimes, so the normal
    # path does no parsing at all. Only a hand-built frame reaches the fallback.
    if pd.api.types.is_datetime64_any_dtype(col):
        return col
    try:
        with warnings.catch_warnings():
            # An unparseable column is a fail-closed case we handle below, not
            # something to warn the operator about on every bar.
            warnings.simplefilter("ignore")
            ts = pd.to_datetime(col, errors="coerce")
    except (TypeError, ValueError):
        return None
    if ts.isna().all():
        return None
    return ts


def _minute_of_day(ts: pd.Series) -> pd.Series:
    """Minutes since midnight, in the timezone the bar was recorded in.

    `.dt.hour` reads the stamp's own wall clock — for a tz-aware IST stamp that is
    IST, and for a naive one it is whatever the feed wrote, which is IST by this
    project's convention. Neither reading consults the host, which is the point.
    """
    return ts.dt.hour * 60 + ts.dt.minute


def time_of_day(df, start_min, end_min):
    """True on bars inside [start_min, end_min) minutes past midnight.

    Half-open on purpose: two windows meeting at the same minute partition the
    bars instead of both claiming the boundary. Overlapping there would make
    `all(window_a, window_b)` satisfiable for two windows meant to be disjoint.

    An inverted or empty window (`end <= start`) selects NOTHING. It is not a wrap
    around midnight — no Indian session does that — it is a nonsensical window, and
    a nonsensical filter must exclude everything rather than include everything.
    """
    ts = _stamps(df)
    if ts is None:
        return _false(df)
    start, end = int(start_min), int(end_min)
    if end <= start:
        return _false(df)
    mod = _minute_of_day(ts)
    return _b((mod >= start) & (mod < end))


def _opening_range(df, bars: int):
    """Per session: (range_high, range_low, position_within_session).

    The two range series are broadcast to every bar of their session, which is
    only safe because the caller masks off every bar inside the range window —
    see the note there. `pos` is the bar's 0-based index within its own session
    and is what makes that mask possible.
    """
    ts = _stamps(df)
    if ts is None:
        return None
    day = ts.dt.normalize()
    n = max(2, int(bars))
    g = df.groupby(day, sort=False)
    pos = g.cumcount()
    inside = pos < n
    # `.where(inside)` blanks every bar outside the opening window BEFORE the
    # groupwise max/min, so the range is a function of the first `n` bars alone.
    # Taking a plain groupby max here would fold the entire session — including
    # bars that had not happened yet — into the level the session is measured
    # against, and the resulting backtest would simply look good.
    rng_high = df["high"].where(inside).groupby(day, sort=False).transform("max")
    rng_low = df["low"].where(inside).groupby(day, sort=False).transform("min")
    # A session with fewer than `n` bars never completed its range (a half day, or
    # a truncated feed). Its range is undefined rather than partial.
    # Completion is known from the observed prefix. Looking at the number of
    # later rows in a session would make today's value depend on future bars.
    complete = pos >= n - 1
    return rng_high, rng_low, pos, complete


def opening_range_break_up(df, bars, buffer_pct):
    """Close breaks above the session's opening range by at least `buffer_pct`.

    The range is the HIGH of the first `bars` bars — the extent price actually
    traded over, wicks included. Using closes would draw the range too narrow and
    fire on ordinary noise.

    **No look-ahead:** a bar can only fire once its session index is >= `bars`, so
    every input to a True reading is the current bar or an earlier one. The buffer
    is what separates this from `close > rolling max`: a close a hair above the
    range is noise, not a breakout.
    """
    parts = _opening_range(df, bars)
    if parts is None:
        return _false(df)
    rng_high, _, pos, complete = parts
    n = max(2, int(bars))
    level = rng_high * (1.0 + float(buffer_pct) / 100.0)
    return _b((pos >= n) & complete & (df["close"] > level))


def opening_range_break_down(df, bars, buffer_pct):
    """Close breaks below the session's opening range by at least `buffer_pct`.
    The mirror of `opening_range_break_up`, measured off the range LOW."""
    parts = _opening_range(df, bars)
    if parts is None:
        return _false(df)
    _, rng_low, pos, complete = parts
    n = max(2, int(bars))
    level = rng_low * (1.0 - float(buffer_pct) / 100.0)
    return _b((pos >= n) & complete & (df["close"] < level))


# ── app-owned regime conditioning ────────────────────────────────────────────
TREND_WINDOW = 20
TREND_CUTOFF = 0.35
VOL_WINDOW = 20
VOL_LOOKBACK = 200
REGIMES = ("trend_hi", "trend_lo", "chop_hi", "chop_lo")
UNKNOWN = "unknown"


def efficiency_ratio(close: pd.Series, window: int = TREND_WINDOW) -> pd.Series:
    net = (close - close.shift(window)).abs()
    path = close.diff().abs().rolling(window).sum()
    return net / path.replace(0.0, np.nan)


def atr_pct(df: pd.DataFrame, window: int = VOL_WINDOW) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev).abs(), (low - prev).abs()], axis=1
    ).max(axis=1)
    return (tr.rolling(window).mean() / close.replace(0.0, np.nan)) * 100.0


def label_regimes(df: pd.DataFrame, *, trend_window: int = TREND_WINDOW,
                  trend_cutoff: float = TREND_CUTOFF,
                  vol_window: int = VOL_WINDOW,
                  vol_lookback: int = VOL_LOOKBACK) -> pd.Series:
    if df is None or len(df) == 0:
        return pd.Series(dtype=object)
    er = efficiency_ratio(df["close"], trend_window)
    vol = atr_pct(df, vol_window)
    med = vol.expanding(min_periods=max(2, vol_lookback // 10)).median()
    trending = er >= trend_cutoff
    high_vol = vol >= med
    known = er.notna() & vol.notna() & med.notna()
    out = np.where(
        trending,
        np.where(high_vol, "trend_hi", "trend_lo"),
        np.where(high_vol, "chop_hi", "chop_lo"),
    )
    return pd.Series(np.where(known, out, UNKNOWN), index=df.index, dtype=object)


def regime_is(df, code):
    """True on bars sitting in the selected market regime.

    `code` indexes `research.regime.REGIMES` (trend_hi | trend_lo | chop_hi |
    chop_lo) and clamps like every other choice parameter, so a generated
    composition can say "only trade this idea in high-volatility trends".

    The labels are computed from backward-looking windows only (see
    `research/regime.py`), so conditioning on regime cannot leak the future. That
    property is what makes this block admissible at all — a regime label built
    with hindsight would leak invisibly, since the leak would live in the
    labelling rather than in any strategy.
    """
    kind = REGIMES[_clamp_code(code, len(REGIMES))]
    if not {"high", "low", "close"} <= set(getattr(df, "columns", ())):
        return pd.Series(False, index=getattr(df, "index", None))
    return _b(label_regimes(df) == kind)


@dataclasses.dataclass(frozen=True)
class BlockSpec:
    fn: Callable
    params: tuple          # ((name, kind), ...) kind ∈ {length, thr, pct, mult}
    warmup: Callable       # (args) -> int  bars needed before the block is meaningful
    sample_args: tuple     # a representative valid arg tuple (tests + search seeds)
    group: str             # trend | momentum | volatility | confirmation
    # F4: declared, never inferred. `inputs` names the OHLCV columns this block
    # reads. `needs_clock` says it also reads bar timestamps, which are the
    # series index rather than a value, so they are not an IR socket.
    inputs: tuple = ("open", "high", "low", "close", "volume")
    needs_clock: bool = False
    history: HistoryBound = HistoryBound("bounded")

    @property
    def context_inputs(self) -> tuple[str, ...]:
        return ("bar_timestamp",) if self.needs_clock else ()


def _len_plus(extra=0):
    return lambda args: int(args[0]) + extra


BLOCKS: dict[str, BlockSpec] = {
    "ema_slope_up":     BlockSpec(ema_slope_up, (("length", "length"), ("lookback", "length")),
                                  lambda a: int(a[0]) + int(a[1]), (50, 5), "trend", inputs=("close",)),
    "ema_slope_down":   BlockSpec(ema_slope_down, (("length", "length"), ("lookback", "length")),
                                  lambda a: int(a[0]) + int(a[1]), (50, 5), "trend", inputs=("close",)),
    "price_above_ema":  BlockSpec(price_above_ema, (("length", "length"),),
                                  _len_plus(), (50,), "trend", inputs=("close",)),
    "price_below_ema":  BlockSpec(price_below_ema, (("length", "length"),),
                                  _len_plus(), (50,), "trend", inputs=("close",)),
    "zscore_gt":        BlockSpec(zscore_gt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (50, 0.0), "momentum", inputs=("close",)),
    "zscore_lt":        BlockSpec(zscore_lt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (50, 0.0), "momentum", inputs=("close",)),
    "zscore_cross_up":  BlockSpec(zscore_cross_up, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (50, 1.0), "momentum", inputs=("close",)),
    "zscore_cross_down": BlockSpec(zscore_cross_down, (("length", "length"), ("thr", "thr")),
                                   _len_plus(1), (50, 1.0), "momentum", inputs=("close",)),
    "roc_gt":           BlockSpec(roc_gt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (10, 0.0), "momentum", inputs=("close",)),
    "roc_lt":           BlockSpec(roc_lt, (("length", "length"), ("thr", "thr")),
                                  _len_plus(1), (10, 0.0), "momentum", inputs=("close",)),
    "atr_pct_lt":       BlockSpec(atr_pct_lt, (("length", "length"), ("max_pct", "pct")),
                                  _len_plus(), (14, 5.0), "volatility", inputs=("high", "low", "close")),
    "range_atr_lt":     BlockSpec(range_atr_lt, (("length", "length"), ("mult", "mult")),
                                  _len_plus(), (14, 2.5), "volatility", inputs=("high", "low", "close")),
    "still_expanding_z": BlockSpec(still_expanding_z, (("length", "length"),),
                                   _len_plus(1), (50,), "confirmation", inputs=("close",)),
    # Phase 2 — formula-level variants. `source`/`smooth` are bounded integer
    # CHOICE codes (see PRICE_SOURCES / SMOOTHINGS); code 0 is the conventional
    # reading, so the sample args describe a plain close-based Wilder-ish RSI.
    # NB: the RSI threshold is a "pct", not a "thr". `thr` is bounded to |x|<=10
    # because it was built for z-scores; RSI reads 0-100, so a 70 threshold is
    # perfectly lawful and would have been rejected by the wrong bound.
    "rsi_gt":           BlockSpec(rsi_gt, (("length", "length"), ("thr", "pct"),
                                           ("source", "choice"), ("smooth", "choice")),
                                  _len_plus(1), (14, 55.0, 0, 2), "momentum", inputs=("open", "high", "low", "close")),
    "rsi_lt":           BlockSpec(rsi_lt, (("length", "length"), ("thr", "pct"),
                                           ("source", "choice"), ("smooth", "choice")),
                                  _len_plus(1), (14, 45.0, 0, 2), "momentum", inputs=("open", "high", "low", "close")),
    "volume_surge":     BlockSpec(volume_surge, (("length", "length"), ("mult", "mult")),
                                  _len_plus(), (20, 1.5), "confirmation", inputs=("volume",)),
    "gap_up_pct":       BlockSpec(gap_up_pct, (("min_pct", "pct"),),
                                  lambda a: 2, (0.5,), "momentum", inputs=("open", "close")),
    "gap_down_pct":     BlockSpec(gap_down_pct, (("min_pct", "pct"),),
                                  lambda a: 2, (0.5,), "momentum", inputs=("open", "close")),
    "body_frac_gt":     BlockSpec(body_frac_gt, (("frac", "pct"),),
                                  lambda a: 0, (0.5,), "confirmation", inputs=("open", "high", "low", "close")),
    # Phase 2 — session awareness. Warmup is session-local (the opening range is
    # rebuilt every day), so it is `bars`, not a multi-day history. `time_of_day`
    # needs no history at all: a bar knows its own clock.
    "time_of_day":      BlockSpec(time_of_day, (("start_min", "minute"),
                                                ("end_min", "minute")),
                                  lambda a: 0, (555, 690), "confirmation", inputs=("close",), needs_clock=True),
    "opening_range_break_up": BlockSpec(
        opening_range_break_up, (("bars", "length"), ("buffer_pct", "pct")),
        _len_plus(), (4, 0.1), "momentum", inputs=("high", "low", "close"), needs_clock=True),
    "opening_range_break_down": BlockSpec(
        opening_range_break_down, (("bars", "length"), ("buffer_pct", "pct")),
        _len_plus(), (4, 0.1), "momentum", inputs=("high", "low", "close"), needs_clock=True),
    # Phase 5 — regime conditioning. Warmup mirrors the labeller's own windows.
    "regime_is":        BlockSpec(regime_is, (("code", "choice"),),
                                  lambda a: 220, (0,), "confirmation", inputs=("open", "high", "low", "close")),
}


def block_names() -> frozenset:
    """The whitelist of callable names an emitted `compute` may reference."""
    return frozenset(BLOCKS)


# ── closed causal declarations ───────────────────────────────────────────────
_HISTORIES = {
    "ema_slope_up": HistoryBound("causal_recursive", terms=(BoundTerm("length"), BoundTerm("lookback"))),
    "ema_slope_down": HistoryBound("causal_recursive", terms=(BoundTerm("length"), BoundTerm("lookback"))),
    "price_above_ema": HistoryBound("causal_recursive", terms=(BoundTerm("length"),)),
    "price_below_ema": HistoryBound("causal_recursive", terms=(BoundTerm("length"),)),
    "zscore_gt": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "zscore_lt": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "zscore_cross_up": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "zscore_cross_down": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "roc_gt": HistoryBound("bounded", constant=1, terms=(BoundTerm("length"),)),
    "roc_lt": HistoryBound("bounded", constant=1, terms=(BoundTerm("length"),)),
    "atr_pct_lt": HistoryBound("causal_recursive", terms=(BoundTerm("length"),)),
    "range_atr_lt": HistoryBound("causal_recursive", terms=(BoundTerm("length"),)),
    "still_expanding_z": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "rsi_gt": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "rsi_lt": HistoryBound("causal_recursive", constant=1, terms=(BoundTerm("length"),)),
    "volume_surge": HistoryBound("bounded", terms=(BoundTerm("length"),)),
    "gap_up_pct": HistoryBound("bounded", constant=2),
    "gap_down_pct": HistoryBound("bounded", constant=2),
    "body_frac_gt": HistoryBound("bounded", constant=1),
    "time_of_day": HistoryBound("bounded"),
    "opening_range_break_up": HistoryBound("causal_recursive", terms=(BoundTerm("bars"),)),
    "opening_range_break_down": HistoryBound("causal_recursive", terms=(BoundTerm("bars"),)),
    "regime_is": HistoryBound("causal_recursive", constant=220),
}

for _name, _spec in tuple(BLOCKS.items()):
    BLOCKS[_name] = dataclasses.replace(_spec, history=_HISTORIES[_name])


def _json_state(state):
    def closed(value):
        if dataclasses.is_dataclass(value):
            return {field.name: closed(getattr(value, field.name))
                    for field in dataclasses.fields(value)}
        if isinstance(value, tuple):
            return [closed(item) for item in value]
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            return {"nonfinite": "nan" if np.isnan(value) else
                    ("positive_infinity" if value > 0 else "negative_infinity")}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f"state contains unsupported {type(value).__name__}")
    return closed(state)


def _mean(values):
    return sum(values) / len(values)


def _ema_next(prior, value, alpha):
    if pd.isna(value):
        return prior
    return float(value) if prior is None else alpha * float(value) + (1.0 - alpha) * prior


def _ewm_next(prior, old_weight, value, alpha):
    """One pandas adjust=False, ignore_na=False transition."""
    if prior is None:
        return ((None, old_weight) if pd.isna(value) else (float(value), 1.0))
    decayed = old_weight * (1.0 - alpha)
    if pd.isna(value):
        return prior, decayed
    if alpha == 0.5 and old_weight < 1.0:
        effective = 1.0 - old_weight * (1.0 - alpha)
        combined = prior + effective * (float(value) - prior)
    else:
        combined = (decayed * prior + alpha * float(value)) / (decayed + alpha)
    return combined, 1.0


@dataclasses.dataclass(frozen=True)
class EmaState:
    ema: float | None = None
    old_weight: float = 1.0
    history: tuple[float, ...] = ()


def _ema_init(params):
    return EmaState()


def _ema_update(state, params, node_inputs, context_inputs):
    length = max(1, int(params["length"]))
    ema, old_weight = _ewm_next(
        state.ema, state.old_weight, node_inputs["close"], 2.0 / (length + 1.0))
    keep = max(1, int(params.get("lookback", 0)) + 1)
    history = (state.history + (ema,))[-keep:]
    return EmaState(ema, old_weight, history)


def _ema_step(direction, slope=False):
    def step(state, params, node_inputs, context_inputs):
        if slope:
            lookback = int(params["lookback"])
            if len(state.history) <= lookback:
                value = False
            elif state.ema is None or state.history[-lookback - 1] is None:
                value = False
            else:
                prior = state.history[-lookback - 1]
                value = state.ema > prior if direction == "up" else state.ema < prior
        else:
            close = float(node_inputs["close"])
            value = False if state.ema is None or not np.isfinite(close) else (
                close > state.ema if direction == "up" else close < state.ema)
        return {"out": bool(value)}
    return step


@dataclasses.dataclass(frozen=True)
class ZState:
    ema: float | None = None
    old_weight: float = 1.0
    closes: tuple[float, ...] = ()
    prior_z: float | None = None
    z: float = 0.0


def _z_init(params):
    return ZState()


def _z_update(state, params, node_inputs, context_inputs):
    length = max(1, int(params["length"]))
    close = float(node_inputs["close"])
    ema, old_weight = _ewm_next(
        state.ema, state.old_weight, close, 2.0 / (length + 1.0))
    closes = (state.closes + (close,))[-length:]
    z = 0.0
    if len(closes) == length:
        mean = _mean(closes)
        std = (_mean(tuple((value - mean) ** 2 for value in closes))) ** 0.5
        if std > 0:
            z = (close - ema) / std
    return ZState(ema, old_weight, closes, state.z if state.ema is not None else None, z)


def _z_step(kind):
    def step(state, params, node_inputs, context_inputs):
        threshold = float(params.get("thr", 0.0))
        if kind == "gt":
            value = state.z > threshold
        elif kind == "lt":
            value = state.z < threshold
        elif kind == "cross_up":
            value = state.prior_z is not None and state.prior_z < threshold and state.z > threshold
        elif kind == "cross_down":
            value = state.prior_z is not None and state.prior_z > -threshold and state.z < -threshold
        else:
            value = state.prior_z is not None and abs(state.z) > abs(state.prior_z)
        return {"out": bool(value)}
    return step


@dataclasses.dataclass(frozen=True)
class AtrState:
    previous_close: float | None = None
    atr: float | None = None
    old_weight: float = 1.0


def _atr_init(params):
    return AtrState()


def _atr_update(state, params, node_inputs, context_inputs):
    high, low, close = (float(node_inputs[name]) for name in ("high", "low", "close"))
    candidates = [abs(high - low)] if np.isfinite(high) and np.isfinite(low) else []
    if state.previous_close is not None:
        if np.isfinite(high):
            candidates.append(abs(high - state.previous_close))
        if np.isfinite(low):
            candidates.append(abs(low - state.previous_close))
    tr = max(candidates) if candidates else float("nan")
    atr, old_weight = _ewm_next(
        state.atr, state.old_weight, tr, 1.0 / max(1, int(params["length"])))
    return AtrState(close if np.isfinite(close) else None, atr, old_weight)


def _atr_step(kind):
    def step(state, params, node_inputs, context_inputs):
        if state.atr is None:
            return {"out": False}
        if kind == "pct":
            value = state.atr / float(node_inputs["close"]) * 100.0 < float(params["max_pct"])
        else:
            value = float(node_inputs["high"]) - float(node_inputs["low"]) \
                < float(params["mult"]) * state.atr
        return {"out": bool(value)}
    return step


@dataclasses.dataclass(frozen=True)
class RsiState:
    previous_source: float | None = None
    average_gain: float | None = None
    average_loss: float | None = None
    gain_weight: float = 1.0
    loss_weight: float = 1.0
    gains: tuple[float, ...] = ()
    losses: tuple[float, ...] = ()
    raw_gains: tuple[float, ...] = ()
    raw_losses: tuple[float, ...] = ()
    rsi: float | None = None


def _rsi_init(params):
    return RsiState()


def _scalar_source(node_inputs, code):
    kind = PRICE_SOURCES[_clamp_code(code, len(PRICE_SOURCES))]
    if kind == "hl2":
        return (float(node_inputs["high"]) + float(node_inputs["low"])) / 2.0
    if kind == "hlc3":
        return (float(node_inputs["high"]) + float(node_inputs["low"])
                + float(node_inputs["close"])) / 3.0
    if kind == "ohlc4":
        return sum(float(node_inputs[name]) for name in ("open", "high", "low", "close")) / 4.0
    return float(node_inputs["close"])


def _rsi_update(state, params, node_inputs, context_inputs):
    source = _scalar_source(node_inputs, params["source"])
    if state.previous_source is None:
        return dataclasses.replace(state, previous_source=source)
    delta = source - state.previous_source if np.isfinite(state.previous_source) else float("nan")
    gain, loss = max(delta, 0.0), max(-delta, 0.0)
    n = max(2, int(params["length"]))
    kind = SMOOTHINGS[_clamp_code(params["smooth"], len(SMOOTHINGS))]
    if not np.isfinite(source):
        gain = loss = float("nan")
    gains, losses = (state.gains + (gain,))[-n:], (state.losses + (loss,))[-n:]
    raw_gains, raw_losses = state.raw_gains, state.raw_losses
    avg_gain, avg_loss = state.average_gain, state.average_loss
    gain_weight, loss_weight = state.gain_weight, state.loss_weight
    if kind == "sma":
        avg_gain = _mean(gains) if len(gains) == n and all(np.isfinite(gains)) else None
        avg_loss = _mean(losses) if len(losses) == n and all(np.isfinite(losses)) else None
    elif kind in ("ema", "wilder"):
        alpha = 2.0 / (n + 1.0) if kind == "ema" else 1.0 / n
        avg_gain, gain_weight = _ewm_next(avg_gain, gain_weight, gain, alpha)
        avg_loss, loss_weight = _ewm_next(avg_loss, loss_weight, loss, alpha)
    else:
        half, root = max(1, n // 2), max(1, int(round(n ** 0.5)))
        if len(gains) == n:
            raw_gains = (raw_gains + (2.0 * _mean(gains[-half:]) - _mean(gains),))[-root:]
            raw_losses = (raw_losses + (2.0 * _mean(losses[-half:]) - _mean(losses),))[-root:]
        avg_gain = _mean(raw_gains) if len(raw_gains) == root else None
        avg_loss = _mean(raw_losses) if len(raw_losses) == root else None
    rsi = None
    if avg_gain is not None and avg_loss is not None:
        avg_gain, avg_loss = max(avg_gain, 0.0), max(avg_loss, 0.0)
        if avg_loss == 0.0:
            rsi = 100.0 if avg_gain > 0 else None
        else:
            ratio = avg_gain / avg_loss
            rsi = 100.0 - 100.0 / (1.0 + ratio)
    return RsiState(source, avg_gain, avg_loss, gain_weight, loss_weight, gains, losses,
                    raw_gains, raw_losses, rsi)


def _rsi_step(direction):
    def step(state, params, node_inputs, context_inputs):
        value = False if state.rsi is None else (
            state.rsi > float(params["thr"]) if direction == "gt"
            else state.rsi < float(params["thr"]))
        return {"out": bool(value)}
    return step


@dataclasses.dataclass(frozen=True)
class OpeningRangeState:
    session_date: str | None = None
    position: int = -1
    range_high: float | None = None
    range_low: float | None = None


def _opening_init(params):
    return OpeningRangeState()


def _opening_update(state, params, node_inputs, context_inputs):
    timestamp = context_inputs["bar_timestamp"]
    if not isinstance(timestamp, pd.Timestamp) or timestamp.tz is None:
        raise ValueError("bar_timestamp must be a timezone-aware recorded timestamp")
    day = timestamp.normalize().isoformat()
    position = state.position + 1 if state.session_date == day else 0
    high = state.range_high if state.session_date == day else None
    low = state.range_low if state.session_date == day else None
    if position < max(2, int(params["bars"])):
        current_high, current_low = float(node_inputs["high"]), float(node_inputs["low"])
        if np.isfinite(current_high):
            high = current_high if high is None else max(high, current_high)
        if np.isfinite(current_low):
            low = current_low if low is None else min(low, current_low)
    return OpeningRangeState(day, position, high, low)


def _opening_step(direction):
    def step(state, params, node_inputs, context_inputs):
        n = max(2, int(params["bars"]))
        if state.position < n or state.range_high is None or state.range_low is None:
            return {"out": False}
        buffer = float(params["buffer_pct"]) / 100.0
        close = float(node_inputs["close"])
        value = close > state.range_high * (1.0 + buffer) if direction == "up" \
            else close < state.range_low * (1.0 - buffer)
        return {"out": bool(value)}
    return step


@dataclasses.dataclass(frozen=True)
class RegimeState:
    closes: tuple[float, ...] = ()
    previous_close: float | None = None
    true_ranges: tuple[float, ...] = ()
    observed_volatility: tuple[float, ...] = ()
    label: str = UNKNOWN


def _regime_init(params):
    return RegimeState()


def _regime_update(state, params, node_inputs, context_inputs):
    close = float(node_inputs["close"])
    high, low = float(node_inputs["high"]), float(node_inputs["low"])
    closes = (state.closes + (close,))[-(TREND_WINDOW + 1):]
    candidates = [abs(high - low)] if np.isfinite(high) and np.isfinite(low) else []
    if state.previous_close is not None:
        if np.isfinite(high):
            candidates.append(abs(high - state.previous_close))
        if np.isfinite(low):
            candidates.append(abs(low - state.previous_close))
    tr = max(candidates) if candidates else float("nan")
    trs = (state.true_ranges + (tr,))[-VOL_WINDOW:]
    er = None
    if len(closes) == TREND_WINDOW + 1:
        path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        er = abs(closes[-1] - closes[0]) / path if path != 0 else None
    vol = _mean(trs) / close * 100.0 if len(trs) == VOL_WINDOW and close != 0 else None
    observed = state.observed_volatility
    if vol is not None and np.isfinite(vol):
        mutable = list(observed)
        bisect.insort(mutable, vol)
        observed = tuple(mutable)
    median = None
    if len(observed) >= max(2, VOL_LOOKBACK // 10):
        middle = len(observed) // 2
        median = observed[middle] if len(observed) % 2 else \
            (observed[middle - 1] + observed[middle]) / 2.0
    label = UNKNOWN
    if er is not None and vol is not None and median is not None:
        label = ("trend_" if er >= TREND_CUTOFF else "chop_") \
            + ("hi" if vol >= median else "lo")
    return RegimeState(closes, close if np.isfinite(close) else None,
                       trs, observed, label)


def _regime_step(state, params, node_inputs, context_inputs):
    selected = REGIMES[_clamp_code(params["code"], len(REGIMES))]
    return {"out": state.label == selected}


def _recursive(initializer, state_type, update, step):
    return RecursiveStateContract(initializer, state_type, _json_state, update, step)


_RECURSIVE_CONTRACTS = {
    "ema_slope_up": _recursive(_ema_init, EmaState, _ema_update, _ema_step("up", True)),
    "ema_slope_down": _recursive(_ema_init, EmaState, _ema_update, _ema_step("down", True)),
    "price_above_ema": _recursive(_ema_init, EmaState, _ema_update, _ema_step("up")),
    "price_below_ema": _recursive(_ema_init, EmaState, _ema_update, _ema_step("down")),
    "zscore_gt": _recursive(_z_init, ZState, _z_update, _z_step("gt")),
    "zscore_lt": _recursive(_z_init, ZState, _z_update, _z_step("lt")),
    "zscore_cross_up": _recursive(_z_init, ZState, _z_update, _z_step("cross_up")),
    "zscore_cross_down": _recursive(_z_init, ZState, _z_update, _z_step("cross_down")),
    "still_expanding_z": _recursive(_z_init, ZState, _z_update, _z_step("expanding")),
    "atr_pct_lt": _recursive(_atr_init, AtrState, _atr_update, _atr_step("pct")),
    "range_atr_lt": _recursive(_atr_init, AtrState, _atr_update, _atr_step("range")),
    "rsi_gt": _recursive(_rsi_init, RsiState, _rsi_update, _rsi_step("gt")),
    "rsi_lt": _recursive(_rsi_init, RsiState, _rsi_update, _rsi_step("lt")),
    "opening_range_break_up": _recursive(
        _opening_init, OpeningRangeState, _opening_update, _opening_step("up")),
    "opening_range_break_down": _recursive(
        _opening_init, OpeningRangeState, _opening_update, _opening_step("down")),
    "regime_is": _recursive(_regime_init, RegimeState, _regime_update, _regime_step),
}


def _contract(name: str):
    spec = BLOCKS[name]
    recursive_state = _RECURSIVE_CONTRACTS.get(name)
    return causal_contract(
        node_input_sockets=tuple(spec.inputs),
        context_inputs=spec.context_inputs,
        history=spec.history,
        recursive_state=recursive_state,
    )


BLOCK_DEPENDENCIES = {
    "ema_slope_up": (ema_slope_up, _ema, _b),
    "ema_slope_down": (ema_slope_down, _ema, _b),
    "price_above_ema": (price_above_ema, _ema, _b),
    "price_below_ema": (price_below_ema, _ema, _b),
    "zscore_gt": (zscore_gt, _zscore, _ema, _b),
    "zscore_lt": (zscore_lt, _zscore, _ema, _b),
    "zscore_cross_up": (zscore_cross_up, _zscore, _ema, _b),
    "zscore_cross_down": (zscore_cross_down, _zscore, _ema, _b),
    "roc_gt": (roc_gt, _b),
    "roc_lt": (roc_lt, _b),
    "atr_pct_lt": (atr_pct_lt, _atr, _b),
    "range_atr_lt": (range_atr_lt, _atr, _b),
    "still_expanding_z": (still_expanding_z, _zscore, _ema, _b),
    "rsi_gt": (rsi_gt, _rsi, _source, _smooth, _ema, _clamp_code, _b),
    "rsi_lt": (rsi_lt, _rsi, _source, _smooth, _ema, _clamp_code, _b),
    "volume_surge": (volume_surge, _b),
    "gap_up_pct": (gap_up_pct, _b),
    "gap_down_pct": (gap_down_pct, _b),
    "body_frac_gt": (body_frac_gt, _b),
    "time_of_day": (time_of_day, _stamps, _minute_of_day, _false, _b),
    "opening_range_break_up": (opening_range_break_up, _opening_range, _stamps, _false, _b),
    "opening_range_break_down": (opening_range_break_down, _opening_range, _stamps, _false, _b),
    "regime_is": (regime_is, label_regimes, efficiency_ratio, atr_pct, _clamp_code, _b),
}
# Recursive implementations are part of the callable boundary too. Task 2
# will hash these exact objects rather than discovering them through imports.
for _name, _recursive_contract in _RECURSIVE_CONTRACTS.items():
    BLOCK_DEPENDENCIES[_name] += (
        _recursive_contract.initializer,
        _recursive_contract.state_type,
        _recursive_contract.state_encoder,
        _recursive_contract.update,
        _recursive_contract.step,
    )


def _admitted(name: str) -> BlockCausalDisposition:
    return BlockCausalDisposition.admitted(_contract(name), BLOCK_DEPENDENCIES[name])


CAUSAL_MANIFEST = {
    "ema_slope_up": _admitted("ema_slope_up"),
    "ema_slope_down": _admitted("ema_slope_down"),
    "price_above_ema": _admitted("price_above_ema"),
    "price_below_ema": _admitted("price_below_ema"),
    "zscore_gt": _admitted("zscore_gt"),
    "zscore_lt": _admitted("zscore_lt"),
    "zscore_cross_up": _admitted("zscore_cross_up"),
    "zscore_cross_down": _admitted("zscore_cross_down"),
    "roc_gt": _admitted("roc_gt"),
    "roc_lt": _admitted("roc_lt"),
    "atr_pct_lt": _admitted("atr_pct_lt"),
    "range_atr_lt": _admitted("range_atr_lt"),
    "still_expanding_z": _admitted("still_expanding_z"),
    "rsi_gt": _admitted("rsi_gt"),
    "rsi_lt": _admitted("rsi_lt"),
    "volume_surge": _admitted("volume_surge"),
    "gap_up_pct": _admitted("gap_up_pct"),
    "gap_down_pct": _admitted("gap_down_pct"),
    "body_frac_gt": _admitted("body_frac_gt"),
    "time_of_day": _admitted("time_of_day"),
    "opening_range_break_up": _admitted("opening_range_break_up"),
    "opening_range_break_down": _admitted("opening_range_break_down"),
    "regime_is": _admitted("regime_is"),
}


# ── Component IR adapter owned by the same contributor ──────────────────────
BAR_INPUTS = ("open", "high", "low", "close", "volume")
DOMAIN = {"instrument": "*", "timeframe": "*"}


def _adapter(fn: Callable, order: tuple[str, ...], fields: tuple[str, ...],
             needs_clock: bool):
    def kernel(params, node_inputs, context_inputs):
        frame = pd.DataFrame({name: node_inputs[name] for name in fields})
        if needs_clock:
            frame["date"] = context_inputs["bar_timestamp"]
        return {"out": fn(frame, *(params[name] for name in order))}

    return kernel


def derive(name: str, spec: BlockSpec, *, instrument: str = "*",
           timeframe: str = "*") -> AuthoredComponent:
    order = tuple(param_name for param_name, _ in spec.params)
    defaults = dict(zip(order, spec.sample_args))
    bar = wire(instrument=instrument, timeframe=timeframe)
    return component(
        f"block.{name}",
        display_name=name.replace("_", " "),
        interface=[
            *(socket(field, "input", bar) for field in spec.inputs),
            *(parameter(param_name, kind, defaults[param_name])
              for param_name, kind in spec.params),
            socket("out", "output", wire("bool", instrument=instrument,
                                          timeframe=timeframe)),
        ],
        warmup=lambda p, order=order, spec=spec: int(
            spec.warmup(tuple(p[param_name] for param_name in order))),
        causal=CAUSAL_MANIFEST[name].contract,
        closes_over={"block": name, "fn": _block_source(spec),
                     "inputs": list(spec.inputs), "context": list(spec.context_inputs)},
    )(_adapter(spec.fn, order, tuple(spec.inputs), spec.needs_clock))


def _block_source(spec: BlockSpec) -> str:
    import inspect
    import textwrap
    return textwrap.dedent(inspect.getsource(spec.fn))


def derive_all(*, instrument: str = "*", timeframe: str = "*") -> dict[str, AuthoredComponent]:
    return {name: derive(name, spec, instrument=instrument, timeframe=timeframe)
            for name, spec in BLOCKS.items()}


def groups() -> Mapping[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, spec in BLOCKS.items():
        out.setdefault(spec.group, []).append(name)
    return {group: tuple(sorted(names)) for group, names in sorted(out.items())}


BLOCK_COMPONENTS = derive_all()


def _declared_dependencies(*roots: object) -> tuple[object, ...]:
    """Derive executable/module reads; identity independently checks exact equality."""
    found: dict[int, object] = {}
    seen: set[int] = set()

    def visit(value: object) -> None:
        if id(value) in seen:
            return
        seen.add(id(value))
        if inspect.ismodule(value):
            return
        if inspect.isfunction(value):
            closure = inspect.getclosurevars(value)
            for dependency in (*closure.globals.values(), *closure.nonlocals.values()):
                if inspect.ismodule(dependency) or inspect.isfunction(dependency) \
                        or inspect.isclass(dependency):
                    if getattr(dependency, "__module__", None) in {
                            "builtins", "dataclasses"} and inspect.isclass(dependency):
                        continue
                    found[id(dependency)] = dependency
                    visit(dependency)
            return
    for root in roots:
        visit(root)
    for root in roots:
        found.pop(id(root), None)
    return tuple(sorted(found.values(), key=lambda value: (
        getattr(value, "__module__", ""),
        getattr(value, "__qualname__", getattr(value, "__name__", "")),
    )))


def _registration_dependencies(authored: AuthoredComponent,
                               disposition: BlockCausalDisposition) -> tuple[object, ...]:
    recursive = disposition.contract.recursive_state if disposition.contract else None
    roots = [authored.kernel]
    if recursive is not None:
        roots.extend((recursive.initializer, recursive.state_type,
                      recursive.state_encoder, recursive.update, recursive.step))
    dependencies = list(_declared_dependencies(*roots))
    if recursive is not None:
        dependencies.extend((recursive.initializer, recursive.state_type,
                             recursive.state_encoder, recursive.update, recursive.step))
    unique = {id(value): value for value in dependencies}
    return tuple(sorted(unique.values(), key=lambda value: (
        getattr(value, "__module__", ""),
        getattr(value, "__qualname__", getattr(value, "__name__", "")),
    )))


REGISTRATIONS = {
    BLOCK_COMPONENTS[name].body_ref: registered_kernel(
        body_ref=BLOCK_COMPONENTS[name].body_ref,
        implementation=BLOCK_COMPONENTS[name].kernel,
        causal=disposition.contract,
        dependency_boundary=DependencyBoundary(
            "declared_objects",
            _registration_dependencies(BLOCK_COMPONENTS[name], disposition)),
        warmup=BLOCK_COMPONENTS[name].spec.warmup,
    )
    for name, disposition in CAUSAL_MANIFEST.items()
    if disposition.status == "admitted"
}
BLOCK_REGISTRATIONS = {
    ref: registration.implementation for ref, registration in REGISTRATIONS.items()
}


def _logic_and(params, node_inputs, context_inputs):
    return {"out": node_inputs["left"] & node_inputs["right"]}


def _logic_or(params, node_inputs, context_inputs):
    return {"out": node_inputs["left"] | node_inputs["right"]}


_BOOLEAN = wire("bool", instrument="*", timeframe="*")
LOGIC_AND = component(
    "logic.and",
    interface=(socket("left", "input", _BOOLEAN), socket("right", "input", _BOOLEAN),
               socket("out", "output", _BOOLEAN)),
    causal=causal_contract(
        node_input_sockets=("left", "right"), history=HistoryBound("bounded")),
)(_logic_and)
LOGIC_OR = component(
    "logic.or",
    interface=(socket("left", "input", _BOOLEAN), socket("right", "input", _BOOLEAN),
               socket("out", "output", _BOOLEAN)),
    causal=causal_contract(
        node_input_sockets=("left", "right"), history=HistoryBound("bounded")),
)(_logic_or)

for _logic in (LOGIC_AND, LOGIC_OR):
    REGISTRATIONS[_logic.body_ref] = registered_kernel(
        body_ref=_logic.body_ref,
        implementation=_logic.kernel,
        causal=_logic.spec.causal,
        dependency_boundary=DependencyBoundary("defining_module"),
    )

COMPONENTS = {
    authored.key: authored.definition
    for authored in (*BLOCK_COMPONENTS.values(), LOGIC_AND, LOGIC_OR)
}
BODIES: dict[str, Mapping[str, Any]] = {}
LIBRARY = Library(
    components=COMPONENTS,
    bodies=BODIES,
    kernels={ref: registration.spec for ref, registration in REGISTRATIONS.items()},
)
IMPLEMENTATIONS = {
    ref: registration.implementation for ref, registration in REGISTRATIONS.items()
}

assert set(CAUSAL_MANIFEST) == set(BLOCKS)
assert set(BLOCK_DEPENDENCIES) == set(BLOCKS)
_ADMITTED = {name for name, disposition in CAUSAL_MANIFEST.items()
             if disposition.status == "admitted"}
assert set(BLOCK_REGISTRATIONS) == {
    BLOCK_COMPONENTS[name].body_ref for name in _ADMITTED
}
assert {"logic.and", "logic.or"} <= {key[0] for key in COMPONENTS}
