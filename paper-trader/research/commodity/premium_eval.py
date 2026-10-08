"""Options-path evaluation: the passing strategies traded the way the live bot
trades them — buy an ATM CE/PE on the signal, premium stop/target/trail — via the
platform's synthetic-premium backtest. Variants are chosen on IS only."""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import json  # noqa: E402
from multiprocessing import Pool  # noqa: E402

import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

CELLS = [("spike_fade", "NATGASMINI", "15m"), ("spike_fade", "CRUDEOILM", "15m"),
         ("shock_reversal", "CRUDEOILM", "15m"), ("vwap_band_reversion", "NATGASMINI", "30m"),
         ("gold_month_turn", "GOLDM", "60m")]
VARIANTS = {
    "a bot default (-35%/+60%, trail)": {},
    "b no target": {"target_pct": 10.0},
    "c strategy exits only": {"target_pct": 10.0, "stop_loss_pct": 0.99, "trail_enabled": False},
    "d stop -50%, no target": {"target_pct": 10.0, "stop_loss_pct": 0.50},
}


def job(args):
    (key, inst, tf), vlab, prem, spread = args
    tr, dropped = rlib.run_premium(get_strategy(key), inst, tf,
                                   premium={**prem, "premium_spread_pct": spread})
    a, b = rlib.split(tr)
    sa, sb = rlib.summarize(a), rlib.summarize(b)
    reasons = {}
    for t in tr:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    return dict(cell=f"{key}:{inst}:{tf}", variant=vlab, spread=spread, IS=sa, OOS=sb,
                dropped=dropped, reasons=reasons, years=rlib.by_year(tr))


if __name__ == "__main__":
    jobs = [(c, v, p, sp) for c in CELLS for v, p in VARIANTS.items() for sp in (0.02, 0.06)]
    with Pool(3) as pool:
        res = pool.map(job, jobs, chunksize=1)
    json.dump(res, open(_os.path.join(HERE, "results", "premium_eval.json"), "w"), indent=1)
    for r in res:
        a, b = r["IS"], r["OOS"]
        print(f"{r['cell']:34s} {r['variant']:32s} spr {r['spread']:.0%} | IS n={a['n']:3d} ₹{a['net']:>8.0f} "
              f"pf={a['pf']} | OOS n={b['n']:3d} ₹{b['net']:>8.0f} pf={b['pf']} dd={b['dd']:.0f} | drop {r['dropped']} {r['reasons']}")
