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

from dataclasses import replace

from app.core.logging import log
from app.engine.broker import PaperBroker
from app.engine.order_executor import OrderRequest, execute_order
from app.engine.reconcile import can_bot_close

TAG = "pt-bot"   # every order the bot places is tagged so it's identifiable


class LiveBroker(PaperBroker):
    MODE = "live"   # every fill this broker books is a REAL trade — tagged so the log never mixes it with paper

    def __init__(self, provider, order_client, *, poll_seconds: float = 0.5,
                 timeout_seconds: float = 30.0, notifier=None) -> None:
        super().__init__(provider)
        self.client = order_client
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.notifier = notifier

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier._emit(text)
            except Exception:
                pass

    def _execute(self, req: OrderRequest):
        return execute_order(self.client, req, poll_seconds=self.poll_seconds,
                             timeout_seconds=self.timeout_seconds)

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
        order_type = plan.action if (plan and plan.action in ("MARKET", "LIMIT")) else "MARKET"
        limit = plan.limit_price if (plan and plan.action == "LIMIT") else None
        res = self._execute(OrderRequest(q.tradingsymbol, inst.segment, "BUY",
                                         q.lot_size, order_type, limit, tag=TAG))
        # L1 — ADOPT whatever actually filled (partial fills and buzzer fills too),
        # never silently drop a real position. Only a genuine zero-fill records nothing.
        filled, avg = self._actual_fill(res)
        if filled <= 0:
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

    def close_position(self, pos, exit_premium, reason, now, spot):
        sym = pos.tradingsymbol
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
        self._cancel_gtt(gid, sym)
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
        res = self._execute(OrderRequest(sym, pos.exchange, "SELL",
                                         want, "MARKET", None, tag=TAG))
        # L2 — book what ACTUALLY sold (re-querying a TIMEOUT to catch a buzzer fill),
        # never assume the full size sold.
        sold, avg = self._actual_fill(res)
        if sold <= 0:
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
        try:
            tid = self.client.place_stop_gtt(pos.tradingsymbol, pos.exchange, pos.qty,
                                             pos.stop_price, last_price)
            pos.gtt_trigger_id = tid
            self.s.commit()
            log.info(f"GTT stop placed {pos.tradingsymbol} @ {pos.stop_price:.2f} (gtt {tid})",
                     instrument=pos.instrument_key, event="GTT_PLACE")
        except Exception as e:
            log.error(f"GTT place failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_FAIL")
            self._notify(f"⚠️ GTT backstop NOT placed for {pos.tradingsymbol} — "
                         f"bot-managed stop only ({e})")

    def _cancel_gtt(self, gid, sym: str = "") -> None:
        if not gid:
            return
        try:
            self.client.delete_gtt(gid)
            log.info(f"GTT {gid} cancelled ({sym})", event="GTT_DELETE")
        except Exception as e:
            log.error(f"GTT {gid} cancel failed: {e}", event="GTT_FAIL")
            self._notify(f"⚠️ could not cancel GTT {gid} for {sym} — check/cancel it on Zerodha")

    def update_stop_protection(self, pos, last_price) -> None:
        gid = getattr(pos, "gtt_trigger_id", None)
        if not gid or not self._gtt_enabled():
            return
        lp = last_price or pos.last_premium or pos.entry_premium
        try:
            self.client.modify_stop_gtt(gid, pos.tradingsymbol, pos.exchange, pos.qty,
                                        pos.stop_price, lp)
            log.info(f"GTT {gid} trailed → {pos.stop_price:.2f} ({pos.tradingsymbol})",
                     instrument=pos.instrument_key, event="GTT_MODIFY")
        except Exception as e:
            log.error(f"GTT modify failed {pos.tradingsymbol}: {e}",
                      instrument=pos.instrument_key, event="GTT_FAIL")

    def reconcile_orphans(self, now) -> list:
        """If the live account no longer backs a bot position (a GTT fired, you
        exited it, or it expired — typically while the bot was down), book it closed
        in the ledger WITHOUT sending any order, and cancel its GTT."""
        from app.engine.broker import PaperBroker
        from app.engine.reconcile import find_orphans
        acct = self.provider.account_positions()
        booked = []
        for pos in find_orphans(self.open_positions(), acct):
            if (now - pos.entry_time).total_seconds() < 60:
                continue  # just opened — the account feed may simply be lagging
            gid, sym = pos.gtt_trigger_id, pos.tradingsymbol
            prem = pos.last_premium or pos.entry_premium
            PaperBroker.close_position(self, pos, prem, "RECONCILED_EXTERNAL_EXIT",
                                       now, pos.last_spot)   # ledger-only, no order
            self._cancel_gtt(gid, sym)
            self._notify(f"ℹ️ {sym} is no longer in your account (GTT fired, manual "
                         f"exit, or expiry) — booked closed at ~{prem:.2f}; verify the "
                         f"fill on Zerodha")
            booked.append(pos.instrument_key)
        return booked
