"""The wire client for Dhan orders. Everything here is Dhan's vocabulary; nothing above it is.

Sibling of `kite_order_client.py`, and deliberately NOT a subclass of it: the two brokers share
no request shape, no status vocabulary and no id semantics. Inheriting would create exactly the
"second order lifecycle wearing the first one's clothes" that `.claude/rules/providers-brokers.md`
disqualifies.

Read from https://dhanhq.co/docs/v2/orders/ and .../funds/ on 2026-08-10. Facts that shape this
file, each read rather than assumed:

  * `POST /orders` · `PUT /orders/{id}` · `DELETE /orders/{id}` · `GET /orders` · `GET /orders/{id}`.
    Modify and cancel are **PUT and DELETE**, not POSTs to an action path.
  * `orderType` is one of `LIMIT` · `MARKET` · `STOP_LOSS` · `STOP_LOSS_MARKET`.
    `STOP_LOSS_MARKET` is the resting protective stop — Kite spells the same thing `SL-M`.
  * `productType` is `CNC` · `INTRADAY` · `MARGIN` · `MTF` · `CO` · `BO`. Note `INTRADAY`, not
    Kite's `MIS`, and `MARGIN`, not `NRML`.
  * Status is `TRANSIT` · `PENDING` · `REJECTED` · `CANCELLED` · `PART_TRADED` · `TRADED` ·
    `EXPIRED`. **`TRADED` is the terminal fill, not `COMPLETE`** — a status map copied from Kite
    would read every filled Dhan order as still working, and the poll would time out on a fill
    that already happened.
  * `correlationId` (max 30 chars) is the tag equivalent. Our durable intent tag is 20, so it
    fits — which is what keeps execution attribution working across brokers.
  * Fills come back on the order itself as `filledQty` / `averageTradedPrice`. There is **no
    documented trade-book endpoint**, so `find_fill` reads the order book rather than a trades
    feed. That is a real difference from Kite and is stated rather than hidden.

The transport must provide `post`/`get`/`put`/`delete`. `DhanTransport` currently implements
`post` only; the rest arrive with the wiring slice. Until then this class is exercised against a
fake transport, so it is a checked translation table rather than a hopeful one.
"""
from __future__ import annotations

from app.core.logging import log
from app.engine.order_executor import OrderRequest
from app.providers.base import ProviderReadError

#: Dhan order statuses that mean the order is dead — no working order remains.
DEAD_STATUSES = frozenset({"REJECTED", "CANCELLED", "EXPIRED"})

#: The terminal SUCCESS status. Deliberately named, because it is the single most likely thing
#: to be got wrong by analogy: Kite says COMPLETE, Dhan says TRADED, and reading Dhan's fill as
#: "not terminal" makes `execute_order` poll to TIMEOUT on an order that filled instantly.
FILLED_STATUS = "TRADED"

#: Partial fill. Terminal only when the order is also no longer working, which the order book
#: reports separately via `remainingQuantity`.
PARTIAL_STATUS = "PART_TRADED"


class DhanOrderRejected(ProviderReadError):
    """Dhan refused the order before it reached the exchange, with its own error code."""


class DhanOrderClient:
    """Place, modify, cancel and read Dhan orders. No decisions — translation only.

    `client_id_source` is a callable for the same reason the token is: Dhan requires
    `dhanClientId` in the *body* of every order as well as the `client-id` header, and a
    connection that re-authenticates must not need a restart to pick up either.
    """

    def __init__(self, transport, client_id_source, *, tick_source=None,
                 default_product: str = "MARGIN") -> None:
        self.transport = transport
        self._client_id_source = client_id_source
        # (tradingsymbol, exchange) -> float | None. Every trigger and limit price sent to Dhan
        # must land on THIS grid. The 2026-07-15 incident was 2,437 SL-M placements rejected
        # for assuming 0.05. Dhan publishes the real value as SEM_TICK_SIZE in its scrip master.
        self._tick_source = tick_source
        self.product = default_product

    # ── identity ──────────────────────────────────────────────────────────
    def _client_id(self) -> str:
        cid = (self._client_id_source() if callable(self._client_id_source)
               else self._client_id_source)
        if not cid:
            raise ProviderReadError("dhan: no client id on this connection")
        return str(cid)

    def tick_size(self, tradingsymbol: str, exchange: str | None = None) -> float:
        """The instrument's real price grid, or 0.05 when this connection cannot say.

        The fallback is the same one `KiteOrderClient` uses and it is a known compromise, not a
        good answer: it is correct for most NSE equity and wrong for LT (0.10) and MARUTI (1.00).
        A venue that cannot read ticks must not declare execution — `tests/provider_conformance.py`
        holds an executing connection to answering a real non-default tick.
        """
        if not tradingsymbol or self._tick_source is None:
            return 0.05
        try:
            tick = self._tick_source(tradingsymbol, exchange)
        except Exception as e:                     # noqa: BLE001
            log.warn(f"dhan tick lookup failed {tradingsymbol}: {e}", event="TICK_LOOKUP_FAIL")
            return 0.05
        return float(tick) if tick else 0.05

    def round_to_tick(self, price: float, tradingsymbol: str, exchange: str | None = None):
        tick = self.tick_size(tradingsymbol, exchange)
        if tick <= 0:
            return price
        return round(round(float(price) / tick) * tick, 4)

    # ── plain orders ──────────────────────────────────────────────────────
    def _body(self, req: OrderRequest, *, order_type: str, price: float = 0.0,
              trigger: float | None = None, product: str | None = None) -> dict:
        body = {
            "dhanClientId": self._client_id(),
            "transactionType": str(req.side).upper(),
            "exchangeSegment": req.exchange,
            "productType": product or req.product or self.product,
            "orderType": order_type,
            "validity": "DAY",
            "securityId": req.tradingsymbol,
            "quantity": int(req.qty),
            "price": float(price or 0.0),
        }
        if trigger is not None:
            body["triggerPrice"] = float(trigger)
        if req.tag:
            # 30-char limit, documented. Truncating silently would break attribution, so the
            # length is asserted rather than trimmed — our tags are 20 and must stay under it.
            tag = str(req.tag)
            if len(tag) > 30:
                raise DhanOrderRejected(
                    f"correlationId {tag!r} is {len(tag)} chars; dhan allows 30. Refusing rather "
                    f"than truncating — a truncated tag is an order nobody can attribute.")
            body["correlationId"] = tag
        return body

    def place(self, req: OrderRequest) -> str:
        """Submit once, return Dhan's order id. Never retries: a duplicate real order is worse
        than a missed one."""
        price = 0.0
        if req.order_type == "LIMIT":
            if not req.limit_price:
                raise DhanOrderRejected("LIMIT order with no limit price")
            price = self.round_to_tick(req.limit_price, req.tradingsymbol, req.exchange)
        resp = self.transport.post("/orders", self._body(
            req, order_type=req.order_type, price=price), allow_list=True)
        return _order_id(resp, "/orders")

    def place_stop_order(self, tradingsymbol: str, exchange: str, qty: int,
                         trigger_price: float, side: str = "SELL",
                         tag: str | None = None, product: str | None = None) -> str:
        """A resting protective stop — Dhan's `STOP_LOSS_MARKET`.

        The trigger is snapped to the instrument's real tick before submission. An unsnapped
        trigger is rejected by the exchange, and a rejected protective stop means an open
        position with no exchange-side backstop.
        """
        trigger = self.round_to_tick(trigger_price, tradingsymbol, exchange)
        req = OrderRequest(tradingsymbol, exchange, side, qty, "MARKET", None, tag=tag,
                           product=product)
        resp = self.transport.post("/orders", self._body(
            req, order_type="STOP_LOSS_MARKET", price=0.0, trigger=trigger, product=product),
            allow_list=True)
        return _order_id(resp, "/orders")

    def modify_stop_order(self, order_id: str, trigger_price: float,
                          tradingsymbol: str | None = None, exchange: str | None = None,
                          quantity: int | None = None):
        """Re-price a resting stop. `PUT /orders/{id}`, not a POST."""
        trigger = self.round_to_tick(trigger_price, tradingsymbol or "", exchange)
        body = {
            "dhanClientId": self._client_id(),
            "orderId": str(order_id),
            "orderType": "STOP_LOSS_MARKET",
            "triggerPrice": float(trigger),
            "validity": "DAY",
        }
        if quantity is not None:
            body["quantity"] = int(quantity)
        return self.transport.put(f"/orders/{order_id}", body)

    def cancel(self, order_id: str):
        """`DELETE /orders/{id}`. Raises if Dhan refused — a refused cancel means the old order
        may still fire, and the caller must not then send a second one."""
        return self.transport.delete(f"/orders/{order_id}")

    def status(self, order_id: str) -> dict:
        """Normalised `{status, filled_qty, avg_price, reason}` for one order.

        `status` is returned in **Kite's vocabulary** deliberately: `order_executor` and
        `live_broker` already speak it, and translating here is what keeps one order lifecycle
        rather than two. `TRADED` becomes `COMPLETE`, `PART_TRADED` becomes `PARTIAL`.
        """
        resp = self.transport.get(f"/orders/{order_id}")
        return normalise_order(_one(resp.data))

    def orders(self) -> list[dict]:
        """Today's order book, in the shape `live_broker` reads."""
        resp = self.transport.get("/orders")
        rows = resp.data if isinstance(resp.data, list) else resp.data.get("data") or []
        return [_identity_row(r) for r in rows if isinstance(r, dict)]

    def find_fill(self, tradingsymbol: str, side: str = "SELL") -> dict | None:
        """Today's real fill for symbol/side, or None.

        Reads the ORDER BOOK, not a trade book: Dhan documents no trades endpoint, and the fill
        quantity and average price are carried on the order itself. Returns `None` for "no fill
        found", never for "could not look" — a read failure raises.
        """
        for row in self.orders():
            if (row.get("tradingsymbol") == tradingsymbol
                    and str(row.get("transaction_type") or "").upper() == str(side).upper()
                    and int(row.get("filled_qty") or 0) > 0):
                return {"avg_price": float(row.get("avg_price") or 0.0),
                        "filled_qty": int(row.get("filled_qty") or 0)}
        return None

    # ── account ───────────────────────────────────────────────────────────
    def funds(self) -> dict:
        """`GET /fundlimit`. Note `availabelBalance` — Dhan's own spelling, reproduced exactly
        because correcting it to `availableBalance` reads nothing and returns zero deployable
        cash, which sizing then fails closed on for the wrong reason."""
        resp = self.transport.get("/fundlimit")
        return dict(_one(resp.data))

    def margin_probe(self, req: OrderRequest) -> float:
        """Margin Dhan would actually block. `0.0` when unanswerable — sizing fails CLOSED to
        zero deployable cash rather than falling back to an assumed leverage figure."""
        try:
            resp = self.transport.post("/margincalculator", {
                "dhanClientId": self._client_id(),
                "exchangeSegment": req.exchange,
                "transactionType": str(req.side).upper(),
                "quantity": int(req.qty),
                "productType": req.product or self.product,
                "securityId": req.tradingsymbol,
                "price": float(req.limit_price or 0.0),
                "triggerPrice": 0.0,
            })
        except Exception as e:                     # noqa: BLE001
            log.warn(f"dhan margin probe failed: {e}", event="MARGIN_PROBE_FAIL")
            return 0.0
        return float((_one(resp.data) or {}).get("totalMargin", 0.0) or 0.0)


# ── normalisation ─────────────────────────────────────────────────────────

def _one(data):
    """Dhan returns some reads as a single-element list and others as an object."""
    if isinstance(data, list):
        return data[0] if data else {}
    return data if isinstance(data, dict) else {}


def _order_id(resp, endpoint: str) -> str:
    row = _one(resp.data)
    oid = row.get("orderId")
    if not oid:
        raise DhanOrderRejected(
            f"dhan {endpoint}: no orderId in the response "
            f"({row.get('omsErrorCode')}: {row.get('omsErrorDescription')})")
    status = str(row.get("orderStatus") or "").upper()
    if status in DEAD_STATUSES:
        # Dhan can answer 200 with a REJECTED order. Treating that as a successful placement
        # would leave the caller polling an order that will never work, and — worse — believing
        # a protective stop is resting when none is.
        raise DhanOrderRejected(
            f"dhan {endpoint}: order {oid} came back {status} "
            f"({row.get('omsErrorCode')}: {row.get('omsErrorDescription')})")
    return str(oid)


def normalise_order(row: dict) -> dict:
    """One Dhan order → the `{status, filled_qty, avg_price, reason}` shape this engine reads.

    The status translation is the load-bearing line. `TRADED` → `COMPLETE`; a map copied from
    Kite would leave every filled Dhan order looking like it was still working.
    """
    raw = str(row.get("orderStatus") or "").upper()
    if raw == FILLED_STATUS:
        status = "COMPLETE"
    elif raw == PARTIAL_STATUS:
        status = "PARTIAL"
    elif raw in DEAD_STATUSES:
        status = "REJECTED" if raw == "REJECTED" else "CANCELLED"
    else:
        status = raw or ""
    return {
        "status": status,
        "filled_qty": int(row.get("filledQty") or 0),
        "avg_price": float(row.get("averageTradedPrice") or 0.0),
        "reason": str(row.get("omsErrorDescription") or ""),
    }


def _identity_row(row: dict) -> dict:
    """One order-book row, in the field names `live_broker` reads."""
    normalised = normalise_order(row)
    return {
        "order_id": str(row.get("orderId")) if row.get("orderId") else None,
        "tradingsymbol": row.get("tradingSymbol") or row.get("securityId"),
        "tag": row.get("correlationId"),
        "status": normalised["status"],
        "filled_qty": normalised["filled_qty"],
        "avg_price": normalised["avg_price"],
        "transaction_type": row.get("transactionType"),
        "exchange": row.get("exchangeSegment"),
        "quantity": int(row.get("quantity") or 0),
        "trigger_price": float(row.get("triggerPrice") or 0.0),
    }
