"""Options-path results with each strategy's SHIPPED option_exits policy."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

CELLS = [("spike_fade", "NATGASMINI", "15m"), ("spike_fade", "CRUDEOILM", "15m"),
         ("shock_reversal", "CRUDEOILM", "15m"), ("vwap_band_reversion", "NATGASMINI", "30m"),
         ("gold_month_turn", "GOLDM", "60m")]
for key, inst, tf in CELLS:
    for spread in (0.02, 0.06):
        tr, dropped = rlib.run_premium(get_strategy(key), inst, tf, premium={"premium_spread_pct": spread})
        a, b = rlib.split(tr)
        sa, sb = rlib.summarize(a), rlib.summarize(b)
        avg_cost = sum(t.notional for t in tr) / max(1, len(tr))
        print(f"{key:20s} {inst:10s} {tf} spread {spread:.0%} | IS n={sa['n']} ₹{sa['net']:.0f} pf={sa['pf']} dd={sa['dd']:.0f} "
              f"| OOS n={sb['n']} ₹{sb['net']:.0f} pf={sb['pf']} dd={sb['dd']:.0f} | avg premium/lot ₹{avg_cost:.0f} | dropped {dropped}")
        if spread == 0.02:
            print("     years", rlib.by_year(tr))
