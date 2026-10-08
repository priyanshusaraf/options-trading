"""Real-MCX validation: the strategies on REAL MCX futures prints (Moneycontrol, per
contract, stitched front-month; fetch_mcx_moneycontrol.py) vs the proxy over the SAME
window. Run once per data root (COMMODITY_DATA → mcx/ = mcx_real or the proxy)."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

START = {"NATGASMINI": "2025-11-25", "CRUDEOILM": "2025-12-19"}
CELLS = [("spike_fade", "NATGASMINI", "15m"), ("spike_fade", "CRUDEOILM", "15m"),
         ("shock_reversal", "CRUDEOILM", "15m"), ("vwap_band_reversion", "NATGASMINI", "30m"),
         ("vwap_slope_divergence", "NATGASMINI", "30m"), ("adaptive_supertrend", "NATGASMINI", "15m"),
         ("vol_squeeze_breakout", "NATGASMINI", "60m"), ("trend_impulse_v3", "NATGASMINI", "15m"),
         ("trend_impulse_v3", "CRUDEOILM", "15m")]
f = rlib.frame("NATGASMINI", "15m")
f = f[f.index >= START["NATGASMINI"]]
print(f"NATGASMINI bars {len(f)} from {f.index.min()} close {f.close.iloc[0]:.1f} -> {f.close.iloc[-1]:.1f}")
for key, inst, tf in CELLS:
    s = get_strategy(key)
    tr, _ = rlib.run(s, inst, tf, start=START[inst])
    a = rlib.summarize(tr)
    po, _ = rlib.run_premium(s, inst, tf, start=START[inst], premium={"premium_spread_pct": 0.04})
    b = rlib.summarize(po)
    print(f"{key:22s} {inst:10s} {tf} | futures n={a['n']:3d} ₹{a['net']:>8,.0f} pf={a['pf']} "
          f"| options n={b['n']:3d} ₹{b['net']:>8,.0f} pf={b['pf']}")
