"""Final unified evaluation: every registered commodity strategy at its DEFAULT
params on the corrected (mcx2) data, IS 2019-2023 vs OOS 2024-01..2026-10."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys, json, itertools
sys.path.insert(0, HERE)
from multiprocessing import Pool
import numpy as np, rlib
from app.strategy.registry import get_strategy

KEYS = ["vwap_slope_divergence", "adaptive_supertrend", "vol_squeeze_breakout",
        "vwap_band_reversion", "shock_reversal", "spike_fade", "session_gap_carry",
        "trend_impulse_v3"]
INSTS = ["NATGASMINI", "CRUDEOILM", "GOLDPETAL", "GOLDM"]
TFS = ["15m", "30m", "60m"]


def boot_pos(trades, n=2000, seed=1):
    x = np.array([t.net_pnl for t in trades])
    if len(x) < 5:
        return None
    rng = np.random.default_rng(seed)
    s = rng.choice(x, size=(n, len(x)), replace=True).sum(axis=1)
    return round(float((s > 0).mean()), 3)


def job(cfg):
    key, inst, tf = cfg
    S = get_strategy(key)
    try:
        tr, _ = rlib.run(S, inst, tf)
        tr2, _ = rlib.run(S, inst, tf, slippage=rlib.SLIP[inst] * 2)
    except FileNotFoundError:
        return None
    a, b = rlib.split(tr)
    _, b2 = rlib.split(tr2)
    sa, sb = rlib.summarize(a), rlib.summarize(b)
    L = rlib.summarize([t for t in b if t.direction == "LONG"])
    Sh = rlib.summarize([t for t in b if t.direction == "SHORT"])
    return dict(key=key, inst=inst, tf=tf,
                IS_n=sa["n"], IS_net=sa["net"], IS_pf=sa["pf"], IS_dd=sa["dd"],
                OOS_n=sb["n"], OOS_net=sb["net"], OOS_pf=sb["pf"], OOS_dd=sb["dd"],
                OOS_wr=sb["wr"], OOS_chg=sb["chg"], OOS_long=L["net"], OOS_short=Sh["net"],
                OOS_net_2xslip=rlib.summarize(b2)["net"], OOS_p_pos=boot_pos(b),
                IS_p_pos=boot_pos(a), years=rlib.by_year(tr))


if __name__ == "__main__":
    cfgs = [c for c in itertools.product(KEYS, INSTS, TFS)
            if not (c[1] == "GOLDM" and c[0] not in ("session_gap_carry", "adaptive_supertrend", "shock_reversal"))]
    with Pool(4) as p:
        res = [r for r in p.map(job, cfgs, chunksize=1) if r]
    json.dump(res, open(_os.path.join(HERE, "results", "final_eval.json"), "w"), indent=1)
    for r in res:
        print(f"{r['key']:22s} {r['inst']:10s} {r['tf']:3s} IS {r['IS_net']:>9.0f} pf={r['IS_pf']} | OOS {r['OOS_net']:>9.0f} pf={r['OOS_pf']} n={r['OOS_n']} dd={r['OOS_dd']:.0f} 2xslip={r['OOS_net_2xslip']:.0f} P(>0)={r['OOS_p_pos']}")
