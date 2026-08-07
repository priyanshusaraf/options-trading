"""
The domain-facing broker contract — Phase F, audit findings C2 + H7.

Layering this file anchors:

    Broker (domain verbs)  ->  ExecutionVenue (wire verbs)  ->  broker-specific impl

`Broker` is what the engine is allowed to know about. It speaks in positions,
fills, protection and ledger state — never in Zerodha product codes, GTT trigger
ids or SL-M order types. Everything Kite-shaped lives behind `ExecutionVenue`
(`app/engine/venue.py`) and its Kite implementation (`app/engine/kite_venue.py`).

Two things in here are load-bearing beyond documentation:

**`VENUE_FACING_METHODS`.** `LiveBroker` subclasses `PaperBroker`, so any method it
does not override runs the *simulator's* arithmetic in the real-money path. For
pure bookkeeping (`mark`, `snapshot`, `capital`, `book_partial_close`) that is
correct and intended — the ledger maths is genuinely shared. For anything that
must reach the exchange it is a silent simulation of real money, which is the same
"looks wired, isn't" defect class this codebase has shipped three times. This set
is the explicit line between the two, and `tests/test_broker_protocol.py` fails the
build if a venue-facing method is inherited rather than defined.

**The neutral protective-order accessors.** `Position.gtt_trigger_id` is a Zerodha
concept sitting in the domain model. The column cannot be renamed here (it is owned
by `db/models.py` + migrations), so engine code goes through
`protective_order_id()` / `set_protective_order_id()` instead. When the column is
eventually renamed to `protective_order_id`, exactly one line in this file changes.
See /tmp/phaseF_needs.md.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Protocol, runtime_checkable

# ── neutral vocabulary ────────────────────────────────────────────────────
# Kite spells these MIS / NRML / GTT / SL-M. The engine must not.


class Tenor(str, Enum):
    """How long a position is allowed to live — the neutral form of a product code.

    INTRADAY: same-day only; the venue auto-squares-off near the close and grants
              intraday leverage. Kite calls this MIS.
    CARRY:    may be held overnight. Kite calls this NRML (CNC for cash delivery,
              which this system does not trade).
    """
    INTRADAY = "intraday"
    CARRY = "carry"


class ProtectiveStopKind(str, Enum):
    """How the venue holds a protective stop on our behalf.

    RESTING_STOP:   a real order resting in the order book that becomes a market
                    order when the trigger is crossed. Kite: an SL-M order. It has
                    an *order id*, so its state is readable via `status()`.
    SERVER_TRIGGER: a broker-side conditional that only becomes an order once it
                    fires. Kite: a GTT. It has a *trigger id*, which is NOT an
                    order id — its state needs the venue's own trigger lookup.

    The distinction is not cosmetic: Zerodha refuses GTTs on MIS positions, which
    is why intraday equity is protected by a resting SL-M and options by a GTT.
    Other venues split differently (IB has bracket/OCA orders and neither of
    these), which is exactly why the engine should branch on the *kind* rather
    than on "is this equity_intraday".
    """
    RESTING_STOP = "resting_stop"
    SERVER_TRIGGER = "server_trigger"


# ── neutral accessor for the protective-order id ──────────────────────────
# The ORM column is `gtt_trigger_id` and holds BOTH a GTT trigger id (options) and
# an SL-M order id (intraday equity) — it has been dual-purpose since the MIS
# backstop shipped, so the name has been wrong for longer than it has been right.

_PROTECTIVE_ID_COLUMN = "gtt_trigger_id"


def protective_order_id(pos) -> str | None:
    """The venue-side id of this position's resting protective stop, or None.

    `getattr` with a default rather than attribute access: several call sites pass
    objects that are not full ORM rows (recovery contexts, test doubles), and a
    missing protection id must read as "no protection", never raise.
    """
    return getattr(pos, _PROTECTIVE_ID_COLUMN, None)


def set_protective_order_id(pos, value) -> None:
    """Record the venue-side id of a newly-rested protective stop."""
    setattr(pos, _PROTECTIVE_ID_COLUMN, value)


def clear_protective_order_id(pos) -> None:
    """Forget the protective stop — it was cancelled, fired, or is being replaced.

    Callers must persist this promptly (H4): a dead id left in the DB makes
    `ensure_stop_protection` trust a stop that no longer exists.
    """
    setattr(pos, _PROTECTIVE_ID_COLUMN, None)


# ── the domain contract ───────────────────────────────────────────────────


@runtime_checkable
class Broker(Protocol):
    """What the engine may ask of a broker. Implemented by PaperBroker (simulated
    fills) and LiveBroker (real fills), which are behaviourally siblings even
    though LiveBroker is still implemented as a subclass — see PHASE_F_REMAINING.
    """

    MODE: str

    # ledger / state
    def capital(self): ...
    def cash(self) -> float: ...
    def open_positions(self, deployment_id: int | None = None) -> list: ...
    def position_for(self, key: str, deployment_id: int | None = None): ...
    def snapshot(self, now: dt.datetime): ...
    def reconcile(self) -> dict: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...

    # fills
    # `strategy_key`/`strategy_version` are the executed identity, passed down from the
    # runner's canonical binding. Both are on every entry path as of L1.3C: the options
    # path resolved the binding and refused to open without it, but did not carry it onto
    # the row, so option positions were written unattributed.
    def open_position(self, inst, direction, q, reason, now, spot,
                      params=None, plan=None, strategy_key=None,
                      strategy_version=None): ...
    def open_equity_position(self, inst, direction, price, qty, charge_segment,
                             reason, now, params=None, strategy_key=None,
                             strategy_version=None,
                             margin=None, sl_pct=None, tp_pct=None): ...
    def close_position(self, pos, exit_premium, reason, now, spot,
                       exit_price_estimated: bool = False): ...
    def close_equity_position(self, pos, exit_price, reason, now,
                              exit_price_estimated: bool = False): ...
    def book_partial_close(self, pos, qty, exit_premium, reason, now, spot): ...
    def book_partial_close_equity(self, pos, qty, exit_price, reason, now): ...

    # marking / management
    def mark(self, pos, premium, spot, now=None) -> None: ...
    def reinforce_position(self, pos, params, now) -> dict: ...

    # protection
    def ensure_stop_protection(self, pos, last_price) -> None: ...
    def update_stop_protection(self, pos, last_price) -> None: ...

    # recovery / reconciliation
    def reconcile_orphans(self, now) -> list: ...
    def adopt_pending_entries(self, now) -> list: ...
    def cancel_working_entries(self) -> list: ...
    def recover_journal(self, now) -> list: ...


# ── the bookkeeping / venue split (H7) ────────────────────────────────────

#: Methods whose correct behaviour is pure ledger arithmetic. A live broker
#: SHOULD inherit these — that sharing is the whole point of a common core, and
#: re-implementing them per broker is how the money path diverges.
BOOKKEEPING_METHODS = frozenset({
    "capital", "cash", "open_positions", "position_for", "commit", "close",
    "snapshot", "reconcile", "mark", "reinforce_position", "manual_open",
    "book_partial_close", "book_partial_close_equity",
})

#: Methods that MUST reach the venue when the broker is a real-money one. A live
#: broker that inherits any of these from the paper simulator is silently
#: simulating real money. Enforced by tests/test_broker_protocol.py.
VENUE_FACING_METHODS = frozenset({
    "open_position",
    "open_equity_position",
    "open_futures_position",
    "close_position",
    "close_equity_position",
    "close_futures_position",
    "ensure_stop_protection",
    "update_stop_protection",
    "reconcile_orphans",
    "adopt_pending_entries",
    "cancel_working_entries",
    "recover_journal",
})

#: Venue-facing methods the live broker does NOT currently implement, with the
#: reason each is tolerated. This is a *pinned* list, not an escape hatch: the
#: guard test asserts the set of inherited venue methods equals this exactly, so
#: closing a gap without deleting its entry fails, and opening a new one fails too.
#:
#: `index_futures_enabled` defaults False and there is no production override, so
#: the futures entry path is unreachable in live today. If it is ever enabled
#: before these are implemented, `open_futures_position` would book a simulated
#: position with no order behind it. Tracked in /tmp/phaseF_needs.md.
KNOWN_UNIMPLEMENTED_VENUE_METHODS = frozenset({
    "open_futures_position",
    "close_futures_position",
})
