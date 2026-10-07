import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys, numpy as np, pandas as pd
D = _os.path.join(DATA_ROOT, "mcx")
name = sys.argv[1]
df = pd.read_pickle(f"{D}/{name}_15m.pkl")
d = df.groupby(df.index.date).agg(open=("open", "first"), close=("close", "last"), high=("high", "max"), low=("low", "min"))
d.index = pd.to_datetime(d.index)
try:
    rr = pd.read_csv(f"{D}/{name}_rolls.csv", parse_dates=["first_after"])
    adj = pd.Series(1.0, index=d.index)
    for _, x in rr.iterrows(): adj[d.index < x.first_after.normalize()] *= (1 + x.gap_pct)
    for c in ("open", "close", "high", "low"): d[c] = d[c] * adj
except FileNotFoundError: pass
r = np.log(d.close / d.close.shift(1))            # close-to-close (incl. overnight)
rin = np.log(d.close / d.open)                   # in-session
sd = r.rolling(60).std().shift(1)
z = r / sd
zin = rin / rin.rolling(60).std().shift(1)
for lab, zz in (("close-to-close z", z), ("in-session z", zin)):
    for thr in (1.5, 2.0, 2.5):
        for side, m in (("up", zz > thr), ("down", zz < -thr)):
            out = []
            for per, pm in (("IS", d.index < "2024"), ("OOS", d.index >= "2024")):
                for h in (1, 3):
                    # next h days: from NEXT open to close h days later
                    fwd = (d.close.shift(-h) / d.open.shift(-1) - 1) * 1e4
                    x = fwd[m & pm].dropna()
                    out.append(f"{per} h{h}: n={len(x):3d} {x.mean():+6.0f}bps t={x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 else 0:+.2f}")
            print(f"{name} {lab} {side} >{thr}: " + " | ".join(out))
