"""
Single-instrument backtest of the EMA50 + z-score strategy on the UNDERLYING.

Options history is mostly unavailable, so the sweep evaluates the *strategy's*
raw edge on the underlying price series — exactly what the owner asked for ("only
the z-score + EMA strategy performance matters"). Entries fire on the strategy's
longEntry/shortEntry crossovers; exits fire on its own longExit/shortExit (z
reversal / trend flip) — **pure strategy signal**, no option-premium stop/target
(those don't map to the underlying).

Sizing: 1 lot at the instrument's F&O lot size; for pure-cash equities, as many
shares as ₹50,000 allows. ₹50,000 is the P&L accounting base. Every trade is
charged the full, direction-correct Zerodha stack via engine/charges.py.
"""
from __future__ import annotations

import pandas as pd

from app.backtest.metrics import BTMetrics, BTTrade, compute_metrics
from app.core.market_hours import ist_epoch
from app.engine.charges import compute_charges
from app.strategy.signals import compute_signals

# Map an instrument's live segment to the charge schedule for its UNDERLYING.
_BACKTEST_SEGMENT = {
    "NFO": "NFO_FUT", "BFO": "NFO_FUT",     # index/stock futures
    "MCX": "MCX_FUT", "NCDEX": "NCDEX_FUT",  # commodity futures
    "NSE": "NSE_EQ", "BSE": "BSE_EQ",        # cash equity (non-F&O names)
    "NSE_EQ": "NSE_EQ", "BSE_EQ": "BSE_EQ",
}
_CASH_SEGMENTS = {"NSE", "BSE", "NSE_EQ", "BSE_EQ"}


def backtest_charge_segment(inst) -> str:
    return _BACKTEST_SEGMENT.get(inst.segment, "NSE_EQ")


def backtest_qty(inst, price: float, capital: float) -> int:
    """1 F&O lot, or as many cash-equity shares as `capital` buys (≥1)."""
    if inst.segment in _CASH_SEGMENTS:
        return max(1, int(capital // price)) if price > 0 else 0
    return int(inst.lot_size)


def _candles_to_df(candles) -> pd.DataFrame:
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


def simulate(candles, inst, interval: str, *, capital: float = 50_000.0,
             ema_length: int = 50, z_length: int = 50, entry_z: float = 1.0,
             slope_lookback: int = 5) -> tuple[list[BTTrade], BTMetrics]:
    """Run the strategy over `candles` and return (trades, metrics)."""
    if len(candles) < ema_length + slope_lookback + 2:
        return [], BTMetrics()

    seg = backtest_charge_segment(inst)
    sig = compute_signals(_candles_to_df(candles), ema_length=ema_length,
                          z_length=z_length, entry_z=entry_z,
                          slope_lookback=slope_lookback)
    sig = sig.dropna(subset=["ema", "z", "slope"]).reset_index(drop=True)
    if sig.empty:
        return [], BTMetrics()

    trades: list[BTTrade] = []
    pos = None  # dict: direction, entry_price, entry_time, entry_idx, qty

    rows = sig.to_dict("records")
    for i, r in enumerate(rows):
        t = ist_epoch(r["date"])   # IST wall-clock -> true instant (no +5:30 shift)
        close = float(r["close"])
        if pos is None:
            direction = None
            if r["longEntry"]:
                direction = "LONG"
            elif r["shortEntry"]:
                direction = "SHORT"
            if direction:
                qty = backtest_qty(inst, close, capital)
                if qty <= 0:
                    continue
                pos = {"direction": direction, "entry_price": close,
                       "entry_time": t, "entry_idx": i, "qty": qty}
        else:
            d = pos["direction"]
            exit_now = (d == "LONG" and bool(r["longExit"])) or \
                       (d == "SHORT" and bool(r["shortExit"]))
            if exit_now:
                trades.append(_close(pos, close, t, i, seg, "STRATEGY_EXIT"))
                pos = None

    # close any still-open position at the LAST AVAILABLE CANDLE (end of data, not
    # end of day) — it never hit a strategy reversal within the loaded history.
    if pos is not None:
        last = rows[-1]
        trades.append(_close(pos, float(last["close"]),
                             ist_epoch(last["date"]),
                             len(rows) - 1, seg, "OPEN_AT_END"))

    return trades, compute_metrics(trades, capital)


def _close(pos, exit_price, exit_time, exit_idx, seg, reason) -> BTTrade:
    d, qty = pos["direction"], pos["qty"]
    entry_price = pos["entry_price"]
    gross = (exit_price - entry_price) * qty if d == "LONG" else (entry_price - exit_price) * qty
    entry_side, exit_side = ("BUY", "SELL") if d == "LONG" else ("SELL", "BUY")
    charges = (compute_charges(seg, entry_side, entry_price, qty)["total"]
               + compute_charges(seg, exit_side, exit_price, qty)["total"])
    return BTTrade(
        direction=d, entry_time=pos["entry_time"], entry_price=entry_price,
        exit_time=exit_time, exit_price=exit_price, qty=qty,
        gross_pnl=gross, charges=charges, net_pnl=gross - charges,
        reason=reason, bars_held=exit_idx - pos["entry_idx"],
    )
