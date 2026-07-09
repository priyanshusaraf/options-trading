"""
The autonomous engine loop. One `tick()` is the whole brain:

  1. Recompute the strategy on each enabled instrument's latest candles.
  2. EXIT pass — mark open positions to market; close any that hit the premium
     stop/target or the strategy's exit flag (run first so freed capital is
     usable this same tick).
  3. ENTRY pass — collect instruments showing a FRESH entry crossover that we
     are not already holding; price the best contract for each; hand the costed
     candidates to the allocator (priority order only bites under a shortfall);
     fill the funded ones at 1 lot each. Unfunded signals are dropped, never
     queued.
  4. Snapshot portfolio equity.

In mock mode the loop also advances the simulated clock each iteration so the
whole story plays out on its own. In live mode it polls on a fixed cadence and
acts on completed candles. The owner does nothing after starting it.
"""
from __future__ import annotations

import asyncio

import pandas as pd
from sqlalchemy import select

from app.core.config import get_settings
from app.core.instruments import all_instruments, get_instrument
from app.core.logging import log
from app.db.models import InstrumentState, SignalEvent
from app.db.session import SessionLocal
from app.core.config import DEFAULT_LIVE_INTERVAL, normalize_live_interval
from app.engine.allocator import Candidate, allocate
from app.engine.broker import PaperBroker
from app.engine.broker_factory import make_broker
from app.engine.capital import deployable_capital
from app.engine.charges import compute_charges
from app.engine.equity_entry import (
    IntradayCandidate, equity_exit, select_intraday_entries)
from app.engine.execution_policy import plan_order
from app.engine.exit_monitor import evaluate_exit, trailing_stop
from app.engine.health import HealthTracker, is_stale
from app.core.market_hours import ist_epoch
from app.core.mis_blocklist import is_mis_blocked
from app.engine.risk_controls import (
    before_entry_window, daily_loss_halt, expiry_too_close, in_reentry_cooldown,
    intraday_blocked_for_expiry_day, outside_trading_session, over_per_trade_cap,
    round_trip_cap_reached, signal_already_evaluated, signal_too_old, slots_available)
from app.notify.notifier import Notifier
from app.options.picker import pick_option
from app.providers.factory import get_provider
from app.strategy.registry import DEFAULT_STRATEGY_KEY, get_strategy
from app.strategy.signals import to_payload


def _to_df(candles) -> pd.DataFrame:
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


def _equity_charge_segment(inst) -> str:
    """Charge segment for an intraday-equity position (MIS): BSE names on BSE,
    everything else on NSE."""
    seg = (getattr(inst, "segment", "") or "").upper()
    return "BSE_INTRADAY" if seg in ("BSE", "BSE_EQ") else "NSE_INTRADAY"


# live-interval string -> candle minutes (shared by the scan gate and the
# signal-age guard; an unknown interval falls back to 15m, the strategy default)
_INTERVAL_MINUTES = {"5minute": 5, "15minute": 15, "30minute": 30, "60minute": 60}


class EngineRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = get_provider()
        self.notifier = Notifier()             # Telegram alerts (no-op if unconfigured)
        # PaperBroker unless the live-execution flags are set (then LiveBroker).
        self.broker = make_broker(self.provider, self.notifier)
        self.state: dict[str, dict] = {}      # latest per-instrument engine snapshot
        self.last_pick: dict[str, dict] = {}  # latest picker output (Options-Calc view)
        self.enabled: set[str] = self._load_enabled()
        self.intervals: dict[str, str] = self._load_intervals()   # per-instrument live TF
        self.entry_blocks: set[str] = self._load_entry_blocks()   # entries disabled
        # dual-segment / multi-strategy per-instrument config
        self.products, self.strategy_keys, self.priority_flags, self.overtrade_flags = self._load_instr_config()
        self.health = HealthTracker()
        self.params: dict = self._effective_params()   # runtime-overridable knobs
        self.position_ticks: dict[str, dict] = {}   # latest marks for open positions (fast UI feed)
        self.last_scan_ok: dict[str, object] = {}   # key -> last successful candle scan time (per-instrument freshness)
        self._stopped_at: dict[str, object] = {}    # instrument -> last stop-out time (re-entry cooldown)
        self._next_scan: dict[str, float] = {}      # key -> earliest epoch to refetch candles
        self.last_entry_bar: dict[str, int] = {}    # key -> candle epoch of the last ENTRY signal evaluated (fresh-signal guard #12)
        self.running = False
        # ARM-TO-TRADE gate: the engine always scans, marks open positions, fires
        # SL/TP and sends alerts — but it NEVER opens a new position until the owner
        # explicitly arms it. Defaults disarmed on every process start (you must arm
        # each session), and the kill switch disarms it again.
        self.armed = False
        self._halt_notified_date = None        # de-dupe the daily-loss-halt alert
        self._next_reconcile_epoch = 0.0       # throttle live orphan reconciliation
        self._next_cache_sweep_epoch = 0.0     # throttle the watchlist option-chain research cache
        self._account_funds: dict | None = None  # cached live Kite funds {available, net}
        self._next_funds_epoch = 0.0           # throttle margins() polling (live balance)
        self._next_ledger_epoch = 0.0          # throttle the cash-invariant self-check (H10)
        self._ledger_drift_alerted = False     # de-dupe the ledger-drift alert per episode
        self.tick_count = 0
        self._idle_logged = False  # de-dupe the "markets closed" log line
        self._lock = asyncio.Lock()           # serialise risk vs signal lane DB mutations
        self.on_update = None                 # async callback(state) — signal-lane snapshot
        self.on_position_ticks = None         # async callback(ticks) — fast-lane marks

    # ── instrument enable/disable ─────────────────────────────────────────
    def _load_enabled(self) -> set[str]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(InstrumentState)))
            en = {r.instrument_key for r in rows if r.enabled}
        return en or {i.key for i in all_instruments()}

    def set_enabled(self, key: str, enabled: bool) -> None:
        with SessionLocal() as s:
            r = s.get(InstrumentState, key)
            if r:
                r.enabled = enabled
                s.commit()
        self.enabled.add(key) if enabled else self.enabled.discard(key)
        log.info(f"{'ENABLED' if enabled else 'DISABLED'} {key} for trading")

    # ── per-instrument live interval + entry blocks ───────────────────────
    def _load_intervals(self) -> dict[str, str]:
        with SessionLocal() as s:
            return {r.instrument_key: normalize_live_interval(r.live_interval or "")
                    for r in s.scalars(select(InstrumentState))}

    def _load_entry_blocks(self) -> set[str]:
        with SessionLocal() as s:
            return {r.instrument_key for r in s.scalars(select(InstrumentState))
                    if r.entries_blocked}

    def _load_instr_config(self) -> tuple[dict, dict, dict, dict]:
        """Per-instrument product (options|equity_intraday), assigned strategy, the
        purple priority flag, and the red overtrading flag. Missing/legacy rows
        default to options/v3/not-priority/not-overtraded."""
        products, strategies, priority, overtrade = {}, {}, {}, {}
        with SessionLocal() as s:
            for r in s.scalars(select(InstrumentState)):
                products[r.instrument_key] = r.product or "options"
                if r.strategy_key:
                    strategies[r.instrument_key] = r.strategy_key
                if r.priority_flag:
                    priority[r.instrument_key] = True
                if getattr(r, "overtrade_flag", False):
                    overtrade[r.instrument_key] = True
        return products, strategies, priority, overtrade

    def _interval_for(self, key: str) -> str:
        return normalize_live_interval(self.intervals.get(key, DEFAULT_LIVE_INTERVAL))

    def set_interval(self, key: str, interval: str) -> str:
        iv = normalize_live_interval(interval)
        with SessionLocal() as s:
            r = s.get(InstrumentState, key)
            if r:
                r.live_interval = iv
                s.commit()
        self.intervals[key] = iv
        self._next_scan.pop(key, None)   # force a re-scan at the new interval
        log.info(f"live interval set to {iv}", instrument=key)
        return iv

    def _effective_params(self) -> dict:
        from app.core.runtime_config import effective
        return effective(self.settings)

    def refresh_params(self) -> None:
        """Re-read runtime overrides so live Settings edits take effect."""
        self.params = self._effective_params()

    def set_entries_blocked(self, key: str, blocked: bool) -> None:
        with SessionLocal() as s:
            r = s.get(InstrumentState, key)
            if r:
                r.entries_blocked = blocked
                s.commit()
        self.entry_blocks.add(key) if blocked else self.entry_blocks.discard(key)
        log.info(f"{'BLOCKED' if blocked else 'UNBLOCKED'} new entries", instrument=key)

    def _upsert_state(self, key: str):
        """Get the InstrumentState row for `key`, creating it if missing (a freshly
        added instrument may not have a row yet)."""
        s = SessionLocal()
        r = s.get(InstrumentState, key)
        if r is None:
            r = InstrumentState(instrument_key=key)
            s.add(r)
        return s, r

    def set_product(self, key: str, product: str) -> str:
        """Assign an instrument to the options or equity_intraday segment (live-applied).
        Refuses intraday for a name the MIS-availability sheet marks ineligible (#5)."""
        product = "equity_intraday" if product == "equity_intraday" else "options"
        if product == "equity_intraday" and is_mis_blocked(key):
            raise ValueError(f"{key} is not MIS-eligible (no/low intraday leverage) — "
                             f"can't add it to the intraday portfolio")
        s, r = self._upsert_state(key)
        r.product = product
        s.commit(); s.close()
        self.products[key] = product
        log.info(f"PRODUCT set to {product}", instrument=key)
        return product

    def set_priority_flag(self, key: str, flag: bool) -> None:
        """Toggle the watchlist 'purple' priority flag (intraday selection always wins)."""
        s, r = self._upsert_state(key)
        r.priority_flag = bool(flag)
        s.commit(); s.close()
        if flag:
            self.priority_flags[key] = True
        else:
            self.priority_flags.pop(key, None)
        log.info(f"PRIORITY {'set' if flag else 'cleared'}", instrument=key)

    def set_overtrade_flag(self, key: str, flag: bool) -> None:
        """Toggle the watchlist 'red' overtrading flag. Advisory only — the engine
        does NOT change behavior based on it."""
        s, r = self._upsert_state(key)
        r.overtrade_flag = bool(flag)
        s.commit(); s.close()
        if flag:
            self.overtrade_flags[key] = True
        else:
            self.overtrade_flags.pop(key, None)
        log.info(f"OVERTRADE {'set' if flag else 'cleared'}", instrument=key)

    def set_strategy(self, key: str, strategy_key: str | None) -> str | None:
        """Assign which registered strategy trades this instrument (None = default v3)."""
        from app.strategy.registry import strategy_keys as _keys
        sk = strategy_key if (strategy_key and strategy_key in _keys()) else None
        s, r = self._upsert_state(key)
        r.strategy_key = sk
        s.commit(); s.close()
        if sk:
            self.strategy_keys[key] = sk
        else:
            self.strategy_keys.pop(key, None)
        log.info(f"STRATEGY set to {sk or 'default'}", instrument=key)
        return sk

    # ── lane 1: strategy recompute (per-instrument interval) ──────────────
    def scan_signals(self) -> None:
        s, prov = self.settings, self.provider
        opens = {p.instrument_key: p for p in self.broker.open_positions()}
        for key in list(self.enabled):
            inst = get_instrument(key)
            if not prov.is_tradable_now(inst):
                continue  # market closed — no new candle can print; don't poll
            try:
                candles = prov.get_candles(inst, self._interval_for(key), s.history_days)
                self.health.record_ok("candle", prov.now())
                self.last_scan_ok[key] = prov.now()   # per-instrument freshness
            except Exception as e:
                self.health.record_fail("candle", str(e), prov.now())
                if self.health.should_log_failure("candle"):
                    log.error(f"candles failed: {e}", instrument=key)
                continue
            if len(candles) < s.ema_length + 5:
                continue
            # per-instrument strategy: the default (v3) keeps the exact chart payload;
            # any other strategy yields a strategy-agnostic latest (canonical flags).
            strat = get_strategy(self.strategy_keys.get(key))
            if strat.key == DEFAULT_STRATEGY_KEY:
                sig = strat.signals(_to_df(candles), ema_length=s.ema_length,
                                    z_length=s.z_length, entry_z=s.entry_z,
                                    slope_lookback=s.slope_lookback)
                latest = to_payload(sig, entry_z=s.entry_z)["latest"]
            else:
                sig = strat.signals(_to_df(candles))
                latest = self._generic_latest(sig)
            if not latest:
                continue
            held = opens.get(key)
            self.state[key] = {
                "instrument": key, "name": inst.name, "segment": inst.segment,
                "interval": self._interval_for(key),
                "time": latest["time"], "close": latest["close"], "ema": latest["ema"],
                "z": latest["z"], "z_prev": latest["z_prev"], "slope": latest["slope"],
                "std": latest["std"], "trend": latest["trend"], "signal": latest["signal"],
                "long_exit": latest["long_exit"], "short_exit": latest["short_exit"],
                "position": held.to_dict() if held else None,
                "has_options": inst.has_options,
                "entries_blocked": key in self.entry_blocks,
                "product": self.products.get(key, "options"),
                "strategy": strat.key,
                "priority_flag": self.priority_flags.get(key, False),
            }

    def _generic_latest(self, sig) -> dict | None:
        """Strategy-agnostic 'latest bar' for non-default strategies — reads the
        canonical flag columns (and whatever indicator columns exist) so any
        registered strategy can drive the engine without the v3-only chart payload."""
        from app.strategy.signals import _epoch
        sig = sig.dropna(subset=["longEntry", "shortEntry"]).reset_index(drop=True) \
            if "longEntry" in sig.columns else sig
        if sig.empty:
            return None
        last = sig.iloc[-1]

        def g(col):
            return float(last[col]) if col in sig.columns and pd.notna(last[col]) else None
        signal = ("LONG_ENTRY" if bool(last["longEntry"])
                  else "SHORT_ENTRY" if bool(last["shortEntry"]) else "NONE")
        drift, z = g("driftScore"), g("z")
        trend = (None if drift is None else
                 "bull" if drift > 0 else "bear" if drift < 0 else "flat")
        return {
            "time": _epoch(last["date"]), "close": round(float(last["close"]), 2),
            "ema": round(g("ema"), 2) if g("ema") is not None else None,
            "z": round(z, 4) if z is not None else None, "z_prev": None,
            "slope": None, "std": None, "trend": trend, "signal": signal,
            "long_exit": bool(last["longExit"]), "short_exit": bool(last["shortExit"]),
        }

    # ── lane 2 (fast): mark open positions, trail stop, staleness guard, exit ─
    def mark_and_exit_positions(self) -> None:
        prov = self.provider
        now = prov.now()
        opens = {p.instrument_key: p for p in self.broker.open_positions()}
        if not opens:
            self.position_ticks = {}
            return
        insts = [get_instrument(k) for k in opens]
        try:
            snap = prov.live_snapshot(insts, list(opens.values()))
            self.health.record_ok("quote", now)
        except Exception as e:
            self.health.record_fail("quote", str(e), now)
            if self.health.should_log_failure("quote"):
                log.error(f"position snapshot failed: {e}")
            snap = {}
        ticks: dict[str, dict] = {}
        for key, pos in list(opens.items()):
            data = snap.get(key) or {}
            premium = data.get("option_premium")
            spot = data.get("spot")
            # intraday equity marks to SPOT (no option), exits on direction-aware
            # SL/TP + strategy flag, and never trails. Handled separately so the
            # options long-premium path below is untouched.
            if pos.segment == "equity_intraday":
                self._mark_exit_equity(pos, key, spot, now, ticks, opens)
                continue
            if premium is not None:
                self.broker.mark(pos, premium, spot, now=now)
                self._apply_trailing(pos)
            pos_stale = premium is None or is_stale(
                pos.last_mark_time, now, self.settings.max_stale_seconds)
            st = self.state.get(key, {})
            if not pos_stale:
                should, reason = evaluate_exit(
                    pos.direction, pos.stop_price, pos.target_price, premium,
                    st.get("long_exit", False), st.get("short_exit", False),
                    target_disabled=pos.no_take_profit)
                if should:
                    trade = self.broker.close_position(pos, premium, reason, now, spot)
                    if trade is not None:
                        if reason == "STOP_LOSS":
                            self._stopped_at[key] = now   # start the re-entry cooldown
                        if self.params.get("notify_enabled", True):
                            self.notifier.closed(trade)
                        opens.pop(key, None)
                        if key in self.state:
                            self.state[key]["position"] = None
                        continue
                    # live close didn't go through (unfilled / ownership block) —
                    # keep managing the position; LiveBroker has already alerted.
                # not exiting — warn (once) if the premium is nearing the SL or TP
                if self.params.get("notify_enabled", True):
                    self.notifier.check_proximity(
                        key, pos.tradingsymbol, premium, pos.stop_price, pos.target_price,
                        self.params.get("alert_proximity_pct", 0.10))
            d = pos.to_dict()
            ticks[key] = {
                "instrument": key, "tradingsymbol": pos.tradingsymbol,
                "option_premium": round(premium, 2) if premium is not None else None,
                "spot": round(spot, 2) if spot else None,
                "unrealized_pnl": d["unrealized_pnl"],
                "stop_price": d["stop_price"], "target_price": d["target_price"],
                "high_water_premium": d["high_water_premium"],
                "stale": pos_stale,
                "stale_age": None if pos.last_mark_time is None
                             else round((now - pos.last_mark_time).total_seconds(), 1),
                "last_mark_time": pos.last_mark_time.isoformat() if pos.last_mark_time else None,
            }
        self.broker.commit()  # persist marks + ratcheted stops
        self.position_ticks = ticks

    def _apply_trailing(self, pos) -> None:
        """Ratchet the premium stop upward as profit thresholds are crossed."""
        self.broker.ensure_stop_protection(pos, pos.last_premium)  # self-heal a missing backstop every tick
        p = self.params
        if not p.get("trail_enabled", True):
            return
        new_stop = trailing_stop(
            pos.entry_premium, pos.high_water_premium or pos.entry_premium, pos.stop_price,
            trigger_pct=p["trail_trigger_pct"],
            first_step_lock_pct=p["trail_first_step_lock_pct"],
            step_lock_pct=p["trail_step_lock_pct"])
        if new_stop > pos.stop_price:
            log.info(f"TRAIL SL {pos.tradingsymbol} {pos.stop_price:.2f} -> {new_stop:.2f} "
                     f"(high {pos.high_water_premium:.2f})", instrument=pos.instrument_key,
                     event="TRAIL")
            pos.stop_price = new_stop
            self.broker.update_stop_protection(pos, pos.last_premium)  # ratchet the GTT too (live)

    def _apply_lockstep(self, pos) -> None:
        """Lockstep band: once an equity position is in profit, ratchet its stop AND
        target together (break-even floored). A hand-pinned target is left in place;
        only the stop slides then."""
        self.broker.ensure_stop_protection(pos, pos.last_premium)  # self-heal a missing backstop every tick
        from app.engine.equity_entry import lockstep_band
        p = self.params
        if not p.get("intraday_lockstep_enabled", True):
            return
        last = pos.last_premium or pos.entry_premium
        margin = pos.entry_cost - pos.entry_charges
        rt = (2.0 * pos.entry_charges / pos.qty) if pos.qty else 0.0   # round-trip cost/share
        be = pos.entry_premium + rt if pos.direction == "LONG" else pos.entry_premium - rt
        new_stop, new_target = lockstep_band(
            pos.direction, pos.entry_premium, pos.qty, margin,
            pos.stop_price, pos.target_price, last,
            trigger_pct=p.get("intraday_lockstep_trigger_pct", 0.02),
            sl_pct=p.get("intraday_stop_loss_pct", 0.01),
            tp_pct=p.get("intraday_target_pct", 0.02),
            breakeven_price=be, rt_per_share=rt,
            profit_lock_threshold=p.get("intraday_profit_lock_threshold", 200.0),
            profit_lock_frac=p.get("intraday_profit_lock_frac", 0.5))
        if pos.manual_target:
            new_target = pos.target_price   # owner-pinned target isn't auto-extended
        if new_stop != pos.stop_price or new_target != pos.target_price:
            log.info(f"LOCKSTEP {pos.tradingsymbol} SL {pos.stop_price:.2f}->{new_stop:.2f} "
                     f"TP {pos.target_price:.2f}->{new_target:.2f}",
                     instrument=pos.instrument_key, event="LOCKSTEP")
            stop_moved = new_stop != pos.stop_price
            pos.stop_price, pos.target_price = new_stop, new_target
            if stop_moved:
                # #18: ratchet the exchange-side SL-M backstop too (no-op on paper;
                # LiveBroker re-prices the resting SL-M). Options trail this at L402.
                self.broker.update_stop_protection(pos, pos.last_premium)

    def _mark_exit_equity(self, pos, key, spot, now, ticks, opens) -> None:
        """Mark + exit an intraday-equity position against SPOT (direction-aware
        SL/TP + strategy flag + lockstep band). No proximity alerts; mirrors the
        options lane's bookkeeping (ticks, cooldown, state) for the equity case."""
        if spot is not None:
            self.broker.mark(pos, spot, spot, now=now)
        pos_stale = spot is None or is_stale(pos.last_mark_time, now, self.settings.max_stale_seconds)
        st = self.state.get(key, {})
        if not pos_stale:
            self._apply_lockstep(pos)   # ratchet SL+TP together before the exit check
            should, reason = equity_exit(
                pos.direction, spot, pos.stop_price, pos.target_price,
                st.get("long_exit", False), st.get("short_exit", False),
                target_disabled=pos.no_take_profit)
            if should:
                trade = self.broker.close_equity_position(pos, spot, reason, now)
                if trade is not None:
                    if reason == "STOP_LOSS":
                        self._stopped_at[key] = now
                    if self.params.get("notify_enabled", True):
                        self.notifier.closed(trade)
                    opens.pop(key, None)
                    if key in self.state:
                        self.state[key]["position"] = None
                    return
        d = pos.to_dict()
        ticks[key] = {
            "instrument": key, "tradingsymbol": pos.tradingsymbol,
            "option_premium": None, "spot": round(spot, 2) if spot else None,
            "unrealized_pnl": d["unrealized_pnl"],
            "stop_price": d["stop_price"], "target_price": d["target_price"],
            "high_water_premium": d["high_water_premium"], "stale": pos_stale,
            "stale_age": None if pos.last_mark_time is None
                         else round((now - pos.last_mark_time).total_seconds(), 1),
            "last_mark_time": pos.last_mark_time.isoformat() if pos.last_mark_time else None,
        }

    # ── lane 3: entries + reinforcement (fresh crossovers) ────────────────
    def process_entries(self) -> None:
        s, prov = self.settings, self.provider
        now = prov.now()
        held = {p.instrument_key: p for p in self.broker.open_positions()}
        halted = self._entries_halted(now)   # daily-loss circuit breaker (new entries only)
        # #14 order circuit breaker: N CONSECUTIVE live order failures means the
        # problem is systemic (expired token, IP not whitelisted, margin exhausted)
        # — every further attempt is another real-money order shot into the same
        # wall. DISARM once and alert; the owner re-arms after fixing the cause
        # (arm(True) resets the streak). Exits/protection keep running regardless.
        cb = self.params.get("order_failure_disarm_count", 3)
        streak = getattr(self.broker, "order_fail_streak", 0)
        if self.armed and cb and cb > 0 and streak >= cb:
            self.arm(False)
            log.error(f"ORDER CIRCUIT BREAKER — {streak} consecutive live order "
                      f"failures; DISARMED. Check Zerodha/token/IP, then re-arm.",
                      event="ORDER_CB_DISARM")
            if self.params.get("notify_enabled", True):
                self.notifier._emit(f"⛔ ORDER CIRCUIT BREAKER: {streak} consecutive "
                                    f"live order failures — bot DISARMED. Fix the "
                                    f"cause (token/IP/margin), then re-arm.")
        cands: list[Candidate] = []
        meta: dict[str, tuple] = {}
        eq_cands: list[IntradayCandidate] = []   # intraday-equity signals this tick
        eq_meta: dict[str, tuple] = {}
        intraday_on = self.params.get("intraday_enabled", False)
        for key in list(self.enabled):
            st = self.state.get(key)
            sig = st["signal"] if st else "NONE"
            # A fresh SAME-DIRECTION crossover on a held position is a reinforcement,
            # never added quantity (no pyramiding). Equity (MIS) is never reinforced.
            if key in held:
                if held[key].segment == "equity_intraday":
                    continue
                if sig in ("LONG_ENTRY", "SHORT_ENTRY"):
                    pos = held[key]
                    sig_dir = "LONG" if sig == "LONG_ENTRY" else "SHORT"
                    if sig_dir == pos.direction:
                        self._record_signal(now, key, st, note="reinforcement")
                        self.broker.reinforce_position(pos, self.params, now)
                continue
            if key in self.entry_blocks:
                continue  # entries manually disabled for this instrument
            if not st or sig not in ("LONG_ENTRY", "SHORT_ENTRY"):
                continue
            direction = "LONG" if sig == "LONG_ENTRY" else "SHORT"
            inst = get_instrument(key)
            self._record_signal(now, key, st)
            if self.params.get("notify_on_signal", False):
                self.notifier.signal(key, sig)
            # fresh-signal guard (#12): evaluate each candle's entry signal ONCE. A
            # signal that fires but can't enter (no capital / concurrency cap full) is
            # DROPPED, not re-attempted every tick and filled stale when a slot frees
            # up. Held positions (reinforcement) are handled above and exempt.
            bar = st.get("time")
            if signal_already_evaluated(bar, self.last_entry_bar.get(key)):
                continue
            if bar is not None:
                self.last_entry_bar[key] = bar
            # ── day-shape guards — BOTH branches (options AND intraday) ──
            # #15: act only on a LIVE crossover. After a (re)start the latest
            # completed candle can be hours old (pre-open it is the PREVIOUS
            # session's last bar) — that crossover is history and the move has
            # already left (LODHA 2026-07-03: fired at 09:00 on a prior-session
            # bar, ~5% past its origin by noon). Age runs from candle COMPLETION.
            iv_min = _INTERVAL_MINUTES.get(self._interval_for(key), 15)
            if signal_too_old(bar, ist_epoch(now), iv_min,
                              self.params.get("max_signal_age_minutes", 5.0)):
                age_min = (ist_epoch(now) - (bar + iv_min * 60)) / 60.0
                log.info(f"STALE SIGNAL — {key} crossover candle completed "
                         f"~{age_min:.0f}m ago; dropped (history, not a live signal)",
                         instrument=key, event="SIGNAL_STALE_SKIP")
                continue
            # #16: never OPEN outside continuous trading. A protected-market order
            # placed pre-open (before 09:15) just rests and can miss the uncross —
            # the LODHA 09:01:25 dangling-limit. Gates entries only; open positions
            # are still managed/exited elsewhere.
            seg = (_equity_charge_segment(inst)
                   if self.products.get(key, "options") == "equity_intraday"
                   else inst.segment)
            if outside_trading_session(seg, now):
                log.info(f"SESSION not open — not taking {key} "
                         f"(pre-open/closed; a resting order can miss the uncross)",
                         instrument=key, event="SESSION_SKIP")
                continue
            # #16b: the owner's start-of-day gate — in-session but before the entry
            # window opens (default 09:30; the first minutes after the 09:15 open
            # are erratic and the 09:00-09:15 window took the 2026-07-03 orders).
            if before_entry_window(now, self.params.get("entry_window_start", "09:30")):
                log.info(f"ENTRY WINDOW closed — not taking {key} before "
                         f"{self.params.get('entry_window_start', '09:30')}",
                         instrument=key, event="ENTRY_WINDOW_SKIP")
                continue
            # #9 (extended): sit out the weekly-expiry weekday (default Tuesday) for
            # ALL entries unless the owner opted in for today
            # (intraday_override_date == today).
            if intraday_blocked_for_expiry_day(
                    now.date(), self.params.get("intraday_override_date", ""),
                    self.params.get("intraday_block_weekday", 1)):
                log.info(f"ENTRIES blocked today (expiry-day guard) — not taking {key}; "
                         f"set intraday_override_date to opt in",
                         instrument=key, event="EXPIRY_DAY_SKIP")
                continue
            # ── intraday-equity branch (MIS): collect a candidate; the cap-3 /
            # purple / qty-max selection runs after the loop. Guarded by the
            # opt-in flag so the default options behaviour is unchanged. ──
            if self.products.get(key, "options") == "equity_intraday":
                if not intraday_on:
                    continue
                if is_mis_blocked(key):   # #5: never intraday-trade a non-MIS-eligible name
                    log.info(f"INTRADAY skip — {key} not MIS-eligible (blocklist)",
                             instrument=key, event="MIS_BLOCK")
                    continue
                if in_reentry_cooldown(self._stopped_at.get(key), now,
                                       self.params.get("reentry_cooldown_minutes", 0.0)):
                    log.info(f"RE-ENTRY COOLDOWN — skipping {key}", instrument=key,
                             event="COOLDOWN_SKIP")
                    continue
                if not self.armed:
                    log.info(f"DISARMED — intraday signal ready, not taking {key} (arm to trade)",
                             instrument=key, event="DISARMED_SKIP")
                    continue
                if halted:
                    log.warn(f"DAILY LOSS HALT — not taking {key}", instrument=key, event="HALT_SKIP")
                    continue
                # price the entry at the LIVE spot, not the last completed-candle
                # close (st["close"]). Exits mark against the live spot, so opening at
                # a stale candle close on a fast move lands the position already past
                # its SL/TP — an instant exit + re-entry loop. Fall back to the candle
                # close only if there's no live tick.
                live_spot = self.provider.get_ltp(inst)
                entry_price = float(live_spot) if live_spot and live_spot > 0 else float(st["close"])
                eq_cands.append(IntradayCandidate(key, direction, entry_price,
                                                  self.priority_flags.get(key, False)))
                eq_meta[key] = (inst, direction)
                continue
            if not inst.has_options:
                continue  # tracking-only: show the signal, never options-trade it
            # re-entry cooldown after a recent stop-out on this instrument
            if in_reentry_cooldown(self._stopped_at.get(key), now,
                                   self.params.get("reentry_cooldown_minutes", 0.0)):
                log.info(f"RE-ENTRY COOLDOWN — skipping {key}", instrument=key,
                         event="COOLDOWN_SKIP")
                continue
            if not self.armed:
                log.info(f"DISARMED — signal ready, not taking {key} (arm to trade)",
                         instrument=key, event="DISARMED_SKIP")
                continue
            if halted:
                log.warn(f"DAILY LOSS HALT — not taking {key}", instrument=key, event="HALT_SKIP")
                continue
            chain = prov.get_option_chain(inst)
            if not chain:
                log.warn("signal fired but no option chain — skipped", instrument=key)
                continue
            # theta-cliff guard (#1): never OPEN an option within N days of expiry —
            # 0/1/2-DTE premium can evaporate on a small adverse move. Owner rule: >=3 DTE.
            min_dte = self.params.get("entry_min_days_to_expiry", 3)
            if expiry_too_close(chain.expiry, now.date(), min_dte):
                dte = (chain.expiry - now.date()).days
                log.warn(f"signal skipped — option expiry too close ({dte}d < {min_dte}d, "
                         f"theta cliff)", instrument=key, event="DTE_SKIP")
                continue
            pick = pick_option(chain, direction, s, now)
            if self.params.get("option_cache_enabled", True):
                try:
                    from app.options.cache import persist_chain
                    persist_chain(chain, inst, now, self.params["option_cache_snapshot_minutes"])
                except Exception as e:
                    log.error(f"option cache persist failed: {e}")
            self.last_pick[key] = {
                "time": now.isoformat(), "direction": direction, "reason": pick.reason,
                "spot": round(chain.spot, 2), "expiry": chain.expiry.isoformat(),
                "chosen": pick.chosen.to_dict() if pick.chosen else None,
                "candidates": pick.candidates,
            }
            if not pick.chosen:
                log.warn(f"signal fired but {pick.reason}", instrument=key)
                continue
            # adaptive routing: never market into an ugly book (the COPPER case).
            plan = plan_order("BUY", pick.chosen.bid, pick.chosen.ask, pick.chosen.ltp,
                              None, pick.chosen.lot_size, self.params)
            if plan.action == "SKIP":
                log.warn(f"signal fired but routing SKIP — {plan.reason}",
                         instrument=key, event="ROUTE_SKIP")
                if self.params.get("notify_enabled", True):
                    self.notifier.route_skip(key, plan.reason)
                continue
            self.last_pick[key]["route"] = {"action": plan.action,
                                            "limit_price": plan.limit_price,
                                            "reason": plan.reason}
            qty = pick.chosen.lot_size
            charges = compute_charges(inst.segment, "BUY", pick.chosen.ltp, qty)["total"]
            cost = pick.chosen.ltp * qty + charges
            if over_per_trade_cap(cost, self.params.get("max_capital_per_trade", 0.0)):
                log.warn(f"signal skipped — 1-lot cost ₹{cost:,.0f} exceeds per-trade cap "
                         f"₹{self.params['max_capital_per_trade']:,.0f}",
                         instrument=key, event="PER_TRADE_CAP_SKIP")
                continue
            cands.append(Candidate(key, direction, cost))
            meta[key] = (inst, direction, pick, chain, plan)

        if cands:
            # bound auto-entries by DEPLOYABLE capital — your own trades take priority
            alloc = allocate(cands, self.deployable_cash())
            if len(alloc.funded) < len(cands):
                log.info(f"capital shortfall — {len(alloc.funded)}/{len(cands)} "
                         f"signals funded by priority")
            # cap concurrent open positions (counts positions already held this call)
            slots = slots_available(len(held), self.params.get("max_open_positions", 0))
            opened = 0
            for c in alloc.funded:
                if not self.armed:   # #8 defense-in-depth: arm() flips WITHOUT the engine
                    log.warn("DISARMED mid-cycle — aborting remaining entries (gate re-check)",
                             event="ARM_RECHECK_ABORT")
                    break            # lock, so a disarm can land after the entry gate-check
                if slots is not None and opened >= slots:
                    log.info(f"MAX POSITIONS reached ({len(held)} open, cap "
                             f"{self.params['max_open_positions']}) — skipping {c.instrument_key}",
                             instrument=c.instrument_key, event="MAX_POS_SKIP")
                    continue
                inst, direction, pick, chain, plan = meta[c.instrument_key]
                log.info(f"ROUTE {plan.action} {pick.chosen.tradingsymbol}"
                         + (f" @ {plan.limit_price:.2f}" if plan.limit_price else "")
                         + f" — {plan.reason}", instrument=c.instrument_key, event="ROUTE")
                pos = self.broker.open_position(inst, direction, pick.chosen,
                                                pick.reason, now, chain.spot, self.params, plan=plan)
                if pos is None:
                    continue  # live order not filled — nothing recorded (already alerted)
                opened += 1
                if self.params.get("notify_enabled", True):
                    self.notifier.opened(pos)
                if c.instrument_key in self.state:
                    p = self.broker.position_for(c.instrument_key)
                    self.state[c.instrument_key]["position"] = p.to_dict() if p else None
            for c, reason in alloc.skipped:
                log.warn(f"signal dropped — {reason}", instrument=c.instrument_key)

        # ── intraday-equity selection: purple-first, qty-max, hard cap of 3 ──
        if eq_cands and intraday_on:
            open_equity = [p for p in self.broker.open_positions()
                           if p.segment == "equity_intraday"]
            slots = max(0, self.params.get("intraday_max_positions", 3) - len(open_equity))
            if slots <= 0:
                log.info(f"INTRADAY CAP reached ({len(open_equity)} open) — "
                         f"{len(eq_cands)} signals dropped")
            else:
                sel = select_intraday_entries(
                    eq_cands, max_positions=slots,
                    min_margin=self.params.get("intraday_min_margin", 7000.0),
                    max_margin=self.params.get("intraday_max_margin", 10000.0),
                    purple_margin=self.params.get("intraday_purple_margin", 10000.0),
                    leverage=self.params.get("intraday_leverage", 5.0),
                    available_cash=self.deployable_cash())
                for pickk in sel.selected:
                    if not self.armed:   # #8 defense-in-depth: disarm may have landed mid-cycle
                        log.warn("DISARMED mid-cycle — aborting remaining intraday entries",
                                 event="ARM_RECHECK_ABORT")
                        break
                    inst, direction = eq_meta[pickk.instrument_key]
                    seg = _equity_charge_segment(inst)
                    log.info(f"INTRADAY {pickk.direction} {pickk.instrument_key} "
                             f"{pickk.qty}@{pickk.price:.2f} (margin ₹{pickk.margin:,.0f}"
                             f"{', purple' if pickk.is_purple else ''})",
                             instrument=pickk.instrument_key, event="INTRADAY_ENTRY")
                    pos = self.broker.open_equity_position(
                        inst, pickk.direction, pickk.price, pickk.qty, seg,
                        f"INTRADAY {pickk.direction}", now, self.params,
                        strategy_key=self.strategy_keys.get(pickk.instrument_key))
                    if pos is None:
                        continue
                    if self.params.get("notify_enabled", True):
                        self.notifier.opened(pos)
                    if pickk.instrument_key in self.state:
                        p = self.broker.position_for(pickk.instrument_key)
                        self.state[pickk.instrument_key]["position"] = p.to_dict() if p else None
                for c, reason in sel.skipped:
                    log.info(f"intraday signal dropped — {reason}", instrument=c.instrument_key)

    # ── overnight holding (option buying) ─────────────────────────────────
    def square_off_for_overnight(self, now) -> list[dict]:
        """At session close: keep eligible positions overnight (tag + snapshot the
        close mark), paper-close the rest. Returns the per-position decisions."""
        from app.engine.overnight import overnight_decision
        equity = self.capital_dict()["equity"]
        out = []
        for pos in list(self.broker.open_positions()):
            if pos.last_squareoff_date == now.date():
                continue  # already decided this session — don't re-snapshot/re-close
            dte = (pos.expiry - now.date()).days if pos.expiry else None
            holding_days = max(0, (now.date() - pos.entry_time.date()).days)
            into_weekend = now.weekday() == 4   # Friday close
            keep, reason = overnight_decision(
                pos.entry_cost, equity, pos.reinforcement_count,
                dte, holding_days, into_weekend, self.params)
            if keep:
                pos.held_overnight = True
                pos.session_close_premium = pos.last_premium or pos.entry_premium
                pos.last_squareoff_date = now.date()   # re-arm: re-evaluated next session
                self.broker.commit()
                log.info(f"OVERNIGHT HOLD {pos.tradingsymbol} — {reason}",
                         instrument=pos.instrument_key, event="OVERNIGHT_HOLD")
            else:
                prem = pos.last_premium or pos.entry_premium
                self.broker.close_position(pos, prem, "OVERNIGHT_SQUAREOFF", now, pos.last_spot)
                if pos.instrument_key in self.state:
                    self.state[pos.instrument_key]["position"] = None
                log.info(f"OVERNIGHT SQUAREOFF {pos.tradingsymbol} — {reason}",
                         instrument=pos.instrument_key, event="OVERNIGHT_SQUAREOFF")
            out.append({"key": pos.instrument_key, "keep": keep, "reason": reason})
        return out

    def book_overnight_gap(self, now) -> None:
        """At session open: attribute the close→open premium gap to overnight P&L.

        Gated on a LATER calendar day than the close that took the snapshot, so it
        fires once per session boundary and never zeroes the snapshot in the same
        pass it was taken (which would erase the gap before it could be booked)."""
        for pos in list(self.broker.open_positions()):
            if (pos.held_overnight and pos.session_close_premium > 0
                    and pos.last_squareoff_date is not None
                    and now.date() > pos.last_squareoff_date):
                prem = pos.last_premium or pos.entry_premium
                pos.overnight_pnl += (prem - pos.session_close_premium) * pos.qty
                pos.session_close_premium = 0.0
                self.broker.commit()

    def handle_overnight(self, now) -> None:
        """Live-mode orchestration: square off near each segment's close, book the
        gap just after open. No-op for the always-open mock clock."""
        if self.provider.name == "mock":
            return
        try:
            from app.core import market_hours
            buf = self.params["square_off_buffer_minutes"]
            for pos in list(self.broker.open_positions()):
                seg = get_instrument(pos.instrument_key).spot_exchange
                mtc = market_hours.minutes_to_close(seg, now)
                if mtc is not None and 0 <= mtc <= buf and pos.last_squareoff_date != now.date():
                    self.square_off_for_overnight(now)
                    break
            self.square_off_intraday(now)   # MIS equity must be flat by close
            self.book_overnight_gap(now)
        except Exception as e:
            log.error(f"overnight handler error: {e}")

    def square_off_intraday(self, now) -> None:
        """Force every intraday-equity (MIS) position flat near its segment's close —
        MIS cannot carry overnight. Marks to the last spot and books the close."""
        from app.core import market_hours
        buf = self.params.get("intraday_square_off_buffer_minutes", 15.0)
        for pos in list(self.broker.open_positions()):
            if pos.segment != "equity_intraday":
                continue
            seg = get_instrument(pos.instrument_key).spot_exchange
            mtc = market_hours.minutes_to_close(seg, now)
            if mtc is not None and 0 <= mtc <= buf:
                price = pos.last_premium or pos.entry_premium
                self.broker.close_equity_position(pos, price, "INTRADAY_SQUAREOFF", now)
                if pos.instrument_key in self.state:
                    self.state[pos.instrument_key]["position"] = None
                log.info(f"INTRADAY SQUAREOFF {pos.tradingsymbol} @ {price:.2f}",
                         instrument=pos.instrument_key, event="INTRADAY_SQUAREOFF")

    # ── combined step — mock dry-run + tests (semantics unchanged) ────────
    def tick(self) -> None:
        self.scan_signals()
        self.mark_and_exit_positions()
        self.process_entries()
        self.broker.snapshot(self.provider.now())
        self.tick_count += 1

    # ── capital available to the bot (owner's trades take priority) ────────
    def deployable_cash(self) -> float:
        cap_state = self.broker.capital()
        bot_deployed = sum(p.entry_cost for p in self.broker.open_positions())
        is_live = self.provider.name == "kite"
        funds = self.provider.account_funds() if is_live else None
        return deployable_capital(
            ledger_base=cap_state.cash + bot_deployed,
            bot_deployed=bot_deployed,
            account_available=(funds["available"] if funds else None),
            reserve=self.params.get("capital_reserve", 0.0),
            cap=self.params.get("bot_capital_cap", 0.0),
            is_live=is_live)

    # ── daily-loss circuit breaker ────────────────────────────────────────
    def _today_net_realized(self, today) -> float:
        from app.db.models import Trade
        with SessionLocal() as s:
            return sum(t.net_pnl for t in s.scalars(select(Trade))
                       if t.exit_time and t.exit_time.date() == today)

    def _today_round_trips(self, today) -> int:
        """Count of completed round trips (closed trades) today — drives the hard
        daily round-trip cap (#10)."""
        from app.db.models import Trade
        with SessionLocal() as s:
            return sum(1 for t in s.scalars(select(Trade))
                       if t.exit_time and t.exit_time.date() == today)

    def _open_unrealized(self) -> float:
        """Mark-to-market P&L across all currently open positions (can be negative).
        Direction-aware for intraday-equity SHORTs (which profit as price falls)."""
        total = 0.0
        for p in self.broker.open_positions():
            last = p.last_premium or p.entry_premium
            if p.segment == "equity_intraday" and p.direction == "SHORT":
                total += (p.entry_premium - last) * p.qty
            else:
                total += (last - p.entry_premium) * p.qty
        return total

    def _entries_halted(self, now) -> bool:
        """Halt NEW entries for the day once a circuit breaker trips (open positions
        are still managed throughout). Three breakers, any trips:
          • max_daily_loss          — today's REALIZED net loss.
          • max_open_drawdown       — today's REALIZED + UNREALIZED (open MTM) loss.
          • max_round_trips_per_day — count of completed round trips today (#10).
        Alerts at most once per day; the open-drawdown breaker un-trips on recovery."""
        max_loss = self.params.get("max_daily_loss", 0.0)
        max_dd = self.params.get("max_open_drawdown", 0.0)
        max_rt = self.params.get("max_round_trips_per_day", 0)
        if ((not max_loss or max_loss <= 0) and (not max_dd or max_dd <= 0)
                and (not max_rt or max_rt <= 0)):
            return False
        today = now.date()
        realized = self._today_net_realized(today)
        unreal = self._open_unrealized() if (max_dd and max_dd > 0) else 0.0
        halted, why = daily_loss_halt(realized, unreal, max_loss, max_dd)
        rts = self._today_round_trips(today) if (max_rt and max_rt > 0) else 0
        if not halted and round_trip_cap_reached(rts, max_rt):
            halted, why = True, "round_trips"
        if halted and self._halt_notified_date != today:
            self._halt_notified_date = today
            if why == "round_trips":
                log.warn(f"ROUND-TRIP CAP — {rts} completed round trips today >= cap "
                         f"{max_rt}; no new entries today")
            elif why == "open_drawdown":
                combined = realized + unreal
                log.warn(f"DAILY DRAWDOWN HALT — today realized ₹{realized:,.0f} + open "
                         f"₹{unreal:,.0f} = ₹{combined:,.0f} <= -₹{max_dd:,.0f}; no new entries today")
                if self.params.get("notify_enabled", True):
                    self.notifier.daily_halt(combined, max_dd)
            else:
                log.warn(f"DAILY LOSS HALT — today realized net ₹{realized:,.0f} <= "
                         f"-₹{max_loss:,.0f}; no new entries today")
                if self.params.get("notify_enabled", True):
                    self.notifier.daily_halt(realized, max_loss)
        return halted

    def halt_status(self, now) -> dict:
        """Pure, side-effect-free read of the daily-loss / open-drawdown circuit
        breaker for the snapshot/UI. Mirrors _entries_halted's computation but does
        NOT log, notify, or mutate _halt_notified_date — safe to call on every WS
        push. _entries_halted stays the one place that fires the once-per-day alert.

        Returns: {halted, reason ('', 'realized', 'open_drawdown', 'round_trips'),
        realized, open_unrealized, max_daily_loss, max_open_drawdown, round_trips,
        max_round_trips}."""
        max_loss = self.params.get("max_daily_loss", 0.0) or 0.0
        max_dd = self.params.get("max_open_drawdown", 0.0) or 0.0
        max_rt = self.params.get("max_round_trips_per_day", 0) or 0
        if max_loss <= 0 and max_dd <= 0 and max_rt <= 0:
            return {"halted": False, "reason": "", "realized": 0.0,
                    "open_unrealized": 0.0, "max_daily_loss": max_loss,
                    "max_open_drawdown": max_dd, "round_trips": 0,
                    "max_round_trips": max_rt}
        realized = self._today_net_realized(now.date())
        unreal = self._open_unrealized() if max_dd > 0 else 0.0
        halted, reason = daily_loss_halt(realized, unreal, max_loss, max_dd)
        rts = self._today_round_trips(now.date()) if max_rt > 0 else 0
        if not halted and round_trip_cap_reached(rts, max_rt):
            halted, reason = True, "round_trips"
        return {
            "halted": halted, "reason": reason,
            "realized": round(realized, 2), "open_unrealized": round(unreal, 2),
            "max_daily_loss": max_loss, "max_open_drawdown": max_dd,
            "round_trips": rts, "max_round_trips": max_rt,
        }

    def _record_signal(self, now, key, st, note: str = "") -> None:
        with SessionLocal() as s:
            s.add(SignalEvent(time=now, instrument_key=key, signal=st["signal"],
                              z=st["z"], slope=st["slope"], close=st["close"],
                              acted=True, note=note))
            s.commit()

    # ── next-candle gating ────────────────────────────────────────────────
    def _due_for_scan(self, key: str, now) -> bool:
        """Refetch candles only when a new completed candle could exist — gates
        Kite historical calls so the signal lane stays cheap."""
        import datetime as _dt
        epoch = now.timestamp() if isinstance(now, _dt.datetime) else float(now)
        nxt = self._next_scan.get(key)
        if nxt is None or epoch >= nxt:
            minutes = _INTERVAL_MINUTES.get(self._interval_for(key), 15)
            self._next_scan[key] = epoch + minutes * 60
            return True
        return False

    # ── per-lane single iterations (lock-serialised DB mutation) ──────────
    async def _risk_iteration(self) -> None:
        # L5 — mark_and_exit_positions can block for the live order-poll window
        # (place + poll to a terminal state). Run it OFF the event loop so a slow
        # poll never freezes WS heartbeats, the signal scheduler, or the cockpit.
        # The lock is still held across the offload, so the single shared DB session
        # is only ever touched by one lane at a time (risk vs signal stay serialised).
        async with self._lock:
            await asyncio.to_thread(self.mark_and_exit_positions)
        if self.on_position_ticks:
            try:
                await self.on_position_ticks(self.position_ticks)
            except Exception:
                pass

    def _maybe_refresh_funds(self) -> None:
        """Throttled (~20s) poll of the REAL Kite account funds in live mode, cached
        for the snapshot so the cockpit shows the actual account balance instead of
        the paper ledger. margins() is rate-limited, so never call it per-tick. No-op
        (and clears the cache) on the mock/paper provider."""
        if self.provider.name != "kite":
            self._account_funds = None
            return
        epoch = self.provider.now().timestamp()
        if epoch < self._next_funds_epoch:
            return
        self._next_funds_epoch = epoch + 20.0
        try:
            funds = self.provider.account_funds()
            if funds:
                self._account_funds = funds
                self._persist_daily_snapshot(funds)
        except Exception as e:
            log.warn(f"account funds refresh failed: {e}")

    def _maybe_check_ledger(self) -> None:
        """H10: run the cash-invariant self-check in production (it was only ever run by
        the offline dry-run). A nonzero diff means the ledger drifted from
        cash == initial + realized − Σ(open entry_cost) — a bad write or partial commit.
        Throttled; alerts once per drift episode (log + Telegram) and clears when it
        returns to balance. Detection only — it never mutates the ledger."""
        epoch = self.provider.now().timestamp()
        if epoch < self._next_ledger_epoch:
            return
        self._next_ledger_epoch = epoch + float(self.params.get("ledger_check_seconds", 60))
        rec = self.broker.reconcile()
        if abs(rec["diff"]) > 0.01:
            if not self._ledger_drift_alerted:
                log.error(f"LEDGER DRIFT ₹{rec['diff']} — cash {rec['cash']} vs expected "
                          f"{rec['expected_cash']} (realized {rec['realized_pnl']}, "
                          f"{rec['open']} open); invariant broken, investigate",
                          event="LEDGER_DRIFT")
                try:
                    self.notifier._emit(f"🚨 LEDGER DRIFT ₹{rec['diff']}: cash "
                                        f"{rec['cash']} vs expected {rec['expected_cash']} "
                                        f"— the bot's cash invariant is broken; verify.")
                except Exception:
                    pass
                self._ledger_drift_alerted = True
        else:
            self._ledger_drift_alerted = False

    def _persist_daily_snapshot(self, funds: dict) -> None:
        """Upsert today's (IST) account equity row for the Calendar view. Called from
        the throttled funds refresh, so it captures the latest balance of the day."""
        from app.db.models import DailyAccountSnapshot
        day = self.provider.now().date().isoformat()
        try:
            with SessionLocal() as s:
                row = s.get(DailyAccountSnapshot, day)
                if row is None:
                    row = DailyAccountSnapshot(day=day)
                    s.add(row)
                row.account_net = float(funds.get("net", 0.0) or 0.0)
                row.account_available = float(funds.get("available", 0.0) or 0.0)
                s.commit()
        except Exception as e:
            log.warn(f"daily snapshot persist failed: {e}")

    def _maybe_reconcile_orphans(self) -> None:
        """Throttled (~30s): book any bot position the live account no longer backs
        (e.g. its GTT fired while the bot was down). No-op on the paper broker."""
        now = self.provider.now()
        epoch = now.timestamp()
        if epoch >= self._next_reconcile_epoch:
            self._next_reconcile_epoch = epoch + 30.0
            try:
                # #17: first adopt any bot entry that filled after its poll window (a late
                # uncross / slow open), so it's booked + stopped rather than left orphaned.
                self.broker.adopt_pending_entries(now)
                reconciled = self.broker.reconcile_orphans(now) or []
            except Exception as e:
                log.error(f"orphan reconcile error: {e}")
                return
            # #2: a position that vanished from the account (manual Zerodha exit or a GTT
            # fire) is an exit the bot didn't initiate — block same-day re-entry so the
            # live signal can't immediately re-open it (the PAYTM/IREDA thrash).
            for k in reconciled:
                if k not in self.entry_blocks:
                    self.set_entries_blocked(k, True)
                    log.info("auto-blocked re-entry after external/reconciled exit",
                             instrument=k, event="AUTO_BLOCK")

    # ── option-chain research cache (whole watchlist, not just traded names) ─
    def cache_option_chains(self, now) -> int:
        """Snapshot the option chain of EVERY enabled, in-session, option-bearing
        instrument into the OptionData research dataset — not only the ones a
        signal happened to fire on. Kite sells no historical option chains / IV /
        OI / greeks, so anything not snapshotted live today is unrecoverable. Each
        write is deduped to `option_cache_snapshot_minutes` per instrument by
        `persist_chain`, so calling this often is cheap."""
        if not self.params.get("option_cache_enabled", True):
            return 0
        from app.options.cache import persist_chain
        snap_min = self.params.get("option_cache_snapshot_minutes", 15.0)
        written = 0
        for key in list(self.enabled):
            inst = get_instrument(key)
            if not inst.has_options or not self.provider.is_tradable_now(inst):
                continue
            try:
                chain = self.provider.get_option_chain(inst)
                if chain:
                    written += persist_chain(chain, inst, now, snap_min)
            except Exception as e:
                if self.health.should_log_failure("quote"):
                    log.error(f"option cache sweep failed: {e}", instrument=key)
        if written:
            log.info(f"option research cache +{written} rows across the watchlist",
                     event="OPTION_CACHE")
        return written

    def _maybe_cache_chains(self) -> None:
        """Throttled watchlist option-chain snapshot (cadence = snapshot minutes,
        floored at 60s). Off when option_cache_enabled is false."""
        if not self.params.get("option_cache_enabled", True):
            return
        now = self.provider.now()
        epoch = now.timestamp()
        if epoch < self._next_cache_sweep_epoch:
            return
        snap_min = self.params.get("option_cache_snapshot_minutes", 15.0)
        self._next_cache_sweep_epoch = epoch + max(60.0, snap_min * 60.0)
        try:
            self.cache_option_chains(now)
        except Exception as e:
            log.error(f"option cache sweep error: {e}")

    def _signal_iteration_blocking(self) -> None:
        # C5 — the body that can block: scan_signals fetches Kite candles per
        # instrument, and process_entries places a live order and polls it to a
        # terminal state (up to order_timeout_seconds). Runs OFF the event loop
        # (see _signal_iteration) so a slow entry never freezes the risk scheduler,
        # WS heartbeats, or the cockpit — the same guarantee the risk lane already has.
        self.refresh_params()          # pick up live Settings overrides
        self._maybe_refresh_funds()    # cache real account balance (live only)
        self._maybe_reconcile_orphans()
        self.scan_signals()
        self.process_entries()
        self._maybe_cache_chains()     # grow the watchlist-wide options dataset
        self.handle_overnight(self.provider.now())   # no-op for mock
        self.broker.snapshot(self.provider.now())
        self._maybe_check_ledger()     # H10: periodic cash-invariant drift alarm
        self.tick_count += 1

    async def _signal_iteration(self) -> None:
        # Offload the blocking body but keep the lock across it, so the single shared
        # DB session is only ever touched by one lane at a time (signal vs risk stay
        # serialised) — identical discipline to _risk_iteration.
        async with self._lock:
            await asyncio.to_thread(self._signal_iteration_blocking)
        if self.on_update:
            try:
                await self.on_update(self.snapshot_state())
            except Exception:
                pass

    # ── async loops ───────────────────────────────────────────────────────
    async def run_risk_loop(self) -> None:
        """Fast lane: mark open positions, ratchet the trailing stop, fire SL/TP.
        Independent of the slower signal scan so positions are managed promptly."""
        while self.running:
            try:
                await self._risk_iteration()
            except Exception as e:
                log.error(f"risk loop error: {e}")
            await asyncio.sleep(self.settings.position_loop_seconds)

    async def run_signal_loop(self) -> None:
        """Slow lane: recompute strategy on completed candles, open new entries."""
        self.running = True
        log.info(f"engine started — provider={self.provider.name}, "
                 f"enabled={sorted(self.enabled)}")
        while self.running:
            try:
                if self.provider.name == "mock":
                    await self._signal_iteration()
                    if not self.provider.advance():
                        log.info("mock history exhausted — engine idling")
                        await asyncio.sleep(5)
                        continue
                    await asyncio.sleep(self.settings.mock_tick_seconds)
                else:
                    any_open = any(self.provider.is_tradable_now(get_instrument(k))
                                   for k in self.enabled)
                    if not any_open:
                        if not self._idle_logged:
                            log.info("all enabled markets closed — engine idling until next session")
                            self._idle_logged = True
                        # Even while idle (overnight / pre-market) keep the real account
                        # balance fresh and push a snapshot, so after the morning Kite
                        # re-login the cockpit reflects funds + LIVE/armed state within a
                        # minute — no restart, no waiting for the open.
                        self._maybe_refresh_funds()
                        if self.on_update:
                            try:
                                await self.on_update(self.snapshot_state())
                            except Exception:
                                pass
                        await asyncio.sleep(60)
                    else:
                        self._idle_logged = False
                        await self._signal_iteration()
                        await asyncio.sleep(self.settings.signal_loop_seconds)
            except Exception as e:
                log.error(f"signal loop error: {e}")
                await asyncio.sleep(self.settings.signal_loop_seconds)

    async def run(self) -> None:   # back-compat alias (signal lane)
        self.running = True
        await self.run_signal_loop()

    def stop(self) -> None:
        self.running = False

    # ── arm-to-trade + kill switch ────────────────────────────────────────
    def arm(self, value: bool) -> bool:
        """Owner control: arm (start auto-executing) or disarm (pause new entries —
        open positions are still managed and protected)."""
        self.armed = bool(value)
        if self.armed and hasattr(self.broker, "order_fail_streak"):
            # #14: a deliberate re-arm is the owner saying the cause is fixed —
            # give the circuit breaker a clean slate.
            self.broker.order_fail_streak = 0
        log.info("engine ARMED — will auto-execute trades" if self.armed
                 else "engine DISARMED — no new entries (open positions still managed)",
                 event="ARM" if self.armed else "DISARM")
        if self.params.get("notify_enabled", True):
            self.notifier.armed(self.armed)
        return self.armed

    def kill(self, now=None, square_off: bool = True) -> list[str]:
        """Emergency stop: disarm immediately and (by default) square off every
        open position at its last mark. Used when things go south."""
        now = now or self.provider.now()
        self.armed = False
        # H8: a hard stop must also cancel working/timed-out ENTRY orders — otherwise one
        # still resting at the exchange can fill AFTER the kill and leave an untracked,
        # stopless position. (No-op on paper.)
        cancelled = self.broker.cancel_working_entries()
        closed: list[str] = []
        if square_off:
            for pos in list(self.broker.open_positions()):
                prem = pos.last_premium or pos.entry_premium
                # route each segment through its correct close (equity covers a short
                # via BUY; the options close always SELLs) — same fix as reconcile.
                if pos.segment == "equity_intraday":
                    tr = self.broker.close_equity_position(pos, prem, "KILL_SWITCH", now)
                else:
                    tr = self.broker.close_position(pos, prem, "KILL_SWITCH", now, pos.last_spot)
                if tr is None:
                    log.error(f"KILL could not square off {pos.tradingsymbol} — left open",
                              instrument=pos.instrument_key, event="KILL_FAIL")
                    continue
                self.notifier.clear(pos.instrument_key)
                if pos.instrument_key in self.state:
                    self.state[pos.instrument_key]["position"] = None
                closed.append(pos.instrument_key)
        log.info(f"KILL SWITCH — disarmed; cancelled {len(cancelled)} working order(s); "
                 f"squared off {len(closed)} position(s)", event="KILL")
        if self.params.get("notify_enabled", True):
            self.notifier.killed(closed)
        return closed

    # ── snapshots for API/WS ──────────────────────────────────────────────
    def capital_dict(self) -> dict:
        cap = self.broker.capital()
        opens = self.broker.open_positions()
        # equity = cash + each open position's mark-to-market VALUE. For leveraged
        # MIS equity that's margin + unrealized P&L, not the full notional (mtm_value
        # handles the distinction); options stay premium × qty.
        mtm = sum(p.mtm_value() for p in opens)
        d = {
            "initial": cap.initial_capital, "cash": round(cap.cash, 2),
            "invested": round(sum(p.entry_cost for p in opens), 2),
            "equity": round(cap.cash + mtm, 2),
            "realized_pnl": round(cap.realized_pnl, 2),
            "open_count": len(opens),
        }
        # LIVE: surface the REAL account balance (cached margins) so the cockpit shows
        # the actual ~free funds, not the 50k paper-ledger seed. available = free cash
        # (not locked in your securities); net = total account equity. Paper mode omits
        # these and the UI keeps showing the ledger equity/cash.
        f = self._account_funds
        if self.provider.name == "kite" and f:
            d["account_available"] = round(f.get("available", 0.0), 2)
            d["account_net"] = round(f.get("net", 0.0), 2)
        return d

    def _market_open_by_segment(self) -> dict[str, bool]:
        """Per-segment open/closed for the operational screens. Mirrors the engine's
        own scan gate (scan_signals skips closed instruments via is_tradable_now), so
        the UI can render a closed market as a neutral 'market closed' instead of an
        amber 'stale' alarm when no candle can possibly print. Read-only / no network."""
        out: dict[str, bool] = {}
        for inst in (get_instrument(k) for k in self.enabled):
            if inst.segment not in out:
                out[inst.segment] = self.provider.is_tradable_now(inst)
        return out

    def snapshot_state(self) -> dict:
        market_open = self._market_open_by_segment()
        return {"tick": self.tick_count, "provider": self.provider.name,
                "time": self.provider.now().isoformat(),
                "broker_mode": getattr(self.broker, "MODE", "paper"),  # "paper" | "live"
                "armed": self.armed, "running": self.running,
                "halt": self.halt_status(self.provider.now()),
                "enabled": sorted(self.enabled), "states": self.state,
                "intervals": {k: self._interval_for(k) for k in self.enabled},
                "health": self.health.as_dict(),
                "market_open": market_open,                       # {segment: bool}
                "any_market_open": any(market_open.values()),     # feed-wide idle flag
                "position_ticks": self.position_ticks,
                "capital": self.capital_dict()}
