import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import numpy as np, pandas as pd
D = DATA_ROOT
df = pd.read_csv(f"{D}/h1/xauusd_h1.csv")
df.index = pd.to_datetime(df.timestamp, unit="ms") + pd.Timedelta(hours=5, minutes=30)
mins = df.index.hour * 60 + df.index.minute
s = df[(df.index.weekday < 5) & (mins >= 570) & (mins <= 1350)]
g = s.groupby(s.index.date)
day = pd.DataFrame({"o": g.open.first(), "c": g.close.last()})
day.index = pd.to_datetime(day.index)
day["gap"] = (day.o / day.c.shift(1) - 1) * 1e4
day["ins"] = (day.c / day.o - 1) * 1e4
day["wkend"] = day.index.weekday == 0
for lab, m in (("all", day.gap.notna()), ("weekday nights", ~day.wkend), ("weekend (Fri->Mon)", day.wkend)):
    x = day[m]
    print(f"USD gold gap {lab}: mean={x.gap.mean():+.2f} t={x.gap.mean()/x.gap.std()*np.sqrt(x.gap.count()):+.2f}")
print("by year: gap sum vs in-session sum (bps, USD)")
print(pd.DataFrame({"gap": day.gap.groupby(day.index.year).sum().round(0), "in": day.ins.groupby(day.index.year).sum().round(0)}).T.to_string())
# finer: decompose overnight into 23:30-04:30 IST (US afternoon) and 04:30-09:30 (Asia) using raw hourly
r = (df.close / df.open - 1) * 1e4
h = df.index.hour + df.index.minute / 60
seg = pd.cut(h, [0, 4.6, 9.4, 23.4, 24.1], labels=["00:30-04:30 US pm", "04:30-09:30 Asia", "09:30-23:30 MCX", "23:30-00:30"], right=False)
t = pd.DataFrame({"r": r, "seg": seg, "y": df.index.year})
print(t.groupby(["y", "seg"], observed=True)["r"].sum().unstack().round(0).to_string())
