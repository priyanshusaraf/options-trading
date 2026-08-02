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
