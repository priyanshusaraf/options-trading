"""VWAP-Slope Divergence — the owner's VWAP-slope idea + RSI divergence, built in
layers so each component's contribution can be measured on its own.

Core quantity — the VWAP slope:
    vslope = (VWAP_t − VWAP_{t−L}) / ATR_t           (L = 10 bars, session VWAP)
The session VWAP is the volume-weighted average price since the session open
(resets daily, as on Kite). Its slope says which side has been paying up all
session: vslope < 0 → sellers have dragged the day's average price down.

Layers (each one is a param, so a backtest can switch it on/off):
  1. trigger = "slope_cross"        bare base: trade the sign of vslope.
  2. trigger = "failed_divergence"  RSI divergence AGAINST the VWAP trend is a
     FAILED reversal → enter WITH the trend. Component analysis on 2019-2026
     MCX NG 15m: a bullish divergence printed while vslope < 0 was followed by
     −10 bps (OOS) over the next 8 bars, i.e. the "reversal" fails and the VWAP
     trend resumes. trigger = "divergence_reversal" is the textbook reading
     (buy the bullish divergence) kept for comparison.
  3. candle confirmation: the trigger bar must CLOSE in the trend's end of its
     range (close-location value), i.e. the divergence bar shows no rejection.
  4. VWAP side: price must be on the trend's side of the VWAP.
  5. time window: entries only between entry_start and entry_end (IST minutes).
  6. pyramiding: a later same-direction trigger adds one lot while price is at
     least `add_min_dist` ATR beyond the VWAP in the trend's direction.
  7. trade management: risk_model ratchet (ATR stop → Chandelier → MFE floor),
     exit on VWAP-slope flip and/or VWAP cross, session square-off (intraday).

Regime: TRENDING markets (a persistent one-sided VWAP). In balanced, two-sided
sessions the slope flips often and the strategy should stand aside.

Results (MCX proxy 2019-2023 IS / 2024-2026 OOS, net of charges + slippage; full
tables in docs/strategies/2026-10-commodity-strategy-research.md): the intraday
(session-VWAP, flat-at-close) version lost on every layer on NG and crude; a
VWAP-pullback trigger lost in all 192 IS configs. Defaults are therefore the best
IS-robust swing variant — failed-divergence trigger on a 120-bar ROLLING VWAP,
held overnight, ratchet exit, no pyramiding: NATGASMINI 30m IS +₹73k (PF 1.23)
-> OOS +₹18k (PF 1.10), but only ≈ +₹3k at 2x slippage; crude/gold lose.
NOT recommended for deployment. Kept as the documented test bed of the idea.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.ta import (atr, minutes_of_day, rolling_vwap, rsi, rsi_divergence,
                             session_bar_no, session_vwap)

from .base import Strategy


class VwapSlopeDivergence(Strategy):
    key = "vwap_slope_divergence"
    display_name = "VWAP-Slope Divergence (intraday)"
    default_params = {
        "vwap_mode": "rolling",           # session (resets daily) | rolling (n bars)
        "vwap_window": 120,
        "vwap_slope_len": 10, "atr_length": 14, "rsi_length": 14,
        "min_vslope": 0.25,
        "trigger": "failed_divergence",   # slope_cross | failed_divergence | divergence_reversal | vwap_pullback
        "trend_frac": 0.7,                # vwap_pullback: share of session bars on the trend side of VWAP
        "touch_atr": 0.2,                 # vwap_pullback: bar must reach within this many ATR of VWAP
        "div_lookback": 20, "div_min_gap": 3, "div_rsi_delta": 3.0,
        "div_os": 40.0, "div_ob": 60.0,
        "candle_clv": 0.0,                # 0 = off; e.g. 0.35 -> close in the trend-side 35% of the bar
        "require_vwap_side": True,
        "entry_start": 0, "entry_end": 1440,
        "add_min_dist": 1.0,              # ATR beyond VWAP to allow a pyramid add
        "exit_on_slope_flip": True, "exit_on_vwap_cross": False,
    }
    risk_model = {
        "atr_length": 14, "initial_risk_atr": 1.5,
        "trail_start_r": 1.0, "trail_atr": 2.5,
        "use_mfe_capture_floor": True, "capture_start_r": 1.5, "capture_pct": 0.4,
    }
    pyramiding = None                 # tested (L7): adds hurt — off
    session_flat = False              # multi-session holds; the intraday variant lost
    warmup_columns = ("atr",)

    def compute(self, df: pd.DataFrame, vwap_mode: str = "session", vwap_window: int = 60,
                vwap_slope_len: int = 10, atr_length: int = 14,
                rsi_length: int = 14, min_vslope: float = 0.5,
                trigger: str = "failed_divergence", trend_frac: float = 0.7,
                touch_atr: float = 0.2, div_lookback: int = 20,
                div_min_gap: int = 3, div_rsi_delta: float = 3.0, div_os: float = 40.0,
                div_ob: float = 60.0, candle_clv: float = 0.0,
                require_vwap_side: bool = True, entry_start: int = 570,
                entry_end: int = 1350, add_min_dist: float = 1.0,
                exit_on_slope_flip: bool = True,
                exit_on_vwap_cross: bool = False) -> pd.DataFrame:
        out = df.copy()
        c, h, lo, o = out["close"], out["high"], out["low"], out["open"]
        a = atr(out, atr_length)
        L = int(vwap_slope_len)
        if vwap_mode == "rolling":
            vw = rolling_vwap(out, int(vwap_window))
            vslope = (vw - vw.shift(L)) / a
        else:
            vw = session_vwap(out)
            bn = session_bar_no(out)
            vslope = ((vw - vw.shift(L)) / a).where(bn >= L)
        r = rsi(c, rsi_length)
        bull_div, bear_div = rsi_divergence(lo.to_numpy(float), h.to_numpy(float),
                                            r.to_numpy(float), int(div_lookback),
                                            int(div_min_gap), float(div_rsi_delta),
                                            float(div_os), float(div_ob))
        bull_div = pd.Series(bull_div, index=out.index)
        bear_div = pd.Series(bear_div, index=out.index)

        up = vslope > min_vslope
        dn = vslope < -min_vslope
        if trigger == "slope_cross":
            long_t = up & ~(vslope.shift(1) > min_vslope)
            short_t = dn & ~(vslope.shift(1) < -min_vslope)
            # same-session only: a cross needs a valid previous slope
            long_t &= vslope.shift(1).notna()
            short_t &= vslope.shift(1).notna()
        elif trigger == "divergence_reversal":
            long_t = dn & bull_div
            short_t = up & bear_div
        elif trigger == "vwap_pullback":
            key = pd.to_datetime(out["date"]).dt.date
            frac_above = (c > vw).astype(float).groupby(key).expanding().mean().reset_index(
                level=0, drop=True).sort_index()
            frac_below = 1.0 - frac_above
            long_t = (up & (frac_above.shift(1) >= trend_frac) & (lo <= vw + touch_atr * a)
                      & (c > vw) & (c > o))
            short_t = (dn & (frac_below.shift(1) >= trend_frac) & (h >= vw - touch_atr * a)
                       & (c < vw) & (c < o))
        else:  # failed_divergence (continuation)
            long_t = up & bear_div
            short_t = dn & bull_div

        rng = (h - lo).replace(0, np.nan)
        clv = (c - lo) / rng
        if candle_clv and candle_clv > 0:
            if trigger == "divergence_reversal":
                long_t &= clv >= 1 - candle_clv    # rejection of the low (hammer-like)
                short_t &= clv <= candle_clv
            else:
                long_t &= clv >= 1 - candle_clv    # closes near its high: no rejection
                short_t &= clv <= candle_clv
        if require_vwap_side and trigger != "divergence_reversal":
            long_t &= c > vw
            short_t &= c < vw

        mins = minutes_of_day(out)
        window = (mins >= entry_start) & (mins <= entry_end)
        long_entry = long_t & window
        short_entry = short_t & window

        long_add = long_t & (c > vw + add_min_dist * a)
        short_add = short_t & (c < vw - add_min_dist * a)

        long_exit = pd.Series(False, index=out.index)
        short_exit = pd.Series(False, index=out.index)
        if trigger == "divergence_reversal":
            long_exit |= short_t
            short_exit |= long_t
        else:
            if exit_on_slope_flip:
                long_exit |= vslope < 0
                short_exit |= vslope > 0
            if exit_on_vwap_cross:
                long_exit |= c < vw
                short_exit |= c > vw

        out["atr"] = a
        out["vwap"] = vw
        out["vslope"] = vslope
        out["rsi"] = r
        out["bullDiv"] = bull_div
        out["bearDiv"] = bear_div
        out["longEntry"] = long_entry.fillna(False).astype(bool)
        out["shortEntry"] = short_entry.fillna(False).astype(bool)
        out["longExit"] = long_exit.fillna(False).astype(bool)
        out["shortExit"] = short_exit.fillna(False).astype(bool)
        out["longAdd"] = long_add.fillna(False).astype(bool)
        out["shortAdd"] = short_add.fillna(False).astype(bool)
        return out


STRATEGY = VwapSlopeDivergence()
