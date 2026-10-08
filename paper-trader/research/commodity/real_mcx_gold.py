"""gold_month_turn on REAL MCX GOLDPETAL prints vs the proxy, same window."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

START = "2025-12-01"
s = get_strategy("gold_month_turn")
f = rlib.frame("GOLDPETAL", "15m")
f = f[f.index >= START]
print(f"GOLDPETAL {f.index.min()} -> {f.index.max()}  ₹{f.close.iloc[0]:,.0f} -> ₹{f.close.iloc[-1]:,.0f}")
for inst in ("GOLDPETAL", "GOLDM"):
    for tf in ("15m", "60m"):
        tr, _ = rlib.run(s, inst, tf, start=START)
        a = rlib.summarize(tr)
        line = f"{inst:9s} {tf} futures n={a['n']} ₹{a['net']:,.0f} pf={a['pf']} wr={a['wr']}"
        if inst == "GOLDM":
            po, _ = rlib.run_premium(s, inst, tf, start=START, premium={"premium_spread_pct": 0.04})
            b = rlib.summarize(po)
            line += f" | options n={b['n']} ₹{b['net']:,.0f} pf={b['pf']}"
        print(line, "| per trade:", [round(t.net_pnl) for t in tr])
