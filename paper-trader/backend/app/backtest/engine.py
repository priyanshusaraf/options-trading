"""
Single-instrument backtest of the EMA50 + z-score strategy on the UNDERLYING.

Options history is mostly unavailable, so the sweep evaluates the *strategy's*
raw edge on the underlying price series — exactly what the owner asked for ("only
the z-score + EMA strategy performance matters"). Entries fire on the strategy's
longEntry/shortEntry flags; exits fire on its own longExit/shortExit flags plus —
when the strategy DECLARES a risk_model — the Pine-parity ratchet overlay (initial
ATR stop -> Chandelier trail -> MFE-capture floor, close-confirmed; see
app/backtest/ratchet.py). Every decision confirmed on bar i fills at bar i+1's
OPEN (Pine process_orders_on_close=false parity); the option-premium stop/target
of the LIVE engine is not modelled here (it doesn't map to the underlying).

POSITION SIZING (fixed ONE lot — the owner's chosen model):
  Every position is exactly ONE F&O lot (cash equities: floor(capital/price)
  shares). We NEVER skip an instrument for being "unaffordable" and never stuff a
  ₹50k account with many lots — the point is to see the STRATEGY's edge on a single
  realistic position, then flag separately whether you can afford to play it today.

RETURN MODEL (additive, no compounding, no leverage):
  base capital = the cost to enter the FIRST 1-lot position (entry_price × lot).
  Equity = base + cumulative 1-lot net P&L; Return% = total net P&L / base. This
  is the owner's "₹2.5L in → ₹5L out = +100%" framing — NOT the compounding-%
  curve that balloons to +1000% over many years. `capital` only sizes cash equities
  and seeds the fallback base; F&O sizing ignores it (always 1 lot).

AFFORDABILITY (two flags, against your real budget — computed at the payload layer):
  - futures: the 1-lot UNDERLYING notional (entry_price × lot) — usually far above a
    small account, so most names read "unaffordable at futures price".
  - options: an ATM option premium ESTIMATE (Black-Scholes on the last close at the
    instrument's own realised vol) × lot — because we BUY options, which are far
    cheaper. If the option cost fits your budget the name is tradable NOW; if not it
    is flagged unaffordable but kept visible so a promising edge stays on the radar.

Every trade is charged the full, direction-correct Zerodha stack via
engine/charges.py.
"""
from __future__ import annotations

import math

import pandas as pd

from app.backtest.metrics import BTMetrics, BTTrade, compute_metrics
from app.backtest.ratchet import RatchetState, wilder_atr
from app.core.market_hours import ist_epoch
from app.engine.charges import compute_charges
from app.strategy.registry import get_strategy

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
    """Fixed ONE-lot, leverage-free position size at `price`:

    - F&O: exactly one lot (= lot_size), ALWAYS — never scaled to `capital` and
      never skipped as unaffordable (affordability is a separate, payload-layer
      flag). `capital` is ignored for F&O.
    - Cash equities: floor(capital / price) shares (there is no lot)."""
    if price <= 0:
        return 0
    if inst.segment in _CASH_SEGMENTS:
        return int(capital // price)
    return max(1, int(inst.lot_size))


def _candles_to_df(candles) -> pd.DataFrame:
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


def _position(inst, price: float, capital: float) -> tuple[int, float, int]:
    """Return (qty, notional, lots) for one 1-lot position at `price`. `lots` is 1
    for F&O (cash: the share count)."""
    qty = backtest_qty(inst, price, capital)
    notional = price * qty
    if inst.segment in _CASH_SEGMENTS:
        lots = qty
    else:
        lots = 1 if qty > 0 else 0
    return qty, notional, lots


def _annualised_vol(candles) -> float:
    """Annualised realised volatility from daily closes (last close per calendar
    day), σ_daily × √252. Used only to ESTIMATE an ATM option premium for the
    affordability flag — a rough gate, not a pricing engine."""
    by_day: dict = {}
    for c in candles:
        by_day[c.ts.date()] = float(c.close)   # last close wins per day
    closes = [by_day[d] for d in sorted(by_day)]
    if len(closes) < 3:
        return 0.0
    rets = [math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes)) if closes[i - 1] > 0 and closes[i] > 0]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    sd = (sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
    return sd * (252 ** 0.5)


def estimate_option_cost(inst, candles, r: float = 0.065) -> float:
    """Estimate the cost to BUY one lot of an ATM option as of the LAST candle:
    Black-Scholes ATM premium (K = S = last close) at the instrument's own realised
    vol, ~14-day expiry, × lot_size. Budget-independent; the affordability flag is
    computed against the live budget at the payload layer. Returns 0 if it can't be
    estimated (caller treats 0 as 'unknown', not free)."""
    from app.options.pricing import bs_price
    if not candles:
        return 0.0
    spot = float(candles[-1].close)
    sigma = _annualised_vol(candles)
    if spot <= 0 or sigma <= 0:
        return 0.0
    lot = max(1, int(inst.lot_size)) if inst.segment not in _CASH_SEGMENTS else 1
    premium = bs_price(spot, spot, 14.0 / 365.0, r, sigma, "CE")   # ATM call ≈ ATM put
    return round(premium * lot, 2)


def simulate(candles, inst, interval: str, *, capital: float = 50_000.0,
             strategy=None, params: dict | None = None,
             ema_length: int = 50, z_length: int = 50, entry_z: float = 1.0,
             slope_lookback: int = 5) -> tuple[list[BTTrade], BTMetrics]:
    """Run a strategy over `candles` and return (trades, metrics).

    `strategy` is a registry Strategy (None → the default trend_impulse_v3); `params`
    overrides its inputs (None → the strategy's own defaults, or the legacy v3 kwargs
    when no strategy is given). Entries/exits come purely from the strategy's
    canonical flag columns; the engine owns no premium stop/target here."""
    strat = strategy if strategy is not None else get_strategy(None)
    if params is None:
        params = (dict(strat.default_params) if strategy is not None
                  else {"ema_length": ema_length, "z_length": z_length,
                        "entry_z": entry_z, "slope_lookback": slope_lookback})
    warmup = int(params.get("ema_length", ema_length)) + \
        int(params.get("slope_lookback", slope_lookback)) + 2
    if len(candles) < warmup:
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

    # Estimate the cost to BUY one lot of an ATM option as of the last candle — a
    # budget-independent number; the affordability FLAG is computed against the live
    # budget at the payload layer (so it never goes stale when funds change).
    option_cost = estimate_option_cost(inst, candles)

    sig = strat.signals(_candles_to_df(candles), **params)
    rm = getattr(strat, "risk_model", None)
    if rm:
        # computed on the FULL frame so warmup trimming can't shift ATR values
        sig["_ratchet_atr"] = wilder_atr(sig, int(rm["atr_length"]))
    # trim warmup rows where the strategy's indicators are still NaN. The columns
    # differ per strategy (v3: slope; v4: atr/absZ), so drop on whichever of the
    # known indicator columns this strategy actually emitted — keeps v3 identical.
    warm_cols = [c for c in ("ema", "z", "slope", "atr", "absZ") if c in sig.columns]
    sig = sig.dropna(subset=warm_cols).reset_index(drop=True)
    if sig.empty:
        m = BTMetrics()
        m.bh_return_pct = bh_return_pct
        m.bh_curve = bh_curve
        m.option_cost = option_cost
        return [], m

    trades: list[BTTrade] = []
    pos = None      # dict: direction, entry_price, entry_time, entry_idx, qty, …, mae
    pending = None  # ("ENTER", "LONG"|"SHORT") | ("EXIT", reason) — fills next bar OPEN
    ratchet = None  # RatchetState for the open position, iff strat declares risk_model

    rows = sig.to_dict("records")
    for i, r in enumerate(rows):
        t = ist_epoch(r["date"])   # IST wall-clock -> true instant (no +5:30 shift)
        open_px = float(r["open"])
        close = float(r["close"])

        # 1) execute the PREVIOUS bar's confirmed decision at THIS bar's open
        #    (Pine parity: process_orders_on_close=false — no same-bar fills).
        if pending is not None:
            kind, arg = pending
            pending = None
            if kind == "ENTER" and pos is None:
                qty, notional, lots = _position(inst, open_px, capital)
                if qty > 0:
                    pos = {"direction": arg, "entry_price": open_px,
                           "entry_time": t, "entry_idx": i, "qty": qty,
                           "notional": notional, "lots": lots,
                           "mae_pct": 0.0}
                    ratchet = None
                    if rm:
                        entry_atr = r.get("_ratchet_atr")
                        if entry_atr is not None and math.isfinite(entry_atr) \
                                and entry_atr > 0:
                            # risk units freeze at the FILL bar (pine:212)
                            ratchet = RatchetState(arg, open_px,
                                                   float(entry_atr), rm)
            elif kind == "EXIT" and pos is not None:
                trades.append(_close(pos, open_px, t, i, seg, arg))
                pos = None
                ratchet = None

        if pos is not None:
            # MAE includes the fill bar (the position lives through it) …
            _update_mae(pos, r)
            # … but exit DECISIONS start the bar AFTER the fill (Pine canManage:
            # no same-bar management, pine:233-234).
            if i > pos["entry_idx"]:
                d = pos["direction"]
                if ratchet is not None:
                    ratchet.update(float(r["high"]), float(r["low"]), close,
                                   float(r["_ratchet_atr"]))
                    if ratchet.stop_hit(close):
                        pending = ("EXIT", "RATCHET_STOP")
                if pending is None and (
                        (d == "LONG" and bool(r["longExit"])) or
                        (d == "SHORT" and bool(r["shortExit"]))):
                    pending = ("EXIT", "STRATEGY_EXIT")
        elif r["longEntry"] or r["shortEntry"]:
            pending = ("ENTER", "LONG" if r["longEntry"] else "SHORT")

    # close any still-open position at the LAST AVAILABLE CANDLE (end of data,
    # not end of day) — includes a decision confirmed on the final bar, which
    # has no next open to fill at.
    if pos is not None:
        last = rows[-1]
        trades.append(_close(pos, float(last["close"]),
                             ist_epoch(last["date"]),
                             len(rows) - 1, seg, "OPEN_AT_END"))

    m = compute_metrics(trades, capital)
    m.bh_return_pct = bh_return_pct
    m.bh_curve = bh_curve
    m.option_cost = option_cost
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
        lots=pos.get("lots", 0),
    )
