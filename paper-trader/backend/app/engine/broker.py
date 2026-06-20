"""
The paper broker. Simulates fills at the contract LTP, books realistic charges,
and keeps the persistent capital ledger.

Every open position has removed (premium×qty + entry charges) from cash; closing
adds back (exit_premium×qty − exit charges) and folds the net into realized P&L.
This keeps the reconciliation invariant in models.py true at all times.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.core.config import get_settings
from app.core.instruments import Instrument
from app.core.logging import log
from app.db.models import CapitalState, EquitySnapshot, Position, Trade
from app.db.session import SessionLocal
from app.core.runtime_config import effective
from app.engine.charges import compute_charges
from app.providers.base import MarketDataProvider, OptionQuote


class PaperBroker:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider
        self.settings = get_settings()
        self.s = SessionLocal()

    # ── ledger ────────────────────────────────────────────────────────────
    def capital(self) -> CapitalState:
        return self.s.get(CapitalState, 1)

    def cash(self) -> float:
        return self.capital().cash

    def open_positions(self) -> list[Position]:
        return list(self.s.scalars(select(Position)))

    def position_for(self, key: str) -> Position | None:
        return self.s.scalar(select(Position).where(Position.instrument_key == key))

    def commit(self) -> None:
        self.s.commit()

    # ── fills ─────────────────────────────────────────────────────────────
    def open_position(self, inst: Instrument, direction: str, q: OptionQuote,
                      reason: str, now: dt.datetime, spot: float,
                      params: dict | None = None) -> Position:
        qty, premium = q.lot_size, q.ltp
        charges = compute_charges(inst.segment, "BUY", premium, qty)["total"]
        cost = premium * qty + charges
        # Initial SL/TP honor live Settings overrides (runtime_config). The runner
        # passes its already-resolved snapshot; other callers (manual_open, tests)
        # fall back to the effective merge so an override is never silently ignored.
        p = params if params is not None else effective(self.settings)
        stop_loss_pct = p.get("stop_loss_pct", self.settings.stop_loss_pct)
        target_pct = p.get("target_pct", self.settings.target_pct)

        cap = self.capital()
        cap.cash -= cost
        cap.updated_at = now

        pos = Position(
            instrument_key=inst.key, direction=direction, option_type=q.option_type,
            tradingsymbol=q.tradingsymbol, exchange=inst.segment, strike=q.strike,
            expiry=q.expiry, lot_size=qty, qty=qty, entry_premium=premium,
            entry_charges=charges, entry_cost=cost, entry_spot=spot, entry_time=now,
            entry_reason=reason,
            stop_price=premium * (1 - stop_loss_pct),
            target_price=premium * (1 + target_pct),
            last_premium=premium, last_spot=spot,
            last_mark_time=now, high_water_premium=premium,
        )
        self.s.add(pos)
        self.s.commit()
        log.trade(
            f"OPEN {direction} {q.tradingsymbol} @ {premium:.2f} ×{qty} "
            f"— cost ₹{cost:,.0f} (chg ₹{charges:.0f}); SL {pos.stop_price:.2f} / "
            f"TP {pos.target_price:.2f}",
            instrument=inst.key, event="OPEN", tradingsymbol=q.tradingsymbol,
            premium=premium, cost=round(cost, 2))
        return pos

    def manual_open(self, inst: Instrument, direction: str, chain, settings,
                    now: dt.datetime) -> tuple[Position | None, str]:
        """Owner-initiated paper entry. Same safety as the engine: 1 lot, one
        position per instrument, capital-checked, paper-only. Returns (pos, reason)."""
        from app.options.picker import pick_option
        if self.position_for(inst.key) is not None:
            return None, "already holding a position for this instrument"
        if chain is None:
            return None, "no option chain available to price a contract"
        pick = pick_option(chain, direction, settings, now)
        if not pick.chosen:
            return None, f"no priceable contract: {pick.reason}"
        qty = pick.chosen.lot_size
        charges = compute_charges(inst.segment, "BUY", pick.chosen.ltp, qty)["total"]
        cost = pick.chosen.ltp * qty + charges
        if cost > self.cash():
            return None, f"insufficient cash: need ₹{cost:,.0f}, have ₹{self.cash():,.0f}"
        pos = self.open_position(inst, direction, pick.chosen,
                                 f"MANUAL {direction}", now, chain.spot)
        log.info(f"MANUAL OPEN {direction} {pos.tradingsymbol} @ {pick.chosen.ltp:.2f}",
                 instrument=inst.key, event="MANUAL_OPEN", manual=True)
        return pos, "ok"

    def reinforce_position(self, pos: Position, params: dict, now: dt.datetime) -> dict:
        """Apply a same-direction reinforcement to a held position: ratchet the
        stop, optionally extend the target, bump the count. No quantity change."""
        from app.engine.exit_monitor import apply_reinforcement
        prem = pos.last_premium or pos.entry_premium
        r = apply_reinforcement(pos.entry_premium, pos.stop_price, pos.target_price,
                                prem, pos.reinforcement_count, pos.last_reinforce_time,
                                now, params)
        if r["applied"]:
            pos.stop_price = r["stop_price"]
            pos.target_price = r["target_price"]
            pos.reinforcement_count = r["count"]
            pos.last_reinforce_time = now
            self.s.commit()
            log.info(f"REINFORCE {pos.tradingsymbol} — {r['reason']}",
                     instrument=pos.instrument_key, event="REINFORCE",
                     count=r["count"])
        return r

    def mark(self, pos: Position, premium: float | None, spot: float | None,
             now: dt.datetime | None = None) -> None:
        # Use explicit None checks: a real 0.0 premium (option decayed to zero —
        # the buyer's maximum loss) is a VALID mark and must advance freshness, or
        # the staleness guard would suppress the stop at the worst possible time.
        if premium is not None:
            pos.last_premium = premium
            pos.last_mark_time = now or dt.datetime.now()
            if premium > (pos.high_water_premium or 0.0):
                pos.high_water_premium = premium
        if spot is not None:
            pos.last_spot = spot

    def close_position(self, pos: Position, exit_premium: float, reason: str,
                       now: dt.datetime, spot: float) -> Trade:
        qty = pos.qty
        charges = compute_charges(pos.exchange, "SELL", exit_premium, qty)["total"]
        proceeds = exit_premium * qty - charges
        gross = (exit_premium - pos.entry_premium) * qty
        total_charges = pos.entry_charges + charges
        net = proceeds - pos.entry_cost  # == gross - total_charges

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type=pos.option_type, tradingsymbol=pos.tradingsymbol,
            exchange=pos.exchange, strike=pos.strike, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=pos.entry_cost,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_premium, exit_charges=charges, exit_spot=spot,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=total_charges, net_pnl=net,
            return_pct=(net / pos.entry_cost * 100) if pos.entry_cost else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0,
            held_overnight=pos.held_overnight,
            overnight_pnl=round(pos.overnight_pnl, 2),
            intraday_pnl=round(net - pos.overnight_pnl, 2),
            reinforcements=pos.reinforcement_count,
        )
        self.s.delete(pos)
        self.s.add(tr)
        self.s.commit()
        log.trade(
            f"CLOSE {pos.tradingsymbol} @ {exit_premium:.2f} [{reason}] "
            f"— net ₹{net:,.0f} ({tr.return_pct:+.1f}%)",
            instrument=pos.instrument_key, event="CLOSE", reason=reason,
            net_pnl=round(net, 2))
        return tr

    # ── analytics support ─────────────────────────────────────────────────
    def snapshot(self, now: dt.datetime) -> EquitySnapshot:
        opens = self.open_positions()
        invested = sum(p.entry_cost for p in opens)
        mtm = sum((p.last_premium or p.entry_premium) * p.qty for p in opens)
        cap = self.capital()
        snap = EquitySnapshot(time=now, equity=cap.cash + mtm, cash=cap.cash,
                              invested=invested, realized_pnl=cap.realized_pnl,
                              open_count=len(opens))
        self.s.add(snap)
        self.s.commit()
        return snap

    def reconcile(self) -> dict:
        """Self-check: cash should equal initial + realized − Σ(open entry_cost)."""
        cap = self.capital()
        opens = self.open_positions()
        expected = cap.initial_capital + cap.realized_pnl - sum(p.entry_cost for p in opens)
        return {"cash": round(cap.cash, 2), "expected_cash": round(expected, 2),
                "diff": round(cap.cash - expected, 4),
                "realized_pnl": round(cap.realized_pnl, 2), "open": len(opens)}

    def close(self) -> None:
        self.s.close()
