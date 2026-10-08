"""How wide can the real MCX option bid-ask be before each passing strategy's
options path stops paying? OOS (2024-01 -> 2026-10) net at a grid of spreads, each
strategy with its shipped option_exits / option_tenor_days. Compare the break-even
with the live bid-ask in the Options Calc view (Kite quotes need a login)."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

CELLS = [("spike_fade", "NATGASMINI", "15m"), ("spike_fade", "CRUDEOILM", "15m"),
         ("shock_reversal", "CRUDEOILM", "15m"), ("vwap_band_reversion", "NATGASMINI", "30m")]
SPREADS = (0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
for key, inst, tf in CELLS:
    row = []
    for s in SPREADS:
        tr, _ = rlib.run_premium(get_strategy(key), inst, tf, premium={"premium_spread_pct": s})
        _, oos = rlib.split(tr)
        row.append(rlib.summarize(oos)["net"])
    cells = " | ".join(f"{s:.0%}: {v / 1000:+.1f}k" for s, v in zip(SPREADS, row))
    print(f"{key:20s} {inst:10s} {tf} | {cells}")
