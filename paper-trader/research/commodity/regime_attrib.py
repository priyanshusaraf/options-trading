"""Attribute each strategy's trades to the technical regime at the signal bar."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys
sys.path.insert(0, HERE)
import numpy as np, pandas as pd, rlib
from app.core.market_hours import ist_epoch
from app.strategy.regime import classify, REGIMES


def regime_table(strategy, name, tf, params=None):
    fr = rlib.frame(name, tf).reset_index()
    reg = classify(fr)
    ep = np.array([ist_epoch(t.to_pydatetime()) for t in fr["date"]])
    trades, _ = rlib.run(strategy, name, tf, params)
    rows = []
    for t in trades:
        k = int(np.searchsorted(ep, t.entry_time)) - 1      # signal bar = bar before the fill
        lab = reg["regime"].iloc[max(k, 0)]
        per = "IS" if t.entry_time < ep[np.searchsorted(fr["date"], pd.Timestamp("2024-01-01"))] else "OOS"
        rows.append((lab, per, t.net_pnl))
    x = pd.DataFrame(rows, columns=["regime", "per", "net"])
    share = reg["regime"].value_counts(normalize=True).round(3).to_dict()
    t = x.pivot_table(index="regime", columns="per", values="net", aggfunc=["count", "sum"]).fillna(0)
    return t, share


if __name__ == "__main__":
    from app.strategy.registry import get_strategy
    for key, nm, tf in (("adaptive_supertrend", "NATGASMINI", "15m"), ("adaptive_supertrend", "GOLDPETAL", "60m"),
                        ("vwap_slope_divergence", "NATGASMINI", "15m")):
        t, share = regime_table(get_strategy(key), nm, tf)
        print("==", key, nm, tf, "bar share", share); print(t.round(0).to_string())
