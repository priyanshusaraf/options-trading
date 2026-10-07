import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys, numpy as np, pandas as pd
sys.path.insert(0, _os.path.abspath(_os.path.join(HERE, "..", "..", "backend")))
from app.strategy.ta import session_vwap, rsi
D = _os.path.join(DATA_ROOT, "mcx")
name, side = sys.argv[1], sys.argv[2]
df = pd.read_pickle(f"{D}/{name}_15m.pkl").reset_index()
df["vw"] = session_vwap(df); df["r"] = rsi(df.close); df["day"] = df.date.dt.date
rolls = set()
try:
    rolls = set(pd.read_csv(f"{D}/{name}_rolls.csv", parse_dates=["first_after"]).first_after.dt.date)
except FileNotFoundError: pass
days = list(df.groupby("day"))
res = []
for (d0, g0), (d1, g1) in zip(days[:-1], days[1:]):
    if d1 in rolls or len(g0) < 20 or len(g1) < 10: continue
    for k in (1, 2, 3):
        sig = g0.iloc[-k - 1]          # signal bar (state at its close)
        ent = g0.open.iloc[-k]         # fill at next bar open
        for j in (0, 1, 2, 4, 8):
            ex = g1.open.iloc[j]
            res.append(dict(d=pd.Timestamp(d0), k=k, j=j, r=sig.r, above=sig.close > sig.vw,
                            ret=(ex / ent - 1) * 1e4))
x = pd.DataFrame(res)
x["per"] = np.where(x.d < "2024-01-01", "IS", "OOS")
cond = (x.r > 60) if side == "long" else (x.r < 40)
sgn = 1 if side == "long" else -1
t = x[cond].assign(p=lambda z: sgn * z.ret).groupby(["k", "j", "per"])["p"].agg(["count", "mean", "std"])
t["t"] = t["mean"] / t["std"] * np.sqrt(t["count"])
print(name, side, "(entry at open of k-th last bar; exit at open of next-session bar j) bps, before cost")
print(t[["count", "mean", "t"]].round(2).unstack("per").to_string())
