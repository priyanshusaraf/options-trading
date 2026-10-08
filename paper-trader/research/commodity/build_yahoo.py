"""Build an INDEPENDENT cross-check dataset from Yahoo Finance 60m futures bars
(real NYMEX prints + real exchange volume; ~2 years of history). Same pipeline as
build_dataset.py: roll detection at the daily reopen, USDINR interpolated across
Indian FX hours, MCX-session filter. Bars are IST :30-aligned (Yahoo hours).

usage: build_yahoo.py NG=F:NATGASMINI CL=F:CRUDEOILM   (reads DATA_ROOT/yahoo/<sym>_60m.json)
writes DATA_ROOT/yahoo_mcx/<NAME>_60m.pkl and <NAME>_rolls.csv
"""
import json
import os as _os
import sys

import numpy as np
import pandas as pd

HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_dataset import DATA_ROOT, fx_rate, roll_adjust  # noqa: E402

OUT = _os.path.join(DATA_ROOT, "yahoo_mcx")
# USD quote -> MCX quote unit (same factors as build_dataset.SPECS)
UNIT_FACTOR = {"SILVERMIC": 1.06 * 32.1507, "GOLDPETAL": 1.06 / 31.1035}


def load(sym: str) -> pd.DataFrame:
    j = json.load(open(_os.path.join(DATA_ROOT, "yahoo", f"{sym}_60m.json")))["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")},
                      index=pd.to_datetime(j["timestamp"], unit="s")).dropna()
    return df[~df.index.duplicated(keep="last")].sort_index()


def nymex_expiries(sym: str, start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    """Last trading day of each front contract (US business days, holidays ignored).
    NG: 3 business days before the 1st of the delivery month.
    CL: 3 business days before the 25th of the prior month (4 if the 25th is not a
    business day)."""
    bd = pd.offsets.BDay()
    out = []
    for m in pd.period_range(start, end, freq="M"):
        if sym.startswith(("SI", "GC")):
            # COMEX metals: Yahoo moves to the next ACTIVE month around first notice
            # (last business day of the month before delivery). Silver actives:
            # Mar/May/Jul/Sep/Dec; gold: Feb/Apr/Jun/Aug/Oct/Dec.
            actives = (3, 5, 7, 9, 12) if sym.startswith("SI") else (2, 4, 6, 8, 10, 12)
            if (m + 1).month in actives:
                out.append((m + 1).to_timestamp() - bd)
            continue
        if sym.startswith("NG"):
            first_of_delivery = (m + 1).to_timestamp()
            out.append(first_of_delivery - 3 * bd)
        else:
            d25 = m.to_timestamp() + pd.Timedelta(days=24)
            k = 3 if d25.weekday() < 5 else 4
            out.append(d25 - k * bd)
    return out


def calendar_rolls(df: pd.DataFrame, sym: str, min_gap: float = 0.005) -> list:
    """Around each expiry (−1 … +2 business days) the largest |open/prev close − 1|
    is taken as the contract switch in Yahoo's continuous series."""
    g = df["open"] / df["close"].shift(1) - 1.0
    rolls = []
    for e in nymex_expiries(sym, df.index.min(), df.index.max()):
        lo = 4 if sym.startswith(("SI", "GC")) else 1     # metals switch a few days early
        w = g[(g.index >= e - lo * pd.offsets.BDay()) & (g.index < e + 3 * pd.offsets.BDay())].dropna()
        if len(w) and abs(w).max() >= min_gap:
            t = w.abs().idxmax()
            rolls.append((t, float(w.loc[t])))
    return rolls


def back_adjust(df: pd.DataFrame, rolls: list) -> pd.DataFrame:
    adj = pd.Series(1.0, index=df.index)
    for t, gp in rolls:
        adj[df.index < t] *= (1.0 + gp)
    out = df.copy()
    for c in ("open", "high", "low", "close"):
        out[c] = out[c] * adj
    return out


def build(sym: str, name: str) -> None:
    df = load(sym)
    # Yahoo's contract switch can fall INSIDE the MCX session, so detection-only
    # (as for Dukascopy) would leave fake shocks in the signals: back-adjust instead.
    # Ratio back-adjustment rescales older rupee levels a little — compare profit
    # factor / return per trade on this set, not absolute rupees.
    rolls = calendar_rolls(df, sym)
    df = back_adjust(df, rolls)
    print(sym, "calendar rolls:", [(str(t)[:16], round(g * 100, 2)) for t, g in rolls])
    rolls = []
    df.index = df.index + pd.Timedelta(hours=5, minutes=30)
    rate = fx_rate(df.index) * UNIT_FACTOR.get(name, 1.0)
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].to_numpy() * rate
    mins = df.index.hour * 60 + df.index.minute
    df = df[(df.index.weekday < 5) & (mins >= 9 * 60 + 30) & (mins <= 22 * 60 + 30)]
    df.index.name = "date"
    _os.makedirs(OUT, exist_ok=True)
    df.to_pickle(_os.path.join(OUT, f"{name}_60m.pkl"))
    rr = []
    for t, gp in rolls:
        ti = t + pd.Timedelta(hours=5, minutes=30)
        before, after = df[df.index < ti], df[df.index >= ti]
        if len(before) and len(after):
            rr.append((ti, before.index[-1], after.index[0], gp,
                       float(after.open.iloc[0] - before.close.iloc[-1])))
    pd.DataFrame(rr, columns=["ist", "last_before", "first_after", "gap_pct", "gap_pts"]).to_csv(
        _os.path.join(OUT, f"{name}_rolls.csv"), index=False)
    print(name, len(df), df.index.min(), df.index.max(), "rolls", len(rr))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        s, n = arg.split(":")
        build(s, n)
