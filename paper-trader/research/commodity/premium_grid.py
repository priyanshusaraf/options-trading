"""IS-only grid of option-exit policy for the passing strategies: catastrophic stop
level × option tenor (entry DTE); no target, no trail (variant c family)."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import itertools  # noqa: E402
import json  # noqa: E402
from multiprocessing import Pool  # noqa: E402

import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

CELLS = [("spike_fade", "NATGASMINI", "15m"), ("spike_fade", "CRUDEOILM", "15m"),
         ("shock_reversal", "CRUDEOILM", "15m"), ("vwap_band_reversion", "NATGASMINI", "30m")]


def job(args):
    (key, inst, tf), stop, dte = args
    prem = {"target_pct": 10.0, "stop_loss_pct": stop, "trail_enabled": False,
            "entry_dte_days": dte, "premium_spread_pct": 0.04}
    tr, _ = rlib.run_premium(get_strategy(key), inst, tf, premium=prem)
    a, b = rlib.split(tr)
    return dict(cell=f"{key}:{inst}:{tf}", stop=stop, dte=dte, IS=rlib.summarize(a), OOS=rlib.summarize(b))


if __name__ == "__main__":
    jobs = [(c, s, d) for c in CELLS for s, d in itertools.product((0.5, 0.65, 0.8, 0.99), (14, 21, 30))]
    with Pool(3) as pool:
        res = pool.map(job, jobs, chunksize=2)
    json.dump(res, open(_os.path.join(HERE, "results", "premium_grid.json"), "w"), indent=1)
    for c in CELLS:
        cell = f"{c[0]}:{c[1]}:{c[2]}"
        print("==", cell, "(IS net ₹ by stop × DTE)   [OOS in brackets]")
        for s in (0.5, 0.65, 0.8, 0.99):
            row = [r for r in res if r["cell"] == cell and r["stop"] == s]
            print(f"   stop -{s:.0%}: " + "  ".join(f"DTE{r['dte']}: {r['IS']['net']:>8.0f} [{r['OOS']['net']:>7.0f}]" for r in sorted(row, key=lambda x: x["dte"])))
