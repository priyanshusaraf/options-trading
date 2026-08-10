"""Dhan's dialect — the second `ExecutionVenue`, and the first real test of whether the seam is
a boundary or just Kite with neutral names on it.

Two things live here, mirroring `kite_venue.py`:

  * the pure translation functions (`dhan_product`, `dhan_exchange`), and
  * `DhanVenue`, an `ExecutionVenue` over a `DhanOrderClient`.

Written from https://dhanhq.co/docs/v2/ read on 2026-08-10. **The seam held**: every verb the
protocol declares maps onto something Dhan actually does, with one exception, and that exception
is the valuable part of this file.

## Dhan cannot serve a SERVER_TRIGGER, and this refuses rather than substituting

Kite's GTT is a broker-side conditional that can be placed against a position that already
exists, independently of the order that opened it. That is what `ProtectiveStopKind.SERVER_TRIGGER`
means and it is what protects every options position this system holds.

Dhan has no equivalent. It has `STOP_LOSS_MARKET` — a real resting order, which is
`RESTING_STOP` — and it has **super orders**, which bundle entry, target and stop into one
construct submitted together. A super order cannot be attached to a position that is already
open, so it is not a substitute; it is a different product with a different lifecycle.

The tempting move is to place a `STOP_LOSS_MARKET` when the broker asks for a `SERVER_TRIGGER`,
on the grounds that both end up protecting the position. **That is refused here**, for a reason
that is about correctness rather than purity: the two have different failure modes and the
broker's own code branches on the distinction. A `RESTING_STOP` consumes margin and sits in the
order book where `_protection_inventory` will match it; a `SERVER_TRIGGER` does neither, and its
id is a trigger id that `status()` cannot answer. Silently swapping them would make
`protective_stop_state` report a fill that never happened, and the reconciliation that decides
whether the bot may re-enter a contract reads exactly that.

So `DhanVenue` declares `RESTING_STOP` only, and asking it for a `SERVER_TRIGGER` raises. The
consequence is real and must not be discovered at 09:15: **an options deployment cannot run on
Dhan execution in this build.** Intraday equity can. That is a capability fact, and the venue
seam existing is what lets it be stated instead of guessed.
"""
from __future__ import annotations

from app.engine.broker_protocol import ProtectiveStopKind, Tenor
from app.engine.order_executor import OrderRequest
from app.engine.venue import rows_or_refuse

# ── vocabulary translation ────────────────────────────────────────────────

#: Dhan product codes by neutral tenor. `INTRADAY` where Kite says `MIS`; `MARGIN` where Kite
#: says `NRML`. `CNC` is delivery equity, which this system does not trade, and `MTF` is a
#: funded product with its own interest and risk profile — neither is a default.
_DHAN_PRODUCT = {Tenor.INTRADAY: "INTRADAY", Tenor.CARRY: "MARGIN"}

#: Charge-segments carry an `_INTRADAY` suffix for the charge schedule. Dhan's segment vocabulary
#: is its own (`NSE_EQ`, `NSE_FNO`, `MCX_COMM`), NOT Kite's bare exchange codes — so this is a
#: real mapping rather than a suffix strip. A segment absent here is not a Dhan segment and is
#: refused: sending one is rejected by the API with an error that does not name the field.
_DHAN_EXCHANGE = {
    "NSE_INTRADAY": "NSE_EQ",
    "BSE_INTRADAY": "BSE_EQ",
    "NSE_EQ": "NSE_EQ",
    "BSE_EQ": "BSE_EQ",
    "NFO": "NSE_FNO",
    "NFO_FUT": "NSE_FNO",
    "BFO": "BSE_FNO",
    "MCX": "MCX_COMM",
    "CDS": "NSE_CURRENCY",
}


class UnsupportedProtection(NotImplementedError):
    """Asked for a protective-stop kind this venue cannot place.

    Deliberately loud and deliberately NOT substituted with the other kind — see the module
    docstring. A caller that catches this must treat the position as unprotected at the exchange,
    which is true, rather than as protected by something that behaves differently.
    """


class UnsupportedSegment(ValueError):
    """A charge-segment with no Dhan equivalent. Refused rather than passed through, because
    Dhan's segment vocabulary is its own and an unmapped value is rejected at the API with an
    error that does not say which field was wrong."""


def dhan_product(tenor: Tenor, default: str = "MARGIN") -> str:
    return "INTRADAY" if tenor is Tenor.INTRADAY else default


def dhan_exchange(charge_segment: str) -> str:
    try:
        return _DHAN_EXCHANGE[charge_segment]
    except KeyError:
        raise UnsupportedSegment(
            f"dhan has no segment for charge-segment {charge_segment!r}; known: "
            f"{sorted(_DHAN_EXCHANGE)}") from None

# NOTE: there is deliberately no `dhan_product_for_charge_segment` mirroring
# `kite_venue.kite_product_for_charge_segment`. That one exists because `runner.py` builds a Kite
# margin payload directly; nothing does the equivalent for Dhan. Writing it "for symmetry" is how
# the unconsumed-mechanism defect gets in, and `test_no_unconsumed_mechanisms` caught exactly
# that when this file first landed. It is two lines whenever a caller appears.


# ── the adapter ───────────────────────────────────────────────────────────


class DhanVenue:
    """`ExecutionVenue` over a `DhanOrderClient`.

    Every method is a translation, never a decision: the broker decides *that* a RESTING_STOP is
    needed, this decides that Dhan spells one `STOP_LOSS_MARKET`.
    """

    #: What this venue can actually rest at the exchange. Read by callers that need to know
    #: before committing to a deployment, rather than discovering it on the first stop.
    PROTECTIVE_KINDS = frozenset({ProtectiveStopKind.RESTING_STOP})

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
    def _require(self, kind: ProtectiveStopKind) -> None:
        if kind not in self.PROTECTIVE_KINDS:
            raise UnsupportedProtection(
                f"dhan cannot place a {kind.value} protective stop. It has STOP_LOSS_MARKET (a "
                f"RESTING_STOP) and super orders, which bundle entry+stop+target and cannot be "
                f"attached to an already-open position. Refusing rather than substituting a "
                f"RESTING_STOP: the two have different ids, different margin and different "
                f"reconciliation, and the broker branches on the difference.")

    def place_protective_stop(self, kind: ProtectiveStopKind, *, tradingsymbol: str,
                              exchange: str, qty: int, trigger_price: float,
                              side: str = "SELL", last_price: float = 0.0,
                              tag: str | None = None) -> str:
        self._require(kind)
        # `last_price` is accepted and unused: a GTT needs it to set its own limit leg, a resting
        # market stop does not. Keeping the signature identical is what lets the broker call one
        # method for both venues.
        return str(self.client.place_stop_order(
            tradingsymbol, exchange, qty, trigger_price, side=side, tag=tag))

    def modify_protective_stop(self, kind: ProtectiveStopKind, protective_id: str, *,
                               tradingsymbol: str, exchange: str, qty: int,
                               trigger_price: float, side: str = "SELL",
                               last_price: float = 0.0):
        self._require(kind)
        # tradingsymbol/exchange are what let the client resolve the SAME real tick the initial
        # placement used, instead of falling back to 0.05.
        return self.client.modify_stop_order(protective_id, trigger_price,
                                             tradingsymbol, exchange, quantity=qty)

    def cancel_protective_stop(self, kind: ProtectiveStopKind, protective_id: str):
        self._require(kind)
        # A resting stop is an ordinary order and is cancelled as one. There is no second
        # endpoint here because there is no second kind.
        return self.client.cancel(protective_id)

    def protective_stop_state(self, kind: ProtectiveStopKind, protective_id: str) -> dict:
        """Normalised state of a resting protective stop.

        A RESTING_STOP has a real order id, so its fill is readable and reported: the bot's own
        stop firing is booked at the real price rather than showing up as a mystery external
        exit (R3).
        """
        self._require(kind)
        st = self.client.status(protective_id) or {}
        status = str(st.get("status", "")).upper()
        filled = int(st.get("filled_qty", 0) or 0)
        return {"status": status.lower(),
                "triggered": status == "COMPLETE" and filled > 0,
                "filled_qty": filled,
                "avg_price": float(st.get("avg_price", 0.0) or 0.0)}

    def protective_inventory(self, kind: ProtectiveStopKind) -> list[dict]:
        """Every resting protective stop, as neutral rows.

        Raises on an unreadable venue — it must never return `[]`, because callers read emptiness
        as "this position has no exchange-side stop" and placing one on that basis duplicates a
        protective order on a live position.
        """
        self._require(kind)
        reader = getattr(self.client, "orders", None)
        if reader is None:
            raise NotImplementedError(
                "this Dhan client cannot list orders, so the resting-stop inventory is unknown "
                "— refusing to report it as empty")
        rows = []
        for r in rows_or_refuse(reader, "resting-stop"):
            # `status` arrives already translated into this engine's vocabulary by
            # `dhan_order_client.normalise_order`, so COMPLETE here means TRADED at Dhan.
            status = str(r.get("status") or "").upper()
            rows.append({
                "id": str(r["order_id"]) if r.get("order_id") else None,
                "tradingsymbol": r.get("tradingsymbol"),
                "exchange": r.get("exchange"),
                "side": str(r.get("transaction_type") or "").upper(),
                "qty": int(r.get("qty") or r.get("quantity") or 0),
                "trigger_price": float(r.get("trigger_price") or 0.0),
                # A filled stop is dead: it is no longer protecting anything, which is the whole
                # point of the reconciliation that reads this.
                "status": ("dead" if status in {"REJECTED", "CANCELLED", "COMPLETE", "EXPIRED"}
                           else "live"),
                "tag": r.get("tag"),
            })
        return rows

    # ── vocabulary ─────────────────────────────────────────────────────
    def exchange_for(self, charge_segment: str) -> str:
        return dhan_exchange(charge_segment)

    def product_for(self, tenor: Tenor) -> str:
        return dhan_product(tenor, self._carry_product())

    def _carry_product(self) -> str:
        return str(getattr(self.client, "product", "MARGIN") or "MARGIN")

    # ── account ────────────────────────────────────────────────────────
    def funds(self) -> dict:
        return self.client.funds()

    def margin_probe(self, req: OrderRequest) -> float:
        return self.client.margin_probe(req)

    def tick_size(self, tradingsymbol: str, exchange: str | None = None) -> float:
        return self.client.tick_size(tradingsymbol, exchange)


def build_live_venue(connection, settings):
    """Build Dhan's live order client and venue from a connection. Registry-invoked.

    Two credentials, not one. `client-id` is a header on every request AND `dhanClientId` in the
    body of every order, and a token without it authenticates nothing — so it is read from the
    connection's bundle rather than assumed, and its absence is a refusal at the transport with
    a message naming the field rather than a generic auth failure.

    `tick_source` comes from the connection for the same reason it does for Kite: an unsnapped
    trigger is rejected outright and the position runs with no exchange-side stop.
    """
    from app.engine.dhan_order_client import DhanOrderClient
    from app.providers.dhan_transport import DhanTransport

    def client_id_source():
        return (connection.secrets_source() or {}).get("client_id")

    transport = DhanTransport(connection.token_source, client_id_source)
    client = DhanOrderClient(transport, client_id_source,
                             tick_source=connection.tick_source)
    return client, DhanVenue(client)
