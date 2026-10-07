"""Per-year detail, regime attribution and a combined 1-lot-each portfolio of the
strategies that passed IS and OOS (run after final_eval.py)."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
import numpy as np, pandas as pd, rlib
from app.strategy.registry import get_strategy
from regime_attrib import regime_table

BOOK = [("shock_reversal", "CRUDEOILM", "60m"), ("spike_fade", "NATGASMINI", "60m"),
        ("vwap_band_reversion", "NATGASMINI", "30m"), ("spike_fade", "CRUDEOILM", "60m"),
        ("vwap_slope_divergence", "NATGASMINI", "30m"), ("session_gap_carry", "GOLDM", "15m"),
        ("adaptive_supertrend", "GOLDPETAL", "30m")]
daily = {}
for key, inst, tf in BOOK:
    S = get_strategy(key)
    tr, _ = rlib.run(S, inst, tf)
    print(f"== {key} {inst} {tf} years:", rlib.by_year(tr))
    holds = [t.bars_held for t in tr]
    print(f"   trades={len(tr)} median bars held={np.median(holds):.0f}  avg net/trade=₹{np.mean([t.net_pnl for t in tr]):.0f}  "
          f"avg charges/trade=₹{np.mean([t.charges for t in tr]):.0f}")
    t, share = regime_table(S, inst, tf)
    print(t.round(0).to_string())
    s = pd.Series([x.net_pnl for x in tr], index=pd.to_datetime([x.exit_time for x in tr], unit="s").normalize())
    daily[f"{key}:{inst}"] = s.groupby(level=0).sum()
BOOKS = {
    # pre-declared: each instrument's own in-sample choice
    "CORE A (pre-declared)": ["shock_reversal:CRUDEOILM", "spike_fade:NATGASMINI",
                              "vwap_band_reversion:NATGASMINI"],
    # crude leg swapped to spike_fade AFTER seeing its out-of-instrument result
    "CORE B (post-hoc crude leg)": ["spike_fade:CRUDEOILM", "spike_fade:NATGASMINI",
                                    "vwap_band_reversion:NATGASMINI"],
}
for name, core in BOOKS.items():
    d = pd.DataFrame({k: daily[k] for k in core}).fillna(0.0)
    d = d.reindex(pd.bdate_range(d.index.min(), d.index.max()), fill_value=0.0)
    tot = d.sum(axis=1)
    for per, m in (("IS", tot.index < "2024"), ("OOS", tot.index >= "2024")):
        x = tot[m]; eq = x.cumsum(); dd = (eq.cummax() - eq).max()
        print(f"{name} {per}: net ₹{x.sum():.0f}  daily Sharpe {x.mean()/x.std()*np.sqrt(252):.2f}  maxDD ₹{dd:.0f}")
    print(f"{name} by year:", tot.groupby(tot.index.year).sum().round(0).to_dict())
    print("pairwise corr of monthly P&L:\n", d.resample("ME").sum().corr().round(2).to_string())
