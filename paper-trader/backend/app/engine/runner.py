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
from app.engine.allocator import Candidate, allocate
from app.engine.broker import PaperBroker
from app.engine.charges import compute_charges
from app.engine.exit_monitor import evaluate_exit
from app.options.picker import pick_option
from app.providers.factory import get_provider
from app.strategy.signals import compute_signals, to_payload


def _to_df(candles) -> pd.DataFrame:
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


class EngineRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = get_provider()
        self.broker = PaperBroker(self.provider)
        self.state: dict[str, dict] = {}      # latest per-instrument engine snapshot
        self.last_pick: dict[str, dict] = {}  # latest picker output (Options-Calc view)
        self.enabled: set[str] = self._load_enabled()
        self.running = False
        self.tick_count = 0
        self.on_update = None  # optional async callback(state) for WS broadcast

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

    # ── one engine step ───────────────────────────────────────────────────
    def tick(self) -> None:
        s, prov = self.settings, self.provider
        now = prov.now()
        opens = {p.instrument_key: p for p in self.broker.open_positions()}

        # 1) strategy on every enabled instrument
        for key in list(self.enabled):
            inst = get_instrument(key)
            try:
                candles = prov.get_candles(inst, s.interval, s.history_days)
            except Exception as e:
                log.error(f"candles failed: {e}", instrument=key)
                continue
            if len(candles) < s.ema_length + 5:
                continue
            sig = compute_signals(_to_df(candles), ema_length=s.ema_length,
                                  z_length=s.z_length, entry_z=s.entry_z,
                                  slope_lookback=s.slope_lookback)
            latest = to_payload(sig, entry_z=s.entry_z)["latest"]
            if not latest:
                continue
            held = opens.get(key)
            self.state[key] = {
                "instrument": key, "name": inst.name, "segment": inst.segment,
                "time": latest["time"], "close": latest["close"], "ema": latest["ema"],
                "z": latest["z"], "z_prev": latest["z_prev"], "slope": latest["slope"],
                "std": latest["std"], "trend": latest["trend"], "signal": latest["signal"],
                "long_exit": latest["long_exit"], "short_exit": latest["short_exit"],
                "position": held.to_dict() if held else None,
            }

        # 2) EXIT pass (frees capital before entries this tick)
        for key, pos in list(opens.items()):
            inst = get_instrument(key)
            premium = prov.option_ltp(inst, pos.tradingsymbol, pos.strike,
                                      pos.expiry, pos.option_type)
            spot = prov.get_ltp(inst)
            if premium is None:
                continue
            self.broker.mark(pos, premium, spot)
            st = self.state.get(key, {})
            should, reason = evaluate_exit(
                pos.direction, pos.stop_price, pos.target_price, premium,
                st.get("long_exit", False), st.get("short_exit", False))
            if should:
                self.broker.close_position(pos, premium, reason, now, spot)
                opens.pop(key, None)
                if key in self.state:
                    self.state[key]["position"] = None
        self.broker.commit()  # persist marks

        # 3) ENTRY pass — fresh crossovers on instruments not already held
        cands: list[Candidate] = []
        meta: dict[str, tuple] = {}
        for key in list(self.enabled):
            if key in opens:
                continue  # one position per instrument; ignore new signals while held
            st = self.state.get(key)
            if not st or st["signal"] not in ("LONG_ENTRY", "SHORT_ENTRY"):
                continue
            direction = "LONG" if st["signal"] == "LONG_ENTRY" else "SHORT"
            inst = get_instrument(key)
            self._record_signal(now, key, st)
            chain = prov.get_option_chain(inst)
            if not chain:
                log.warn("signal fired but no option chain — skipped", instrument=key)
                continue
            pick = pick_option(chain, direction, s, now)
            self.last_pick[key] = {
                "time": now.isoformat(), "direction": direction, "reason": pick.reason,
                "spot": round(chain.spot, 2), "expiry": chain.expiry.isoformat(),
                "chosen": pick.chosen.to_dict() if pick.chosen else None,
                "candidates": pick.candidates,
            }
            if not pick.chosen:
                log.warn(f"signal fired but {pick.reason}", instrument=key)
                continue
            qty = pick.chosen.lot_size
            charges = compute_charges(inst.segment, "BUY", pick.chosen.ltp, qty)["total"]
            cost = pick.chosen.ltp * qty + charges
            cands.append(Candidate(key, direction, cost))
            meta[key] = (inst, direction, pick, chain)

        if cands:
            alloc = allocate(cands, self.broker.cash())
            if len(alloc.funded) < len(cands):
                log.info(f"capital shortfall — {len(alloc.funded)}/{len(cands)} "
                         f"signals funded by priority")
            for c in alloc.funded:
                inst, direction, pick, chain = meta[c.instrument_key]
                self.broker.open_position(inst, direction, pick.chosen,
                                          pick.reason, now, chain.spot)
                if c.instrument_key in self.state:
                    p = self.broker.position_for(c.instrument_key)
                    self.state[c.instrument_key]["position"] = p.to_dict() if p else None
            for c, reason in alloc.skipped:
                log.warn(f"signal dropped — {reason}", instrument=c.instrument_key)

        # 4) portfolio equity snapshot
        self.broker.snapshot(now)
        self.tick_count += 1

    def _record_signal(self, now, key, st) -> None:
        with SessionLocal() as s:
            s.add(SignalEvent(time=now, instrument_key=key, signal=st["signal"],
                              z=st["z"], slope=st["slope"], close=st["close"],
                              acted=True))
            s.commit()

    # ── async run loop ────────────────────────────────────────────────────
    async def run(self) -> None:
        self.running = True
        log.info(f"engine started — provider={self.provider.name}, "
                 f"interval={self.settings.interval}, "
                 f"enabled={sorted(self.enabled)}")
        while self.running:
            try:
                self.tick()
            except Exception as e:
                log.error(f"tick error: {e}")
            if self.on_update:
                try:
                    await self.on_update(self.snapshot_state())
                except Exception:
                    pass
            if self.provider.name == "mock":
                if not self.provider.advance():
                    log.info("mock history exhausted — engine idling")
                    await asyncio.sleep(5)
                    continue
                await asyncio.sleep(self.settings.mock_tick_seconds)
            else:
                await asyncio.sleep(30)  # live: poll cadence; acts on completed candles

    def stop(self) -> None:
        self.running = False

    # ── snapshots for API/WS ──────────────────────────────────────────────
    def capital_dict(self) -> dict:
        cap = self.broker.capital()
        opens = self.broker.open_positions()
        mtm = sum((p.last_premium or p.entry_premium) * p.qty for p in opens)
        return {
            "initial": cap.initial_capital, "cash": round(cap.cash, 2),
            "invested": round(sum(p.entry_cost for p in opens), 2),
            "equity": round(cap.cash + mtm, 2),
            "realized_pnl": round(cap.realized_pnl, 2),
            "open_count": len(opens),
        }

    def snapshot_state(self) -> dict:
        return {"tick": self.tick_count, "provider": self.provider.name,
                "time": self.provider.now().isoformat(),
                "enabled": sorted(self.enabled), "states": self.state,
                "capital": self.capital_dict()}
