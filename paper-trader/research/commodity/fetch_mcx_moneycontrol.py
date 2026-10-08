"""Fetch REAL MCX futures bars (per contract) from Moneycontrol's public chart API
and stitch a front-month series in the research harness format.

usage: fetch_mcx_moneycontrol.py NATGASMINI|CRUDEOILM  [first YYYY-MM]
Writes DATA_ROOT/mcx_real/raw/<NAME>_<expiry>_{15,60}.json and
       DATA_ROOT/mcx_real/mcx/<NAME>_{15m,60m}.pkl  + <NAME>_rolls.csv
Only recent contracts are served (expired ones are purged after a few months).
No volume field is provided (strategies needing volume fall back to equal weights)."""
import json
import os as _os
import subprocess
import sys
import time

import pandas as pd

HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
OUT = _os.path.join(DATA_ROOT, "mcx_real")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
BD = pd.offsets.BDay()


def fetch(sym, res, frm, to):
    url = (f"https://priceapi.moneycontrol.com/techCharts/commodity/history?symbol={sym}"
           f"&resolution={res}&from={int(frm)}&to={int(to)}")
    for attempt in range(3):
        out = subprocess.run(["curl", "-s", "-A", UA, "--max-time", "40", url],
                             capture_output=True, text=True).stdout
        try:
            return json.loads(out)
        except Exception:
            time.sleep(2 + 3 * attempt)
    return {"s": "bad"}


def predicted_expiry(name, y, m):
    first_next = pd.Timestamp(y, m, 1) + pd.offsets.MonthBegin(1)
    if name in ("GOLDPETAL", "GOLDGUINEA", "GOLDTEN"):
        return first_next - BD                          # last business day of the month
    if name == "GOLDM":
        d5 = pd.Timestamp(y, m, 5)                      # the 5th (previous bd if a holiday/weekend)
        return d5 if d5.weekday() < 5 else d5 - BD
    if name.startswith("NAT"):
        return first_next - 4 * BD                      # NYMEX NG expiry − 1 business day
    d25 = pd.Timestamp(y, m, 25)                        # WTI: 3 (or 4) bd before the 25th
    nymex = d25 - (3 if d25.weekday() < 5 else 4) * BD
    return nymex - BD


def find_contract(name, y, m):
    p = predicted_expiry(name, y, m)
    for k in (0, -1, 1, -2, 2):
        d = p + k * BD
        sym = f"{name}_{d:%Y-%m-%d}_MCX"
        j = fetch(sym, "1D", (d - pd.Timedelta(days=210)).timestamp(), (d + pd.Timedelta(days=2)).timestamp())
        if j.get("s") == "ok" and j.get("t"):
            return d, sym
        time.sleep(0.5)
    return None, None


def to_frame(j, minutes=15):
    # Moneycontrol stamps a bar with its END time (09:15 = the 09:00-09:15 bar; the
    # winter 23:45-23:55 bar is stamped 00:00 of the next day). Re-stamp by START,
    # as Kite and the platform do.
    df = pd.DataFrame({"open": j["o"], "high": j["h"], "low": j["l"], "close": j["c"],
                       "volume": j.get("v") or [0.0] * len(j["t"])},
                      index=pd.to_datetime(j["t"], unit="s") + pd.Timedelta(hours=5, minutes=30)
                      - pd.Timedelta(minutes=minutes))
    df.index.name = "date"
    df = df.dropna(subset=["open", "high", "low", "close"])        # the API returns some empty bars
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    return df[~df.index.duplicated(keep="last")].sort_index()


def main(name, first="2025-01"):
    raw = _os.path.join(OUT, "raw")
    _os.makedirs(raw, exist_ok=True)
    _os.makedirs(_os.path.join(OUT, "mcx"), exist_ok=True)
    contracts = []
    now = pd.Timestamp.now()
    for per in pd.period_range(first, (now + pd.DateOffset(months=2)).strftime("%Y-%m"), freq="M"):
        d, sym = find_contract(name, per.year, per.month)
        print(per, sym, flush=True)
        if sym:
            contracts.append((d, sym))
    frames = {}
    for d, sym in contracts:
        for res in ("15",):
            f = _os.path.join(raw, f"{sym}_{res}.json")
            if not _os.path.exists(f):
                j = fetch(sym, res, (d - pd.Timedelta(days=210)).timestamp(), min(d + pd.Timedelta(days=2), now).timestamp())
                json.dump(j, open(f, "w"))
                time.sleep(0.5)
            j = json.load(open(f))
            if j.get("s") == "ok":
                fr = to_frame(j)
                sys.path.insert(0, HERE)
                from build_dataset import mcx_session_mask
                frames[(sym, res)] = fr[mcx_session_mask(fr.index)]
    for res, tf in (("15", "15m"),):
        parts, rolls, prev_last = [], [], None
        start = None
        for i, (d, sym) in enumerate(contracts):
            df = frames.get((sym, res))
            if df is None or df.empty:
                continue
            # front month: use this contract until the session before its expiry day
            end = pd.Timestamp(d.date())
            seg = df[(df.index < end) if start is None else ((df.index >= start) & (df.index < end))]
            if seg.empty:
                continue
            if prev_last is not None:
                # roll gap = the CONTRACT SPREAD at the switch: both contracts trade side
                # by side, so compare their closes on the last COMMON bar before it
                old_df, old_end = prev_last
                common = old_df.index[(old_df.index < seg.index[0])].intersection(df.index)
                if len(common):
                    t = common[-1]
                    gap = float(df.close.loc[t] / old_df.close.loc[t] - 1)
                    rolls.append((seg.index[0], t, seg.index[0], gap,
                                  float(df.close.loc[t] - old_df.close.loc[t])))
            parts.append(seg)
            prev_last = (df, end)
            start = end
        if not parts:
            print("no data for", tf)
            continue
        cont = pd.concat(parts)
        cont = cont[~cont.index.duplicated(keep="last")].sort_index()
        cont.to_pickle(_os.path.join(OUT, "mcx", f"{name}_{tf}.pkl"))
        pd.DataFrame(rolls, columns=["ist", "last_before", "first_after", "gap_pct", "gap_pts"]).to_csv(
            _os.path.join(OUT, "mcx", f"{name}_rolls.csv"), index=False)
        print(name, tf, len(cont), cont.index.min(), "->", cont.index.max(), "rolls", len(rolls))
    # 30m/60m bars built from 15m, anchored at 09:00 IST (Kite's MCX convention);
    # the harness reads <NAME>_5m.pkl for roll pricing — reuse the 15m frame
    p15 = _os.path.join(OUT, "mcx", f"{name}_15m.pkl")
    if _os.path.exists(p15):
        d15 = pd.read_pickle(p15)
        d15.to_pickle(_os.path.join(OUT, "mcx", f"{name}_5m.pkl"))
        sys.path.insert(0, HERE)
        from build_dataset import resample
        for m in (30, 60):
            resample(d15, m).rename_axis("date").to_pickle(_os.path.join(OUT, "mcx", f"{name}_{m}m.pkl"))


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:3] or []))
