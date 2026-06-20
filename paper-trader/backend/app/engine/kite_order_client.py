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


class KiteOrderClient:
    def __init__(self, kite, product: str = "NRML", variety: str = "regular") -> None:
        self.kite = kite
        self.product = product
        self.variety = variety

    # ── GTT safety-net stop (lives on Zerodha's servers) ──────────────────
    def place_stop_gtt(self, tradingsymbol: str, exchange: str, qty: int,
                       trigger_price: float, last_price: float) -> str:
        res = self.kite.place_gtt(**stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product))
        tid = res.get("trigger_id") if isinstance(res, dict) else res
        return str(tid)

    def modify_stop_gtt(self, trigger_id: str, tradingsymbol: str, exchange: str,
                        qty: int, trigger_price: float, last_price: float):
        return self.kite.modify_gtt(trigger_id=trigger_id, **stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product))

    def delete_gtt(self, trigger_id: str):
        return self.kite.delete_gtt(trigger_id=trigger_id)

    def place(self, req: OrderRequest) -> str:
        kw = dict(variety=self.variety, exchange=req.exchange,
                  tradingsymbol=req.tradingsymbol, transaction_type=req.side,
                  quantity=req.qty, product=self.product, order_type=req.order_type)
        if req.order_type == "LIMIT" and req.limit_price is not None:
            kw["price"] = req.limit_price
        if req.tag:
            kw["tag"] = req.tag
        return self.kite.place_order(**kw)

    def status(self, order_id: str) -> dict:
        hist = self.kite.order_history(order_id) or []
        last = hist[-1] if hist else {}
        return {
            "status": last.get("status"),
            "filled_qty": int(last.get("filled_quantity", 0) or 0),
            "avg_price": float(last.get("average_price", 0.0) or 0.0),
            "reason": last.get("status_message") or "",
        }
