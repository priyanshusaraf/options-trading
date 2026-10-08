"""Research harness: run registry-style strategies through the platform's REAL
backtest engine (app.backtest.engine.simulate) on the MCX-proxy datasets."""
from __future__ import annotations
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))

import sys
from functools import lru_cache

import numpy as np
import pandas as pd

BACKEND = _os.path.abspath(_os.path.join(HERE, "..", "..", "backend"))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.backtest.engine import simulate            # noqa: E402
from app.core.instruments import Instrument          # noqa: E402
from app.providers.base import Candle                # noqa: E402

import os
DATA = _os.path.join(DATA_ROOT, "mcx")

INSTR = {
    "NATGASMINI": Instrument("NATGASMINI", "NATURAL GAS MINI", "MCX", "MCX", "NATGASMINI",
                             "NATGASMINI", lot_size=250, strike_step=5, priority=1,
                             mock_spot=300, mock_vol=0.5),
    "GOLDPETAL": Instrument("GOLDPETAL", "GOLD PETAL", "MCX", "MCX", "GOLDPETAL", "GOLDPETAL",
                            lot_size=1, strike_step=100, priority=2, mock_spot=9000, mock_vol=0.15),
    "CRUDEOILM": Instrument("CRUDEOILM", "CRUDE OIL MINI", "MCX", "MCX", "CRUDEOILM",
                            "CRUDEOILM", lot_size=10, strike_step=50, priority=3,
                            mock_spot=6000, mock_vol=0.35),
    "SILVERMIC": Instrument("SILVERMIC", "SILVER MICRO", "MCX", "MCX", "SILVERMIC", "SILVERMIC",
                            lot_size=1, strike_step=250, priority=4, mock_spot=90000, mock_vol=0.25),
}
INSTR["GOLDM"] = Instrument("GOLDM", "GOLD MINI", "MCX", "MCX", "GOLDM", "GOLDM", lot_size=100,
                            strike_step=10, priority=5, mock_spot=9000, mock_vol=0.15)
INSTR["GOLDGUINEA"] = Instrument("GOLDGUINEA", "GOLD GUINEA", "MCX", "MCX", "GOLDGUINEA",
                                 "GOLDGUINEA", lot_size=8, strike_step=100, priority=6,
                                 mock_spot=9000, mock_vol=0.15)
SLIP = {"NATGASMINI": 0.0004, "GOLDPETAL": 0.0003, "CRUDEOILM": 0.0003, "SILVERMIC": 0.0002,
        "GOLDM": 0.0001, "GOLDGUINEA": 0.0002}
DATA_ALIAS = {"GOLDM": "GOLDPETAL", "GOLDGUINEA": "GOLDPETAL"}   # same ₹/g price series

IS_END = pd.Timestamp("2024-01-01")


@lru_cache(maxsize=32)
def frame(name: str, tf: str = "15m") -> pd.DataFrame:
    df = pd.read_pickle(f"{DATA}/{DATA_ALIAS.get(name, name)}_{tf}.pkl")
    return df


@lru_cache(maxsize=64)
def candles(name: str, tf: str = "15m", start: str | None = None, end: str | None = None):
    df = frame(name, tf)
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return tuple(Candle(ts.to_pydatetime(), float(o), float(h), float(l), float(c), float(v))
                 for ts, o, h, l, c, v in zip(df.index, df.open, df.high, df.low, df.close,
                                              df.volume))


@lru_cache(maxsize=8)
def rolls(name: str) -> tuple:
    """(roll_epoch, gap_points_inr) for futures-CFD rolls (empty for spot metals)."""
    import os
    f = f"{DATA}/{DATA_ALIAS.get(name, name)}_rolls.csv"
    if not os.path.exists(f):
        return ()
    r = pd.read_csv(f, parse_dates=["ist", "last_before"])
    if r.empty:
        return ()
    px = frame(name, "5m")["close"]
    out = []
    for _, x in r.iterrows():
        before = float(px.loc[:x["last_before"]].iloc[-1])
        ep = int(pd.Timestamp(x["last_before"]).tz_localize("Asia/Kolkata").timestamp()) + 60
        out.append((ep, x["gap_pct"] * before))
    return tuple(out)


def _roll_correct(trades, name):
    """Remove the futures-roll gap from trades HELD across a roll (a real trader
    rolls the position; the contract-spread jump is not P&L)."""
    from dataclasses import replace
    rl = rolls(name)
    if not rl:
        return trades
    out = []
    for t in trades:
        adj = 0.0
        for ep, pts in rl:
            if t.entry_time < ep < t.exit_time:
                sgn = 1.0 if t.direction == "LONG" else -1.0
                adj -= sgn * pts * t.qty
        if adj:
            t = replace(t, gross_pnl=t.gross_pnl + adj, net_pnl=t.net_pnl + adj,
                        reason=t.reason + "+ROLLADJ")
        out.append(t)
    return out


def run(strategy, name: str, tf: str = "15m", params: dict | None = None,
        start: str | None = None, end: str | None = None, slippage: float | None = None):
    cs = candles(name, tf, start, end)
    p = dict(strategy.default_params)
    if params:
        p.update(params)
    slip = SLIP[name] if slippage is None else slippage
    trades, m = simulate(list(cs), INSTR[name], tf, strategy=strategy, params=p,
                         slippage_pct=slip)
    return _roll_correct(trades, name), m


def run_premium(strategy, name: str, tf: str = "15m", params: dict | None = None,
                premium: dict | None = None, start: str | None = None,
                end: str | None = None):
    """The platform's synthetic-premium backtest (app/backtest/premium.py: ATM
    CE/PE bought on the signal, Black-Scholes on realised vol, the live bot's
    premium stop/target/trail, option charges + spread). Trades held across a
    futures roll are DROPPED (an option sits on one contract month; the front-month
    roll gap is not its P&L) — returns (trades, n_dropped)."""
    from app.backtest.premium import simulate_premium
    cs = candles(name, tf, start, end)
    p = dict(strategy.default_params)
    if params:
        p.update(params)
    p.update(premium or {})
    trades, _ = simulate_premium(list(cs), INSTR[name], tf, strategy=strategy, params=p)
    rl = rolls(name)
    keep = [t for t in trades if not any(t.entry_time < ep < t.exit_time for ep, _ in rl)]
    return keep, len(trades) - len(keep)


def summarize(trades, label: str = "") -> dict:
    if not trades:
        return {"label": label, "n": 0, "net": 0.0, "gross": 0.0, "chg": 0.0, "pf": None,
                "wr": None, "dd": 0.0, "exp": 0.0, "sharpe_d": None}
    net = np.array([t.net_pnl for t in trades])
    gross = np.array([t.gross_pnl for t in trades])
    chg = np.array([t.charges for t in trades])
    wins = net[net > 0].sum()
    losses = -net[net < 0].sum()
    eq = np.cumsum(net)
    peak = np.maximum.accumulate(np.concatenate([[0], eq]))[1:]
    dd = float((peak - eq).max())
    # daily P&L Sharpe (by exit date)
    s = pd.Series(net, index=pd.to_datetime([t.exit_time for t in trades], unit="s"))
    daily = s.groupby(s.index.date).sum()
    days = pd.bdate_range(daily.index.min(), daily.index.max())
    daily = daily.reindex(days.date, fill_value=0.0)
    sh = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else None
    return {"label": label, "n": len(trades), "net": round(float(net.sum()), 0),
            "gross": round(float(gross.sum()), 0), "chg": round(float(chg.sum()), 0),
            "pf": round(float(wins / losses), 3) if losses > 0 else None,
            "wr": round(float((net > 0).mean() * 100), 1), "dd": round(dd, 0),
            "exp": round(float(net.mean()), 1), "sharpe_d": round(sh, 2) if sh else None}


def split(trades):
    cut = int(IS_END.tz_localize("Asia/Kolkata").timestamp())
    return ([t for t in trades if t.entry_time < cut], [t for t in trades if t.entry_time >= cut])


def by_year(trades) -> dict:
    s = pd.Series([t.net_pnl for t in trades],
                  index=pd.to_datetime([t.exit_time for t in trades], unit="s"))
    return {int(k): round(float(v), 0) for k, v in s.groupby(s.index.year).sum().items()}


def evaluate(strategy, names=("NATGASMINI", "GOLDPETAL", "CRUDEOILM", "SILVERMIC"),
             tf="15m", params=None, verbose=True, slippage=None):
    rows = []
    for nm in names:
        try:
            tr, _ = run(strategy, nm, tf, params, slippage=slippage)
        except FileNotFoundError:
            continue
        a, b = split(tr)
        r = {"inst": nm, "tf": tf, **{f"IS_{k}": v for k, v in summarize(a).items() if k != "label"},
             **{f"OOS_{k}": v for k, v in summarize(b).items() if k != "label"}}
        r["years"] = by_year(tr)
        rows.append(r)
        if verbose:
            print(f"{nm:11s} {tf:4s} IS n={r['IS_n']:4d} net={r['IS_net']:>9} pf={r['IS_pf']} "
                  f"wr={r['IS_wr']} dd={r['IS_dd']} sh={r['IS_sharpe_d']} | OOS n={r['OOS_n']:4d} "
                  f"net={r['OOS_net']:>9} pf={r['OOS_pf']} wr={r['OOS_wr']} dd={r['OOS_dd']} "
                  f"sh={r['OOS_sharpe_d']} chg={r['OOS_chg']}")
    return rows
