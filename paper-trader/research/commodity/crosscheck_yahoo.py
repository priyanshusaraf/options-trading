"""Cross-check: the same strategies on Yahoo NYMEX 60m bars (real exchange prints,
real volume) vs the Dukascopy proxy, over the SAME window (Yahoo's ~2y history).
Run twice: COMMODITY_DATA=<dukascopy root> and COMMODITY_DATA=<yahoo root>."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

START = "2024-05-16"
CELLS = [("spike_fade", "NATGASMINI"), ("spike_fade", "CRUDEOILM"), ("shock_reversal", "CRUDEOILM"),
         ("vwap_band_reversion", "NATGASMINI"), ("vwap_slope_divergence", "NATGASMINI"),
         ("adaptive_supertrend", "NATGASMINI"), ("vol_squeeze_breakout", "NATGASMINI"),
         ("trend_impulse_v3", "NATGASMINI")]
for key, inst in CELLS:
    tr, _ = rlib.run(get_strategy(key), inst, "60m", start=START)
    s = rlib.summarize(tr)
    ret = np.array([t.net_pnl / t.notional for t in tr]) * 1e4 if tr else np.array([0.0])
    print(f"{key:22s} {inst:10s} n={s['n']:3d} net=₹{s['net']:>8.0f} pf={s['pf']} "
          f"mean net/trade={ret.mean():+6.1f} bps  years={rlib.by_year(tr)}")
