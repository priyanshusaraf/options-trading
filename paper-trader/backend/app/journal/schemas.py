"""Request/response models for the journal REST API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class AddTradeRequest(BaseModel):
    symbol: str
    direction: str          # LONG | SHORT
    lots: int
    entry_price: float
    entry_time: dt.datetime | None = None
    setup_tag: str | None = None
    notes: str | None = None
    view_id: int | None = None


class CloseTradeRequest(BaseModel):
    exit_price: float
    exit_time: dt.datetime | None = None
    manual_net_pnl: float | None = None


class AddMissedRequest(BaseModel):
    symbol: str
    direction: str
    seen_at: dt.datetime | None = None
    setup_tag: str | None = None
    skip_reason: str
    hypothetical_entry: float | None = None
    hypothetical_exit: float | None = None
    notes: str | None = None


class AddViewRequest(BaseModel):
    name: str
    thesis: str | None = None
