"""Independent checks of gold_month_turn: (1) reproduce through the engine,
(2) subtract MCX futures carry (spot proxy overstates a futures long by ~r/365 per
calendar day held), (3) the same calendar event on 2005-2018 daily USD gold —
data never used in this research."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

CARRY_PER_DAY = 0.065 / 365          # INR gold futures premium decays toward spot
S = get_strategy("gold_month_turn")
for inst in ("GOLDPETAL", "GOLDM"):
    for tf in ("15m", "60m"):
        tr, _ = rlib.run(S, inst, tf)
        adj = []
        for t in tr:
            days = (t.exit_time - t.entry_time) / 86400.0
            sgn = 1.0 if t.direction == "LONG" else -1.0
            adj.append(t.net_pnl - sgn * CARRY_PER_DAY * days * t.notional)
        a, b = rlib.split(tr)
        cut = len(a)
        ai, bo = np.array(adj[:cut]), np.array(adj[cut:])
        sa, sb = rlib.summarize(a), rlib.summarize(b)
        print(f"{inst:9s} {tf}: IS n={sa['n']} ₹{sa['net']:.0f} pf={sa['pf']} | OOS n={sb['n']} ₹{sb['net']:.0f} pf={sb['pf']}"
              f" || carry-adjusted IS ₹{ai.sum():.0f} OOS ₹{bo.sum():.0f}"
              f" | avg hold {np.mean([(t.exit_time - t.entry_time) / 86400 for t in tr]):.1f} cal. days")

# (3) unseen period, daily USD bars
D = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
f = _os.path.join(D, "d1", "xauusd_d1.csv")
if _os.path.exists(f):
    d = pd.read_csv(f)
    d.index = pd.to_datetime(d.timestamp, unit="ms")
    d = d[d.index.weekday < 5]
    ym = d.index.to_period("M")
    rows = []
    months = sorted(set(ym))
    for m0, m1 in zip(months[:-1], months[1:]):
        last = d[ym == m0].iloc[-1]
        nxt = d[ym == m1]
        if len(nxt) < 3:
            continue
        rows.append((m0.year, (nxt.open.iloc[2] / last.close - 1) * 1e4,
                     (nxt.index[2] - last.name).days))
    ev = pd.DataFrame(rows, columns=["y", "bps", "days"])
    # benchmark: every same-length window (close of day i -> open of day i+3)
    c, o = d.close.to_numpy(), d.open.to_numpy()
    rnd = (o[3:] / c[:-3] - 1) * 1e4
    print(f"\n2005-2018 USD daily: month-turn n={len(ev)} mean {ev.bps.mean():+.1f} bps "
          f"t={ev.bps.mean() / ev.bps.std() * np.sqrt(len(ev)):+.2f} win {np.mean(ev.bps > 0):.0%} | "
          f"all same-length windows mean {rnd.mean():+.1f} bps | excess {ev.bps.mean() - rnd.mean():+.1f} bps")
    for lo, hi in ((2005, 2011), (2012, 2018)):
        x = ev[(ev.y >= lo) & (ev.y <= hi)].bps
        print(f"   {lo}-{hi}: n={len(x)} mean {x.mean():+.1f} t={x.mean() / x.std() * np.sqrt(len(x)):+.2f}")
    print("   by year:", ev.groupby("y").bps.sum().round(0).astype(int).to_dict())
