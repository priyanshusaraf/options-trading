"""Parameter-neighbourhood robustness of the passing strategies: every combination
around the default, IS and OOS — is the default on a plateau or a lonely peak?"""
import os as _os
import sys
HERE = _os.path.dirname(_os.path.abspath(__file__))
sys.path.insert(0, HERE)
import itertools  # noqa: E402
import json  # noqa: E402
from multiprocessing import Pool  # noqa: E402

import numpy as np  # noqa: E402
import rlib  # noqa: E402
from app.strategy.registry import get_strategy  # noqa: E402

GRIDS = {
    ("spike_fade", "NATGASMINI", "60m"): {"z_entry": [1.25, 1.5, 1.75, 2.0], "hold_sessions": [2, 3, 4, 5],
                                         "z_len": [40, 60, 90], "gap_clip": [0.01, 0.015, 0.03]},
    ("spike_fade", "CRUDEOILM", "60m"): {"z_entry": [1.25, 1.5, 1.75, 2.0], "hold_sessions": [2, 3, 4, 5],
                                        "z_len": [40, 60, 90], "gap_clip": [0.01, 0.015, 0.03]},
    ("shock_reversal", "CRUDEOILM", "60m"): {"z_entry": [1.5, 1.75, 2.0, 2.25], "hold_sessions": [2, 3, 4, 5],
                                            "z_len": [40, 60, 90], "trend_sessions": [10, 20, 40]},
    ("vwap_band_reversion", "NATGASMINI", "30m"): {"anchor_days": [7, 10, 15], "band_k": [2.5, 2.75, 3.0],
                                                  "min_push_er": [0.4, 0.5, 0.6], "add_k": [3.25, 3.5, 4.0]},
}


def job(args):
    (key, inst, tf), p = args
    tr, _ = rlib.run(get_strategy(key), inst, tf, p)
    a, b = rlib.split(tr)
    return {"cell": f"{key}:{inst}:{tf}", "p": p, "IS": rlib.summarize(a)["net"],
            "OOS": rlib.summarize(b)["net"]}


if __name__ == "__main__":
    jobs = []
    for cell, grid in GRIDS.items():
        keys = list(grid)
        for vals in itertools.product(*grid.values()):
            jobs.append((cell, dict(zip(keys, vals))))
    with Pool(3) as pool:
        res = pool.map(job, jobs, chunksize=4)
    json.dump(res, open(_os.path.join(HERE, "results", "neighbourhood.json"), "w"), indent=1)
    for cell in GRIDS:
        c = f"{cell[0]}:{cell[1]}:{cell[2]}"
        r = [x for x in res if x["cell"] == c]
        IS = np.array([x["IS"] for x in r]); OOS = np.array([x["OOS"] for x in r])
        print(f"{c}: {len(r)} neighbours | IS>0 {np.mean(IS > 0):.0%} median ₹{np.median(IS):,.0f} | "
              f"OOS>0 {np.mean(OOS > 0):.0%} median ₹{np.median(OOS):,.0f} | both>0 {np.mean((IS > 0) & (OOS > 0)):.0%} "
              f"| corr(IS,OOS) {np.corrcoef(IS, OOS)[0, 1]:+.2f}")
        for k in GRIDS[cell]:
            for v in GRIDS[cell][k]:
                sel = [x for x in r if x["p"][k] == v]
                print(f"    {k}={v}: median IS ₹{np.median([x['IS'] for x in sel]):>9,.0f}  median OOS ₹{np.median([x['OOS'] for x in sel]):>8,.0f}  OOS>0 {np.mean([x['OOS'] > 0 for x in sel]):.0%}")
