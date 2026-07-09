"""
LiveBroker — places REAL Kite orders, books the ACTUAL fill into the same ledger
as the paper broker, and enforces the position-ownership boundary so it can never
touch the owner's own positions.

Subclasses PaperBroker: every bit of ledger / accounting / mark / snapshot /
reconcile logic is reused unchanged — only the FILL mechanism changes. open/close
return None on any non-fill (rejected / partial / timeout) OR an ownership block,
so the engine keeps managing the position and alerts instead of assuming a fill.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import replace

from sqlalchemy import select

from app.core.instruments import get_instrument
from app.core.logging import log
from app.db.models import OrderJournal, Position
from app.engine.broker import PaperBroker
from app.providers.base import OptionQuote
from app.engine.kite_order_client import exchange_for_segment, product_for_segment
from app.engine.order_executor import OrderRequest, execute_order
from app.engine.reconcile import can_bot_close

TAG = "pt-bot"   # every order the bot places is tagged so it's identifiable

# Kite order statuses that mean the order is dead (no working order left at the
# exchange). Anything else that is not a terminal fill is treated as possibly-working.
_DEAD_STATUSES = frozenset({"REJECTED", "CANCELLED"})


class LiveBroker(PaperBroker):
    MODE = "live"   # every fill this broker books is a REAL trade — tagged so the log never mixes it with paper

    def __init__(self, provider, order_client, *, poll_seconds: float = 0.5,
                 timeout_seconds: float = 30.0, notifier=None) -> None:
        super().__init__(provider)
        self.client = order_client
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.notifier = notifier
        # tradingsymbol -> order id of an order that TIMED OUT while possibly still
        # working at the exchange. Before placing a NEW order for that contract we
        # cancel/await it, so a contract never has two working bot orders at once
        # (the timed-out-but-still-working double-send / oversell residual).
        self._inflight: dict[str, str] = {}
        # instrument_key -> count of CONSECUTIVE reconcile reads showing it orphaned.
        # A position is booked closed only once this reaches orphan_confirm_count, so a
        # single transient account-feed glitch can't phantom-close a live position (L8).
        self._orphan_seen: dict[str, int] = {}
        # tradingsymbol -> context for a bot ENTRY order that timed out with no confirmed
        # fill. It may still fill later (a pre-open uncross, a slow open); the reconcile
        # sweep re-queries it and ADOPTS a confirmed fill into the book (+stop) rather than
        # leaving an untracked, stopless orphan — the BSE 2026-07-03 incident (#17).
        self._pending_entries: dict[str, dict] = {}
        # #14: CONSECUTIVE zero-fill order outcomes. Systemic failures (expired token,
        # IP not whitelisted, margin exhausted) kill every order the same way; the
        # runner disarms once this reaches order_failure_disarm_count. Any real fill
        # resets it, as does a deliberate re-arm.
        self.order_fail_streak: int = 0

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier._emit(text)
            except Exception as e:
                # L11 — a money-critical alert that fails to send must never vanish
                # silently; at least record it (with the dropped text) so it's visible
                # in the Engine/Logs console even when Telegram is down.
                log.error(f"ALERT NOT DELIVERED ({e}): {text}", event="NOTIFY_FAIL")

    def _execute(self, req: OrderRequest, *, intent: str = "", kind: str = "", context=None):
        """Place a real order, JOURNAL it (H13), and return (res, filled, avg). The
        journal row is WORKING before placement, stamped with the order id the instant
        placement acks, and marked TERMINAL on resolution — so a crash in the poll
        window is recoverable on restart. ALL journal I/O is non-fatal: a journal
        write must never block or fail a real order/exit."""
        row_id = self._journal_open(req, intent, kind, context)
        on_placed = (lambda oid: self._journal_set_order_id(row_id, oid)) if row_id else None
        res = execute_order(self.client, req, poll_seconds=self.poll_seconds,
                            timeout_seconds=self.timeout_seconds, on_placed=on_placed)
        filled, avg = self._actual_fill(res)
        self._journal_resolve(row_id, res, filled, avg)
        return res, filled, avg

    # ── order journal (H13) — durable mirror of _inflight ∪ _pending_entries ──
    def _journal_open(self, req, intent: str, kind: str, context) -> int | None:
        if not intent:
            return None
        try:
            row = OrderJournal(
                order_id=None, tradingsymbol=req.tradingsymbol,
                instrument_key=(context or {}).get("inst_key", ""), side=req.side,
                kind=kind, intent=intent, qty=req.qty,
                context_json=json.dumps(context or {}), status="WORKING",
                placed_at=self.provider.now())
            self.s.add(row)
            self.s.commit()
            return row.id
        except Exception as e:
            log.error(f"journal open failed: {e}", event="JOURNAL_FAIL")
            return None

    def _journal_set_order_id(self, row_id: int, order_id: str) -> None:
        try:
            row = self.s.get(OrderJournal, row_id)
            if row:
                row.order_id = order_id
                self.s.commit()
        except Exception as e:
            log.error(f"journal order_id set failed: {e}", event="JOURNAL_FAIL")

    @staticmethod
    def _journal_resolution(res, filled: int, qty: int) -> str | None:
        """None => the row stays WORKING (order may still be live); else terminal."""
        if qty > 0 and filled >= qty:
            return "FILLED"
        if filled > 0:                              # partial
            if "timeout" in (res.reason or "").lower():
                return None                         # may still work — H16 resolves it
            return "CANCELLED"                      # cancelled-after-partial (dead)
        if res.status == "REJECTED":
            return "REJECTED"
        if res.status == "ERROR" and not res.order_id:
            return "NEVER_PLACED"
        if res.order_id and res.status in ("TIMEOUT", "ERROR"):
            return None                             # working — recover on restart
        return "UNKNOWN"

    def _journal_resolve(self, row_id: int | None, res, filled: int, avg: float) -> None:
        if row_id is None:
            return
        try:
            row = self.s.get(OrderJournal, row_id)
            if not row:
                return
            resolution = self._journal_resolution(res, filled, row.qty)
            if resolution is not None:
                row.status = "TERMINAL"
                row.resolution = resolution
                row.filled_qty = filled
                row.avg_price = avg
                row.resolved_at = self.provider.now()
                self.s.commit()
        except Exception as e:
            log.error(f"journal resolve failed: {e}", event="JOURNAL_FAIL")

    def journal_mark_terminal(self, order_id: str, resolution: str,
                              filled: int = 0, avg: float = 0.0) -> None:
        """Mark the WORKING journal row for an order terminal — called from every site
        that pops _inflight/_pending_entries, keeping the journal in lockstep."""
        if not order_id:
            return
        try:
            row = self.s.scalars(
                select(OrderJournal).where(OrderJournal.order_id == order_id,
                                           OrderJournal.status == "WORKING")).first()
            if row:
                row.status = "TERMINAL"
                row.resolution = resolution
                if filled:
                    row.filled_qty = filled
                if avg:
                    row.avg_price = avg
                row.resolved_at = self.provider.now()
                self.s.commit()
        except Exception as e:
            log.error(f"journal mark terminal failed: {e}", event="JOURNAL_FAIL")

    def _rebuild_pending(self, row, ctx) -> dict:
        """Reconstruct a _pending_entries context from a journaled ENTRY row (H13)."""
        inst = get_instrument(ctx["inst_key"])
        if row.kind == "options":
            qd = dict(ctx.get("q", {}))
            exp = qd.get("expiry")
            if isinstance(exp, str):
                try:
                    qd["expiry"] = dt.date.fromisoformat(exp)
                except Exception:
                    pass
            q = OptionQuote(instrument_key=ctx["inst_key"], **qd)
            return {"kind": "options", "order_id": row.order_id, "inst": inst,
                    "direction": ctx["direction"], "q": q,
                    "reason": ctx.get("reason", "recovered"),
                    "spot": ctx.get("spot", 0.0), "params": ctx.get("params")}
        return {"kind": "equity", "order_id": row.order_id, "inst": inst,
                "direction": ctx["direction"], "charge_segment": ctx.get("charge_segment", ""),
                "reason": ctx.get("reason", "recovered"), "params": ctx.get("params"),
                "strategy_key": ctx.get("strategy_key")}

    def recover_journal(self, now) -> list:
        """H13: on startup, replay WORKING journal rows — the in-memory in-flight
        trackers were wiped by the restart. A late-filled ENTRY is adopted (book +
        stop); a filled EXIT is booked ledger-only at the REAL price (beats the orphan
        reconciler's stale mark); still-working orders are re-tracked; dead ones closed.
        A status read failure leaves the row WORKING (fail open — retry next start)."""
        recovered: list[str] = []
        rows = self.s.scalars(
            select(OrderJournal).where(OrderJournal.status == "WORKING")).all()
        for row in rows:
            if not row.order_id:
                continue   # never-acked placement — the tag sweep surfaces it
            try:
                st = self.client.status(row.order_id)
            except Exception as e:
                log.error(f"RECOVER {row.tradingsymbol}: status({row.order_id}) failed: {e} "
                          f"— left WORKING", event="RECOVER_FAIL")
                continue
            status = str(st.get("status", "")).upper()
            filled = int(st.get("filled_qty", 0) or 0)
            avg = float(st.get("avg_price", 0.0) or 0.0)
            try:
                ctx = json.loads(row.context_json or "{}")
            except Exception:
                ctx = {}
            if row.intent == "ENTRY":
                if filled > 0 and avg > 0:
                    self._pending_entries[row.tradingsymbol] = self._rebuild_pending(row, ctx)
                elif status in _DEAD_STATUSES:
                    self.journal_mark_terminal(row.order_id, "DEAD")
                else:
                    self._inflight[row.tradingsymbol] = row.order_id
                    self._pending_entries[row.tradingsymbol] = self._rebuild_pending(row, ctx)
            else:   # EXIT
                pos = self.s.get(Position, ctx["position_id"]) if ctx.get("position_id") else None
                if filled >= row.qty and pos is not None:
                    if pos.segment == "equity_intraday":
                        PaperBroker.close_equity_position(self, pos, avg, "RECOVERED_EXIT_FILL", now)
                    else:
                        PaperBroker.close_position(self, pos, avg, "RECOVERED_EXIT_FILL", now, pos.last_spot)
                    self.journal_mark_terminal(row.order_id, "FILLED", filled, avg)
                    recovered.append(row.tradingsymbol)
                elif status in _DEAD_STATUSES:
                    self.journal_mark_terminal(row.order_id, "DEAD")
                else:
                    self._inflight[row.tradingsymbol] = row.order_id
        try:
            recovered.extend(self.adopt_pending_entries(now))   # books + marks ADOPTED
        except Exception as e:
            log.error(f"RECOVER adopt failed: {e}", event="RECOVER_FAIL")
        self._recover_tag_sweep()
        return recovered

    def _recover_tag_sweep(self) -> None:
        """Surface any tag=pt-bot exchange order with NO journal row (a crash between the
        journal write and the placement ack). Never auto-books — alerts to verify."""
        try:
            orders = self.client.orders()
        except Exception:
            return
        known = {r.order_id for r in self.s.scalars(select(OrderJournal)).all() if r.order_id}
        for o in orders or []:
            if o.get("tag") == TAG and o.get("order_id") not in known:
                log.error(f"RECOVER: tagged order {o.get('order_id')} ({o.get('tradingsymbol')}) "
                          f"has no journal row — verify on Zerodha", event="RECOVER_UNTRACKED")
                self._notify(f"⚠️ a bot-tagged order ({o.get('order_id')}) has no journal record "
                             f"— verify on Zerodha; the bot won't touch it.")

    @staticmethod
    def _quote_to_ctx(q) -> dict:
        """JSON-safe snapshot of an OptionQuote for the journal, rebuilt on recovery."""
        exp = q.expiry.isoformat() if hasattr(q.expiry, "isoformat") else q.expiry
        return {"tradingsymbol": q.tradingsymbol, "exchange": q.exchange, "strike": q.strike,
                "expiry": exp, "option_type": q.option_type, "lot_size": q.lot_size,
                "ltp": q.ltp, "bid": q.bid, "ask": q.ask, "volume": q.volume, "oi": q.oi}

    def _note_order_outcome(self, filled: int) -> None:
        """#14: feed the order circuit breaker — a zero-fill outcome extends the
        consecutive-failure streak, any real fill resets it. Called right after
        every _actual_fill read so the streak tracks ORDERS, not signals."""
        self.order_fail_streak = 0 if filled > 0 else self.order_fail_streak + 1

    def _record_inflight(self, symbol: str, res) -> None:
        """An order that was placed but whose outcome is UNKNOWN — a TIMEOUT (no fill
        reported) or an ERROR after submission (e.g. the status poll failed) — may
        still be live at the exchange. Record it so the next open/close for this
        contract cancels/awaits it first, never sending a second working order. (An
        ERROR with no order id means nothing reached the exchange — not recorded.)"""
        if res.order_id and res.status in ("TIMEOUT", "ERROR"):
            self._inflight[symbol] = res.order_id

    def _ensure_no_inflight(self, symbol: str) -> bool:
        """Guarantee at most ONE working bot order per contract. If a prior order for
        this symbol may still be working, resolve it before placing a new one. Returns
        True if it is now safe to place, False if it is NOT (the prior order already
        filled — a second order would double up — or a stuck order could not be
        cancelled)."""
        oid = self._inflight.pop(symbol, None)
        if not oid:
            return True
        try:
            st = self.client.status(oid)
        except Exception as e:
            st = {}
            log.error(f"INFLIGHT {symbol}: status({oid}) read failed: {e}",
                      event="INFLIGHT_FAIL")
        status = str(st.get("status", "")).upper()
        filled = int(st.get("filled_qty", 0) or 0)
        if filled > 0:
            # the prior order actually filled since we recorded it — placing another
            # would be a duplicate BUY / an oversell. Surface it; do NOT place.
            log.error(f"INFLIGHT {symbol}: prior order {oid} already filled {filled} — "
                      f"NOT placing another", event="INFLIGHT_FILLED")
            self._notify(f"⚠️ {symbol}: a prior bot order ({oid}) already filled {filled} "
                         f"— verify on Zerodha; not sending another")
            return False
        if status in _DEAD_STATUSES or status == "COMPLETE":
            return True   # nothing working at the exchange — safe to place fresh
        # OPEN / PENDING / unknown / unreadable -> cancel and confirm before placing
        try:
            self.client.cancel(oid)
            log.warn(f"INFLIGHT {symbol}: cancelled stuck order {oid} before re-placing",
                     event="INFLIGHT_CANCEL")
        except Exception as e:
            log.error(f"INFLIGHT {symbol}: cancel({oid}) failed: {e} — NOT placing "
                      f"another to avoid a double fill", event="INFLIGHT_FAIL")
            self._notify(f"⚠️ {symbol}: couldn't cancel a stuck order ({oid}); not "
                         f"sending a new one to avoid a double fill — check Zerodha")
            return False
        return True

    def cancel_working_entries(self) -> list[str]:
        """H8: cancel every working/timed-out bot ENTRY order so KILL is a true hard
        stop — a still-resting entry can't fill after the kill and leave an untracked,
        stopless position. Best-effort per order; an order whose cancel FAILS (it may
        have just raced to a fill) is kept in the trackers so adopt_pending_entries can
        still catch and manage that fill. Successfully-cancelled orders are cleared."""
        order_ids = set(self._inflight.values())
        order_ids |= {ctx["order_id"] for ctx in self._pending_entries.values()
                      if ctx.get("order_id")}
        cancelled, failed = [], set()
        for oid in order_ids:
            try:
                self.client.cancel(oid)
                cancelled.append(oid)
                self.journal_mark_terminal(oid, "CANCELLED")   # H13
                log.warn(f"KILL: cancelled working entry order {oid}", event="KILL_CANCEL")
            except Exception as e:
                failed.add(oid)
                log.error(f"KILL: cancel({oid}) failed: {e} — verify on Zerodha",
                          event="KILL_CANCEL_FAIL")
                self._notify(f"⚠️ KILL: couldn't cancel working order {oid} — it may have "
                             f"filled; verify on Zerodha")
        # keep only orders whose cancel failed (a fill may have beaten the cancel — let
        # adoption manage it); drop everything successfully cancelled.
        self._inflight = {s: o for s, o in self._inflight.items() if o in failed}
        self._pending_entries = {s: c for s, c in self._pending_entries.items()
                                 if c.get("order_id") in failed}
        return cancelled

    def _actual_fill(self, res) -> tuple[int, float]:
        """How much actually filled, and at what average price. The poll's own count
        is authoritative for FILLED/PARTIAL; on a TIMEOUT (poll gave up reporting
        nothing) we re-query the order once to catch a fill that landed at the buzzer
        — so a real position is never missed."""
        if res.filled_qty and res.filled_qty > 0:
            return int(res.filled_qty), float(res.avg_price)
        if res.status == "TIMEOUT" and res.order_id:
            try:
                st = self.client.status(res.order_id)
            except Exception:
                return 0, 0.0
            fq = int(st.get("filled_qty", 0) or 0)
            if fq > 0:
                return fq, float(st.get("avg_price", 0.0) or 0.0)
        return 0, 0.0

    def open_position(self, inst, direction, q, reason, now, spot,
                      params=None, plan=None):
        # never two working bot orders on one contract — resolve any prior in-flight
        # order for this symbol first (cancel a stuck one; abort if one already filled).
        if not self._ensure_no_inflight(q.tradingsymbol):
            return None
        order_type = plan.action if (plan and plan.action in ("MARKET", "LIMIT")) else "MARKET"
        limit = plan.limit_price if (plan and plan.action == "LIMIT") else None
        res, filled, avg = self._execute(
            OrderRequest(q.tradingsymbol, inst.segment, "BUY", q.lot_size, order_type, limit, tag=TAG),
            intent="ENTRY", kind="options",
            context={"inst_key": inst.key, "direction": direction, "reason": reason,
                     "spot": spot, "params": params, "q": self._quote_to_ctx(q)})
        # L1 — ADOPT whatever actually filled (partial fills and buzzer fills too),
        # never silently drop a real position. Only a genuine zero-fill records nothing.
        self._note_order_outcome(filled)
        if filled <= 0:
            self._record_inflight(q.tradingsymbol, res)   # may still be working — guard next tick
            # C3: the option order may still fill after the poll window (a slow ack).
            # Remember enough to ADOPT that late fill on the reconcile sweep — otherwise
            # it becomes an invisible, stopless position (the equity #17 fix, now for
            # options, the default segment).
            if res.order_id and res.status in ("TIMEOUT", "ERROR"):
                self._pending_entries[q.tradingsymbol] = {
                    "kind": "options", "order_id": res.order_id, "inst": inst,
                    "direction": direction, "q": q, "reason": reason, "spot": spot,
                    "params": params}
            log.error(f"LIVE OPEN not filled [{res.status}] {q.tradingsymbol} — {res.reason}",
                      instrument=inst.key, event="LIVE_OPEN_FAIL")
            self._notify(f"⚠️ LIVE OPEN {q.tradingsymbol} {res.status}: {res.reason}")
            return None
        # book the ACTUAL filled qty at the ACTUAL fill price (not the snapshot ltp).
        pos = super().open_position(inst, direction,
                                    replace(q, ltp=avg, lot_size=filled),
                                    reason, now, spot, params)
        pos.lot_size = q.lot_size   # qty reflects the real fill; lot_size stays the true lot
        self.s.commit()
        if filled < q.lot_size:
            log.error(f"LIVE OPEN PARTIAL {q.tradingsymbol} {filled}/{q.lot_size} "
                      f"@ {avg:.2f} (order {res.order_id})", instrument=inst.key,
                      event="LIVE_OPEN_PARTIAL")
            self._notify(f"⚠️ LIVE OPEN {q.tradingsymbol} only PARTIAL: {filled}/"
                         f"{q.lot_size} @ {avg:.2f} — managing the partial; verify on Zerodha")
        else:
            log.info(f"LIVE FILLED BUY {q.tradingsymbol} @ {avg:.2f} "
                     f"(order {res.order_id})", instrument=inst.key, event="LIVE_OPEN")
        self._place_gtt(pos, avg)   # exchange-side backstop stop on the real qty
        return pos

    def open_equity_position(self, inst, direction, price, qty, charge_segment, reason,
                             now, params=None, strategy_key=None):
        """Place a REAL intraday-equity (MIS) order and book the ACTUAL fill. Mirrors
        the options open path but direction-aware: LONG buys to open, SHORT sells to
        open (Kite MIS allows real intraday shorts). A direction-aware GTT backstops it."""
        tsym = getattr(inst, "spot_symbol", None) or inst.key
        if not self._ensure_no_inflight(tsym):
            return None
        side = "BUY" if direction == "LONG" else "SELL"
        res, filled, avg = self._execute(
            OrderRequest(tsym, exchange_for_segment(charge_segment), side, qty, "MARKET", None,
                         tag=TAG, product=product_for_segment(charge_segment)),
            intent="ENTRY", kind="equity",
            context={"inst_key": inst.key, "direction": direction, "charge_segment": charge_segment,
                     "reason": reason, "params": params, "strategy_key": strategy_key})
        self._note_order_outcome(filled)
        if filled <= 0:
            self._record_inflight(tsym, res)
            # #17: the order may still fill later (pre-open uncross / slow open). Remember
            # enough to ADOPT that fill on the reconcile sweep instead of orphaning it.
            if res.order_id and res.status in ("TIMEOUT", "ERROR"):
                self._pending_entries[tsym] = {
                    "kind": "equity",
                    "order_id": res.order_id, "inst": inst, "direction": direction,
                    "charge_segment": charge_segment, "reason": reason, "params": params,
                    "strategy_key": strategy_key}
            log.error(f"LIVE EQUITY OPEN not filled [{res.status}] {tsym} — {res.reason}",
                      instrument=inst.key, event="LIVE_EQUITY_OPEN_FAIL")
            self._notify(f"⚠️ LIVE EQUITY OPEN {tsym} {res.status}: {res.reason}")
            return None
        pos = super().open_equity_position(inst, direction, avg, filled, charge_segment,
                                           reason, now, params, strategy_key)
        if filled < qty:
            log.error(f"LIVE EQUITY OPEN PARTIAL {tsym} {filled}/{qty} @ {avg:.2f} "
                      f"(order {res.order_id})", instrument=inst.key,
                      event="LIVE_EQUITY_OPEN_PARTIAL")
            self._notify(f"⚠️ LIVE EQUITY OPEN {tsym} only PARTIAL: {filled}/{qty} @ "
                         f"{avg:.2f} — managing the partial; verify on Zerodha")
        else:
            log.info(f"LIVE FILLED {side} {tsym} {filled}@{avg:.2f} (order {res.order_id})",
                     instrument=inst.key, event="LIVE_EQUITY_OPEN")
        self._place_equity_stop(pos, avg)   # SL-M backstop (GTT is not allowed for MIS)
        return pos

    def close_equity_position(self, pos, exit_price, reason, now):
        """Flat an intraday-equity position with a REAL MIS order: a LONG sells, a
        SHORT buys to cover. Same ownership boundary + cancel-stop-then-send as options,
        but the backstop is a resting SL-M order (not a GTT — GTT isn't allowed for MIS)."""
        sym = pos.tradingsymbol
        if not self._ensure_no_inflight(sym):
            return None
        chk = can_bot_close(pos, self.provider.account_positions())
        if not chk.ok:
            log.error(f"LIVE EQUITY CLOSE BLOCKED {sym} — {chk.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_BLOCKED")
            self._notify(f"🚫 CLOSE blocked {sym}: {chk.reason}")
            return None
        if pos.gtt_trigger_id and not self._cancel_equity_stop(pos.gtt_trigger_id, sym):
            # #7/#18: couldn't cancel the resting SL-M — do NOT send a close (the SL-M
            # could fire into it → oversell/reverse) and don't orphan it. Leave the
            # position protected by its still-resting stop and flag for the owner.
            log.error(f"LIVE EQUITY CLOSE ABORTED {sym} — SL-M cancel failed; position left "
                      f"protected by its stop", instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym}: SL-M cancel failed — still protected by its "
                         f"stop; verify on Zerodha")
            return None
        # H4 — the SL-M stop is now cancelled; persist that before the close order so a
        # crash mid-close can't leave a dead trigger id that self-heal trusts.
        if pos.gtt_trigger_id:
            pos.gtt_trigger_id = None
            self.s.commit()
        chk2 = can_bot_close(pos, self.provider.account_positions())
        if not chk2.ok:
            log.error(f"LIVE EQUITY CLOSE ABORTED {sym} — {chk2.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym}: {chk2.reason}")
            self._place_equity_stop(pos, pos.last_premium or pos.entry_premium)
            return None
        side = "SELL" if pos.direction == "LONG" else "BUY"   # buy to cover a short
        res, filled, avg = self._execute(
            OrderRequest(sym, exchange_for_segment(pos.exchange), side, pos.qty, "MARKET", None,
                         tag=TAG, product=product_for_segment(pos.exchange)),
            intent="EXIT", kind="equity",
            context={"inst_key": pos.instrument_key, "position_id": pos.id, "segment": pos.segment})
        self._note_order_outcome(filled)
        if filled <= 0:
            self._record_inflight(sym, res)
            log.error(f"LIVE EQUITY CLOSE not filled [{res.status}] {sym} — {res.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_FAIL")
            self._notify(f"⚠️ LIVE EQUITY CLOSE {sym} {res.status}: {res.reason}")
            self._place_equity_stop(pos, pos.last_premium or pos.entry_premium)
            return None
        if filled < pos.qty:
            # H16: book the sold slice and re-protect the REMAINDER, instead of leaving a
            # stopless position + a full-qty phantom for the reconciler to mis-book.
            # If the close order may still be working (timeout-partial), it must be
            # cancel-confirmed first — a fresh SL-M alongside a live close order could
            # both execute → oversell into the owner's account.
            if "timeout" in (res.reason or ""):
                try:
                    self.client.cancel(res.order_id)
                except Exception as e:
                    # couldn't cancel a possibly-live order — re-query: a raced full fill
                    # means the whole position closed; otherwise the working order still
                    # owns the exit (don't book, don't re-stop).
                    st = {}
                    try:
                        st = self.client.status(res.order_id)
                    except Exception:
                        pass
                    if int(st.get("filled_qty", 0) or 0) >= pos.qty:
                        return super().close_equity_position(
                            pos, float(st.get("avg_price", avg) or avg), reason, now)
                    log.error(f"LIVE EQUITY CLOSE PARTIAL {sym} {filled}/{pos.qty} — cancel "
                              f"failed ({e}); working order still owns the exit",
                              instrument=pos.instrument_key, event="LIVE_CLOSE_PARTIAL")
                    self._notify(f"⚠️ LIVE EQUITY CLOSE {sym} PARTIAL {filled}/{pos.qty} — "
                                 f"a working order still owns the rest; verify on Zerodha")
                    self._inflight[sym] = res.order_id
                    return None
                # cancel succeeded — re-query for the final fill (a lot can land between
                # the poll giving up and the cancel landing).
                try:
                    st = self.client.status(res.order_id)
                    filled = int(st.get("filled_qty", filled) or filled)
                    avg = float(st.get("avg_price", avg) or avg)
                except Exception:
                    pass
                if filled >= pos.qty:
                    return super().close_equity_position(pos, avg, reason, now)
            log.error(f"LIVE EQUITY CLOSE PARTIAL {sym} {filled}/{pos.qty} @ {avg:.2f} "
                      f"(order {res.order_id}) — booking the slice, re-protecting the rest",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_PARTIAL")
            self._notify(f"⚠️ LIVE EQUITY CLOSE {sym} PARTIAL {filled}/{pos.qty} @ {avg:.2f} "
                         f"— booked the sold lots; {pos.qty - filled} still open & re-stopped")
            self.book_partial_close_equity(pos, filled, avg, reason, now)   # shrinks pos.qty
            self._place_equity_stop(pos, avg)   # SL-M for the (now smaller) remainder
            return None
        log.info(f"LIVE FILLED {side} {sym} {filled}@{avg:.2f} (order {res.order_id})",
                 instrument=pos.instrument_key, event="LIVE_CLOSE")
        return super().close_equity_position(pos, avg, reason, now)

    def close_position(self, pos, exit_premium, reason, now, spot):
        sym = pos.tradingsymbol
        # never two working bot orders on one contract — resolve any prior in-flight
        # SELL for this symbol first (cancel a stuck one; abort if one already filled,
        # which means it likely already closed and a second SELL would oversell).
        if not self._ensure_no_inflight(sym):
            return None
        # OWNERSHIP GUARD — never act on a position the live account doesn't back.
        chk = can_bot_close(pos, self.provider.account_positions())
        if not chk.ok:
            log.error(f"LIVE CLOSE BLOCKED {sym} — {chk.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_BLOCKED")
            self._notify(f"🚫 CLOSE blocked {sym}: {chk.reason}")
            return None
        # L6 — cancel the exchange GTT BEFORE the closing SELL (cancel-then-sell), so
        # a premium gap-down can't fire the server-side stop into the same window as
        # our market SELL (both execute → oversell into the owner's account).
        gid = pos.gtt_trigger_id
        if gid and not self._cancel_gtt(gid, sym):
            # #7: couldn't cancel the exchange GTT — do NOT send the SELL (the live GTT
            # could fire into it → oversell) and don't orphan it. Leave the position
            # protected by its still-resting GTT and flag for the owner.
            log.error(f"LIVE CLOSE ABORTED {sym} — GTT {gid} cancel failed; position left "
                      f"protected by its GTT", instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym}: GTT cancel failed — still protected by its "
                         f"GTT; verify on Zerodha")
            return None
        # H4 — the GTT is now cancelled at the exchange. Persist that immediately: if the
        # process dies during the SELL poll below, the DB must not keep a dead trigger id
        # (ensure_stop_protection would trust it and never re-place a stop, and the next
        # close would re-cancel a dead GTT and abort forever). Every path from here either
        # re-places a fresh GTT (abort/partial/fail) or deletes the row (full fill).
        if gid:
            pos.gtt_trigger_id = None
            self.s.commit()
        # Re-check the account immediately before sending. If the GTT already fired
        # (or the owner exited) the account no longer backs us — send NO order and
        # leave the now-orphaned position for reconcile_orphans to book.
        chk2 = can_bot_close(pos, self.provider.account_positions())
        if not chk2.ok:
            log.error(f"LIVE CLOSE ABORTED {sym} — {chk2.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_ABORT")
            self._notify(f"🚫 CLOSE aborted {sym} (backstop may have fired): {chk2.reason}")
            # we already cancelled the GTT — if this was a transient glitch the
            # position is still real, so restore its backstop rather than leave it
            # unprotected (a stray GTT on a truly-closed position is cancelled by the
            # orphan reconciler, and Kite rejects a SELL of a holding you don't have).
            self._place_gtt(pos, pos.last_premium or pos.entry_premium)
            return None
        want = pos.qty
        res, sold, avg = self._execute(
            OrderRequest(sym, pos.exchange, "SELL", want, "MARKET", None, tag=TAG),
            intent="EXIT", kind="options",
            context={"inst_key": pos.instrument_key, "position_id": pos.id, "segment": pos.segment})
        # L2 — book what ACTUALLY sold (re-querying a TIMEOUT to catch a buzzer fill),
        # never assume the full size sold.
        if sold <= 0:
            self._record_inflight(sym, res)   # may still be working — guard next tick
            log.error(f"LIVE CLOSE not filled [{res.status}] {sym} — {res.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_FAIL")
            self._notify(f"⚠️ LIVE CLOSE {sym} {res.status}: {res.reason}")
            # the SELL didn't go through but the position is still open and REAL —
            # restore the exchange backstop we cancelled so it's never unprotected.
            self._place_gtt(pos, pos.last_premium or pos.entry_premium)
            return None
        if sold < want:
            # only part sold — book that slice, keep (and re-protect) the remainder so
            # the ledger never overstates the position and the next exit can't oversell.
            log.error(f"LIVE CLOSE PARTIAL {sym} {sold}/{want} @ {avg:.2f} "
                      f"(order {res.order_id})", instrument=pos.instrument_key,
                      event="LIVE_CLOSE_PARTIAL")
            self._notify(f"⚠️ LIVE CLOSE {sym} only PARTIAL: {sold}/{want} @ {avg:.2f} "
                         f"— booked the sold lots; {want - sold} still open & protected")
            self.book_partial_close(pos, sold, avg, reason, now, spot)
            self._place_gtt(pos, pos.last_premium or pos.entry_premium)
            return None
        log.info(f"LIVE FILLED SELL {sym} @ {avg:.2f} "
                 f"(order {res.order_id})", instrument=pos.instrument_key, event="LIVE_CLOSE")
        return super().close_position(pos, avg, reason, now, spot)

    # ── GTT safety-net stop ───────────────────────────────────────────────
    def _gtt_enabled(self) -> bool:
        from app.core.runtime_config import effective
        return bool(effective(self.settings).get("gtt_stop_enabled", True))

    def _place_gtt(self, pos, last_price) -> None:
        if pos is None or not self._gtt_enabled() or pos.stop_price <= 0:
            return
        # a long position's protective stop SELLs below; an intraday-equity SHORT's
        # BUYs to cover above. Equity charge-segments map to the bare NSE/BSE exchange.
        side = "BUY" if (pos.segment == "equity_intraday" and pos.direction == "SHORT") else "SELL"
        exchange = exchange_for_segment(pos.exchange)
        try:
            tid = self.client.place_stop_gtt(pos.tradingsymbol, exchange, pos.qty,
                                             pos.stop_price, last_price, side=side)
            pos.gtt_trigger_id = tid
            self.s.commit()
            log.info(f"GTT stop placed {pos.tradingsymbol} @ {pos.stop_price:.2f} (gtt {tid})",
                     instrument=pos.instrument_key, event="GTT_PLACE")
        except Exception as e:
            log.error(f"GTT place failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_FAIL")
            self._notify(f"⚠️ GTT backstop NOT placed for {pos.tradingsymbol} — "
                         f"bot-managed stop only ({e})")

    # ── SL-M protective stop (the MIS backstop; GTT isn't allowed for MIS) ──
    def _place_equity_stop(self, pos, last_price=None) -> None:
        """Exchange-side protective stop for an intraday (MIS) position. Zerodha allows
        GTT only on CNC/NRML, never MIS — so a real SL-M order rests at the exchange
        instead: a LONG is protected by a SELL SL-M below the stop, a SHORT by a BUY SL-M
        above. The resting order id is kept in `pos.gtt_trigger_id` (the protective-stop
        id column). Governed by the same `gtt_stop_enabled` toggle as the option GTT; on
        failure the position is still managed by the bot's own risk-loop stop."""
        if pos is None or not self._gtt_enabled() or pos.stop_price <= 0:
            return
        side = "BUY" if pos.direction == "SHORT" else "SELL"   # cover a short above / sell a long below
        exchange = exchange_for_segment(pos.exchange)
        try:
            oid = self.client.place_stop_order(pos.tradingsymbol, exchange, pos.qty,
                                               pos.stop_price, side=side, tag=TAG)
            pos.gtt_trigger_id = oid
            self.s.commit()
            log.info(f"SL-M stop placed {pos.tradingsymbol} @ {pos.stop_price:.2f} (order {oid})",
                     instrument=pos.instrument_key, event="STOP_PLACE")
        except Exception as e:
            log.error(f"SL-M stop place failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="STOP_FAIL")
            self._notify(f"⚠️ SL-M stop NOT placed for {pos.tradingsymbol} — "
                         f"bot-managed stop only ({e})")

    def _cancel_equity_stop(self, oid, sym: str = "") -> bool:
        """Cancel a resting SL-M protective stop. Returns True on success (or nothing to
        cancel), False if the broker rejected it — the caller MUST NOT then send a closing
        order (the SL-M could still fire into it → oversell / a reversed position) and must
        not mark the position closed (that would orphan the resting SL-M)."""
        if not oid:
            return True
        try:
            self.client.cancel(oid)
            log.info(f"SL-M {oid} cancelled ({sym})", event="STOP_CANCEL")
            return True
        except Exception as e:
            log.error(f"SL-M {oid} cancel failed: {e}", event="STOP_FAIL")
            self._notify(f"⚠️ could not cancel SL-M {oid} for {sym} — check/cancel it on Zerodha")
            return False

    def _cancel_gtt(self, gid, sym: str = "") -> bool:
        """Cancel a resting GTT. Returns True on success (or nothing to cancel), False if
        the broker rejected the cancel — the caller MUST NOT then send a closing order (a
        still-live GTT could fire into it → oversell / a reversed position) and must not
        mark the position closed (that would orphan the GTT)."""
        if not gid:
            return True
        try:
            self.client.delete_gtt(gid)
            log.info(f"GTT {gid} cancelled ({sym})", event="GTT_DELETE")
            return True
        except Exception as e:
            log.error(f"GTT {gid} cancel failed: {e}", event="GTT_FAIL")
            self._notify(f"⚠️ could not cancel GTT {gid} for {sym} — check/cancel it on Zerodha")
            return False

    def ensure_stop_protection(self, pos, last_price) -> None:
        """Cheap per-tick check: if this open position has no resting exchange-side
        backstop (never placed, or an earlier placement attempt failed — e.g. the
        2026-07-08 LODHA tick-size rejection), place one now. A single attribute
        check once a backstop exists, so it's safe to call every risk-loop tick
        regardless of whether the stop ratcheted — a position that never ratchets
        (flat or underwater all session) still gets its missing stop retried."""
        if getattr(pos, "gtt_trigger_id", None) or not self._gtt_enabled():
            return
        lp = last_price or pos.last_premium or pos.entry_premium
        if pos.segment == "equity_intraday":
            self._place_equity_stop(pos, lp)
        else:
            self._place_gtt(pos, lp)

    def update_stop_protection(self, pos, last_price) -> None:
        if not self._gtt_enabled():
            return
        gid = getattr(pos, "gtt_trigger_id", None)
        if not gid:
            # never placed, or an earlier attempt failed — place fresh at the
            # ratcheted level instead of silently no-op'ing forever.
            self.ensure_stop_protection(pos, last_price)
            return
        lp = last_price or pos.last_premium or pos.entry_premium
        try:
            if pos.segment == "equity_intraday":
                # intraday backstop is a resting SL-M order — re-price its trigger.
                self.client.modify_stop_order(gid, pos.stop_price)
                log.info(f"SL-M {gid} trailed → {pos.stop_price:.2f} ({pos.tradingsymbol})",
                         instrument=pos.instrument_key, event="STOP_MODIFY")
            else:
                # options backstop is a GTT (long premium → protective SELL).
                self.client.modify_stop_gtt(gid, pos.tradingsymbol, exchange_for_segment(pos.exchange),
                                            pos.qty, pos.stop_price, lp, side="SELL")
                log.info(f"GTT {gid} trailed → {pos.stop_price:.2f} ({pos.tradingsymbol})",
                         instrument=pos.instrument_key, event="GTT_MODIFY")
        except Exception as e:
            log.error(f"stop modify failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_FAIL")

    def reconcile_orphans(self, now) -> list:
        """If the live account no longer backs a bot position (a GTT fired, you
        exited it, or it expired — typically while the bot was down), book it closed
        in the ledger WITHOUT sending any order, and cancel its GTT.

        L8 — booking requires the position to read orphaned on `orphan_confirm_count`
        CONSECUTIVE passes; a single >60s feed glitch that looks like an exit no longer
        phantom-closes a still-open real position. Any read where the account backs the
        position (or it is no longer open) resets the streak."""
        from app.engine.broker import PaperBroker
        from app.engine.reconcile import find_orphans
        need = int(getattr(self.settings, "orphan_confirm_count", 2) or 1)
        acct = self.provider.account_positions()
        orphans = find_orphans(self.open_positions(), acct)
        orphan_keys = {p.instrument_key for p in orphans}
        # reset the streak for anything no longer seen as orphaned (backed again, or gone)
        for k in list(self._orphan_seen):
            if k not in orphan_keys:
                del self._orphan_seen[k]
        booked = []
        for pos in orphans:
            if (now - pos.entry_time).total_seconds() < 60:
                continue  # just opened — the account feed may simply be lagging
            k = pos.instrument_key
            self._orphan_seen[k] = self._orphan_seen.get(k, 0) + 1
            if self._orphan_seen[k] < need:
                continue  # not enough consecutive confirmations yet — wait
            gid, sym = pos.gtt_trigger_id, pos.tradingsymbol
            prem = pos.last_premium or pos.entry_premium
            # book through the segment's correct close (ledger-only, no order): equity
            # is margin-based and direction-aware; routing it through the options close
            # mistakes the released notional for profit (+₹40k on ₹10k margin) and
            # mislabels the trade 'options'.
            if pos.segment == "equity_intraday":
                PaperBroker.close_equity_position(self, pos, prem,
                                                  "RECONCILED_EXTERNAL_EXIT", now)
                self._cancel_equity_stop(gid, sym)   # pull the resting SL-M backstop
            else:
                PaperBroker.close_position(self, pos, prem, "RECONCILED_EXTERNAL_EXIT",
                                           now, pos.last_spot)
                self._cancel_gtt(gid, sym)
            self._orphan_seen.pop(k, None)
            self._notify(f"ℹ️ {sym} is no longer in your account (GTT fired, manual "
                         f"exit, or expiry) — booked closed at ~{prem:.2f}; verify the "
                         f"fill on Zerodha")
            booked.append(pos.instrument_key)
        return booked

    def adopt_pending_entries(self, now) -> list:
        """Re-query each bot ENTRY order that timed out with no confirmed fill. If it has
        since FILLED and the book doesn't already track that instrument, ADOPT it: book the
        real fill and rest its SL-M stop — so a fill that landed after the poll window (a
        pre-open uncross, a slow open) becomes a managed, stopped position instead of an
        invisible, stopless orphan the engine keeps re-entering (the BSE 2026-07-03
        incident, #17). Dead orders (rejected/cancelled, no fill) are dropped; still-working
        ones are kept for the next pass."""
        adopted = []
        for sym, ctx in list(self._pending_entries.items()):
            try:
                st = self.client.status(ctx["order_id"])
            except Exception as e:
                log.error(f"ADOPT {sym}: status({ctx['order_id']}) read failed: {e}",
                          event="ADOPT_FAIL")
                continue   # transient — retry next pass
            status = str(st.get("status", "")).upper()
            filled = int(st.get("filled_qty", 0) or 0)
            avg = float(st.get("avg_price", 0.0) or 0.0)
            if filled > 0 and avg > 0:
                inst = ctx["inst"]
                if self.position_for(inst.key) is None:
                    if ctx.get("kind") == "options":
                        # C3: adopt an options late fill and rest its GTT backstop, mirroring
                        # the live open_position booking (real filled qty at the real price).
                        q = ctx["q"]
                        pos = super().open_position(
                            inst, ctx["direction"], replace(q, ltp=avg, lot_size=filled),
                            ctx["reason"], now, ctx["spot"], ctx["params"])
                        pos.lot_size = q.lot_size
                        self.s.commit()
                        self._place_gtt(pos, avg)
                    else:
                        pos = super().open_equity_position(
                            inst, ctx["direction"], avg, filled, ctx["charge_segment"],
                            ctx["reason"], now, ctx["params"], ctx["strategy_key"])
                        self._place_equity_stop(pos, avg)
                    log.warn(f"ADOPTED late fill {sym} {filled}@{avg:.2f} — was untracked; "
                             f"now managed + stopped", instrument=inst.key, event="ADOPT_FILL")
                    self._notify(f"ℹ️ {sym}: a bot order filled late ({filled}@{avg:.2f}) — "
                                 f"adopted into the book with a stop; verify on Zerodha")
                    adopted.append(inst.key)
                self.journal_mark_terminal(ctx["order_id"], "ADOPTED", filled, avg)   # H13
                self._pending_entries.pop(sym, None)
                self._inflight.pop(sym, None)
            elif status in _DEAD_STATUSES:
                self.journal_mark_terminal(ctx["order_id"], "DEAD")   # H13
                self._pending_entries.pop(sym, None)   # died with no fill — nothing to adopt
        return adopted
