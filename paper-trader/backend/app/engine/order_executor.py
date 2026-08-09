"""
Real-order lifecycle — broker-agnostic and pure.

`execute_order` places an order ONCE, then polls its status to a terminal state
and reports the ACTUAL fill (price + quantity). It talks only to an `OrderClient`
interface, so it is fully unit-tested against a fake — no exchange, no money, no
Kite. Two safety guarantees matter most for a real-money path:

  * **never double-place** — the order is placed exactly once; everything after is
    read-only polling by order id. A transient error never causes a re-send.
  * **never assume a fill** — a poll TIMEOUT returns TIMEOUT (not FILLED). The
    caller must reconcile against the broker rather than book a phantom fill.

The concrete `OrderClient` for live trading (Kite place_order + order_history) is
a thin adapter built separately and gated behind the live-execution flags.
"""
from __future__ import annotations

import math
import time as _time
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class OrderRequest:
    tradingsymbol: str
    exchange: str
    side: str                       # "BUY" | "SELL"
    qty: int
    order_type: str                 # "MARKET" | "LIMIT"
    limit_price: float | None = None
    tag: str | None = None          # idempotency / correlation tag
    product: str | None = None      # override the client's product (e.g. MIS for intraday equity); None = client default

    def __post_init__(self) -> None:
        self.order_type = str(self.order_type).upper()
        if self.order_type not in ("MARKET", "LIMIT"):
            raise ValueError(f"unsupported order_type {self.order_type!r}")
        if self.order_type == "MARKET" and self.limit_price is not None:
            raise ValueError("MARKET order cannot carry limit_price")
        if self.order_type == "LIMIT":
            if self.limit_price is None:
                raise ValueError("LIMIT entry requires a positive limit_price")
            price = float(self.limit_price)
            if not math.isfinite(price) or price <= 0:
                raise ValueError("LIMIT entry requires a positive limit_price")
            self.limit_price = price


@dataclass
class OrderResult:
    status: str                     # FILLED | PARTIAL | REJECTED | TIMEOUT | ERROR
    order_id: str | None
    filled_qty: int
    avg_price: float
    reason: str
    reconciliation_required: bool = False


class OrderClient(Protocol):
    def place(self, req: OrderRequest) -> str:
        """Submit the order, return its broker order id. Raises on submit failure."""
        ...

    def status(self, order_id: str) -> dict:
        """Return {status, filled_qty, avg_price, reason} for the order."""
        ...


def execute_order(client: OrderClient, req: OrderRequest, *,
                  poll_seconds: float = 0.5, timeout_seconds: float = 30.0,
                  sleep_fn: Callable[[float], None] | None = None,
                  on_placed: Callable[[str], None] | None = None) -> OrderResult:
    sleep = sleep_fn or _time.sleep

    # Place exactly once. A failure here means nothing reached the exchange.
    try:
        order_id = client.place(req)
    except Exception as e:
        return OrderResult("ERROR", None, 0, 0.0, f"place failed: {e}",
                           reconciliation_required=True)

    # Placement has already happened. If the acknowledgement cannot be made durable,
    # preserve the known broker id and stop: polling or retrying through a caller can
    # otherwise turn an uncertain submit into a duplicate real order.
    if on_placed is not None:
        try:
            on_placed(order_id)
        except Exception as e:
            return OrderResult(
                "ERROR", order_id, 0, 0.0,
                f"acknowledgement persistence failed: {e}",
                reconciliation_required=True,
            )

    waited = 0.0
    last: dict = {}
    st = ""
    while waited <= timeout_seconds:
        try:
            last = client.status(order_id)
        except Exception as e:
            # Placement is acknowledged, but its outcome is unknown until a later
            # read succeeds. Keep the durable blocker active for reconciliation.
            return OrderResult("ERROR", order_id, 0, 0.0,
                               f"status poll failed: {e}",
                               reconciliation_required=True)
        st = str(last.get("status", "")).upper()
        if st == "COMPLETE":
            return OrderResult("FILLED", order_id, int(last.get("filled_qty", req.qty)),
                               float(last.get("avg_price", 0.0)), "complete")
        # L9 — any REJECTED-family spelling is terminal; don't poll a dead order to timeout.
        if "REJECT" in st:
            return OrderResult("REJECTED", order_id, 0, 0.0,
                               str(last.get("reason", "rejected")) + f" [{st}]")
        if st == "CANCELLED":
            fq = int(last.get("filled_qty", 0))
            if fq > 0:
                return OrderResult("PARTIAL", order_id, fq,
                                   float(last.get("avg_price", 0.0)), "cancelled after partial")
            return OrderResult("REJECTED", order_id, 0, 0.0, "cancelled before any fill")
        # OPEN / PENDING / partially-filled-but-open / unknown -> keep polling (treating
        # an unknown status as still-working is the safe default — never assume terminal
        # and risk a double-send). The raw status is carried into the TIMEOUT reason
        # below so an unmapped terminal is reconciled, not silently dropped (L9).
        sleep(poll_seconds)
        waited += poll_seconds

    # Timed out. Report what actually filled; never assume the rest filled.
    fq = int(last.get("filled_qty", 0))
    avg = float(last.get("avg_price", 0.0))
    if req.qty > 0 and fq >= req.qty:
        return OrderResult("FILLED", order_id, fq, avg, "filled at timeout")
    if fq > 0:
        return OrderResult("PARTIAL", order_id, fq, avg, "partial fill at timeout")
    return OrderResult("TIMEOUT", order_id, 0, 0.0,
                       f"no fill before timeout (last status: {st or '?'}) — reconcile, "
                       f"do not assume filled")
