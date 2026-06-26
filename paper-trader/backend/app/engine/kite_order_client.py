"""
OrderClient adapter over a LiveExecutionKite — the bridge between our
broker-agnostic order_executor and Kite's order API.

  place(req)  -> kite.place_order(...) -> order id
  status(id)  -> last kite.order_history(id) row, normalised

variety="regular", product="NRML" so options can be carried overnight (the engine
supports overnight holding). The owner's discretionary positions are never touched
by this client — it only ever places the specific orders the LiveBroker hands it.
"""
from __future__ import annotations

from app.engine.gtt import stop_gtt_params
from app.engine.order_executor import OrderRequest

# Charge-segments that trade as intraday equity (MIS): same-day, leveraged, the
# broker auto-squares-off near close. Everything else (options/futures) is NRML.
EQUITY_INTRADAY_SEGMENTS = frozenset({"NSE_INTRADAY", "BSE_INTRADAY"})


def product_for_segment(segment: str, default: str = "NRML") -> str:
    """Kite product code for a charge-segment: MIS for intraday equity, else the
    client default (NRML for options/futures so they can carry overnight)."""
    return "MIS" if segment in EQUITY_INTRADAY_SEGMENTS else default


class KiteOrderClient:
    def __init__(self, kite, *, token_source=None,
                 product: str = "NRML", variety: str = "regular",
                 market_protection: float = -1.0) -> None:
        self.kite = kite
        self.product = product
        self.variety = variety
        # Market protection for MARKET/SL-M orders. Mandatory since SEBI's 1-Apr-2026
        # rule: a market order placed via API WITHOUT non-zero protection is REJECTED
        # (all segments, MCX included). -1 = automatic exchange-guideline protection;
        # >0..100 = an explicit cap %. A 0 means "unprotected" and would be rejected,
        # so it is coerced to -1 at send time — we never send an unprotected market order.
        self.market_protection = market_protection
        # callable returning the data provider's CURRENT access token. Synced before
        # every Kite call so a daily re-login (which refreshes the provider token)
        # flows through to order placement without rebuilding the broker.
        self._token_source = token_source
        self._last_token: str | None = None

    def _sync_token(self) -> None:
        """Adopt the provider's current access token if it changed (post re-login)."""
        if not self._token_source:
            return
        tok = self._token_source()
        if tok and tok != self._last_token:
            self.kite.set_access_token(tok)
            self._last_token = tok

    # ── GTT safety-net stop (lives on Zerodha's servers) ──────────────────
    def place_stop_gtt(self, tradingsymbol: str, exchange: str, qty: int,
                       trigger_price: float, last_price: float) -> str:
        self._sync_token()
        res = self.kite.place_gtt(**stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product))
        tid = res.get("trigger_id") if isinstance(res, dict) else res
        return str(tid)

    def modify_stop_gtt(self, trigger_id: str, tradingsymbol: str, exchange: str,
                        qty: int, trigger_price: float, last_price: float):
        self._sync_token()
        return self.kite.modify_gtt(trigger_id=trigger_id, **stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product))

    def delete_gtt(self, trigger_id: str):
        self._sync_token()
        return self.kite.delete_gtt(trigger_id=trigger_id)

    def place(self, req: OrderRequest) -> str:
        self._sync_token()
        # req.product overrides the client default (MIS for intraday equity); the
        # options/futures path passes None and keeps the client's NRML.
        product = req.product or self.product
        kw = dict(variety=self.variety, exchange=req.exchange,
                  tradingsymbol=req.tradingsymbol, transaction_type=req.side,
                  quantity=req.qty, product=product, order_type=req.order_type)
        if req.order_type == "LIMIT" and req.limit_price is not None:
            kw["price"] = req.limit_price
        if req.order_type == "MARKET":
            # never unprotected: a 0/falsy value would be rejected -> fall back to -1 (auto)
            kw["market_protection"] = self.market_protection or -1.0
        if req.tag:
            kw["tag"] = req.tag
        return self.kite.place_order(**kw)

    def cancel(self, order_id: str):
        """Cancel a working order (same variety it was placed with). Used to kill a
        timed-out-but-still-working order before placing another on the same contract,
        so a contract never has two live bot orders at once."""
        self._sync_token()
        return self.kite.cancel_order(variety=self.variety, order_id=order_id)

    def status(self, order_id: str) -> dict:
        self._sync_token()
        hist = self.kite.order_history(order_id) or []
        last = hist[-1] if hist else {}
        return {
            "status": last.get("status"),
            "filled_qty": int(last.get("filled_quantity", 0) or 0),
            "avg_price": float(last.get("average_price", 0.0) or 0.0),
            "reason": last.get("status_message") or "",
        }
