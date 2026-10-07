"""Gold overnight carry with correct timing (USD, hourly, IST :30 bars).
signal = state at CLOSE of the 21:30 bar (ends 22:30); entry = 22:30 bar OPEN;
exit = next session's 09:30 (j=0) / 10:30 (j=1) / 11:30 (j=2) bar OPEN."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys, numpy as np, pandas as pd
sys.path.insert(0, _os.path.abspath(_os.path.join(HERE, "..", "..", "backend")))
from app.strategy.ta import rsi, atr
D = DATA_ROOT
sym = sys.argv[1] if len(sys.argv) > 1 else "xauusd"
df = pd.read_csv(f"{D}/h1/{sym}_h1.csv")
df.index = pd.to_datetime(df.timestamp, unit="ms") + pd.Timedelta(hours=5, minutes=30)
df = df[["open", "high", "low", "close", "volume"]]
df["rsi"] = rsi(df.close, 14)
df["ema"] = df.close.ewm(span=100, adjust=False).mean()
mins = df.index.hour * 60 + df.index.minute
s = df[(df.index.weekday < 5) & (mins >= 570) & (mins <= 1350)].copy()
s["day"] = s.index.date
rows = []
days = list(s.groupby("day"))
for (d0, g0), (d1, g1) in zip(days[:-1], days[1:]):
    if len(g0) < 12 or len(g1) < 3: continue
    sig = g0.iloc[-2]; ent = g0.open.iloc[-1]
    day_ret = (sig.close / g0.open.iloc[0] - 1) * 1e4
    rows.append(dict(d=pd.Timestamp(d0), wd=pd.Timestamp(d0).weekday(), dret=day_ret, rsi=sig.rsi,
                     above_ema=sig.close > sig.ema,
                     **{f"j{j}": (g1.open.iloc[j] / ent - 1) * 1e4 for j in (0, 1, 2)}))
x = pd.DataFrame(rows)
x["per"] = np.where(x.d < "2024-01-01", "IS", "OOS")
def show(lab, m, col="j0"):
    out = []
    for per in ("IS", "OOS"):
        y = x[(x.per == per) & m][col].dropna()
        out.append(f"{per}: n={len(y):4d} mean={y.mean():+6.2f} t={y.mean()/y.std()*np.sqrt(len(y)):+.2f}")
    print(f"  {lab:30s} " + " | ".join(out))
print(sym, "overnight long (bps, before costs)")
for j in ("j0", "j1", "j2"): show(f"all, exit {j}", x.j0.notna(), j)
show("day down (dret<0)", x.dret < 0); show("day up (dret>0)", x.dret > 0)
show("day down < -50bps", x.dret < -50); show("day up > +50bps", x.dret > 50)
show("RSI<45", x.rsi < 45); show("RSI>55", x.rsi > 55)
show("above EMA100", x.above_ema); show("below EMA100", ~x.above_ema)
for w in range(5): show(f"weekday {w} (Fri=weekend)", x.wd == w)
show("Fri only (weekend)", x.wd == 4); show("Mon-Thu", x.wd < 4)
show("above EMA & day down", x.above_ema & (x.dret < 0))
