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

from app.engine.gtt import round_to_tick, stop_gtt_params
from app.engine.order_executor import OrderRequest

# Charge-segments that trade as intraday equity (MIS): same-day, leveraged, the
# broker auto-squares-off near close. Everything else (options/futures) is NRML.
EQUITY_INTRADAY_SEGMENTS = frozenset({"NSE_INTRADAY", "BSE_INTRADAY"})


def product_for_segment(segment: str, default: str = "NRML") -> str:
    """Kite product code for a charge-segment: MIS for intraday equity, else the
    client default (NRML for options/futures so they can carry overnight)."""
    return "MIS" if segment in EQUITY_INTRADAY_SEGMENTS else default


def exchange_for_segment(segment: str) -> str:
    """Real Kite exchange for a charge-segment. Intraday-equity charge-segments carry
    an _INTRADAY suffix for the charge schedule; the exchange Kite wants is the bare
    NSE/BSE. Options/futures segments (NFO/BFO/MCX/NCDEX) are already Kite exchanges."""
    if segment == "NSE_INTRADAY":
        return "NSE"
    if segment == "BSE_INTRADAY":
        return "BSE"
    return segment


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
                       trigger_price: float, last_price: float, side: str = "SELL") -> str:
        # Zerodha accepts GTTs only for CNC/NRML — an equity-exchange (MIS) GTT is
        # rejected server-side, silently leaving the position stopless (the
        # 2026-07-03 class of failure: option GTTs worked, intraday ones never
        # existed). Refuse locally and loudly; the MIS backstop is place_stop_order.
        if exchange in ("NSE", "BSE"):
            raise ValueError(f"GTT not supported on equity exchange {exchange} "
                             f"(intraday/MIS) — use place_stop_order (SL-M) instead")
        self._sync_token()
        res = self.kite.place_gtt(**stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product, side))
        tid = res.get("trigger_id") if isinstance(res, dict) else res
        return str(tid)

    def modify_stop_gtt(self, trigger_id: str, tradingsymbol: str, exchange: str,
                        qty: int, trigger_price: float, last_price: float, side: str = "SELL"):
        if exchange in ("NSE", "BSE"):
            raise ValueError(f"GTT not supported on equity exchange {exchange} "
                             f"(intraday/MIS) — use modify_stop_order (SL-M) instead")
        self._sync_token()
        return self.kite.modify_gtt(trigger_id=trigger_id, **stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product, side))

    def delete_gtt(self, trigger_id: str):
        self._sync_token()
        return self.kite.delete_gtt(trigger_id=trigger_id)

    # ── SL-M protective stop (a real resting order — the MIS backstop) ────
    def place_stop_order(self, tradingsymbol: str, exchange: str, qty: int,
                         trigger_price: float, side: str = "SELL",
                         tag: str | None = None) -> str:
        """Rest a Stop-Loss-Market order at the exchange as the protective stop for an
        intraday (MIS) position — GTT can't be used for MIS (Zerodha allows GTT only on
        CNC/NRML). It triggers a MARKET order when the LTP crosses `trigger_price`: a
        LONG is protected by a SELL below entry, a SHORT by a BUY (cover) above. Returns
        the broker order id."""
        self._sync_token()
        product = "MIS" if exchange in ("NSE", "BSE") else self.product
        kw = dict(variety=self.variety, exchange=exchange, tradingsymbol=tradingsymbol,
                  transaction_type=side, quantity=int(qty), product=product,
                  order_type="SL-M", trigger_price=round_to_tick(trigger_price),
                  # SL-M fires a MARKET order → same SEBI 1-Apr-2026 protection as MARKET.
                  market_protection=self.market_protection or -1.0)
        if tag:
            kw["tag"] = tag
        return str(self.kite.place_order(**kw))

    def modify_stop_order(self, order_id: str, trigger_price: float):
        """Re-price a resting SL-M stop's trigger (trailing the stop as it ratchets)."""
        self._sync_token()
        return self.kite.modify_order(variety=self.variety, order_id=order_id,
                                      trigger_price=round_to_tick(trigger_price))

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
