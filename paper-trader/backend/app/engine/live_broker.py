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
        return pos

    def close_position(self, pos, exit_premium, reason, now, spot):
        # OWNERSHIP GUARD — never act on a position the live account doesn't back.
        chk = can_bot_close(pos, self.provider.account_positions())
        if not chk.ok:
            log.error(f"LIVE CLOSE BLOCKED {pos.tradingsymbol} — {chk.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_BLOCKED")
            self._notify(f"🚫 CLOSE blocked {pos.tradingsymbol}: {chk.reason}")
            return None
        res = self._execute(OrderRequest(pos.tradingsymbol, pos.exchange, "SELL",
                                         pos.qty, "MARKET", None, tag=TAG))
        if res.status != "FILLED":
            log.error(f"LIVE CLOSE not filled [{res.status}] {pos.tradingsymbol} — {res.reason}",
                      instrument=pos.instrument_key, event="LIVE_CLOSE_FAIL")
            self._notify(f"⚠️ LIVE CLOSE {pos.tradingsymbol} {res.status}: {res.reason}")
            return None
        log.info(f"LIVE FILLED SELL {pos.tradingsymbol} @ {res.avg_price:.2f} "
                 f"(order {res.order_id})", instrument=pos.instrument_key, event="LIVE_CLOSE")
        return super().close_position(pos, res.avg_price, reason, now, spot)
