"""
Kite's dialect — the ONLY place neutral vocabulary becomes MIS/NRML/GTT/SL-M.

Two things live here:

  * the pure translation functions (`kite_product`, `kite_exchange`), which
    `kite_order_client.product_for_segment` / `exchange_for_segment` now delegate
    to so there is exactly one implementation of each mapping; and
  * `KiteVenue`, an `ExecutionVenue` adapter over a `KiteOrderClient`.

`KiteVenue` is deliberately NOT wired into the live path yet. Phase F's job was to
declare the boundary and prove nothing crosses it silently; re-routing the
real-money broker through a new object is a separate, separately-verified change.
It is exercised by `tests/test_venue_boundary.py` against a fake Kite client, so
it is a checked translation table rather than a hopeful one — but read it as the
target shape, not as the shape in production. See /tmp/phaseF_needs.md.
"""
from __future__ import annotations

from app.engine.broker_protocol import ProtectiveStopKind, Tenor
from app.engine.order_executor import OrderRequest
from app.engine.venue import tenor_for_charge_segment

# ── vocabulary translation ────────────────────────────────────────────────

#: Kite product codes, by neutral tenor. NRML rather than CNC for CARRY because
#: the carried instruments here are options/futures, which have no CNC.
_KITE_PRODUCT = {Tenor.INTRADAY: "MIS", Tenor.CARRY: "NRML"}

#: Charge-segments carry an _INTRADAY suffix for the charge schedule; the exchange
#: Kite actually wants is the bare one. Every other charge-segment (NFO/BFO/MCX/
#: NCDEX) is already a Kite exchange and passes through.
_KITE_EXCHANGE = {"NSE_INTRADAY": "NSE", "BSE_INTRADAY": "BSE"}


def kite_product(tenor: Tenor, default: str = "NRML") -> str:
    """Kite product code for a neutral tenor. CARRY resolves to the caller's
    default so a client configured with a non-NRML carry product keeps it."""
    return "MIS" if tenor is Tenor.INTRADAY else default


def kite_exchange(charge_segment: str) -> str:
    """Kite exchange for a charge-segment."""
    return _KITE_EXCHANGE.get(charge_segment, charge_segment)


def kite_product_for_charge_segment(charge_segment: str, default: str = "NRML") -> str:
    """Convenience composition: charge-segment -> neutral tenor -> Kite product."""
    return kite_product(tenor_for_charge_segment(charge_segment), default)


# ── the adapter ───────────────────────────────────────────────────────────


class KiteVenue:
    """`ExecutionVenue` over a `KiteOrderClient`.

    Every method is a translation, never a decision: the broker decides *that* a
    RESTING_STOP is needed, this decides that Kite spells one `SL-M`.
    """

    def __init__(self, client) -> None:
        self.client = client

    # ── plain orders ───────────────────────────────────────────────────
    def place(self, req: OrderRequest) -> str:
        return str(self.client.place(req))

    def status(self, order_id: str) -> dict:
        return self.client.status(order_id)

    def cancel(self, order_id: str):
        return self.client.cancel(order_id)

    def orders(self) -> list[dict]:
        return self.client.orders()

    def find_fill(self, tradingsymbol: str, side: str = "SELL") -> dict | None:
        return self.client.find_fill(tradingsymbol, side=side)

    # ── protective stops ───────────────────────────────────────────────
    def place_protective_stop(self, kind: ProtectiveStopKind, *, tradingsymbol: str,
                              exchange: str, qty: int, trigger_price: float,
                              side: str = "SELL", last_price: float = 0.0,
                              tag: str | None = None) -> str:
        if kind is ProtectiveStopKind.RESTING_STOP:
            return str(self.client.place_stop_order(
                tradingsymbol, exchange, qty, trigger_price, side=side, tag=tag))
        return str(self.client.place_stop_gtt(
            tradingsymbol, exchange, qty, trigger_price, last_price, side=side))

    def modify_protective_stop(self, kind: ProtectiveStopKind, protective_id: str, *,
                               tradingsymbol: str, exchange: str, qty: int,
                               trigger_price: float, side: str = "SELL",
                               last_price: float = 0.0):
        if kind is ProtectiveStopKind.RESTING_STOP:
            # tradingsymbol/exchange are what let the client resolve the SAME real
            # tick the initial placement used, instead of falling back to 0.05.
            return self.client.modify_stop_order(protective_id, trigger_price,
                                                 tradingsymbol, exchange, quantity=qty)
        return self.client.modify_stop_gtt(protective_id, tradingsymbol, exchange,
                                           qty, trigger_price, last_price, side=side)

    def cancel_protective_stop(self, kind: ProtectiveStopKind, protective_id: str):
        # A resting SL-M is an ordinary order, so it is cancelled as one; a GTT is
        # a trigger and needs the GTT endpoint. Sending either to the other's
        # endpoint is rejected — this is the whole reason the kind is carried.
        if kind is ProtectiveStopKind.RESTING_STOP:
            return self.client.cancel(protective_id)
        return self.client.delete_gtt(protective_id)

    def protective_stop_state(self, kind: ProtectiveStopKind, protective_id: str) -> dict:
        """Normalised state of a resting protective stop.

        A RESTING_STOP has an order id, so its fill is readable and reported
        (R3: the bot's own SL-M filling is booked STOP_LOSS at the real price, not
        as a mystery external exit). A SERVER_TRIGGER has only a trigger id, so
        `gtt_status` is the only source and it reports triggered-ness, not a fill.
        """
        if kind is ProtectiveStopKind.RESTING_STOP:
            st = self.client.status(protective_id) or {}
            status = str(st.get("status", "")).upper()
            filled = int(st.get("filled_qty", 0) or 0)
            return {"status": status.lower(),
                    "triggered": status == "COMPLETE" and filled > 0,
                    "filled_qty": filled,
                    "avg_price": float(st.get("avg_price", 0.0) or 0.0)}
        probe = getattr(self.client, "gtt_status", None)
        if probe is None:
            # Conservative: a venue that cannot answer must not be read as
            # "did not fire" with any confidence — callers treat False as
            # "assume external exit", which keeps the safe re-entry block.
            return {"status": "", "triggered": False, "filled_qty": 0, "avg_price": 0.0}
        d = probe(protective_id) or {}
        return {"status": str(d.get("status", "")),
                "triggered": bool(d.get("triggered")
                                  or str(d.get("status", "")).lower() == "triggered"),
                "filled_qty": 0, "avg_price": 0.0}

    # ── account ────────────────────────────────────────────────────────
    def funds(self) -> dict:
        return self.client.kite.margins()

    def margin_probe(self, req: OrderRequest) -> float:
        """Margin Kite would actually block for `req`. Returns 0.0 when the probe
        cannot be answered — the sizing chain fails CLOSED to zero deployable
        cash rather than falling back to an assumed leverage figure."""
        res = self.client.kite.order_margins([{
            "exchange": req.exchange,
            "tradingsymbol": req.tradingsymbol,
            "transaction_type": req.side,
            "variety": self.client.variety,
            "product": req.product or self.client.product,
            "order_type": req.order_type,
            "quantity": int(req.qty),
            "price": req.limit_price or 0,
            "trigger_price": 0,
        }])
        if not res:
            return 0.0
        return float((res[0] or {}).get("total", 0.0) or 0.0)

    def tick_size(self, tradingsymbol: str, exchange: str | None = None) -> float:
        return self.client.tick_size(tradingsymbol, exchange)
