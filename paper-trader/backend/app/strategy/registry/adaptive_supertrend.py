"""Adaptive SuperTrend (auto-select) — port + research-hardened variant.

Lineage
-------
Port of `adaptive_supertrend.py` from deepaksingh-fx/ibkr-forex-dynamic, itself a
Python port of the Pine v6 indicator "Adaptive SuperTrend - Auto Method Selection
V3.4". Seven SuperTrend variants run in parallel, each with its own ATR multiplier:
  0 Percentile     mult = base * (1 + (percentrank(ATR,100)/100 - 0.5) * sens * 2)
  1 Regime         ATR/SMA(ATR,50) <0.7 -> 4.0, >1.3 -> 1.5, else 2.5
  2 Z-Score        mult = base * (1 + z(ATR,100) * sens)
  3 Dynamic Period base mult on a variable-period RMA of TR; period = 7..20 scaled by
                   percentrank(stdev(close,20),100)
  4 ROC            mult = base * (1 + |ROC(close,20)| * sens / 100)
  5 Hybrid         EMA(5) of the mean of methods 0,1,2,base,4
  6 Classic        ATR(base_atr) * base_mult (plain SuperTrend)
Each method keeps a flip-to-flip trade simulator (close-to-close points) over a
rolling `perf_lookback_days * bars_per_day` window. Every `eval_interval_bars`
(bar_index % N == 0) the method with the best score (Average Per Trade / Total
Points / Win Rate, + "Profit Factor" added here; < min_trades -> -1e10, ties ->
lowest index) becomes active. Signal = the ACTIVE method's own direction flips on
this bar AND the optional RSI(14) > 55 / < 45 and MACD line vs signal filters pass.
The source's live state machine (signal first, then close-confirmed TSL) is
replicated bar by bar: TSL = close -/+ tsl_atr_mult * active ATR, set at the signal
bar's close and only ratcheting. The source's T1-T3 targets are markers only (they
never close the trade) and are therefore not ported.

Faithful port = `FAITHFUL_PARAMS` below. The TSL lives in the exit flags (not the
engine's `risk_model`) because that is the source's semantics: it is anchored at
the signal bar's CLOSE, trails from closes using the active method's ATR from bar
one, and is close-confirmed; the platform ratchet (fill-price anchor, initial stop
-> Chandelier from wick high-water only after trail_start_r -> MFE floor) is a
different exit and was tested separately as a layer.

Layers (component analysis, MCX proxy 2019-2023 IS / 2024-2026 OOS, net of the
Zerodha MCX charge stack + slippage; see the research report)
------------------------------------------------------------------------------
  a  Classic SuperTrend stop-and-reverse (enable_auto=False, manual "Classic").
  b  + adaptive auto-selection        -> did NOT add value IS (usually worse).
  c  + RSI/MACD filters (+ 1.5 ATR TSL = the faithful port) -> worse IS and OOS;
     the tight close-TSL churns trend trades into stop-outs.
  d  own ideas: wider band (base_mult 5), ADX(14) >= 20 entry gate, relative tick
     volume >= 1x its 20-bar mean entry gate (all three improved NG IS on a broad
     plateau); efficiency-ratio gate, US-session time window, ratchet risk_model,
     pyramiding on a fast-ST re-flip, session_flat and alternative selection
     criteria were tested and rejected on IS.
Gates only block NEW entries; an opposite flip always exits.

Defaults = the best IS-robust configuration: Classic ST(10, 5.0) flip, ADX >= 20 and
relative volume >= 1.0 entry gates, no filters, no TSL, overnight holding, no
pyramiding, no risk_model. It is a TRENDING-market tool: on NATGASMINI it made
money 2019-2024 (most of it in the 2022 gas spike) and LOST in 2025-2026; on
CRUDEOILM no layer had an edge even in-sample. Out-of-sample after costs it is NOT
profitable on either — do not deploy without a fresh, independent validation.

Mechanics / limitations
-----------------------
* No look-ahead: bar i uses data up to bar i's close; a prefix of the data yields
  identical flags (tested). bars_per_day (for the lookback window) is derived from
  the first 200 timestamps assuming a 14.5 h MCX session (15m -> 58), or passed in.
* Entry flags fire on the bar the internal state turns long/short and are carried
  one more bar: the engine ignores entries while a position is open and fills at
  the next open, so a stop-and-reverse fills one bar after the exit.
* Exit flags are STATE based (longExit = internal state is not long), so an exit is
  never lost on the engine's no-manage fill bar.
* The internal state depends on where the candle history starts until the first
  flip (and, in auto mode, on the 60-day selection window) — the live engine's
  shorter history can differ from a long backtest for the first few trades.
* Volume is tick volume on the research proxy; the volume gate is skipped where
  volume is missing/zero. Percent rank follows Pine ta.percentrank: share of the
  `len` PREVIOUS values <= current. stdev is population (Pine). RMA/ATR/RSI are
  SMA-seeded Wilder; EMA is first-value seeded.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .base import Strategy

METHOD_NAMES = ("Percentile", "Regime", "Z-Score", "Dynamic Period",
                "Rate of Change", "Hybrid", "Classic")
METHOD_INDEX = {n: i for i, n in enumerate(METHOD_NAMES)}
NUM_METHODS = len(METHOD_NAMES)
_CRITERIA = ("Total Points", "Win Rate", "Average Per Trade", "Profit Factor")
_MCX_SESSION_MIN = 870.0   # 09:00-23:30 IST = 14.5 h


# ── indicator primitives (Pine semantics, numpy in / numpy out) ──────────────
def _first_valid(x: np.ndarray) -> int:
    v = ~np.isnan(x)
    return int(np.argmax(v)) if v.any() else len(x)


def _rma(x: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.rma: SMA seed over the first n valid values, then Wilder 1/n."""
    out = np.full(len(x), np.nan)
    f = _first_valid(x)
    s = f + n - 1
    if s >= len(x):
        return out
    seed = float(np.mean(x[f:s + 1]))
    tail = pd.Series(np.concatenate([[seed], x[s + 1:]]))
    out[s:] = tail.ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()
    return out


def _ema(x: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.ema: seeded with the first valid value, alpha = 2/(n+1)."""
    out = np.full(len(x), np.nan)
    f = _first_valid(x)
    if f >= len(x):
        return out
    out[f:] = pd.Series(x[f:]).ewm(span=n, adjust=False).mean().to_numpy()
    return out


def _sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def _stdev(x: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.stdev (biased=true) — POPULATION standard deviation."""
    return pd.Series(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()


def _percentrank(x: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.percentrank(src, n): % of the n PREVIOUS values (src[1]..src[n])
    that are <= the current value. Needs n+1 valid values (NaN otherwise)."""
    out = np.full(len(x), np.nan)
    if len(x) <= n:
        return out
    w = sliding_window_view(x, n + 1)
    cur = w[:, -1:]
    res = (w[:, :-1] <= cur).sum(axis=1) * (100.0 / n)
    res = res.astype(float)
    res[np.isnan(w).any(axis=1)] = np.nan
    out[n:] = res
    return out


def _roc(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) > n:
        prev = x[:-n]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n:] = np.where(prev != 0, 100.0 * (x[n:] - prev) / prev, np.nan)
    return out


def _true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def _rsi(c: np.ndarray, n: int) -> np.ndarray:
    d = np.r_[np.nan, np.diff(c)]
    up = _rma(np.where(np.isnan(d), np.nan, np.maximum(d, 0.0)), n)
    dn = _rma(np.where(np.isnan(d), np.nan, np.maximum(-d, 0.0)), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = np.where(dn == 0, 100.0, np.where(up == 0, 0.0, 100.0 - 100.0 / (1.0 + up / dn)))
    rsi[np.isnan(up) | np.isnan(dn)] = np.nan
    return rsi


def _adx(h, l, c, n: int) -> np.ndarray:
    up = np.r_[np.nan, np.diff(h)]
    dn = np.r_[np.nan, -np.diff(l)]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdm[0] = mdm[0] = np.nan
    tr = _true_range(h, l, c)
    tr[0] = np.nan
    atr = _rma(tr, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * _rma(pdm, n) / atr
        mdi = 100.0 * _rma(mdm, n) / atr
        dx = 100.0 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = np.where(np.isfinite(dx), dx, np.nan)
    return _rma(dx, n)


def _efficiency_ratio(c: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    vol = pd.Series(np.abs(np.r_[np.nan, np.diff(c)])).rolling(n, min_periods=n).sum().to_numpy()
    net = np.abs(c[n:] - c[:-n])
    with np.errstate(divide="ignore", invalid="ignore"):
        out[n:] = np.where(vol[n:] > 0, net / vol[n:], 0.0)
    return out


def _hhmm(s: str | None) -> int | None:
    if s is None or s == "":
        return None
    hh, mm = str(s).split(":")
    return int(hh) * 60 + int(mm)


# ── per-method SuperTrend + flip-to-flip trade log (source parity) ───────────
def _supertrend(hl2, close, prev_close, mult, atrv, cost_frac):
    """One method's SuperTrend. Returns (dir[], st[], flip_bars, flip_pts).

    Band/direction maths mirror the source (= Pine ta.supertrend). dir is 0 until
    the method's multiplier and ATR are first defined, then seeded to +1. Each
    direction flip closes a simulated trade (close-to-close points, optionally
    minus `cost_frac` x price as a cost-aware selection variant)."""
    n = len(close)
    d = [0] * n
    st = [math.nan] * n
    fb: list[int] = []
    fp: list[float] = []
    pu = pl = None
    cur = 0
    entry = None
    for i in range(n):
        m = mult[i]
        a = atrv[i]
        if m != m or a != a:          # NaN -> method not valid yet (source: continue)
            d[i] = cur
            continue
        h2 = hl2[i]
        ub = h2 + m * a
        lb = h2 - m * a
        pu_ = ub if pu is None else pu
        pl_ = lb if pl is None else pl
        pc = prev_close[i]
        nu = ub if (ub < pu_ or pc > pu_) else pu_
        nl = lb if (lb > pl_ or pc < pl_) else pl_
        ci = close[i]
        if cur == 0:
            nd = 1
        elif cur == -1 and ci > nu:
            nd = 1
        elif cur == 1 and ci < nl:
            nd = -1
        else:
            nd = cur
        pu, pl = nu, nl
        st[i] = nl if nd == 1 else nu
        if cur != 0 and nd != cur:
            if entry is not None:
                pts = (ci - entry) if cur == 1 else (entry - ci)
                fb.append(i)
                fp.append(pts - cost_frac * ci)
            entry = ci
        elif entry is None:
            entry = ci
        cur = nd
        d[i] = nd
    return (np.asarray(d, dtype=np.int8), np.asarray(st, dtype=float),
            np.asarray(fb, dtype=np.int64), np.asarray(fp, dtype=float))


def _bars_per_day(dates: pd.Series) -> int:
    """MCX session (14.5 h) / bar length. Bar length = median timestamp step over
    the FIRST 200 bars only, so a prefix of the data gets the same value (no
    look-ahead). Pass `bars_per_day` explicitly to override."""
    d = pd.to_datetime(dates.iloc[:200])
    if len(d) < 3:
        return 58
    step = d.diff().dropna().dt.total_seconds() / 60.0
    step = step[step > 0]
    bm = float(step.median()) if len(step) else 15.0
    return max(1, int(_MCX_SESSION_MIN / bm + 0.5))


# Exact source configuration (Pine V3.4 / ibkr-forex-dynamic defaults). All the
# extensions are off, so `signals(df, **FAITHFUL_PARAMS)` is the faithful port.
FAITHFUL_PARAMS: dict[str, Any] = {
    # base
    "base_atr": 10, "base_mult": 3.0,
    # auto-selection
    "enable_auto": True, "selection_criterion": "Average Per Trade",
    "eval_interval_bars": 30, "min_trades": 5, "perf_lookback_days": 60,
    "manual_method": "Percentile", "bars_per_day": None, "methods": None,
    "sel_cost_pct": 0.0,
    # method inputs
    "pctl_lookback": 100, "pctl_sens": 0.5,
    "reg_ma": 50, "low_vol_mult": 4.0, "norm_vol_mult": 2.5, "high_vol_mult": 1.5,
    "zs_lookback": 100, "zs_sens": 0.3,
    "min_atr": 7, "max_atr": 20, "period_sens": 50.0,
    "roc_lookback": 20, "roc_sens": 0.4,
    "hyb_smooth": 5,
    # filters
    "enable_rsi": True, "rsi_len": 14, "rsi_buy": 55.0, "rsi_sell": 45.0,
    "enable_macd": True, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
    # trailing stop (close-confirmed, source semantics)
    "enable_tsl": True, "tsl_method": "ATR", "tsl_atr_mult": 1.5,
    "tsl_pct": 1.0, "tsl_points": 50.0,
    # ---- extensions (all OFF = faithful port) ----
    "exit_on_flip": False,          # exit when the active ST opposes the position
    "entry_start": None, "entry_end": None,   # "HH:MM" IST entry window
    "er_len": 20, "er_min": 0.0,    # Kaufman efficiency-ratio entry gate
    "adx_len": 14, "adx_min": 0.0,  # ADX entry gate
    "vol_len": 20, "vol_min": 0.0,  # relative tick-volume entry gate
    "add_atr": 10, "add_mult": 1.5,  # fast classic ST for pyramid adds (longAdd/shortAdd)
}


class AdaptiveSuperTrend(Strategy):
    key = "adaptive_supertrend"
    display_name = "Adaptive SuperTrend (auto-select)"
    # Best IS-robust configuration from the layer study (see module docstring):
    # classic ST(10, 5.0) flip + ADX(14) >= 20 + relative volume >= 1.0 entry gates.
    default_params: dict[str, Any] = {
        **FAITHFUL_PARAMS,
        "enable_auto": False, "manual_method": "Classic",
        "base_atr": 10, "base_mult": 5.0,
        "enable_rsi": False, "enable_macd": False, "enable_tsl": False,
        "adx_len": 14, "adx_min": 20.0,
        "vol_len": 20, "vol_min": 1.0,
    }
    risk_model = None
    session_flat = False
    pyramiding = None
    warmup_columns = ("activeST",)

    def compute(self, df: pd.DataFrame, **p: Any) -> pd.DataFrame:
        out = df.copy()
        n = len(out)
        h = out["high"].to_numpy(float)
        lo = out["low"].to_numpy(float)
        c = out["close"].to_numpy(float)
        if n == 0:
            for col in ("longEntry", "shortEntry", "longExit", "shortExit", "longAdd",
                        "shortAdd"):
                out[col] = pd.Series(dtype=bool)
            return out
        base_mult = float(p["base_mult"])
        crit = p["selection_criterion"]
        if crit not in _CRITERIA:
            raise ValueError(f"bad selection_criterion {crit!r}")
        if p["manual_method"] not in METHOD_INDEX:
            raise ValueError(f"bad manual_method {p['manual_method']!r}")
        if p["tsl_method"] not in ("ATR", "Percentage", "Fixed Points"):
            raise ValueError(f"bad tsl_method {p['tsl_method']!r}")

        prev_c = np.r_[c[0], c[:-1]]
        hl2 = (h + lo) / 2.0
        tr = _true_range(h, lo, c)
        atr = _rma(tr, int(p["base_atr"]))

        # dynamic-period sub-pipeline: vol score = percentrank(stdev(close,20),100)
        vs = _percentrank(_stdev(c, 20), 100) / 100.0
        dper = np.clip(p["min_atr"] + (p["max_atr"] - p["min_atr"]) * vs
                       * (p["period_sens"] / 50.0), 2.0, 500.0)
        dyn = np.full(n, np.nan)
        prev = None
        trl = tr.tolist()
        dpl = dper.tolist()
        for i in range(n):
            P = dpl[i]
            if P != P:
                continue
            prev = trl[i] if prev is None else (prev * (P - 1.0) + trl[i]) / P
            dyn[i] = prev

        mults = np.full((NUM_METHODS, n), np.nan)
        pr = _percentrank(atr, int(p["pctl_lookback"])) / 100.0
        mults[0] = base_mult * (1.0 + (pr - 0.5) * p["pctl_sens"] * 2.0)
        avg = _sma(atr, int(p["reg_ma"]))
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = atr / avg
        m1 = np.where(ratio < 0.7, p["low_vol_mult"],
                      np.where(ratio > 1.3, p["high_vol_mult"], p["norm_vol_mult"]))
        mults[1] = np.where(np.isfinite(ratio) & (avg > 0), m1, np.nan)
        zm = _sma(atr, int(p["zs_lookback"]))
        zsd = _stdev(atr, int(p["zs_lookback"]))
        with np.errstate(divide="ignore", invalid="ignore"):
            z = (atr - zm) / zsd
        mults[2] = np.where(zsd > 0, base_mult * (1.0 + z * p["zs_sens"]),
                            np.where(np.isnan(zm), np.nan, base_mult))
        mults[3] = np.where(np.isnan(dyn), np.nan, base_mult)
        roc = _roc(c, int(p["roc_lookback"]))
        mults[4] = base_mult * (1.0 + np.abs(roc) * p["roc_sens"] / 100.0)
        hyb_raw = (mults[0] + mults[1] + mults[2] + base_mult + mults[4]) / 5.0
        mults[5] = _ema(hyb_raw, int(p["hyb_smooth"]))
        mults[6] = np.where(np.isnan(atr), np.nan, base_mult)
        atrs = [atr, atr, atr, dyn, atr, atr, atr]

        bpd = int(p["bars_per_day"] or _bars_per_day(out["date"]))
        L = max(1, int(p["perf_lookback_days"]) * bpd)
        cost_frac = float(p.get("sel_cost_pct") or 0.0) / 100.0

        hl2l, cl, pcl = hl2.tolist(), c.tolist(), prev_c.tolist()
        D = np.zeros((NUM_METHODS, n), dtype=np.int8)
        ST = np.full((NUM_METHODS, n), np.nan)
        evals = np.arange(0, n, max(1, int(p["eval_interval_bars"])))
        scores = np.full((NUM_METHODS, len(evals)), -1.0e10)
        allowed = (set(range(NUM_METHODS)) if not p.get("methods")
                   else {METHOD_INDEX[m] for m in p["methods"]})
        for k in range(NUM_METHODS):
            d_k, st_k, fb, fp = _supertrend(hl2l, cl, pcl, mults[k].tolist(),
                                            atrs[k].tolist(), cost_frac)
            D[k], ST[k] = d_k, st_k
            if k not in allowed:
                scores[k] = -np.inf
                continue
            if len(fb) == 0:
                continue
            hi = np.searchsorted(fb, evals, "right")
            lw = np.searchsorted(fb, evals - L, "left")
            cnt = hi - lw
            cs = np.r_[0.0, np.cumsum(fp)]
            tot = cs[hi] - cs[lw]
            cw = np.r_[0, np.cumsum(fp > 0)]
            wins = cw[hi] - cw[lw]
            with np.errstate(divide="ignore", invalid="ignore"):
                if crit == "Total Points":
                    sc = tot
                elif crit == "Win Rate":
                    sc = 100.0 * wins / cnt
                elif crit == "Average Per Trade":
                    sc = tot / cnt
                else:  # Profit Factor
                    gp = np.r_[0.0, np.cumsum(np.where(fp > 0, fp, 0.0))]
                    g = gp[hi] - gp[lw]
                    ls = g - tot
                    sc = np.where(ls > 0, g / ls, 1.0e6)
            scores[k] = np.where(cnt >= int(p["min_trades"]), sc, -1.0e10)

        if p["enable_auto"]:
            best = np.argmax(scores, axis=0)          # ties -> lowest index (source)
            act = np.zeros(n, dtype=np.int64)
            act[evals] = best
            mark = np.zeros(n, dtype=bool)
            mark[evals] = True
            idx = np.where(mark, np.arange(n), 0)
            np.maximum.accumulate(idx, out=idx)
            act = act[idx]
        else:
            act = np.full(n, METHOD_INDEX[p["manual_method"]], dtype=np.int64)

        ar = np.arange(n)
        adir = D[act, ar].astype(int)
        aprev = np.r_[0, D[act[1:], ar[:-1]]].astype(int)
        ast = ST[act, ar]
        amult = mults[act, ar]
        aatr = np.where(act == 3, dyn, atr)

        # filters
        rsi = _rsi(c, int(p["rsi_len"]))
        ml = _ema(c, int(p["macd_fast"])) - _ema(c, int(p["macd_slow"]))
        msig = _ema(ml, int(p["macd_signal"]))
        rsi_b = (rsi > p["rsi_buy"]) if p["enable_rsi"] else np.ones(n, bool)
        rsi_s = (rsi < p["rsi_sell"]) if p["enable_rsi"] else np.ones(n, bool)
        mac_b = (ml > msig) if p["enable_macd"] else np.ones(n, bool)
        mac_s = (ml < msig) if p["enable_macd"] else np.ones(n, bool)
        bull = (aprev == -1) & (adir == 1) & rsi_b & mac_b
        bear = (aprev == 1) & (adir == -1) & rsi_s & mac_s

        # entry gates (extensions; they never block an EXIT)
        gate = np.ones(n, dtype=bool)
        if p.get("entry_start") or p.get("entry_end"):
            t = pd.to_datetime(out["date"])
            tod = (t.dt.hour * 60 + t.dt.minute).to_numpy()
            s0 = _hhmm(p.get("entry_start")) or 0
            s1 = _hhmm(p.get("entry_end"))
            s1 = 24 * 60 if s1 is None else s1
            gate &= (tod >= s0) & (tod <= s1)
        er = _efficiency_ratio(c, int(p["er_len"]))
        if p.get("er_min"):
            gate &= er >= float(p["er_min"])
        adx = None
        if p.get("adx_min"):
            adx = _adx(h, lo, c, int(p["adx_len"]))
            gate &= adx >= float(p["adx_min"])
        if p.get("vol_min") and "volume" in out.columns:
            v = out["volume"].to_numpy(float)
            vavg = _sma(v, int(p["vol_len"]))
            with np.errstate(divide="ignore", invalid="ignore"):
                rv = v / vavg
            has_vol = np.isfinite(vavg) & (vavg > 0)
            gate &= ~has_vol | (rv >= float(p["vol_min"]))

        # TSL distance (computed off the ACTIVE method's ATR, as the source)
        tm = p["tsl_method"]
        if tm == "ATR":
            sld = float(p["tsl_atr_mult"]) * aatr
        elif tm == "Percentage":
            sld = c * float(p["tsl_pct"]) / 100.0
        else:
            sld = np.full(n, float(p["tsl_points"]))

        # live trade state machine (source _update_live_state, signal-before-TSL)
        en_tsl = bool(p["enable_tsl"])
        flip_exit = bool(p.get("exit_on_flip"))
        live = np.zeros(n, dtype=np.int8)
        tsl_arr = np.full(n, np.nan)
        bl, brl, gl, sl_l, adl = bull.tolist(), bear.tolist(), gate.tolist(), sld.tolist(), \
            adir.tolist()
        st_dir = 0
        tsl = None
        for i in range(n):
            ci = cl[i]
            sdist = sl_l[i]
            sdist = None if sdist != sdist else sdist
            old = st_dir
            new = old
            bu, be = bl[i], brl[i]
            if old == 0 and bu and gl[i]:
                new = 1
            if old == 0 and be and gl[i]:
                new = -1
            if old == 1 and be:
                new = -1 if gl[i] else 0
            if old == -1 and bu:
                new = 1 if gl[i] else 0
            if old == 1 and new == 1:
                if en_tsl and tsl is not None and ci < tsl:
                    new = 0
                elif flip_exit and adl[i] == -1:
                    new = 0
            if old == -1 and new == -1:
                if en_tsl and tsl is not None and ci > tsl:
                    new = 0
                elif flip_exit and adl[i] == 1:
                    new = 0
            if new != old:
                st_dir = new
                if new == 0 or sdist is None:
                    tsl = None
                else:
                    tsl = ci - sdist if new == 1 else ci + sdist
            elif st_dir != 0 and sdist is not None:
                cand = ci - sdist if st_dir == 1 else ci + sdist
                if tsl is None or (cand > tsl if st_dir == 1 else cand < tsl):
                    tsl = cand
            live[i] = st_dir
            tsl_arr[i] = tsl if (tsl is not None and en_tsl) else np.nan

        lv = live.astype(int)
        lv_prev = np.r_[0, lv[:-1]]
        e_long = (lv == 1) & (lv_prev != 1)
        e_short = (lv == -1) & (lv_prev != -1)
        # The engine ignores entry flags while a position is open and fills the
        # previous bar's decision at this open, so a stop-and-reverse would be
        # lost: carry the entry ONE bar (only while still in that state) so the
        # reverse fills one bar after the exit.
        long_entry = e_long | (np.r_[False, e_long[:-1]] & (lv == 1))
        short_entry = e_short | (np.r_[False, e_short[:-1]] & (lv == -1))

        # pyramid adds: a faster classic SuperTrend flips back WITH the position
        fdir, _, _, _ = _supertrend(hl2l, cl, pcl, [float(p["add_mult"])] * n,
                                    _rma(tr, int(p["add_atr"])).tolist(), 0.0)
        fdir = fdir.astype(int)
        fprev = np.r_[0, fdir[:-1]]
        long_add = (lv == 1) & (lv_prev == 1) & (fdir == 1) & (fprev == -1)
        short_add = (lv == -1) & (lv_prev == -1) & (fdir == -1) & (fprev == 1)

        warm = np.isfinite(mults).all(axis=0) & np.isfinite(atr) & np.isfinite(dyn)
        if warm.any():
            warm = np.maximum.accumulate(warm)
        out["atr"] = atr
        out["activeST"] = np.where(warm, ast, np.nan)
        out["activeDir"] = adir
        out["activeMethod"] = act
        out["activeMult"] = amult
        out["rsi"] = rsi
        out["macd"] = ml
        out["macdSignal"] = msig
        out["er"] = er
        out["tsl"] = tsl_arr
        out["liveDir"] = lv
        out["bullSignal"] = bull
        out["bearSignal"] = bear
        out["longEntry"] = long_entry.astype(bool)
        out["shortEntry"] = short_entry.astype(bool)
        out["longExit"] = (lv != 1)
        out["shortExit"] = (lv != -1)
        out["longAdd"] = long_add.astype(bool)
        out["shortAdd"] = short_add.astype(bool)
        return out


STRATEGY = AdaptiveSuperTrend()
