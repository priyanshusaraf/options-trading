"""
Expanding Trend Impulse V3 — the single source of truth for the strategy math.
Faithful port of the Pine v5 script (copied verbatim from the repo's strategy.py;
the math is unchanged and remains the only thing that decides direction).

Pine -> Python parity notes:
  * ta.stdev is POPULATION stdev -> .std(ddof=0)   (sample stdev would be wrong)
  * ta.ema seeds like ewm(adjust=False); feed plenty of warmup bars
  * crossover(a,b): a[1] < b and a > b ; crossunder(a,b): a[1] > b and a < b

The strategy is tuned for 15-minute / 30-minute candles only (see config).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_signals(df: pd.DataFrame, ema_length=50, z_length=50,
                    entry_z=1.0, slope_lookback=5) -> pd.DataFrame:
    out = df.copy()
    c = out["close"]

    out["ema"] = c.ewm(span=ema_length, adjust=False).mean()
    out["std"] = c.rolling(z_length).std(ddof=0)                  # population stdev
    out["z"] = np.where(out["std"] > 0, (c - out["ema"]) / out["std"], 0.0)
    out["ema_prev"] = out["ema"].shift(slope_lookback)           # EMA50 N bars ago
    out["slope"] = out["ema"] - out["ema_prev"]

    bull, bear = out["slope"] > 0, out["slope"] < 0
    z, zp = out["z"], out["z"].shift(1)
    out["bull"], out["bear"] = bull, bear

    out["longEntry"] = bull & (zp < entry_z) & (z > entry_z) & (z > zp)
    out["shortEntry"] = bear & (zp > -entry_z) & (z < -entry_z) & (z.abs() > zp.abs())
    out["longExit"] = (z < 0) | bear
    out["shortExit"] = (z > 0) | bull
    return out


def _epoch(t) -> int:
    # IST wall-clock candle -> true instant (see market_hours.ist_epoch). Using
    # pd.Timestamp(...).timestamp() here would treat IST as UTC and shift every
    # chart bar +5:30.
    from app.core.market_hours import ist_epoch
    return ist_epoch(t)


def to_payload(sig: pd.DataFrame, entry_z=1.0) -> dict:
    """Serialize candles + indicators + entry markers + the latest bar's state
    into the JSON shape the frontend chart expects."""
    sig = sig.dropna(subset=["ema", "z", "slope"]).reset_index(drop=True)
    if sig.empty:
        return {"candles": [], "ema": [], "zscore": [], "markers": [],
                "latest": None, "entry_z": entry_z}

    candles, ema, zscore, markers = [], [], [], []
    for _, r in sig.iterrows():
        t = _epoch(r["date"])
        candles.append({"time": t, "open": r["open"], "high": r["high"],
                        "low": r["low"], "close": r["close"]})
        ema.append({"time": t, "value": round(float(r["ema"]), 2)})
        zscore.append({"time": t, "value": round(float(r["z"]), 4)})
        if r["longEntry"]:
            markers.append({"time": t, "position": "belowBar", "color": "#2EBD85",
                            "shape": "arrowUp", "text": "LONG"})
        elif r["shortEntry"]:
            markers.append({"time": t, "position": "aboveBar", "color": "#F6465D",
                            "shape": "arrowDown", "text": "SHORT"})

    last = sig.iloc[-1]
    trend = "bull" if last["slope"] > 0 else ("bear" if last["slope"] < 0 else "flat")
    if bool(last["longEntry"]):
        signal = "LONG_ENTRY"
    elif bool(last["shortEntry"]):
        signal = "SHORT_ENTRY"
    else:
        signal = "NONE"

    latest = {
        "time": _epoch(last["date"]),
        "close": round(float(last["close"]), 2),
        "ema": round(float(last["ema"]), 2),
        "ema_5_ago": round(float(last["ema_prev"]), 2) if pd.notna(last["ema_prev"]) else None,
        "slope": round(float(last["slope"]), 3),
        "z": round(float(last["z"]), 4),
        "z_prev": round(float(sig.iloc[-2]["z"]), 4) if len(sig) >= 2 else None,
        "std": round(float(last["std"]), 4),
        "trend": trend,
        "signal": signal,
        "long_exit": bool(last["longExit"]),
        "short_exit": bool(last["shortExit"]),
    }
    return {"candles": candles, "ema": ema, "zscore": zscore,
            "markers": markers, "latest": latest, "entry_z": entry_z}
