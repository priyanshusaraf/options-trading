"""
Single-instrument backtest of the EMA50 + z-score strategy on the UNDERLYING.

Options history is mostly unavailable, so the sweep evaluates the *strategy's*
raw edge on the underlying price series — exactly what the owner asked for ("only
the z-score + EMA strategy performance matters"). Entries fire on the strategy's
longEntry/shortEntry crossovers; exits fire on its own longExit/shortExit (z
reversal / trend flip) — **pure strategy signal**, no option-premium stop/target
(those don't map to the underlying).

POSITION SIZING (honest, no leverage):
  Each position is sized to the LARGEST WHOLE NUMBER OF F&O LOTS that fits inside
  the user-supplied `capital` with NO leverage — i.e. floor(capital / lot_notional)
  lots, capped at whatever `capital` actually affords. Cash equities buy
  floor(capital / price) shares. An instrument whose SINGLE lot notional already
  exceeds `capital` is NOT silently sized to 1 lot: it is reported as a distinct,
  non-error 'unaffordable' result (lots=0, affordable=False, "lot > capital — not
  tradable at this size") so the cell still appears but is clearly marked rather
  than pretending a ₹50k account took an ₹18L position.

  Because Return%/equity/CAGR compound the per-trade return on the position's own
  notional (anchor-independent), sizing affects absolute Net P&L and the
  affordability flag — not the % math. `capital` is the "capital available to the
  backtest", NOT an account base.

Every trade is charged the full, direction-correct Zerodha stack via
engine/charges.py.
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
    """Affordable, leverage-free position size at `price`:

    - Cash equities: floor(capital / price) shares.
    - F&O: the largest WHOLE number of lots that fits inside `capital`, i.e.
      floor(capital / (price × lot_size)) × lot_size. Returns 0 when even one
      lot's notional exceeds `capital` (caller treats 0 as 'unaffordable', NOT
      a silent 1-lot fallback)."""
    if price <= 0:
        return 0
    if inst.segment in _CASH_SEGMENTS:
        return int(capital // price)
    lot = int(inst.lot_size)
    lot_notional = price * lot
    if lot_notional <= 0:
        return 0
    affordable_lots = int(capital // lot_notional)
    return max(0, affordable_lots) * lot


def _candles_to_df(candles) -> pd.DataFrame:
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


def _affordability(inst, price: float, capital: float) -> tuple[int, float, bool, int]:
    """Return (qty, notional, affordable, lots) for one position at `price`.

    `affordable` is False when even a single lot's notional exceeds `capital`
    (qty==0); the caller then records a distinct 'unaffordable' result instead of
    silently sizing to 1 lot. `lots` is whole F&O lots (cash: share count)."""
    qty = backtest_qty(inst, price, capital)
    notional = price * qty
    if inst.segment in _CASH_SEGMENTS:
        lot = 1
    else:
        lot = max(1, int(inst.lot_size))
    affordable = qty > 0
    lots = qty // lot if lot else 0
    return qty, notional, affordable, lots


def _unaffordable_metrics(inst, ref_price: float, capital: float) -> BTMetrics:
    """A distinct, non-error result for an instrument whose one lot already costs
    more than `capital`: lots=0, affordable=False, notional = one lot's cost."""
    lot = max(1, int(inst.lot_size))
    m = BTMetrics()
    m.affordable = False
    m.lots = 0
    m.notional = ref_price * lot
    return m


def simulate(candles, inst, interval: str, *, capital: float = 50_000.0,
             ema_length: int = 50, z_length: int = 50, entry_z: float = 1.0,
             slope_lookback: int = 5) -> tuple[list[BTTrade], BTMetrics]:
    """Run the strategy over `candles` and return (trades, metrics)."""
    if len(candles) < ema_length + slope_lookback + 2:
        return [], BTMetrics()

    seg = backtest_charge_segment(inst)
    # buy-and-hold benchmark over the SAME (already-clipped) candle span — the
    # underlying's own return, so a strategy edge is distinguishable from beta.
    first_close = float(candles[0].close)
    last_close = float(candles[-1].close)
    bh_return_pct = ((last_close / first_close - 1.0) * 100.0) if first_close else None
    bh_curve = ([{"time": ist_epoch(candles[0].ts), "value": round(first_close, 2)},
                 {"time": ist_epoch(candles[-1].ts), "value": round(last_close, 2)}]
                if first_close else [])

    # Affordability gate: if even one lot's notional at a representative price
    # exceeds `capital`, this instrument is not tradable at this size — record a
    # distinct unaffordable result rather than silently sizing to 1 lot.
    ref_price = first_close
    if inst.segment not in _CASH_SEGMENTS and ref_price > 0:
        if backtest_qty(inst, ref_price, capital) <= 0:
            m = _unaffordable_metrics(inst, ref_price, capital)
            m.bh_return_pct = bh_return_pct
            m.bh_curve = bh_curve
            return [], m

    sig = compute_signals(_candles_to_df(candles), ema_length=ema_length,
                          z_length=z_length, entry_z=entry_z,
                          slope_lookback=slope_lookback)
    sig = sig.dropna(subset=["ema", "z", "slope"]).reset_index(drop=True)
    if sig.empty:
        m = BTMetrics()
        m.bh_return_pct = bh_return_pct
        m.bh_curve = bh_curve
        return [], m

    trades: list[BTTrade] = []
    pos = None  # dict: direction, entry_price, entry_time, entry_idx, qty, …, mae

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
                qty, notional, affordable, lots = _affordability(inst, close, capital)
                if qty <= 0:
                    continue
                pos = {"direction": direction, "entry_price": close,
                       "entry_time": t, "entry_idx": i, "qty": qty,
                       "notional": notional, "lots": lots, "affordable": affordable,
                       "mae_pct": 0.0}
        else:
            # track Maximum Adverse Excursion from this bar's high/low while open
            _update_mae(pos, r)
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

    m = compute_metrics(trades, capital)
    m.bh_return_pct = bh_return_pct
    m.bh_curve = bh_curve
    return trades, m


def _update_mae(pos, row) -> None:
    """Update a position's running Maximum Adverse Excursion from a bar's extreme.

    For a LONG the worst point is the bar LOW; for a SHORT it's the bar HIGH.
    MAE% is measured against the entry price so it's comparable across trades."""
    entry = pos["entry_price"]
    if entry <= 0:
        return
    if pos["direction"] == "LONG":
        worst = float(row["low"])
        adverse = (entry - worst) / entry * 100.0
    else:
        worst = float(row["high"])
        adverse = (worst - entry) / entry * 100.0
    if adverse > pos["mae_pct"]:
        pos["mae_pct"] = adverse


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
        mae_pct=pos.get("mae_pct", 0.0), notional=pos.get("notional", entry_price * qty),
        lots=pos.get("lots", 0), affordable=pos.get("affordable", True),
    )
