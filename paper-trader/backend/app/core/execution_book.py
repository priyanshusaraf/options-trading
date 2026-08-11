"""Which ledger a piece of money state belongs to, and the one place that decides.

**The book is the execution mode.** This module deliberately introduces no new
abstraction: `positions.mode` and `trades.mode` already named the book correctly on the
two tables that carry most of the money record. What was missing was a *name*, a
*resolver*, and reach — the discriminator was written on every fill and read by no
position query, and it did not exist at all on `capital_state` or `equity_snapshots`.

**Why the fallback is `live`.** Every caller here is asking a question whose wrong answer
has an asymmetric cost. Treating a live position as paper lets a broker with no order
client "close" a contract that is still open at Zerodha. Treating a paper position as live
merely refuses to act. So an unset, missing, or malformed mode resolves to `live` — the
book with the strictest rules — and the word `paper` is only ever produced by the literal
string. `getattr(broker, "MODE", "paper")`, the shape this replaces, had it backwards.

**Ground truth is the broker object, not the setting.** `make_broker` returns a
`PaperBroker` unless *both* live flags are set *and* the Kite provider is active, so a
malformed `PT_EXECUTION` yields a paper broker while the setting reads as unrecognised.
`book_of(broker)` asks the object that was actually built; `configured_execution_mode()`
answers the different question the authority gate asks — what mode was *requested* — and
both fail closed the same way.
"""
from __future__ import annotations

PAPER = "paper"
LIVE = "live"

#: Every book there is. A third would need its own capital row, its own reconciliation
#: and its own entries in `GRANTS`; naming them here means adding one is a deliberate
#: edit rather than a new string appearing in a column.
BOOKS = (PAPER, LIVE)


#: What happens to the single pre-slice ledger when the evidence is contradictory —
#: money rows from *both* books, so nothing says whose cash it is. It is left
#: unattributed and both books start fresh, loudly. Raising instead was the first design
#: and it was wrong: a broker that cannot construct is an engine that cannot run its risk
#: lane, and hard invariant 2 says not getting out is worse than any accounting defect.
#: The property that matters is preserved either way — the cash is never *guessed* onto a
#: book. Production has never been in this state (72 live rows, zero paper), and this
#: slice makes it unreachable going forward, because every write is book-scoped from here.
LEGACY_LEDGER_AMBIGUOUS = ("capital_state row {row_id} is unattributed and both books "
                           "already hold money records ({owners}). Its cash cannot be "
                           "assigned from the evidence, so it is left alone and {book} "
                           "starts a fresh ledger.")


def resolve_book(raw) -> str:
    """The book named by `raw`, failing closed to `live`.

    Not a lookup with a default: `paper` must be spelled, and everything else — None, a
    typo, an integer, a `Settings` field nobody set — is `live`.
    """
    if not isinstance(raw, str):
        return LIVE
    return PAPER if raw.strip().lower() == PAPER else LIVE


def book_of(broker) -> str:
    """The book a broker writes to, from the object itself rather than from config."""
    return resolve_book(getattr(broker, "MODE", None))


def configured_execution_mode() -> str:
    """The execution mode this process was *asked* to run in — the authority gate's
    half of the `(source, execution_mode)` pair. Fails closed to `live` exactly as
    `resolve_book` does, so a blank or malformed setting can never widen a grant."""
    from app.core.config import get_settings

    return resolve_book(getattr(get_settings(), "execution", None))


def _books_with_money_rows(session) -> set[str]:
    """Which books already own persisted money records. Immutable evidence: `mode` was
    stamped on every fill long before this slice, by the broker that made it."""
    from sqlalchemy import select

    from app.db.models import Position, Trade

    return ({resolve_book(m) for m in session.scalars(select(Position.mode).distinct())}
            | {resolve_book(m) for m in session.scalars(select(Trade.mode).distinct())})


def capital_for_book(session, book: str, *, broker_account_id: str):
    """This book's `capital_state` row, claiming or creating it if it has none.

    Three cases, in order:

    1. The book already owns a row — return it.
    2. The single unclaimed pre-slice row exists and the money rows prove it belongs to
       this book (every `positions`/`trades` row is this book's, or there are none) —
       claim it, preserving the cash and realised P&L those fills produced.
    3. Otherwise — a fresh ledger for this book, seeded at the configured initial
       capital, leaving the other book's history untouched and readable.

    When the ledger is unclaimed and both books already hold money rows, case 2 is
    skipped and the row is left unattributed with a warning — see
    `LEGACY_LEDGER_AMBIGUOUS`.
    """
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.logging import log
    from app.db.models import CapitalState

    if book not in BOOKS:
        raise ValueError(f"{book!r} is not an execution book; expected one of {BOOKS}")

    row = session.get(CapitalState, (broker_account_id, book))
    if row is not None:
        return row

    seed = get_settings().initial_capital
    row = CapitalState(broker_account_id=broker_account_id, book=book,
                       initial_capital=seed, cash=seed, realized_pnl=0.0)
    session.add(row)
    _commit_the_bootstrap(session)
    return row


def _commit_the_bootstrap(session) -> None:
    """Commit the claim immediately rather than flushing into the caller's transaction.

    A flush would leave an open write transaction, and the broker holds its session for
    its entire lifetime by design — so an uncommitted claim keeps a SQLite write lock for
    the life of the process. That is not theoretical: it turned eight unrelated ledger
    tests red with `database is locked` on `DROP TABLE`, because `init_db(reset=True)`
    could no longer get the write lock.

    Committing here is safe because attributing a ledger to a book is bootstrap, not part
    of any caller's unit of work: it is idempotent, it is the first thing a broker does
    (see `PaperBroker.__init__`), and no call site reaches `capital()` with its own
    writes pending.
    """
    session.commit()


def foreign_book_positions(session, book: str) -> list:
    """Open positions belonging to a book **other** than `book`.

    The compensating control for scoping the exit lane. `broker.open_positions()` is now
    book-scoped, which means a live position left open while the paper book runs is
    managed by nobody — and hard invariant 2 says not getting out is the worst failure
    there is. Scoping is still correct (a paper broker cannot close a live contract; it
    would only fake the close), so the answer is not to widen the read but to make the
    orphan impossible to miss. Reported at engine startup and on `/api/health`.
    """
    from sqlalchemy import select

    from app.db.models import Position

    return [p for p in session.scalars(select(Position))
            if resolve_book(p.mode) != book]


__all__ = ["BOOKS", "LEGACY_LEDGER_AMBIGUOUS", "LIVE", "PAPER", "book_of",
           "capital_for_book", "configured_execution_mode", "foreign_book_positions",
           "resolve_book"]
