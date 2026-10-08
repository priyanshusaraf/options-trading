"""VWAP Band Reversion (chop) — fade σ-stretched closes back to a VWAP anchor
while the anchor is balanced. Built in layers so each component's marginal value
can be measured (every layer is a param; 0 / "off" disables it).

WHAT IT TRADES
  z = (close − anchor VWAP) / anchor σ, where σ is the volume-weighted standard
  deviation of the typical price around that VWAP (the classic VWAP σ-band).
  A close at z ≤ −band_k is faded LONG, z ≥ +band_k SHORT; the position exits when
  the close gets back to the anchor (z crosses −target_k / +target_k; default the
  VWAP itself). Fills at the next bar open (engine convention).

LAYERS
  anchor        "session": session VWAP (resets 09:00 IST) — the textbook intraday
                version. "rolling": a multi-session VWAP over the last
                `anchor_days` sessions (floating, does not reset) — the DEFAULT.
  stretch       band_k (σ); optional min ATR distance (min_atr_dist), min bps
                distance (min_bps, cost-aware), RSI extreme (rsi_extreme).
  trigger       close_beyond (default) | reclaim (prior bar beyond, this bar back
                inside) | rejection (wick pierced the band, close in far end).
  chop gates    max_vslope: |VWAP − VWAP[10]| / ATR (flat-VWAP, lead's measure).
                max_drift: |anchor − anchor[D]| / (ATR·√D) — self-derived "anchor
                drift vs a random walk" (≈0 flat/balanced, ≈1 trending), D = half the
                anchor window by default. max_er: Kaufman efficiency ratio ceiling.
                min_rot: VWAP crossings in the last rot_len bars (session rotation
                count, self-derived). max_imbalance: |share of session closes above
                VWAP − ½|·2 (two-sided auction ≈ 0, one-way day ≈ 1, self-derived).
  climax push   min_push_er: the stretch must have been REACHED by a directional push
                (ER over push_len bars ≥ x), not a slow drift into the band.
                Self-derived from IS trade attribution: slow drifts into the band
                kept drifting; impulsive excursions reverted.
  time window   entry_start / entry_end (IST minutes).
  exits         target_k (σ from anchor), stop_k (σ disaster stop), max_hold (bars
                since the last qualifying setup — a time stop).
  scale-in      add_k: while in a trade, one more lot when |z| ≥ add_k (deeper band);
                class `pyramiding = {"max_adds": 1}`. All legs exit together.

COMPONENT ANALYSIS (research harness, real engine, MCX proxies 2019-01 → 2026-10,
net of the full Zerodha MCX charge stack + per-side slippage, futures-roll gaps
removed; IS = 2019-2023 for every choice, OOS = 2024-01 → 2026-10 checked once).
30m, 1 lot, ₹ net (PF):           NATGASMINI IS | OOS            CRUDEOILM IS | OOS
  L0 session VWAP |z|≥2 → VWAP    −263k (.76) | −133k (.75)      −185k (.68) | −125k (.64)
  L1 + k=2.75                     −100k (.76) | −45k (.79)       −105k (.52) | −35k (.58)
  L2 + flat VWAP |vslope|≤.5      −62k (.76)  | −44k (.72)       −47k (.64)  | −21k (.56)
  L3 + 20:00-21:30 IST window     −0.3k (.98) | −0.4k (.95)      −6.5k (.69) | −3.9k (.49)
  L4 rolling 10-day anchor, k2.75 +76k (1.78) | +14k (1.17)      +25k (1.46) | −1.2k (.98)
  L5a + drift ≤ .6 (chop gate)    +75k (1.79) | +14k (1.17)      +30k (1.58) | −2.4k (.95)
  L5b + er20 ≤ .5 (chop gate)     +27k (1.38) | +21k (1.46)      +18k (1.46) | −7.0k (.80)
  L5c + climax push er20 ≥ .5     +118k (2.66)| +23k (1.36)      +39k (1.81) | +2.0k (1.04)
  L6 L5c + scale-in at 3.5σ  ★    +135k (2.55)| +39k (1.49)      +45k (1.72) | +9.8k (1.14)
  L7 L6 + 5σ disaster stop        +135k       | +32k             +43k        | +9.8k
  L8 L6 + 10-day time stop        +130k       | +45k             +37k        | +4.5k
  (★ = default. Intraday session-VWAP fading loses before AND after costs: gross is
  negative — extremes vs the session VWAP continue more than they revert.)

REGIME / USE
  A slow SWING mean-reversion (median hold ≈ 3 sessions, up to ~3 weeks), holding
  overnight (session_flat = False): it fades multi-σ excursions from a 10-session
  VWAP when the excursion is impulsive. It is the "balance" counterpart of a
  breakout/trend system: it profits when multi-day ranges hold and loses when a
  range turns into a trend (e.g. CRUDEOILM 2026, GOLDPETAL 2024-26 bull run).
  The intraday chop variant (anchor="session", session_flat) is kept for research
  only — no intraday configuration survived costs.

PER-INSTRUMENT (final config, OOS 2024-01 → 2026-10)
  NATGASMINI 30m: +₹38.6k, PF 1.49, 29 trades, max DD ₹42.8k; every OOS year > 0
                  (2024 +15.5k, 2025 +17.1k, 2026 +6.0k); also positive on 15m/60m
                  and for every neighbour tried (anchor 8-15 d, k 2.5-3.0, push
                  .4-.6). Gains come mostly from fading UP-spikes (shorts).
                  BUT t-stat 0.8 (bootstrap P(loss) ≈ 20%): weak evidence.
  CRUDEOILM:      ≈ break-even OOS (+9.8k PF 1.14 on 30m; −1.9k 15m; −18k 60m;
                  neighbours flip sign) — no reliable edge. Not recommended.
  GOLDPETAL 60m:  IS ≈ 0, OOS −₹6.0k (PF .23) — fading a trending metal. Avoid.

LIMITATIONS
  Small samples (≈10 trades/yr/instrument); P&L concentrated in a few large
  reversions (NG 2022); no stop by default and one scale-in → large adverse
  excursions (MAE p90 ≈ 15% on NG; OOS DD ≈ 0.5-0.6× one lot's notional). Data are
  international-futures proxies in INR with tick volume, not MCX prints. Bars per
  session are inferred from the first 64 bars (session_minutes / bar length, MCX
  = 870 min); set session_minutes for other venues.

LINEAGE
  VWAP σ-bands: standard volume-weighted variance around the session VWAP (as on
  most charting packages); Kaufman efficiency ratio (app.strategy.ta). The
  random-walk-normalised anchor drift, VWAP rotation count, session imbalance and
  the climax-push filter are constructions derived for this study.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.ta import (atr, efficiency_ratio, minutes_of_day, rsi, session_bar_no,
                             session_key, session_vwap, session_vwap_sd)

from .base import Strategy


def _bar_minutes(dates: pd.Series) -> float:
    """Bar length in minutes from the first in-session date diffs (prefix-stable)."""
    d = pd.to_datetime(dates).iloc[:64].diff().dropna()
    d = d[d > pd.Timedelta(0)]
    if d.empty:
        return 15.0
    return float(d.min().total_seconds() / 60.0)


def _rolling_vwap(df: pd.DataFrame, n: int) -> tuple[pd.Series, pd.Series]:
    """Rolling (multi-session) volume-weighted mean and sigma of the typical price
    over the last n bars — a 'floating anchor' that does not reset at the open."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    v = df["volume"] if "volume" in df.columns else pd.Series(0.0, index=df.index)
    v = v.fillna(0.0).clip(lower=0.0) + 1e-9
    sv = v.rolling(n, min_periods=n).sum()
    m = (tp * v).rolling(n, min_periods=n).sum() / sv
    ex2 = (tp * tp * v).rolling(n, min_periods=n).sum() / sv
    sd = np.sqrt((ex2 - m * m).clip(lower=0.0))
    return m, sd


def _within_session_count(flag: pd.Series, key: pd.Series, n: int) -> pd.Series:
    """Count of True flags over the last n bars, never reaching into the prior session."""
    cs = flag.astype(float).groupby(key).cumsum()
    prev = cs.groupby(key).shift(n).fillna(0.0)
    return cs - prev


def _bars_since(flag: pd.Series) -> pd.Series:
    idx = pd.Series(np.arange(len(flag), dtype=float), index=flag.index)
    last = idx.where(flag).ffill()
    return idx - last          # NaN until the first flag


class VwapBandReversion(Strategy):
    key = "vwap_band_reversion"
    display_name = "VWAP Band Reversion (chop)"
    default_params = {
        "anchor": "rolling", "anchor_days": 10.0, "session_minutes": 870, "atr_length": 14,
        "band_k": 2.75, "min_atr_dist": 0.0, "min_bps": 0.0, "min_session_bars": 8,
        "trigger": "close_beyond", "clv": 0.4,
        "max_vslope": 0.0, "vslope_len": 10,
        "max_drift": 0.0, "drift_len": 0,
        "max_er": 0.0, "er_len": 20,
        "min_push_er": 0.5, "push_len": 20,
        "min_rot": 0, "rot_len": 20,
        "max_imbalance": 0.0,
        "rsi_length": 14, "rsi_extreme": 0.0,
        "entry_start": 0, "entry_end": 1440,
        "target_k": 0.0, "stop_k": 0.0, "max_hold": 0,
        "add_k": 3.5,
    }
    risk_model = None                   # ATR stops hurt (IS): reversion needs room
    # Options path: holds last days-to-weeks; the global −35%/+60%/trail exits
    # turned it into a loser. No target/trail; a −95% disaster stop (research §6c).
    option_exits = {"stop_loss_pct": 0.95, "target_pct": None, "trail_enabled": False}
    pyramiding = {"max_adds": 1}        # one scale-in at the deeper add_k band
    session_flat = False                # swing: holds overnight (set True for anchor="session")
    warmup_columns = ("atr",)

    def compute(self, df: pd.DataFrame, anchor: str = "rolling", anchor_days: float = 10.0,
                session_minutes: int = 870,
                atr_length: int = 14, band_k: float = 2.75, min_atr_dist: float = 0.0,
                min_bps: float = 0.0, min_session_bars: int = 8,
                trigger: str = "close_beyond", clv: float = 0.4,
                max_vslope: float = 0.0, vslope_len: int = 10,
                max_drift: float = 0.0, drift_len: int = 0,
                max_er: float = 0.0, er_len: int = 20,
                min_push_er: float = 0.5, push_len: int = 20,
                min_rot: int = 0, rot_len: int = 20,
                max_imbalance: float = 0.0,
                rsi_length: int = 14, rsi_extreme: float = 0.0,
                entry_start: int = 0, entry_end: int = 1440,
                target_k: float = 0.0, stop_k: float = 0.0, max_hold: int = 0,
                add_k: float = 3.5) -> pd.DataFrame:
        out = df.copy()
        c, h, lo = out["close"], out["high"], out["low"]
        a = atr(out, atr_length)
        key = session_key(out)
        bn = session_bar_no(out)
        bpd = int(np.ceil(session_minutes / _bar_minutes(out["date"])))   # bars per session
        anchor_bars = max(2, int(round(anchor_days * bpd)))
        if anchor == "rolling":
            vw, sd = _rolling_vwap(out, anchor_bars)
            ok = vw.notna()
        else:
            vw = session_vwap(out)
            sd = session_vwap_sd(out, vw)
            ok = bn >= int(min_session_bars)
        sd = sd.where(sd > 0)
        z = (c - vw) / sd
        dist_atr = (c - vw) / a
        dist_bps = (c - vw) / c * 1e4

        # ---- stretch ------------------------------------------------------
        lo_str = (z <= -band_k) & (dist_atr <= -min_atr_dist) & (dist_bps <= -min_bps)
        hi_str = (z >= band_k) & (dist_atr >= min_atr_dist) & (dist_bps >= min_bps)
        if rsi_extreme and rsi_extreme > 0:
            r = rsi(c, rsi_length)
            lo_str &= r <= rsi_extreme
            hi_str &= r >= 100.0 - rsi_extreme
            out["rsi"] = r

        # ---- trigger ------------------------------------------------------
        rng = (h - lo).replace(0, np.nan)
        loc = (c - lo) / rng
        same = key == key.shift(1)
        if trigger == "reclaim":
            # previous bar closed beyond the band, this bar closes back inside it
            long_t = lo_str.shift(1, fill_value=False) & (z > -band_k) & same & (z < 0)
            short_t = hi_str.shift(1, fill_value=False) & (z < band_k) & same & (z > 0)
        elif trigger == "rejection":
            # the bar pierced the band but closed in the far end of its own range
            zl = (lo - vw) / sd
            zh = (h - vw) / sd
            long_t = (zl <= -band_k) & (loc >= 1 - clv) & (z < 0) & \
                (dist_atr <= -min_atr_dist) & (dist_bps <= -min_bps)
            short_t = (zh >= band_k) & (loc <= clv) & (z > 0) & \
                (dist_atr >= min_atr_dist) & (dist_bps >= min_bps)
        else:
            long_t, short_t = lo_str, hi_str

        # ---- chop gate ----------------------------------------------------
        L = int(vslope_len)
        vslope = (vw - vw.shift(L)) / a
        if anchor != "rolling":
            vslope = vslope.where(bn >= L)
        gate = ok.copy()
        if max_vslope and max_vslope > 0:
            gate &= vslope.abs() <= max_vslope
        # anchor drift vs a random walk: |anchor move over D bars| / (ATR * sqrt(D)).
        # ~1 = the anchor is travelling like a trending price; ~0 = flat (balance).
        D = int(drift_len) if drift_len and drift_len > 0 else max(2, anchor_bars // 2)
        drift = (vw - vw.shift(D)).abs() / (a * np.sqrt(D))
        if max_drift and max_drift > 0:
            gate &= drift <= max_drift
        er = efficiency_ratio(c, int(er_len) if er_len and er_len > 0 else anchor_bars)
        if max_er and max_er > 0:
            gate &= er <= max_er
        # climax filter: the stretch must have been reached by a directional push
        # (high short-window efficiency ratio), not by a slow drift into the band
        push = efficiency_ratio(c, int(push_len))
        if min_push_er and min_push_er > 0:
            gate &= push >= min_push_er
        side = np.sign(c - vw)
        cross = (side != side.shift(1)) & same & side.shift(1).notna()
        rot = _within_session_count(cross, key, int(rot_len))
        if min_rot and min_rot > 0:
            gate &= rot >= min_rot
        # session imbalance: 0 = closes split evenly either side of the VWAP so far
        # (two-sided auction), 1 = every close on one side (one-way trend day)
        above = (c > vw).astype(float)
        imb = ((above.groupby(key).cumsum() / (bn + 1)) - 0.5).abs() * 2.0
        if max_imbalance and max_imbalance > 0:
            gate &= imb <= max_imbalance

        mins = minutes_of_day(out)
        window = (mins >= entry_start) & (mins <= entry_end)
        long_entry = long_t & gate & window
        short_entry = short_t & gate & window

        # ---- exits --------------------------------------------------------
        long_exit = z >= -target_k
        short_exit = z <= target_k
        if stop_k and stop_k > 0:
            long_exit |= z <= -stop_k
            short_exit |= z >= stop_k
        if max_hold and max_hold > 0:
            long_exit |= _bars_since(long_t & gate) >= max_hold
            short_exit |= _bars_since(short_t & gate) >= max_hold

        long_add = pd.Series(False, index=out.index)
        short_add = pd.Series(False, index=out.index)
        if add_k and add_k > 0:
            long_add = (z <= -add_k) & gate
            short_add = (z >= add_k) & gate

        out["atr"] = a
        out["vwap"] = vw
        out["vwapSd"] = sd
        out["upperBand"] = vw + band_k * sd
        out["lowerBand"] = vw - band_k * sd
        out["z"] = z
        out["vslope"] = vslope
        out["drift"] = drift
        out["push"] = push
        out["er"] = er
        out["rot"] = rot
        out["imbalance"] = imb
        out["longEntry"] = long_entry.fillna(False).astype(bool)
        out["shortEntry"] = short_entry.fillna(False).astype(bool)
        out["longExit"] = long_exit.fillna(False).astype(bool)
        out["shortExit"] = short_exit.fillna(False).astype(bool)
        out["longAdd"] = long_add.fillna(False).astype(bool)
        out["shortAdd"] = short_add.fillna(False).astype(bool)
        return out


STRATEGY = VwapBandReversion()
