"""Silver (SILVERMIC) — never used for tuning, so every number here is out-of-sample:
all registered strategies at their defaults on Yahoo COMEX SI=F 60m (2024-05 → 2026-10,
calendar-roll adjusted), futures path and options path. Run with COMMODITY_DATA pointing
at a root whose mcx/ is the yahoo_mcx build."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

KEYS = ["spike_fade", "shock_reversal", "vwap_band_reversion", "gold_month_turn",
        "vwap_slope_divergence", "adaptive_supertrend", "vol_squeeze_breakout",
        "session_gap_carry", "trend_impulse_v3"]
f = rlib.frame("SILVERMIC", "60m")
print(f"buy-and-hold 1 kg: ₹{f.close.iloc[-1] - f.close.iloc[0]:,.0f} "
      f"({(f.close.iloc[-1] / f.close.iloc[0] - 1) * 100:.0f}%), max DD ₹{(f.close.cummax() - f.close).max():,.0f}")
for k in KEYS:
    s = get_strategy(k)
    tr, _ = rlib.run(s, "SILVERMIC", "60m")
    a = rlib.summarize(tr)
    L = rlib.summarize([t for t in tr if t.direction == "LONG"])["net"]
    Sh = rlib.summarize([t for t in tr if t.direction == "SHORT"])["net"]
    po, _ = rlib.run_premium(s, "SILVERMIC", "60m", premium={"premium_spread_pct": 0.04})
    b = rlib.summarize(po)
    print(f"{k:22s} futures n={a['n']:3d} ₹{a['net']:>9,.0f} pf={a['pf']} dd={a['dd']:,.0f} (long ₹{L:,.0f} short ₹{Sh:,.0f})"
          f" | options n={b['n']:3d} ₹{b['net']:>8,.0f} pf={b['pf']} dd={b['dd']:,.0f} | years {rlib.by_year(tr)}")
