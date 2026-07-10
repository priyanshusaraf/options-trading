"""
Synthetic-premium backtest (audit C6) — pure/offline, no live-money path.

The spot backtest (`app/backtest/engine.py`) evaluates the strategy's edge on the
UNDERLYING, because option history is mostly unavailable. That deliberately skips
the thing the live engine actually trades: an ATM option premium, with its own
decay, convexity and stop/target mechanics. This module reconstructs a realistic
premium path OFFLINE from the underlying candles via Black-Scholes, using a
volatility estimate derived purely from the underlying's own realised vol (no
external IV feed — there isn't one for historical options in this codebase).

MODEL (deliberately the smallest correct version — no rolls, no per-delta strike
selection, no event-driven IV):
  - IV: sigma(t) = clamp(RV_20d(t), 0.10, 2.0) * iv_rv_multiplier. RV is a trailing
    20-DAILY-close realised vol, annualised (×√252), and — critically — KNOWN ONLY
    AS OF THE START of the day it's applied to (computed from the PRIOR day's close
    backwards), so pricing a bar never uses information from that bar's own future.
    Forward-filled: every intraday bar of a given day reuses that day's single sigma.
  - Entry: strike = nearest `inst.strike_step` to the fill bar's OPEN; CE for a LONG
    signal, PE for a SHORT signal (mirrors the live engine's buy-CE/buy-PE rule).
    A signal confirmed on bar i fills at bar i+1's OPEN (Pine parity, same as
    `engine.simulate`). Entries during the RV warmup (sigma unknown) or whose
    computed premium is a sub-₹0.50 dead cheap contract are skipped — dropped, not
    retried.
  - Per bar: the underlying's low/high map (monotonically, via Black-Scholes) to a
    premium low/high; the close maps to a premium close. The exit stack, evaluated
    in strict priority, is INTRABAR for the protective legs (stop/target/ratchet —
    mirroring how the live engine's risk loop marks continuously) but bar-CLOSE +
    next-bar-OPEN for the strategy's own exit flag (mirroring engine.simulate's
    Pine-parity fill convention, since a flag only confirms on a completed bar):
      1. trail the premium stop upward (legacy `exit_monitor.trailing_stop`) —
         UNLESS the strategy declares a `risk_model`, in which case H2 applies:
         the underlying-based ratchet drives the exit instead and this legacy
         trail is skipped entirely.
      2. STOP_LOSS if the bar's low-side premium pierces the (possibly trailed)
         stop — checked BEFORE target, so a same-bar double-breach is a stop.
      3. TARGET if the bar's high-side premium reaches the target.
      4. RATCHET_STOP (only when `risk_model` declared): the Pine-parity
         `RatchetState` is driven on the UNDERLYING exactly as in `engine.simulate`;
         a close-confirmed hit exits at that bar's close-mapped premium.
      5. STRATEGY_EXIT: the strategy's own longExit/shortExit flag, deferred to
         next-bar-OPEN like every other signal-driven exit in this codebase.
  - Expiry: once time-to-expiry drops to (or below) one calendar day
    (1/365 year), the contract is forced closed at that bar's close-mapped
    premium, reason EXPIRY. No roll — the smallest correct version stops there.
  - Spread: `premium_spread_pct` (round-trip) is modelled as a HALF-spread markup
    on entry (buy above mid) and a half-spread markdown on every exit (sell below
    whatever level triggered the exit) — applied uniformly across all five exit
    reasons for a single, consistent cost model.
  - Charges: the OPTIONS schedule (`inst.segment` — NFO/BFO/MCX/NCDEX — used
    AS-IS, unlike the spot backtest which maps to the futures schedule), on both
    the entry premium and the exit premium.

Position sizing is always exactly ONE lot (`inst.lot_size`), long-premium only
(BUY CE or BUY PE — never short options), matching the live engine.
"""
from __future__ import annotations

import math

import pandas as pd

from app.backtest.metrics import BTMetrics, BTTrade, compute_metrics
from app.backtest.ratchet import RatchetState, wilder_atr
from app.core.market_hours import ist_epoch
from app.engine.charges import compute_charges
from app.engine.exit_monitor import trailing_stop
from app.options.pricing import bs_price
from app.strategy.registry import get_strategy

# Mirrors Settings.risk_free_rate — kept as a local constant (not `get_settings()`)
# so this module stays pure/offline and import-safe with no env/DB coupling.
RISK_FREE_RATE = 0.065

RV_WINDOW_DAYS = 20          # trailing daily-return window for the RV estimate
IV_FLOOR, IV_CEIL = 0.10, 2.0
EXPIRY_FLOOR_YEARS = 1.0 / 365.0
MIN_ENTRY_PREMIUM = 0.50     # sub-50-paisa contracts are skipped (dead/illiquid)
SECONDS_PER_YEAR = 365 * 86400

DEFAULT_PREMIUM_PARAMS: dict = {
    "stop_loss_pct": 0.35,
    "target_pct": 0.60,
    "iv_rv_multiplier": 1.15,
    "premium_spread_pct": 0.02,
    "entry_dte_days": 14,
    "trail_enabled": True,
    "trail_trigger_pct": 0.10,
    "trail_first_step_lock_pct": 0.025,
    "trail_step_lock_pct": 0.10,
}


def _candles_to_df(candles) -> pd.DataFrame:
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


def _row_date(row):
    d = row["date"]
    return d.date() if hasattr(d, "date") else d


def _daily_rv_by_date(candles) -> dict:
    """Trailing-20-daily-log-return realised vol (annualised, ×√252), KEYED BY THE
    DAY IT BECOMES AVAILABLE (i.e. the day AFTER it was computable) — so looking it
    up for any bar never uses that bar's own day's close. Needs ~21 daily closes
    before the first value appears (RV_WINDOW_DAYS returns + 1 day of lag)."""
    by_day: dict = {}
    for c in candles:
        by_day[c.ts.date()] = float(c.close)   # last close wins per day (chronological)
    days = sorted(by_day)
    closes = [by_day[d] for d in days]
    n = len(days)
    # rets[k-1] == the log-return REALISED on day `days[k]` (k = 1..n-1)
    rets = [math.log(closes[k] / closes[k - 1])
            if closes[k - 1] > 0 and closes[k] > 0 else 0.0
            for k in range(1, n)]
    sigma_by_date: dict = {}
    for d in range(RV_WINDOW_DAYS, n - 1):
        window = rets[d - RV_WINDOW_DAYS:d]   # 20 returns ending at day `d`
        mean = sum(window) / len(window)
        var = (sum((x - mean) ** 2 for x in window) / (len(window) - 1)) if len(window) > 1 else 0.0
        rv = math.sqrt(var) * math.sqrt(252)
        sigma_by_date[days[d + 1]] = rv        # available at the OPEN of day d+1
    return sigma_by_date


def _sigma_for(sigma_map: dict, day, multiplier: float) -> float | None:
    rv = sigma_map.get(day)
    if rv is None or not math.isfinite(rv):
        return None
    return min(max(rv, IV_FLOOR), IV_CEIL) * multiplier


def _T(pos: dict, ts: int) -> float:
    return max(0.0, pos["T0"] - (ts - pos["entry_time"]) / SECONDS_PER_YEAR)


def _open_position(direction: str, S0: float, t: int, i: int, inst, p: dict,
                   sigma: float) -> dict | None:
    flag = "c" if direction == "LONG" else "p"
    step = float(getattr(inst, "strike_step", 0) or 0)
    K = round(S0 / step) * step if step > 0 else S0
    T0 = p["entry_dte_days"] / 365.0
    half_spread = p["premium_spread_pct"] / 2.0
    raw = bs_price(S0, K, T0, RISK_FREE_RATE, sigma, flag)
    entry_fill = raw * (1 + half_spread)
    if entry_fill < MIN_ENTRY_PREMIUM:
        return None
    qty = max(1, int(inst.lot_size))
    return {
        "direction": direction, "flag": flag, "K": K, "T0": T0,
        "entry_fill": entry_fill, "entry_time": t, "entry_idx": i, "qty": qty,
        "stop": entry_fill * (1 - p["stop_loss_pct"]),
        "target": entry_fill * (1 + p["target_pct"]),
        "hw": entry_fill, "notional": entry_fill * qty, "mae_pct": 0.0,
        "entry_spot": S0,
    }


def _update_mae_premium(pos: dict, worst_premium: float) -> None:
    entry = pos["entry_fill"]
    if entry <= 0:
        return
    adverse = (entry - worst_premium) / entry * 100.0
    if adverse > pos["mae_pct"]:
        pos["mae_pct"] = adverse


def _close_premium(pos: dict, exit_price: float, exit_time: int, exit_idx: int,
                   seg: str, reason: str) -> BTTrade:
    qty = pos["qty"]
    entry_price = pos["entry_fill"]
    # ALWAYS long-premium (buy CE on a LONG signal, buy PE on a SHORT signal) —
    # unlike the spot backtest, direction never flips the P&L sign here.
    gross = (exit_price - entry_price) * qty
    charges = (compute_charges(seg, "BUY", entry_price, qty)["total"]
              + compute_charges(seg, "SELL", exit_price, qty)["total"])
    return BTTrade(
        direction=pos["direction"], entry_time=pos["entry_time"], entry_price=entry_price,
        exit_time=exit_time, exit_price=exit_price, qty=qty,
        gross_pnl=gross, charges=charges, net_pnl=gross - charges,
        reason=reason, bars_held=exit_idx - pos["entry_idx"],
        mae_pct=pos.get("mae_pct", 0.0), notional=pos.get("notional", entry_price * qty),
        lots=1,
    )


def simulate_premium(candles, inst, interval: str, *, strategy=None,
                     params: dict | None = None,
                     capital: float = 50_000.0) -> tuple[list[BTTrade], BTMetrics]:
    """Run a strategy's signals over `candles` and translate them into a synthetic
    ATM-option premium path (Black-Scholes on the underlying's own realised vol),
    returning (trades, metrics) exactly like `engine.simulate`. Pure/offline — no
    network, no DB, no live-money path.

    Skips (returns `([], BTMetrics())`) when the instrument has no listed options
    (`inst.has_options is False`) — the CALLER is responsible for surfacing that as
    a `premium_error` (this function has no error channel of its own)."""
    if not getattr(inst, "has_options", True):
        return [], BTMetrics()

    strat = strategy if strategy is not None else get_strategy(None)
    params = params or {}
    p = dict(DEFAULT_PREMIUM_PARAMS)
    p.update({k: v for k, v in params.items() if k in DEFAULT_PREMIUM_PARAMS and v is not None})
    strat_kwargs = {k: v for k, v in params.items() if k in strat.default_params}

    sig = strat.signals(_candles_to_df(candles), **strat_kwargs)
    rm = getattr(strat, "risk_model", None)
    if rm:
        sig["_ratchet_atr"] = wilder_atr(sig, int(rm["atr_length"]))
    warm_cols = [c for c in ("ema", "z", "slope", "atr", "absZ") if c in sig.columns]
    sig = sig.dropna(subset=warm_cols).reset_index(drop=True)
    if sig.empty:
        return [], BTMetrics()

    sigma_map = _daily_rv_by_date(candles)
    seg = inst.segment
    half_spread = p["premium_spread_pct"] / 2.0

    trades: list[BTTrade] = []
    pos: dict | None = None
    pending: tuple[str, str] | None = None
    ratchet: RatchetState | None = None
    last_sigma: float | None = None

    rows = sig.to_dict("records")
    for i, r in enumerate(rows):
        t = ist_epoch(r["date"])
        S_open, S_close = float(r["open"]), float(r["close"])
        S_high, S_low = float(r["high"]), float(r["low"])
        sigma = _sigma_for(sigma_map, _row_date(r), p["iv_rv_multiplier"])
        if sigma is not None:
            last_sigma = sigma
        eff_sigma = sigma if sigma is not None else last_sigma

        # 1) fill the PREVIOUS bar's confirmed decision at THIS bar's OPEN
        if pending is not None:
            kind, arg = pending
            pending = None
            if kind == "ENTER" and pos is None:
                if eff_sigma is not None:
                    pos = _open_position(arg, S_open, t, i, inst, p, eff_sigma)
                    ratchet = None
                    if pos is not None and rm:
                        entry_atr = r.get("_ratchet_atr")
                        if entry_atr is not None and math.isfinite(entry_atr) and entry_atr > 0:
                            ratchet = RatchetState(arg, S_open, float(entry_atr), rm)
                # eff_sigma is None (still in RV warmup) -> the signal is dropped
            elif kind == "EXIT" and pos is not None:
                T_i = max(_T(pos, t), EXPIRY_FLOOR_YEARS)   # never price a non-positive T
                exit_prem = bs_price(S_open, pos["K"], T_i, RISK_FREE_RATE, eff_sigma, pos["flag"])
                trades.append(_close_premium(pos, exit_prem * (1 - half_spread), t, i, seg, arg))
                pos = None
                ratchet = None

        # 2) manage the currently open position — bars STRICTLY AFTER the fill bar
        if pos is not None and i > pos["entry_idx"]:
            T_i = _T(pos, t)
            if T_i <= EXPIRY_FLOOR_YEARS:
                # price at the floor (last tradeable moment), never a non-positive T
                prem_close = bs_price(S_close, pos["K"], EXPIRY_FLOOR_YEARS, RISK_FREE_RATE,
                                      eff_sigma, pos["flag"])
                trades.append(_close_premium(pos, prem_close * (1 - half_spread), t, i, seg, "EXPIRY"))
                pos = None
                ratchet = None
                continue

            p_lo = bs_price(S_low, pos["K"], T_i, RISK_FREE_RATE, eff_sigma, pos["flag"])
            p_hi = bs_price(S_high, pos["K"], T_i, RISK_FREE_RATE, eff_sigma, pos["flag"])
            prem_low, prem_high = min(p_lo, p_hi), max(p_lo, p_hi)
            _update_mae_premium(pos, prem_low)

            # the stop/target check uses the level AS OF THE START of this bar
            # (whatever the PRIOR bar's trailing update left it at) — trailing
            # against THIS bar's own high and then immediately checking THIS
            # bar's own low against the freshly-raised stop would be a same-bar
            # whipsaw artifact of bar-level (not tick-level) data: a bar's high
            # and low order within the bar is unknown, so a fresh trail must
            # only take effect starting the NEXT bar.
            if prem_low <= pos["stop"]:
                trades.append(_close_premium(pos, pos["stop"] * (1 - half_spread), t, i, seg, "STOP_LOSS"))
                pos = None
                ratchet = None
            elif prem_high >= pos["target"]:
                trades.append(_close_premium(pos, pos["target"] * (1 - half_spread), t, i, seg, "TARGET"))
                pos = None
                ratchet = None
            elif rm is not None:
                atr_i = r.get("_ratchet_atr")
                ratchet_hit = False
                if ratchet is not None and atr_i is not None and math.isfinite(atr_i):
                    ratchet.update(S_high, S_low, S_close, float(atr_i))
                    ratchet_hit = ratchet.stop_hit(S_close)
                if ratchet_hit:
                    prem_close = bs_price(S_close, pos["K"], T_i, RISK_FREE_RATE, eff_sigma, pos["flag"])
                    trades.append(_close_premium(pos, prem_close * (1 - half_spread), t, i, seg, "RATCHET_STOP"))
                    pos = None
                    ratchet = None
                else:
                    d = pos["direction"]
                    if (d == "LONG" and bool(r["longExit"])) or (d == "SHORT" and bool(r["shortExit"])):
                        pending = ("EXIT", "STRATEGY_EXIT")
            else:
                d = pos["direction"]
                if (d == "LONG" and bool(r["longExit"])) or (d == "SHORT" and bool(r["shortExit"])):
                    pending = ("EXIT", "STRATEGY_EXIT")

            # trail the stop for the NEXT bar (H2: skipped when risk_model is
            # declared — the underlying ratchet drives the exit instead)
            if pos is not None and rm is None and p.get("trail_enabled", True):
                pos["hw"] = max(pos["hw"], prem_high)
                pos["stop"] = trailing_stop(
                    pos["entry_fill"], pos["hw"], pos["stop"],
                    trigger_pct=p["trail_trigger_pct"],
                    first_step_lock_pct=p["trail_first_step_lock_pct"],
                    step_lock_pct=p["trail_step_lock_pct"])
        elif pos is None and (r["longEntry"] or r["shortEntry"]):
            pending = ("ENTER", "LONG" if r["longEntry"] else "SHORT")

    # close any still-open position at the LAST AVAILABLE CANDLE (end of data)
    if pos is not None:
        last = rows[-1]
        t_last = ist_epoch(last["date"])
        T_i = max(_T(pos, t_last), EXPIRY_FLOOR_YEARS)   # never price a non-positive T
        sigma_last = last_sigma if last_sigma is not None else IV_FLOOR * p["iv_rv_multiplier"]
        prem_close = bs_price(float(last["close"]), pos["K"], T_i, RISK_FREE_RATE, sigma_last, pos["flag"])
        trades.append(_close_premium(pos, prem_close * (1 - half_spread), t_last, len(rows) - 1,
                                     seg, "OPEN_AT_END"))

    m = compute_metrics(trades, capital)
    return trades, m
