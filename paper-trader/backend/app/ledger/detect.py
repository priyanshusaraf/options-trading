"""Read the live orderbook, attribute each order, persist the owner's.

READ-AND-RECORD ONLY. This module must never write `positions` or `trades`, and
must never influence can_bot_close(). It reads the execution DB only to learn
which order_ids and symbols belong to the bot. tests/ledger/test_isolation.py
asserts that boundary mechanically.

Kite's orderbook is same-day only, so anything seen here is persisted
immediately — there is no way to ask again tomorrow.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.ledger.classify import BOT, classify_order
from app.ledger.models import LedgerManualFill

# Only COMPLETE orders with a real fill are journalled. A cancelled or rejected
# order is not a trade the owner took, and prompting for its reasoning would
# train them to dismiss the prompt.
_FILLED = {"COMPLETE"}


def bot_order_ids(exec_session, *, owner_id: str, broker_account_id: str) -> set[str]:
    """order_ids the bot placed, from the local order_journal.

    NULLs are dropped: a crash between _journal_open and the placement ack
    leaves order_id NULL, and a None here must never match a real order."""
    from app.db.models import OrderJournal

    rows = exec_session.scalars(select(OrderJournal.order_id).where(
        OrderJournal.owner_id == owner_id,
        OrderJournal.broker_account_id == broker_account_id)).all()
    return {str(r) for r in rows if r is not None}


def bot_symbols_today(exec_session, *, owner_id: str,
                      broker_account_id: str) -> set[str]:
    """Symbols the bot placed or held. Used only to force NEEDS_REVIEW on an
    untagged order — the GTT hole. See classify.py for why."""
    from app.db.models import OrderJournal, Position

    syms: set[str] = set()
    for col in (OrderJournal.tradingsymbol, Position.tradingsymbol):
        model = col.class_
        for r in exec_session.scalars(select(col).where(
                model.owner_id == owner_id,
                model.broker_account_id == broker_account_id)).all():
            if r:
                syms.add(str(r).strip().upper())
    return syms


def _is_filled(o: dict) -> bool:
    return (str(o.get("status", "")).upper() in _FILLED
            and int(o.get("filled_quantity", 0) or 0) > 0)


def detect_manual_fills(provider, exec_session, ledger_sm, now: datetime,
                        *, owner_id: str, broker_account_id: str,
                        bot_ids: set[str] | None = None,
                        bot_symbols: set[str] | None = None) -> int:
    """Poll once. Returns the number of NEW rows written. Never raises."""
    orders = provider.account_orders()
    if orders is None:
        # A failed read is NOT an empty orderbook. Persisting nothing is the
        # only honest response: recording "no manual trades today" because the
        # broker was unreachable would be a lie the owner cannot detect.
        return 0

    if bot_ids is None:
        bot_ids = (bot_order_ids(exec_session, owner_id=owner_id,
                                 broker_account_id=broker_account_id)
                   if exec_session is not None else set())
    if bot_symbols is None:
        bot_symbols = (bot_symbols_today(
            exec_session, owner_id=owner_id,
            broker_account_id=broker_account_id)
                       if exec_session is not None else set())

    keep: list[tuple[dict, str]] = []
    for o in orders:
        if not _is_filled(o):
            continue
        verdict = classify_order(o, bot_ids, bot_symbols)
        if verdict == BOT:
            continue
        keep.append((o, verdict))

    return _upsert(ledger_sm, keep, now) if keep else 0


def _upsert(sm, rows: list[tuple[dict, str]], now: datetime) -> int:
    written = 0
    with sm() as s, s.begin():
        for o, verdict in rows:
            oid = str(o.get("order_id"))
            existing = s.get(LedgerManualFill, oid)
            if existing is not None:
                # Never clobber a row the owner has already reasoned about.
                if existing.claimed_trade:
                    continue
                existing.verdict = verdict
                existing.qty = int(o.get("filled_quantity", 0) or 0)
                existing.avg_price = float(o.get("average_price") or 0.0) or None
                continue
            s.add(LedgerManualFill(
                order_id=oid,
                tradingsymbol=str(o.get("tradingsymbol") or ""),
                exchange=o.get("exchange"),
                product=o.get("product"),
                side=str(o.get("transaction_type") or "").upper(),
                qty=int(o.get("filled_quantity", 0) or 0),
                avg_price=float(o.get("average_price") or 0.0) or None,
                order_ts=o.get("order_timestamp"),
                fill_ts=o.get("exchange_timestamp"),
                verdict=verdict,
                raw=json.dumps(o, default=str),
                seen_at=now,
            ))
            written += 1
    return written
