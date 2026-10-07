import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys, numpy as np, pandas as pd
D = _os.path.join(DATA_ROOT, "mcx")
name = sys.argv[1]
df = pd.read_pickle(f"{D}/{name}_60m.pkl")
same = pd.Series(df.index.date, index=df.index)
r = (df.close / df.open - 1) * 1e4          # in-bar return
gap = (df.open / df.close.shift(1) - 1) * 1e4
gap = gap.where(same != same.shift(1))       # overnight gap (session open vs prev session close)
try:
    rr = pd.read_csv(f"{D}/{name}_rolls.csv", parse_dates=["first_after"])
    gap = gap.drop(index=[t for t in rr.first_after if t in gap.index], errors="ignore")
except FileNotFoundError:
    pass
t = pd.DataFrame({"r": r, "h": df.index.hour, "y": df.index.year})
print(f"== {name} mean in-bar return by IST hour (bps) per period; t-stat")
out = {}
for per, m in (("19-21", t.y <= 2021), ("22-23", (t.y >= 2022) & (t.y <= 2023)), ("24-26", t.y >= 2024)):
    g = t[m].groupby("h")["r"]
    out[per] = (g.mean()).round(1)
    out[per + "_t"] = (g.mean() / g.std() * np.sqrt(g.count())).round(1)
print(pd.DataFrame(out).to_string())
for per, m in (("19-21", gap.index.year <= 2021), ("22-23", (gap.index.year >= 2022) & (gap.index.year <= 2023)), ("24-26", gap.index.year >= 2024)):
    x = gap[m].dropna()
    print(f"overnight gap {per}: mean={x.mean():+.1f} t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} n={len(x)}")
x = t.groupby("y")["r"].sum().round(0)
print("in-session sum by year", x.to_dict())
print("gap sum by year", gap.groupby(gap.index.year).sum().round(0).to_dict())
