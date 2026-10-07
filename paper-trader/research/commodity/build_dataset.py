"""Build MCX-proxy OHLCV datasets from Dukascopy 5m bars.

- back-adjusts futures-CFD roll gaps (NG, WTI) at the daily reopen
- converts to INR per MCX quote unit with daily USDINR (Yahoo INR=X)
- keeps only MCX session bars (09:00 IST -> 23:30 IST in US-DST, 23:55 otherwise)
- writes IST-naive 5m/15m/30m/60m parquet files
"""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import glob, json, sys
import numpy as np, pandas as pd

D = DATA_ROOT
import os
OUT = _os.path.join(DATA_ROOT, "mcx")

# (dukascopy symbol, MCX name, unit factor: INR price = usd * usdinr * factor, roll-adjust?)
SPECS = {
    "gascmdusd":   ("NATGASMINI", 1.0, True),                 # Rs / mmBtu
    "lightcmdusd": ("CRUDEOILM", 1.0, True),                  # Rs / bbl
    "xauusd":      ("GOLDPETAL", 1.06 / 31.1035, False),      # Rs / gram (incl ~6% duty premium)
    "xagusd":      ("SILVERMIC", 1.06 * 32.1507, False),      # Rs / kg
}


def usdinr() -> pd.Series:
    j = json.load(open(f"{D}/yahoo/INR=X_1d.json"))["chart"]["result"][0]
    s = pd.Series(j["indicators"]["quote"][0]["close"],
                  index=pd.to_datetime(j["timestamp"], unit="s")).dropna()
    # Yahoo stamps the INR=X daily bar at 23:00 UTC of the PREVIOUS day (London
    # midnight) — shift so the index is the trading date the close belongs to.
    s.index = (s.index + pd.Timedelta(hours=2)).normalize()
    s = s[~s.index.duplicated(keep="last")]
    # drop obvious bad prints
    s = s[(s > 60) & (s < 120)]
    return s


def fx_rate(ist: pd.DatetimeIndex) -> np.ndarray:
    """USDINR at each IST timestamp: the previous day's close before 09:00 IST,
    moving linearly to the day's close across Indian FX hours (09:00 -> 17:00),
    the day's close after 17:00. Keeps rupee drift OUT of the overnight gap."""
    fx = usdinr()
    days = pd.DatetimeIndex(ist.normalize())
    allday = pd.date_range(min(days.min(), fx.index.min()), days.max(), freq="D")
    fxc = fx.reindex(allday).ffill().bfill()
    cur = fxc.reindex(days).to_numpy()
    prev = fxc.shift(1).bfill().reindex(days).to_numpy()
    m = (ist.hour * 60 + ist.minute).to_numpy()
    w = np.clip((m - 540) / 480.0, 0.0, 1.0)
    return prev + (cur - prev) * w


def load_raw(sym: str) -> pd.DataFrame:
    parts = []
    for f in sorted(glob.glob(f"{D}/raw/{sym}/*.csv")):
        d = pd.read_csv(f)
        if len(d):
            parts.append(d)
    df = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp")
    df["utc"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("utc")[["open", "high", "low", "close", "volume"]]
    # drop flat/zero-volume filler bars
    df = df[~((df.high == df.low) & (df.volume == 0))]
    return df


def roll_adjust(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Back-adjust roll gaps. A roll candidate is the first bar after a >=45min
    data gap on a WEEKDAY reopen (not the Sunday open), day-of-month 14..30,
    |gap| >= 1.5%. Per calendar month keep only the largest candidate."""
    prev_close = df["close"].shift(1)
    dt = df.index.to_series().diff()
    gap = df["open"] / prev_close - 1.0
    reopen = dt >= pd.Timedelta(minutes=45)
    weekday_reopen = reopen & (dt < pd.Timedelta(hours=12))   # daily break, not weekend
    cand = weekday_reopen & (df.index.day >= 14) & (gap.abs() >= 0.015)
    c = pd.DataFrame({"gap": gap[cand]})
    c["ym"] = c.index.to_period("M")
    rolls = []
    for _, g in c.groupby("ym"):
        i = g["gap"].abs().idxmax()
        rolls.append((i, float(g.loc[i, "gap"])))
    adj = pd.Series(1.0, index=df.index)
    for t, gp in rolls:
        # prices BEFORE the roll are scaled by (1+gap) so the series is continuous
        adj[df.index < t] *= (1.0 + gp)
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = out[col] * adj
    return out, rolls


def mcx_session_mask(ist_index: pd.DatetimeIndex) -> np.ndarray:
    ny = (ist_index.tz_localize("Asia/Kolkata").tz_convert("America/New_York"))
    dst = np.array([bool(t.dst()) for t in ny])
    mins = ist_index.hour * 60 + ist_index.minute
    close_min = np.where(dst, 23 * 60 + 30, 23 * 60 + 55)
    wd = ist_index.weekday < 5
    return wd & (mins >= 9 * 60) & (mins < close_min)


def resample(df5: pd.DataFrame, minutes: int) -> pd.DataFrame:
    # bars anchored at 09:00 IST of each session (matches Kite MCX candles)
    g = df5.groupby(df5.index.date)
    out = []
    for day, d in g:
        origin = pd.Timestamp(day) + pd.Timedelta(hours=9)
        r = d.resample(f"{minutes}min", origin=origin, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna(subset=["open"])
        out.append(r)
    return pd.concat(out)


def build(sym: str):
    name, factor, do_roll = SPECS[sym]
    df = load_raw(sym)
    rolls = []
    if do_roll:
        # detect only — prices stay at their TRUE level (P&L in real rupees); the
        # harness removes roll-gap P&L from any trade held across a roll.
        _, rolls = roll_adjust(df)
    ist = df.index + pd.Timedelta(hours=5, minutes=30)
    df.index = ist
    rate = fx_rate(ist)
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].to_numpy() * rate * factor
    df = df[mcx_session_mask(df.index)]
    df.index.name = "date"
    df.to_pickle(f"{OUT}/{name}_5m.pkl")
    for m in (15, 30, 60):
        resample(df, m).rename_axis("date").to_pickle(f"{OUT}/{name}_{m}m.pkl")
    print(name, len(df), df.index.min(), df.index.max(), "rolls:", len(rolls),
          "close range", round(df.close.min(), 2), round(df.close.max(), 2))
    if rolls:
        rr = []
        for t, gp in rolls:
            ti = t + pd.Timedelta(hours=5, minutes=30)
            after = df[df.index >= ti]
            before = df[df.index < ti]
            if len(after) and len(before):
                # gap in INR between the last session bar before and first after
                rr.append((ti, before.index[-1], after.index[0], gp,
                           float(after.open.iloc[0] - before.close.iloc[-1])))
        pd.DataFrame(rr, columns=["ist", "last_before", "first_after", "gap_pct", "gap_pts"]
                     ).to_csv(f"{OUT}/{name}_rolls.csv", index=False)


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    for s in (sys.argv[1:] or SPECS):
        build(s)
