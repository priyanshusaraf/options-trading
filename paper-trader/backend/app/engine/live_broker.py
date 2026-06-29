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

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier._emit(text)
            except Exception as e:
                # L11 — a money-critical alert that fails to send must never vanish
                # silently; at least record it (with the dropped text) so it's visible
                # in the Engine/Logs console even when Telegram is down.
                log.error(f"ALERT NOT DELIVERED ({e}): {text}", event="NOTIFY_FAIL")

    def _execute(self, req: OrderRequest):
        return execute_order(self.client, req, poll_seconds=self.poll_seconds,
                             timeout_seconds=self.timeout_seconds)

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
        res = self._execute(OrderRequest(q.tradingsymbol, inst.segment, "BUY",
                                         q.lot_size, order_type, limit, tag=TAG))
        # L1 — ADOPT whatever actually filled (partial fills and buzzer fills too),
        # never silently drop a real position. Only a genuine zero-fill records nothing.
        filled, avg = self._actual_fill(res)
        if filled <= 0:
            self._record_inflight(q.tradingsymbol, res)   # may still be working — guard next tick
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
        """Real intraday-equity (MIS) order routing is NOT implemented on the live
        broker — only options route to Kite. Refuse rather than silently paper-book
        the position as a REAL trade (which never reaches the account, can't be closed
        by the ownership-guarded path, and pollutes the ledger as a phantom 'live'
        fill). Run equity in paper mode until live MIS routing exists."""
        log.error(f"LIVE equity entry refused {inst.key} {direction} {qty}@{price:.2f} — "
                  f"real MIS order routing is not implemented (options only). No order placed.",
                  instrument=inst.key, event="LIVE_EQUITY_UNSUPPORTED")
        self._notify(f"🚫 {inst.key}: live equity (MIS) isn't supported yet — no order "
                     f"placed. Run equity in paper mode.")
        return None

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
