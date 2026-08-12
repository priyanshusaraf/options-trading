"""Ledger tables.

The snapshot is the whole journal as one JSON document — see the design spec
§3.1 for why that is the right shape here: THE LEDGER already persisted as a
single debounced blob, and keeping that shape means all 43 of its mutators and
every business rule inside them stay untouched.

Artifacts are held OUT of the snapshot because they are binary and would
otherwise be rewritten on every debounced save (§3.2).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, Float, Integer, LargeBinary, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.ledger.db import LedgerBase


class LedgerSnapshot(LedgerBase):
    """One versioned snapshot per owner/account.

    `version` is the optimistic-concurrency token: a client PUT carries the
    version it last read, and a mismatch is a 409 rather than a silent clobber.
    """

    __tablename__ = "ledger_snapshot"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ledger_snapshot_single_row"),)

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="owner")
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True,
                                                    default="account.default")
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LedgerArtifact(LedgerBase):
    """A screenshot.

    `id` is the client-generated uid() from the journal, so the snapshot can
    reference the artifact before the upload round-trips.
    """

    __tablename__ = "ledger_artifact"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="owner")
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True,
                                                    default="account.default")
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LedgerManualFill(LedgerBase):
    """A Kite order attributed to the owner rather than the bot.

    Persisted on FIRST SIGHT, because Kite's orderbook is same-day only: there
    is no historical order/trade API, so anything not captured before midnight
    is gone from the broker forever. `raw` keeps the whole Kite dict for
    forensics precisely because we cannot go back and ask again.

    `order_id` is the primary key, so re-polling the same order is idempotent.
    `claimed_trade` holds the journal trade id once the owner has said why they
    took it — a claimed row is never overwritten by a later poll.
    """

    __tablename__ = "ledger_manual_fill"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="owner")
    broker_account_id: Mapped[str] = mapped_column(String(64), primary_key=True,
                                                    default="account.default")
    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tradingsymbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(16), nullable=True)
    product: Mapped[str | None] = mapped_column(String(16), nullable=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)      # BUY | SELL
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fill_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    raw: Mapped[str] = mapped_column(Text, nullable=False)
    claimed_trade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


from app.events.outbox import define_outbox_models as _define_outbox_models

LEDGER_OUTBOX_MODELS = _define_outbox_models(LedgerBase, "ledger")
