"""
`ExecutionVenue` — the wire-facing contract, and the neutral segment vocabulary
the engine uses to decide *what* to ask for without knowing *how* it is spelled.

`OrderClient` (order_executor.py) declares only place/status/cancel, but the live
broker already calls `place_stop_gtt`, `modify_stop_gtt`, `delete_gtt`,
`place_stop_order`, `modify_stop_order`, `gtt_status`, `find_fill` and `orders`
straight through it. So the real seam has been eight methods wider than the
declared one for months, and every one of those is Kite-shaped. `ExecutionVenue`
declares the full seam in neutral terms; `KiteVenue` is the translation.

`OrderClient` deliberately stays as-is: `execute_order` needs only place+status,
and narrowing what that function can reach is a safety property worth keeping.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.engine.broker_protocol import ProtectiveStopKind, Tenor
from app.engine.order_executor import OrderRequest

# ── neutral segment classification ────────────────────────────────────────
# Two different "segment" vocabularies exist in this codebase and confusing them
# is a real bug, so they get two differently-named functions here.
#
#   charge segment  — "NSE_INTRADAY" / "BSE_INTRADAY" / "NFO" / "NFO_FUT" / "MCX"…
#                     drives the charge schedule; stored on `Position.exchange`.
#   book segment    — "options" / "equity_intraday" / "futures"
#                     drives engine routing; stored on `Position.segment`.

#: Charge-segments that trade as leveraged same-day equity.
INTRADAY_EQUITY_CHARGE_SEGMENTS = frozenset({"NSE_INTRADAY", "BSE_INTRADAY"})

#: Book-segment whose protective stop must be a resting order, not a server
#: trigger — Zerodha refuses GTTs on MIS. (The 2026-07-03 failure class: option
#: GTTs worked, intraday ones were never created at all.)
_RESTING_STOP_BOOK_SEGMENTS = frozenset({"equity_intraday"})


def tenor_for_charge_segment(charge_segment: str) -> Tenor:
    """INTRADAY for the same-day equity segments, CARRY for everything else
    (options/futures are held to expiry or overnight)."""
    return (Tenor.INTRADAY if charge_segment in INTRADAY_EQUITY_CHARGE_SEGMENTS
            else Tenor.CARRY)


def protective_kind_for_book_segment(book_segment: str) -> ProtectiveStopKind:
    """Which shape of protective stop this position's venue will accept.

    Intraday equity gets a RESTING_STOP (Kite SL-M); options and futures get a
    SERVER_TRIGGER (Kite GTT). Same predicate the live broker has always used —
    named, so the branch reads as a venue capability rather than a segment string.
    """
    return (ProtectiveStopKind.RESTING_STOP
            if book_segment in _RESTING_STOP_BOOK_SEGMENTS
            else ProtectiveStopKind.SERVER_TRIGGER)



def rows_or_refuse(reader, family: str) -> list:
    """Call an inventory reader and refuse a `None`.

    The distinction is the whole point of `protective_inventory`, and both venues previously
    wrote `reader() or []` — which turns a client that answers `None` on a failed read into an
    EMPTY inventory. Callers read emptiness as "this position has no exchange-side stop" and
    place one, so a duplicate protective order lands on a live position.

    Not reachable through `KiteOrderClient`, which returns a list or raises. It is fixed anyway
    because the protocol docstring states the guarantee absolutely, and a docstring ahead of the
    code is this codebase's repeat failure shape — noted by the execution-safety review that
    found it (F6, 2026-08-10).
    """
    rows = reader()
    if rows is None:
        raise NotImplementedError(
            f"this client answered None for the {family} inventory. None is not an empty "
            f"inventory — it is an unreadable one, and reporting it as empty licenses placing a "
            f"second protective stop on a position that already has one.")
    return list(rows)

# ── the wire contract ─────────────────────────────────────────────────────


@runtime_checkable
class ExecutionVenue(Protocol):
    """Everything a broker needs from the outside world.

    Implementations translate to their own wire vocabulary and MUST NOT leak it
    back: no MIS/NRML/GTT/SL-M in a return value or an argument name.

    Failure semantics are part of the contract, because the live broker's safety
    depends on them (H7 — they used to be inherited rather than declared):

      * `place` raises on submit failure and returns an id otherwise. It must
        never retry internally: a duplicate real order is worse than a missed one.
      * `status` raises only on a *read* failure. A read failure must never be
        reported as "no fill" — callers treat an unreadable order as possibly
        working and refuse to send another.
      * `cancel` raises if the venue refused. A refused cancel means the old order
        may still fire, so callers must not then place a second one.
      * `find_fill` / `gtt_status`-shaped reads return None / a conservative value
        rather than raising when the answer is merely unknown.
    """

    # ── plain orders ───────────────────────────────────────────────────
    def place(self, req: OrderRequest) -> str:
        """Submit once, return the venue order id. Raises if nothing was sent."""
        ...

    def status(self, order_id: str) -> dict:
        """{status, filled_qty, avg_price, reason} for an order."""
        ...

    def cancel(self, order_id: str):
        """Cancel a working order. Raises if the venue refused."""
        ...

    def orders(self) -> list[dict]:
        """Today's orders as {order_id, tradingsymbol, tag}."""
        ...

    def find_fill(self, tradingsymbol: str, side: str = "SELL") -> dict | None:
        """Today's real fill for symbol/side as {avg_price, filled_qty}, or None."""
        ...

    # ── protective stops ───────────────────────────────────────────────
    #: Which protective shapes this venue can actually rest at the exchange.
    #:
    #: On the protocol so a caller can ASK rather than know. `DhanVenue` declared it and
    #: `KiteVenue` did not, which meant the question was answerable for one venue only and any
    #: caller needing it had to branch on the broker's name — the exact branch the capability
    #: model exists to remove (`.claude/rules/providers-brokers.md`: what must not appear under
    #: `app/engine/` is a branch on a provider's identity).
    #:
    #: It is load-bearing, not descriptive. Dhan has no GTT equivalent, so this set is
    #: RESTING_STOP only there, and an options deployment — which needs a SERVER_TRIGGER —
    #: cannot run on Dhan execution. The venues refuse rather than substituting a weaker shape,
    #: because a caller that believes it holds exchange-side protection and does not is worse
    #: off than one that was told no.
    PROTECTIVE_KINDS: frozenset

    def place_protective_stop(self, kind: ProtectiveStopKind, *, tradingsymbol: str,
                              exchange: str, qty: int, trigger_price: float,
                              side: str = "SELL", last_price: float = 0.0,
                              tag: str | None = None) -> str:
        """Rest a protective stop of `kind`, return its venue-side id."""
        ...

    def modify_protective_stop(self, kind: ProtectiveStopKind, protective_id: str, *,
                               tradingsymbol: str, exchange: str, qty: int,
                               trigger_price: float, side: str = "SELL",
                               last_price: float = 0.0):
        """Re-price a resting protective stop (the ratchet). Raises if refused."""
        ...

    def cancel_protective_stop(self, kind: ProtectiveStopKind, protective_id: str):
        """Cancel a resting protective stop. Raises if the venue refused."""
        ...

    def protective_stop_state(self, kind: ProtectiveStopKind, protective_id: str) -> dict:
        """{status, triggered, filled_qty, avg_price} for a resting protective stop.

        Needed because a SERVER_TRIGGER id is not an order id, so `status()` cannot
        answer it — the distinction that E6 was about.
        """
        ...

    def protective_inventory(self, kind: ProtectiveStopKind) -> list[dict]:
        """Every protective stop of `kind` currently known to the venue, as rows of

            {id, tradingsymbol, exchange, side, qty, trigger_price, status, tag}

        `status` is normalised to one of `"live"` / `"dead"` / `""` (unknown), because
        the two families report deadness in different and venue-specific vocabularies
        and the broker must not learn either. `""` means the venue gave no status at
        all; a caller deciding whether a stop is still protecting a position must treat
        it as live, since assuming dead is what would place a second one.

        This exists because the broker used to read the raw `orders()` / `gtts()` dumps
        and filter them on Kite's own field names (`trigger_id` vs `order_id`,
        `transaction_type` vs `side`, `quantity` vs `qty`). Those spellings are exactly
        what a second venue does not share.

        Raises on a read failure. It must never return `[]` for an unreadable venue:
        callers use emptiness to conclude "this position has no exchange-side stop",
        and concluding that wrongly places a duplicate.
        """
        ...

    # ── vocabulary ─────────────────────────────────────────────────────
    def exchange_for(self, charge_segment: str) -> str:
        """The venue's own name for the exchange a charge-segment trades on.

        Strategy OS classifies by charge-segment because that is what drives the charge
        schedule; the venue's exchange code is a different alphabet (Kite's `NSE` for
        both `NSE_EQ` and `NSE_INTRADAY`). Translating here is what lets the broker hold
        one classification while two venues spell it differently.
        """
        ...

    def product_for(self, tenor: Tenor) -> str:
        """The venue's product code for a neutral holding period.

        The broker decides INTRADAY or CARRY — a risk decision it owns. Which of the
        venue's product codes expresses that is the venue's business: Kite says MIS and
        NRML, and nothing above this line may.
        """
        ...

    # ── account ────────────────────────────────────────────────────────
    def funds(self) -> dict:
        """Deployable balance per segment."""
        ...

    def margin_probe(self, req: OrderRequest) -> float:
        """Margin the venue would actually block for `req`."""
        ...

    def tick_size(self, tradingsymbol: str, exchange: str | None = None) -> float:
        """The instrument's real price grid. Every trigger/limit must land on it —
        the 2026-07-15 incident was 2,437 rejections for assuming 0.05."""
        ...
