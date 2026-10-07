"""Volatility Squeeze Breakout — trade the release of a multi-session "coil".

REGIME: squeeze / transition — a market that has gone quiet for ~2 sessions
(relative to what those HOURS normally deliver) and then closes out of its box.
It is NOT a trend-follower (it only engages right after a compression, never on a
plain trend flip) and NOT a fader (it trades WITH the break and is flat in chop
until a fresh coil forms).

CORE INDICATOR — the coil ratio (self-derived, time-of-day aware):
    e_t   = mean bar range at this same clock slot over the previous `slot_k`
            sessions (the "expected" range of this hour — MCX energy ranges in
            US hours are 2-4x the Indian-hours ranges, so a raw ATR squeeze
            mostly measures the clock)
    coil  = (HH_n - LL_n) / sqrt( sum_{last n bars} e^2 )
The denominator is the range a random walk would be expected to cover over
exactly those hours, so coil << 1 means price is genuinely compressed for the
time of day it spans. The box is the n bars ending at the previous bar
(n = box_hours of bars, so the default means the same on 15m/30m/60m).

LAYERS (each is a parameter, so a backtest can switch it on/off):
  L0  squeeze + break: previous box had coil <= coil_max; this bar CLOSES beyond
      the box high/low -> long/short (fills next open). Exit = opposite break.
  L1  failed-break exit (exit_box="mid"): once in, exit on a close back through
      the box midpoint of the triggering box — a break that falls back into the
      middle of its coil has failed. [DEFAULT ON]
  --- tested, NOT adopted (they improved in-sample but not out-of-sample) ---
  L2  trigger quality: min_clv (close in the break-side part of the bar),
      min_expansion (bar range vs its slot norm), min_vol_surge (volume vs the
      same slot's average), break_buf (ATR buffer), confirm_bars (acceptance).
  L3  direction: drift_len (only break with the N-bar drift), vwap_side,
      allow_long / allow_short.
  L4  time gate: entry_start/entry_end (IST minutes), e.g. US-session release.
  L5  exits: time_stop, recoil exit (a NEW coil after entry = expansion over),
      the class `risk_model` ratchet (None by default), session_flat (False:
      positions are held across sessions — typical hold ~3-6 sessions).
  L6  pyramiding: longAdd/shortAdd = a fresh coil-break in the trade's direction.
  REF squeeze="bbkc" (Bollinger-inside-Keltner, the textbook TTM squeeze),
      "atr_ratio", "none" (plain Donchian break) — for comparison only.

LINEAGE: the squeeze idea is the classic Bollinger/Keltner "squeeze" and
Crabel's narrow-range breakouts; the coil ratio (slot-normalised range vs the
sqrt-of-time expectation), the box-midpoint failure exit and the re-coil exit
are constructions of this module.

EVIDENCE (Oct 2026 research; MCX proxies 2019-01..2026-10; platform engine; net
of the Zerodha MCX charge stack + per-side slippage; roll gaps removed; IS =
2019-2023, OOS = 2024-01..2026-10; defaults chosen on IS as the centre of a
broad plateau — box 22-38 h x coil 0.65-0.85 all IS-positive on NG):
  NATGASMINI 60m  IS +1.98L PF 2.30 (137 tr)  OOS +0.13L PF 1.12 (70 tr), max DD 0.63L
                  OOS by year: 2024 +20k, 2025 +52k, 2026 -59k.
                  IS is almost entirely 2022 (+1.98L of +1.98L) — a fat-tail
                  catcher that needs a high-vol trending year.
  CRUDEOILM 60m   IS -8k PF 0.93, OOS -41k PF 0.52  -> NOT recommended for crude.
  Measured premise check: on these proxies a tight coil does NOT predict a
  larger-than-normal forward move (vol clusters: forward |move| / expected is
  LOWEST after the tightest coils). The breakout's edge, where it exists, comes
  from asymmetric exits (cut failed breaks fast, hold good ones for days), not
  from "compression -> expansion" per se.

LIMITATIONS: few trades (~25/yr), multi-session holds (overnight gap risk; roll
handling needed live), results depend on a 2022-type volatile trending year;
OOS is roughly break-even. Treat it as a low-frequency NG satellite / research
baseline, not a stand-alone production strategy. Recommended use: NATGASMINI on
30m or 60m candles with the defaults; not crude.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.ta import atr, ema, minutes_of_day, rma, session_vwap

from .base import Strategy


def _slot_norm(s: pd.Series, slot: pd.Series, k: int) -> pd.Series:
    """Trailing mean of `s` over the previous `k` occurrences of the SAME intraday
    slot (time of day), excluding the current bar — the 'expected' value of s at
    this clock time. Causal."""
    return s.groupby(slot).transform(
        lambda x: x.shift(1).rolling(k, min_periods=max(2, k // 2)).mean())


def _ffill_on(mask: pd.Series, values: pd.Series) -> pd.Series:
    """Value of `values` at the most recent bar where `mask` was True (incl. now)."""
    return values.where(mask).ffill()


def _bars_since(mask: pd.Series) -> pd.Series:
    """Bars since `mask` was last True (0 on the bar itself; NaN before the first)."""
    idx = pd.Series(np.arange(len(mask)), index=mask.index, dtype=float)
    return idx - idx.where(mask).ffill()


def _bar_minutes(dates: pd.Series) -> float:
    """Bar spacing of the feed: the most common positive intraday step (minutes).
    A static property of the candle feed (identical on any prefix with >= 2
    bars in a session)."""
    d = pd.to_datetime(dates).diff().dt.total_seconds().div(60.0)
    d = d[(d > 0) & (d <= 240)]
    return float(d.mode().iloc[0]) if len(d) else 60.0


def _coil(h: pd.Series, lo: pd.Series, exp_rng: pd.Series, n: int) -> pd.Series:
    return ((h.rolling(n).max() - lo.rolling(n).min())
            / np.sqrt((exp_rng ** 2).rolling(n).sum()))


class VolSqueezeBreakout(Strategy):
    key = "vol_squeeze_breakout"
    display_name = "Volatility Squeeze Breakout"
    default_params = {
        # --- compression (coil) ---
        "squeeze": "coil",          # coil | bbkc | atr_ratio | none
        "box_hours": 30.0,          # box span in hours (~2 MCX sessions)
        "box_len": 0,               # >0 overrides box_hours with an explicit bar count
        "slot_k": 20,               # sessions in the same-time-of-day range norm
        "coil_max": 0.75,           # armed when the box's coil ratio <= this
        "arm_bars": 0,              # squeeze may have ended up to N bars before the break
        # --- trigger quality (off) ---
        "break_buf": 0.0, "min_expansion": 0.0, "min_vol_surge": 0.0, "min_clv": 0.0,
        "confirm_bars": 0,
        # --- direction (off) ---
        "mode": "breakout",         # breakout | fade (failed-break reversal; rejected)
        "drift_len": 0, "vwap_side": False, "allow_long": True, "allow_short": True,
        # --- time gate, IST minutes of day (off = whole session) ---
        "entry_start": 0, "entry_end": 24 * 60,
        # --- exits ---
        "exit_box": "mid",          # mid | far | none
        "time_stop": 0, "recoil_len": 0, "recoil_max": 0.75,
        "atr_length": 14,
    }
    risk_model = None          # ratchet tested; hurt both IS and OOS (see docstring)
    pyramiding = None          # {"max_adds": n} amplifies IS and OOS alike
    session_flat = False       # multi-session holds are the point of the design
    warmup_columns = ("atr",)

    def compute(self, df: pd.DataFrame, squeeze: str = "coil", box_hours: float = 30.0,
                box_len: int = 0, slot_k: int = 20, coil_max: float = 0.75,
                arm_bars: int = 0, break_buf: float = 0.0, min_expansion: float = 0.0,
                min_vol_surge: float = 0.0, min_clv: float = 0.0, confirm_bars: int = 0,
                mode: str = "breakout", drift_len: int = 0, vwap_side: bool = False,
                allow_long: bool = True, allow_short: bool = True, entry_start: int = 0,
                entry_end: int = 1440, exit_box: str = "mid", time_stop: int = 0,
                recoil_len: int = 0, recoil_max: float = 0.75, atr_length: int = 14,
                **_: object) -> pd.DataFrame:
        out = df.copy()
        h, lo, c = out["high"], out["low"], out["close"]
        n = int(box_len) if box_len and box_len > 0 else \
            max(2, int(round(float(box_hours) * 60.0 / _bar_minutes(out["date"]))))
        a = atr(out, int(atr_length))
        mins = minutes_of_day(out)
        rng = h - lo
        # expected range at this clock slot; ATR where slot history is too short
        exp_rng = _slot_norm(rng, mins, int(slot_k)).fillna(a)

        # --- compression box: the n bars ending at the PREVIOUS bar --------------
        box_hi = h.rolling(n).max().shift(1)
        box_lo = lo.rolling(n).min().shift(1)
        coil = _coil(h, lo, exp_rng, n)
        if squeeze == "coil":
            sq_on = coil <= coil_max
        elif squeeze == "bbkc":   # textbook: Bollinger(20,2) inside Keltner(20,1.5 ATR)
            m = c.rolling(20).mean()
            sd = c.rolling(20).std(ddof=0)
            kc = ema(c, 20)
            sq_on = (m + 2 * sd < kc + 1.5 * a) & (m - 2 * sd > kc - 1.5 * a)
        elif squeeze == "atr_ratio":
            sq_on = rma(rng, 5) / rma(rng, 50) <= coil_max
        else:
            sq_on = pd.Series(True, index=out.index)
        sq_on = sq_on.fillna(False).astype(bool)
        armed = sq_on.shift(1, fill_value=False)
        if arm_bars and arm_bars > 0:
            armed = armed.astype(int).rolling(int(arm_bars) + 1,
                                              min_periods=1).max().astype(bool)

        # --- trigger -------------------------------------------------------------
        up = c > box_hi + break_buf * a
        dn = c < box_lo - break_buf * a
        if min_expansion and min_expansion > 0:
            xp = rng / exp_rng >= min_expansion
            up &= xp
            dn &= xp
        if min_vol_surge and min_vol_surge > 0 and "volume" in out.columns:
            vr = out["volume"] / _slot_norm(out["volume"], mins, int(slot_k))
            up &= vr >= min_vol_surge
            dn &= vr >= min_vol_surge
        if min_clv and min_clv > 0:
            clv = (c - lo) / rng.replace(0, np.nan)
            up &= clv >= 1 - min_clv
            dn &= clv <= min_clv
        brk_up = (up & armed).fillna(False)
        brk_dn = (dn & armed).fillna(False)
        if confirm_bars and confirm_bars > 0:
            # acceptance: one bar later price still closes beyond the SAME box
            box_hi, box_lo = box_hi.shift(1), box_lo.shift(1)
            brk_up = (brk_up.shift(1, fill_value=False) & (c > box_hi)).fillna(False)
            brk_dn = (brk_dn.shift(1, fill_value=False) & (c < box_lo)).fillna(False)
        box_mid = (box_hi + box_lo) / 2.0

        if mode == "fade":
            long_t, short_t = brk_dn.copy(), brk_up.copy()
        else:
            long_t, short_t = brk_up.copy(), brk_dn.copy()
        if drift_len and drift_len > 0:
            drift = c - c.shift(int(drift_len))
            long_t &= (drift > 0).fillna(False)
            short_t &= (drift < 0).fillna(False)
        if vwap_side:
            vw = session_vwap(out)
            long_t &= c > vw
            short_t &= c < vw
        if not allow_long:
            long_t[:] = False
        if not allow_short:
            short_t[:] = False
        window = (mins >= entry_start) & (mins <= entry_end)

        # --- exits -----------------------------------------------------------------
        long_exit = short_t.copy()      # opposite coil-break always ends the trade
        short_exit = long_t.copy()
        if exit_box in ("mid", "far"):
            frac = 0.5 if exit_box == "mid" else 1.0
            width = box_hi - box_lo
            if mode == "fade":
                lvl_l, lvl_s = box_lo - frac * width, box_hi + frac * width
            else:
                lvl_l, lvl_s = box_hi - frac * width, box_lo + frac * width
            # level frozen at the most recent same-direction signal (the entry or a
            # later re-break) — stateless equivalent of "the entry box"
            long_exit |= (c < _ffill_on(long_t, lvl_l)).fillna(False)
            short_exit |= (c > _ffill_on(short_t, lvl_s)).fillna(False)
        if recoil_len and recoil_len > 0:
            m_ = int(recoil_len)
            rc = (_coil(h, lo, exp_rng, m_) <= recoil_max).fillna(False)
            long_exit |= (rc & (_bars_since(long_t) >= m_)).fillna(False)
            short_exit |= (rc & (_bars_since(short_t) >= m_)).fillna(False)
        if time_stop and time_stop > 0:
            long_exit |= (_bars_since(long_t) >= time_stop).fillna(False)
            short_exit |= (_bars_since(short_t) >= time_stop).fillna(False)

        out["atr"] = a
        out["coil"] = coil
        out["squeeze"] = sq_on
        out["boxHigh"] = box_hi
        out["boxLow"] = box_lo
        out["longEntry"] = (long_t & window).fillna(False).astype(bool)
        out["shortEntry"] = (short_t & window).fillna(False).astype(bool)
        out["longExit"] = long_exit.fillna(False).astype(bool)
        out["shortExit"] = short_exit.fillna(False).astype(bool)
        out["longAdd"] = long_t.fillna(False).astype(bool)
        out["shortAdd"] = short_t.fillna(False).astype(bool)
        return out


STRATEGY = VolSqueezeBreakout()
