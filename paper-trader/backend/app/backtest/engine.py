"""
Single-instrument backtest of the EMA50 + z-score strategy on the UNDERLYING.

Options history is mostly unavailable, so the sweep evaluates the *strategy's*
raw edge on the underlying price series — exactly what the owner asked for ("only
the z-score + EMA strategy performance matters"). Entries fire on the strategy's
longEntry/shortEntry flags; exits fire on its own longExit/shortExit flags plus —
when the strategy DECLARES a risk_model — the Pine-parity ratchet overlay (initial
ATR stop -> Chandelier trail -> MFE-capture floor, close-confirmed; see
app/backtest/ratchet.py). Every decision confirmed on bar i fills at bar i+1's
OPEN (Pine process_orders_on_close=false parity). Explicit percentage bands use
the actual underlying entry fill and completed closes after the entry bar; the option-premium stop/target
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

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.backtest.metrics import BTMetrics, BTTrade, compute_metrics
from app.backtest.ratchet import RatchetState, wilder_atr
from app.core.config import get_settings
from app.core.market_hours import ist_epoch
from app.engine.charges import (
    CORRECTED_RESEARCH_CHARGE_SCHEDULE,
    ChargeScheduleRefusal,
    compute_charges_exact,
)
from app.market_data.candles import candles_to_df
from app.engine.decision_kernel import ExitPolicy, protective_band_document
from app.strategy import replay_decisions
from app.strategy.registry import get_strategy

# The backtest's exit policy, stated once and reported with every result.
#
# The DEFAULT protective stop/target is NOT modelled. Explicit percentage bands
# opt into a directional close-confirmed policy below. For the options path there is no
# historical premium series to evaluate it against (Kite does not sell one and the
# synthetic path is an estimate); for the spot path the live band is applied to the
# TRADED instrument, which for equity_intraday is the same series — so this policy
# understates exits there and that gap is real, not cosmetic. It is declared here so
# it travels with the numbers instead of living in a docstring nobody reads next to
# the published result.
BACKTEST_EXIT_POLICY = ExitPolicy.no_protective_band(
    "no historical option-premium series exists to evaluate a premium stop/target "
    "against; the spot path trades the underlying, where the live SL/TP band is "
    "applied by the engine and not reproduced here")

# Map an instrument's live segment to the charge schedule for its UNDERLYING.
_BACKTEST_SEGMENT = {
    "NFO": "NFO_FUT", "BFO": "NFO_FUT",     # index/stock futures
    "MCX": "MCX_FUT", "NCDEX": "NCDEX_FUT",  # commodity futures
    "NSE": "NSE_EQ", "BSE": "BSE_EQ",        # cash equity (non-F&O names)
    "NSE_EQ": "NSE_EQ", "BSE_EQ": "BSE_EQ",
}
_CASH_SEGMENTS = {"NSE", "BSE", "NSE_EQ", "BSE_EQ"}


def backtest_charge_segment(inst) -> str:
    try:
        return _BACKTEST_SEGMENT[inst.segment]
    except (KeyError, TypeError):
        raise ChargeScheduleRefusal(
            "CHARGE_SEGMENT_UNKNOWN",
            f"unknown backtest charge segment {getattr(inst, 'segment', None)!r}",
        ) from None


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
    """Backtest signal frame. Thin alias for the shared, VALIDATED converter —
    this and `runner._to_df` were byte-identical copies, which is how a live and
    a backtest plane quietly stop agreeing about what the data even is."""
    return candles_to_df(candles)


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


def replay_exit_kwargs(strategy):
    """Carry only the adapter's frozen economic exit policy into every replay."""
    document = getattr(strategy, "protective_band_document", None)
    values = {} if document is None else {name: document[name] for name in ("stop_loss_pct", "take_profit_pct")}
    slippage = getattr(strategy, "replay_slippage_pct", None)
    if slippage is not None:
        values["slippage_pct"] = slippage
    return values


def _simulate_exit_kwargs(strat, stop_loss_pct, take_profit_pct, slippage_pct=None):
    exits = replay_exit_kwargs(strat)
    if stop_loss_pct is not None:
        exits["stop_loss_pct"] = stop_loss_pct
    if take_profit_pct is not None:
        exits["take_profit_pct"] = take_profit_pct
    protective_band_document(exits.get("stop_loss_pct", 0.0), exits.get("take_profit_pct", 0.0))
    if slippage_pct is not None:
        exits["slippage_pct"] = slippage_pct
    return exits


def simulate(candles, inst, interval: str, *, capital: float = 50_000.0,
             strategy=None, params: dict | None = None,
             ema_length: int = 50, z_length: int = 50, entry_z: float = 1.0,
             slope_lookback: int = 5,
             slippage_pct: float | None = None,
             signals: pd.DataFrame | None = None,
             stop_loss_pct: float | None = None,
             take_profit_pct: float | None = None) -> tuple[list[BTTrade], BTMetrics]:
    """Run a strategy over `candles` and return (trades, metrics).

    `strategy` is a registry Strategy (None → the default trend_impulse_v3); `params`
    overrides its inputs (None → the strategy's own defaults, or the legacy v3 kwargs
    when no strategy is given). Entries/exits come purely from the strategy's
    canonical flag columns. Explicit percentage bands manage the underlying, using
    the same close-confirmed next-open replay; they do not model option premiums."""
    strat = strategy if strategy is not None else get_strategy(None)
    exits = _simulate_exit_kwargs(strat, stop_loss_pct, take_profit_pct, slippage_pct)
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

    rm = getattr(strat, "risk_model", None)
    sig = (compute_signals(candles, strat, params)
           if signals is None else signals.copy(deep=True))
    if sig.empty:
        m = BTMetrics()
        m.bh_return_pct = bh_return_pct
        m.bh_curve = bh_curve
        m.option_cost = option_cost
        return [], m

    trades = run_trades(sig, inst, seg, capital, rm,
                        replay_policy=getattr(strat, "replay_policy", None), **exits)
    m = compute_metrics(trades, capital)
    m.bh_return_pct = bh_return_pct
    m.bh_curve = bh_curve
    m.option_cost = option_cost
    return trades, m


def prepare_signal_frame(candles) -> pd.DataFrame:
    """Build the validated canonical frame once for a shared candle dataset."""
    return _candles_to_df(candles)


def compute_signals(candles, strat, params, *,
                    frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compute a strategy's canonical signal frame over the FULL candle series and
    trim warmup. Split out of `simulate` (behaviour-preserving) so a caller can
    compute signals ONCE and replay trades over each walk-forward fold with
    identical, seed-consistent indicator values — slicing candles *before* signal
    computation would shift the path-dependent EMA/ATR seeds. Adds `_ratchet_atr`
    when the strategy declares a risk_model. Returns a fresh 0-indexed frame
    (possibly empty)."""
    # A strategy may add working columns. A shared base frame is copied so one
    # strategy can never change the input observed by the next strategy.
    source = _candles_to_df(candles) if frame is None else frame.copy(deep=True)
    sig = strat.signals(source, **params)
    rm = getattr(strat, "risk_model", None)
    if rm:
        # computed on the FULL frame so warmup trimming can't shift ATR values
        sig["_ratchet_atr"] = wilder_atr(
            sig, int(rm["atr_length"]),
            seed_policy=getattr(strat, "risk_atr_seed_policy", "first_observation"),
        )
        if getattr(strat, "risk_atr_seed_policy", "first_observation") == "sma":
            from app.backtest.ratchet import require_risk_atr
            require_risk_atr(sig)
    # trim warmup rows where the strategy's indicators are still NaN. The columns
    # differ per strategy (v3: slope; v4: atr/absZ), so drop on whichever of the
    # known indicator columns this strategy actually emitted — keeps v3 identical.
    return trim_warmup(sig, strat).reset_index(drop=True)


def trim_warmup(sig: pd.DataFrame, strat) -> pd.DataFrame:
    """Drop the bars this strategy does not consider settled.

    Two mechanisms, because strategies declare warmup two different ways:

    1. A strategy that **declares** its warmup (`declared_warmup`) is trimmed by count.
       A graph-backed strategy emits only the four canonical columns, so the NaN sniff
       below finds nothing to drop and would hand the backtest 302 warmup bars the live
       lane masks to False — the two planes would then disagree about which bars exist,
       which is hard invariant 4.
    2. Every hand-written strategy keeps the original behaviour exactly: drop rows where
       its own indicator columns are still NaN. The columns differ per strategy (v3:
       slope; v4: atr/absZ), so drop on whichever it actually emitted.
    """
    declared = getattr(strat, "declared_warmup", None)
    if isinstance(declared, int) and declared > 0:
        return sig.iloc[declared:]
    warm_cols = [c for c in ("ema", "z", "slope", "atr", "absZ") if c in sig.columns]
    return sig.dropna(subset=warm_cols)


def _event_blocked_bar(inst, row, product: str) -> bool:
    """True if a fill on this bar would land inside a scheduled-event blackout.

    The backtest MUST apply the same table as the live engine. If it didn't, every
    backtest would be measured on bars the live bot refuses to trade — flattering the
    result with exactly the event bars the rules exist to avoid, and making the two
    planes disagree about what the strategy even is. Only the calendar-derivable rules
    apply here (weekday sit-outs, the DST-correct US release windows); earnings needs a
    historical calendar the backtester does not have, so it is live-only and documented
    as such."""
    from app.engine.event_risk import active_blackout
    try:
        when = row["date"]
        if not isinstance(when, dt.datetime):
            when = dt.datetime.fromisoformat(str(when))
        if when.tzinfo is not None:
            when = when.replace(tzinfo=None)
    except Exception:
        return False
    # An instrument with no key can match no rule — in a backtest that means "trade it"
    # (unknown history, not unknown danger); the live engine always has a real key.
    return active_blackout(getattr(inst, "key", ""), product, when) is not None


def slipped(price: float, side: str, half_spread: float) -> float:
    """Apply ADVERSE execution cost to a fill.

    You buy above the mid and sell below it, always — so this is direction-aware
    on both legs of a trade. A SHORT pays it inverted (sells lower to open, buys
    higher to cover), which a symmetric implementation would get wrong and quietly
    bias the model toward one side.

    `half_spread` is half the round-trip cost, mirroring how `premium.py` has
    modelled the option spread since it was written — the spot path simply never
    had an equivalent.
    """
    if half_spread <= 0:
        return price
    return price * (1.0 + half_spread) if side == "BUY" else price * (1.0 - half_spread)


PINE_REVERSAL_FIXED_UNIT_POLICY = "pine-reversal-fixed-unit/1"


@dataclass(frozen=True)
class _ReplayContext:
    inst: Any
    seg: str
    capital: float
    rm: Any
    event_risk: bool
    half: float
    fixed_unit: bool
    protective_band: Any = None


@dataclass
class _ReplayState:
    pos: Any = None
    pending: Any = None
    ratchet: Any = None


def _replay_position(context, fill):
    if not context.fixed_unit:
        return _position(context.inst, fill, context.capital)
    lots = 1 if context.inst.segment in _CASH_SEGMENTS else 1 // max(1, int(context.inst.lot_size))
    return 1, fill, lots


def _entry_ratchet(direction, fill, row, rm):
    entry_atr = row.get("_ratchet_atr")
    if rm and entry_atr is not None and math.isfinite(entry_atr) and entry_atr > 0:
        return RatchetState(direction, fill, float(entry_atr), rm)
    return None


def _open_replay_position(state, context, row, index, direction):
    product = "equity_intraday" if context.inst.segment in _CASH_SEGMENTS else "futures"
    fill = slipped(float(row["open"]), "BUY" if direction == "LONG" else "SELL", context.half)
    qty, notional, lots = _replay_position(context, fill)
    if context.event_risk and _event_blocked_bar(context.inst, row, product):
        qty = 0
    if qty <= 0:
        return
    state.pos = {"direction": direction, "entry_price": fill,
                 "entry_time": ist_epoch(row["date"]), "entry_idx": index,
                 "qty": qty, "notional": notional, "lots": lots, "mae_pct": 0.0}
    state.ratchet = _entry_ratchet(direction, fill, row, context.rm)


def _fill_replay_pending(state, context, row, index, trades):
    kind, argument, _ = state.pending
    state.pending = None
    if kind in {"EXIT", "REVERSE"} and state.pos is not None:
        side = "SELL" if state.pos["direction"] == "LONG" else "BUY"
        fill = slipped(float(row["open"]), side, context.half)
        reason = "STRATEGY_REVERSAL" if kind == "REVERSE" else argument
        trades.append(_close(state.pos, fill, ist_epoch(row["date"]), index, context.seg, reason))
        state.pos = None
        state.ratchet = None
    if kind in {"ENTER", "REVERSE"} and state.pos is None:
        _open_replay_position(state, context, row, index, argument)


def _replay_decision(state, context, row, index):
    direction = replay_decisions.entry_direction(row, context.fixed_unit)
    if state.pos is not None:
        _update_mae(state.pos, row)
    return replay_decisions.next_decision(state.pos, state.ratchet, row, index, direction,
        allow_reversal=context.fixed_unit, protective_band=context.protective_band,
        unprotected_exit_policy=BACKTEST_EXIT_POLICY)


def run_trades(sig, inst, seg: str, capital: float, rm,
               event_risk: bool = True, slippage_pct: float | None = None,
               replay_policy: str | None = None,
               stop_loss_pct: float | None = None,
               take_profit_pct: float | None = None) -> list[BTTrade]:
    """Replay one shared next-open state machine.

    None preserves one-lot/cash-budget legacy behavior. The explicit Pine replay
    policy uses one unit and permits opposite confirmed entries to replace a held
    position at the next open, including signals on its original fill bar. This
    models only these declared rules, not complete Pine order-emulator parity.
    Optional percentage bands use the slipped entry fill and completed closes after
    the entry bar. Intrabar touches are ignored; confirmed exits fill at the next
    actual open with adverse slippage, including gaps beyond the band. A terminal
    trigger has no next-open fill and remains OPEN_AT_END. Protective exits precede
    reversals; disabled bands preserve the original Pine reversal behavior.
    """
    if replay_policy not in {None, PINE_REVERSAL_FIXED_UNIT_POLICY}:
        raise ValueError("BACKTEST_REPLAY_POLICY_UNSUPPORTED")
    if slippage_pct is None:
        slippage_pct = float(get_settings().backtest_slippage_pct)
    context = _ReplayContext(inst, seg, capital, rm, event_risk,
                             float(slippage_pct) / 2.0,
                             replay_policy == PINE_REVERSAL_FIXED_UNIT_POLICY,
                             protective_band_document(stop_loss_pct, take_profit_pct))
    state = _ReplayState()
    trades: list[BTTrade] = []
    rows = sig.to_dict("records")
    for index, row in enumerate(rows):
        if state.pending is not None and state.pending[2] == index:
            _fill_replay_pending(state, context, row, index, trades)
        state.pending = _replay_decision(state, context, row, index)
    # An unfillable terminal decision never invents a next open. Mark the held
    # position at the final close under the existing OPEN_AT_END convention.
    if state.pos is not None:
        last = rows[-1]
        side = "SELL" if state.pos["direction"] == "LONG" else "BUY"
        fill = slipped(float(last["close"]), side, context.half)
        trades.append(_close(state.pos, fill, ist_epoch(last["date"]),
                             len(rows) - 1, seg, "OPEN_AT_END"))
    return trades


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
    entry_charge = compute_charges_exact(
        seg, entry_side, entry_price, qty,
        schedule_id=CORRECTED_RESEARCH_CHARGE_SCHEDULE,
    )
    exit_charge = compute_charges_exact(
        seg, exit_side, exit_price, qty,
        schedule_id=CORRECTED_RESEARCH_CHARGE_SCHEDULE,
    )
    charges = (entry_charge["total_minor"] + exit_charge["total_minor"]) / 100
    return BTTrade(
        direction=d, entry_time=pos["entry_time"], entry_price=entry_price,
        exit_time=exit_time, exit_price=exit_price, qty=qty,
        gross_pnl=gross, charges=charges, net_pnl=gross - charges,
        reason=reason, bars_held=exit_idx - pos["entry_idx"],
        mae_pct=pos.get("mae_pct", 0.0), notional=pos.get("notional", entry_price * qty),
        lots=pos.get("lots", 0),
    )
