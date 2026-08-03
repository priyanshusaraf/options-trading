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
import warnings
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
    complete = g.cumcount(ascending=False) + pos + 1 >= n
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


# ── regime conditioning (Phase 5) ────────────────────────────────────────────
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
    from research.regime import REGIMES, label_regimes
    kind = REGIMES[_clamp_code(code, len(REGIMES))]
    try:
        return _b(label_regimes(df) == kind)
    except Exception:
        # A frame this labeller cannot read means NO signal, never an
        # unconditional one: a broken filter must narrow the strategy to nothing
        # rather than silently removing the condition it was added to impose.
        return pd.Series(False, index=df.index)


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
                                  lambda a: 2, (0.5,), "confirmation", inputs=("open", "high", "low", "close")),
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
