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

    def open_position(self, inst, direction, q, reason, now, spot,
                      params=None, plan=None):
        order_type = plan.action if (plan and plan.action in ("MARKET", "LIMIT")) else "MARKET"
        limit = plan.limit_price if (plan and plan.action == "LIMIT") else None
        res = self._execute(OrderRequest(q.tradingsymbol, inst.segment, "BUY",
                                         q.lot_size, order_type, limit, tag=TAG))
        if res.status != "FILLED":
            log.error(f"LIVE OPEN not filled [{res.status}] {q.tradingsymbol} — {res.reason}",
                      instrument=inst.key, event="LIVE_OPEN_FAIL")
            self._notify(f"⚠️ LIVE OPEN {q.tradingsymbol} {res.status}: {res.reason}")
            return None
        # book the ACTUAL fill price (not the snapshot ltp)
        pos = super().open_position(inst, direction, replace(q, ltp=res.avg_price),
                                    reason, now, spot, params)
        log.info(f"LIVE FILLED BUY {q.tradingsymbol} @ {res.avg_price:.2f} "
                 f"(order {res.order_id})", instrument=inst.key, event="LIVE_OPEN")
        self._place_gtt(pos, res.avg_price)   # exchange-side backstop stop
        return pos

    def close_position(self, pos, exit_premium, reason, now, spot):
        # OWNERSHIP GUARD — never act on a position the live account doesn't back.
        chk = can_bot_close(pos, self.provider.account_positions())
        if not chk.ok:
            log.error(f"LIVE CLOSE BLOCKED {pos.tradingsymbol} — {chk.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_BLOCKED")
            self._notify(f"🚫 CLOSE blocked {pos.tradingsymbol}: {chk.reason}")
            return None
        gid = pos.gtt_trigger_id   # capture before super() deletes the row
        res = self._execute(OrderRequest(pos.tradingsymbol, pos.exchange, "SELL",
                                         pos.qty, "MARKET", None, tag=TAG))
        if res.status != "FILLED":
            log.error(f"LIVE CLOSE not filled [{res.status}] {pos.tradingsymbol} — {res.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_FAIL")
            self._notify(f"⚠️ LIVE CLOSE {pos.tradingsymbol} {res.status}: {res.reason}")
            return None
        log.info(f"LIVE FILLED SELL {pos.tradingsymbol} @ {res.avg_price:.2f} "
                 f"(order {res.order_id})", instrument=pos.instrument_key, event="LIVE_CLOSE")
        sym = pos.tradingsymbol
        trade = super().close_position(pos, res.avg_price, reason, now, spot)
        # the bot exited itself — cancel the backstop so it can NEVER fire on a
        # position we no longer hold (which would sell into your account).
        self._cancel_gtt(gid, sym)
        return trade

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
