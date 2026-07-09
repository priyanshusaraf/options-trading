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
from app.engine.equity_entry import equity_stop_target
from app.providers.base import MarketDataProvider, OptionQuote


class PaperBroker:
    MODE = "paper"   # stamped on every Position/Trade this broker creates (LiveBroker overrides to "live")

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
                      params: dict | None = None, plan=None) -> Position:
        # `plan` (routing decision) is used by LiveBroker to choose market/limit;
        # the paper broker ignores it and fills at the quote.
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
            mode=self.MODE,
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

    # ── intraday equity (MIS): margin-sized shares, direction-aware ──────────
    def open_equity_position(self, inst: Instrument, direction: str, price: float,
                             qty: int, charge_segment: str, reason: str,
                             now: dt.datetime, params: dict | None = None,
                             strategy_key: str | None = None) -> Position:
        """Open an intraday equity (MIS) position of `qty` shares at `price`.

        MIS is leveraged: only the MARGIN (notional/leverage) leaves cash, not the
        full notional — but P&L is on the full share move. We store entry_cost =
        margin + entry charges (the actual cash out), so the ledger reconciliation
        invariant holds exactly. SL/TP are direction-aware (a SHORT's stop is above
        entry). Charges use the intraday charge segment (NSE_INTRADAY/BSE_INTRADAY)."""
        p = params if params is not None else effective(self.settings)
        leverage = p.get("intraday_leverage", 5.0) or 5.0
        sl_pct = p.get("intraday_stop_loss_pct", 0.01)
        tp_pct = p.get("intraday_target_pct", 0.02)
        notional = price * qty
        margin = notional / leverage
        charges = compute_charges(charge_segment, "BUY", price, qty)["total"]
        cost = margin + charges
        stop, target = equity_stop_target(direction, price, sl_pct, tp_pct)

        cap = self.capital()
        cap.cash -= cost
        cap.updated_at = now

        pos = Position(
            instrument_key=inst.key, direction=direction, option_type="EQ",
            tradingsymbol=getattr(inst, "spot_symbol", "") or inst.key,
            exchange=charge_segment, segment="equity_intraday", strategy_key=strategy_key,
            strike=0.0, expiry=now.date(), lot_size=qty, qty=qty, entry_premium=price,
            entry_charges=charges, entry_cost=cost, entry_spot=price, entry_time=now,
            entry_reason=reason, stop_price=stop, target_price=target,
            last_premium=price, last_spot=price, last_mark_time=now,
            high_water_premium=price, mode=self.MODE)
        self.s.add(pos)
        self.s.commit()
        log.trade(
            f"OPEN EQUITY {direction} {pos.tradingsymbol} {qty}@{price:.2f} "
            f"— margin ₹{margin:,.0f} (chg ₹{charges:.0f}); SL {stop:.2f} / TP {target:.2f}",
            instrument=inst.key, event="OPEN_EQUITY", tradingsymbol=pos.tradingsymbol,
            premium=price, cost=round(cost, 2))
        return pos

    def close_equity_position(self, pos: Position, exit_price: float, reason: str,
                              now: dt.datetime) -> Trade:
        """Close an intraday equity position. Releases the blocked margin and books
        direction-aware P&L (a SHORT profits when price falls), net of both legs'
        charges. proceeds = entry_cost + net, so the ledger invariant stays exact."""
        qty = pos.qty
        charges = compute_charges(pos.exchange, "SELL", exit_price, qty)["total"]
        gross = ((exit_price - pos.entry_premium) * qty if pos.direction == "LONG"
                 else (pos.entry_premium - exit_price) * qty)
        total_charges = pos.entry_charges + charges
        net = gross - total_charges
        proceeds = pos.entry_cost + net    # == released margin + gross − exit charges
        margin = pos.entry_cost - pos.entry_charges

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type="EQ", tradingsymbol=pos.tradingsymbol, exchange=pos.exchange,
            segment="equity_intraday", strategy_key=pos.strategy_key,
            strike=0.0, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=pos.entry_cost,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_price, exit_charges=charges, exit_spot=exit_price,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=total_charges, net_pnl=net,
            return_pct=(net / margin * 100) if margin else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0, held_overnight=False, overnight_pnl=0.0,
            intraday_pnl=round(net, 2), reinforcements=0, mode=self.MODE)
        self.s.delete(pos)
        self.s.add(tr)
        self.s.commit()
        log.trade(
            f"CLOSE EQUITY {pos.tradingsymbol} @ {exit_price:.2f} [{reason}] "
            f"— net ₹{net:,.0f} ({tr.return_pct:+.1f}% on margin)",
            instrument=pos.instrument_key, event="CLOSE_EQUITY", reason=reason,
            net_pnl=round(net, 2))
        return tr

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
            if not pos.manual_target:
                pos.target_price = r["target_price"]   # owner-set target is not auto-extended
            pos.reinforcement_count = r["count"]
            pos.last_reinforce_time = now
            self.s.commit()
            # the stop just ratcheted — push it to the exchange GTT backstop too
            # (no-op on paper; LiveBroker modifies the live GTT).
            self.update_stop_protection(pos, pos.last_premium)
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
            mode=self.MODE,
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

    def book_partial_close(self, pos: Position, qty: int, exit_premium: float,
                           reason: str, now: dt.datetime, spot: float) -> Trade:
        """Realize PART of an open position (a SELL that only partially filled): book
        a Trade for `qty`, shrink the open position by `qty`, and split its entry cost
        proportionally. The position stays open at the reduced qty so the remainder
        can still be managed/exited. Keeps the cash reconciliation invariant exact:
        the realized entry-cost slice and the remaining entry_cost sum to the original.
        """
        qty = min(int(qty), pos.qty)
        charges = compute_charges(pos.exchange, "SELL", exit_premium, qty)["total"]
        proceeds = exit_premium * qty - charges
        gross = (exit_premium - pos.entry_premium) * qty
        # split the entry cost/charges by the fraction sold; the remainder and the
        # realized slice add back to the originals exactly (no rounding drift).
        remaining_cost = pos.entry_cost * (pos.qty - qty) / pos.qty
        cost_slice = pos.entry_cost - remaining_cost
        remaining_entry_charges = pos.entry_charges * (pos.qty - qty) / pos.qty
        charges_slice = pos.entry_charges - remaining_entry_charges
        net = proceeds - cost_slice

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type=pos.option_type, tradingsymbol=pos.tradingsymbol,
            exchange=pos.exchange, strike=pos.strike, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=cost_slice,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_premium, exit_charges=charges, exit_spot=spot,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=charges_slice + charges, net_pnl=net,
            return_pct=(net / cost_slice * 100) if cost_slice else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0,
            held_overnight=pos.held_overnight,
            overnight_pnl=0.0, intraday_pnl=round(net, 2),
            reinforcements=pos.reinforcement_count,
            mode=self.MODE,
        )
        pos.qty -= qty
        pos.entry_cost = remaining_cost
        pos.entry_charges = remaining_entry_charges
        self.s.add(tr)
        self.s.commit()
        log.trade(
            f"PARTIAL CLOSE {pos.tradingsymbol} {qty} @ {exit_premium:.2f} [{reason}] "
            f"— net ₹{net:,.0f}; {pos.qty} still open",
            instrument=pos.instrument_key, event="PARTIAL_CLOSE", reason=reason,
            net_pnl=round(net, 2))
        return tr

    def book_partial_close_equity(self, pos: Position, qty: int, exit_price: float,
                                  reason: str, now: dt.datetime) -> Trade:
        """Realize PART of an intraday-equity (MIS) position — the equity analogue of
        book_partial_close (H16). Direction-aware P&L (a SHORT profits when price
        falls), releases the sold slice's margin, and splits entry cost/charges
        proportionally so the cash invariant stays exact (the realized slice + the
        remaining entry_cost sum to the original). The position stays open at the
        reduced qty so the remainder can be re-stopped and exited later."""
        qty = min(int(qty), pos.qty)
        exit_charges = compute_charges(pos.exchange, "SELL", exit_price, qty)["total"]
        gross = ((exit_price - pos.entry_premium) * qty if pos.direction == "LONG"
                 else (pos.entry_premium - exit_price) * qty)
        remaining_cost = pos.entry_cost * (pos.qty - qty) / pos.qty
        cost_slice = pos.entry_cost - remaining_cost
        remaining_entry_charges = pos.entry_charges * (pos.qty - qty) / pos.qty
        charges_slice = pos.entry_charges - remaining_entry_charges
        margin_slice = cost_slice - charges_slice
        net = gross - charges_slice - exit_charges
        proceeds = cost_slice + net    # released margin slice + net

        cap = self.capital()
        cap.cash += proceeds
        cap.realized_pnl += net
        cap.updated_at = now

        tr = Trade(
            instrument_key=pos.instrument_key, direction=pos.direction,
            option_type="EQ", tradingsymbol=pos.tradingsymbol, exchange=pos.exchange,
            segment="equity_intraday", strategy_key=pos.strategy_key,
            strike=0.0, expiry=pos.expiry, qty=qty,
            entry_premium=pos.entry_premium, entry_cost=cost_slice,
            entry_spot=pos.entry_spot, entry_time=pos.entry_time,
            exit_premium=exit_price, exit_charges=exit_charges, exit_spot=exit_price,
            exit_time=now, exit_reason=reason, gross_pnl=gross,
            charges_total=charges_slice + exit_charges, net_pnl=net,
            return_pct=(net / margin_slice * 100) if margin_slice else 0.0,
            holding_minutes=(now - pos.entry_time).total_seconds() / 60,
            win=net > 0, held_overnight=False, overnight_pnl=0.0,
            intraday_pnl=round(net, 2), reinforcements=0, mode=self.MODE)
        pos.qty -= qty
        pos.entry_cost = remaining_cost
        pos.entry_charges = remaining_entry_charges
        self.s.add(tr)
        self.s.commit()
        log.trade(
            f"PARTIAL CLOSE EQUITY {pos.tradingsymbol} {qty} @ {exit_price:.2f} "
            f"[{reason}] — net ₹{net:,.0f}; {pos.qty} still open",
            instrument=pos.instrument_key, event="PARTIAL_CLOSE_EQUITY", reason=reason,
            net_pnl=round(net, 2))
        return tr

    # ── exchange-side stop protection (no-op for paper; LiveBroker overrides) ──
    def update_stop_protection(self, pos, last_price) -> None:
        """Sync an exchange-side GTT stop to the (possibly ratcheted) stop price."""

    def ensure_stop_protection(self, pos, last_price) -> None:
        """Per-tick check that a backstop is resting; no-op for paper."""

    def reconcile_orphans(self, now: dt.datetime) -> list:
        """Book any bot position the live account no longer backs (e.g. a GTT fired
        while the bot was down). No-op on paper."""
        return []

    def adopt_pending_entries(self, now: dt.datetime) -> list:
        """Adopt any bot entry order that filled AFTER its poll window into the book.
        No-op on paper (paper fills are synchronous, never late)."""
        return []

    def cancel_working_entries(self) -> list:
        """Cancel working/timed-out entry orders on KILL. No-op on paper (paper fills
        are synchronous — there is never a resting entry order)."""
        return []

    def recover_journal(self, now) -> list:
        """Replay the persisted order journal on startup (H13). No-op on paper (paper
        fills are synchronous — nothing is ever left in flight across a restart)."""
        return []

    # ── analytics support ─────────────────────────────────────────────────
    def snapshot(self, now: dt.datetime) -> EquitySnapshot:
        opens = self.open_positions()
        invested = sum(p.entry_cost for p in opens)
        # mtm_value() is segment-aware: options = premium × qty (full cost left cash),
        # leveraged MIS = margin + unrealized P&L (only margin left cash). Summing raw
        # last × qty double-counts MIS leverage and inflates the persisted equity curve.
        mtm = sum(p.mtm_value() for p in opens)
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
