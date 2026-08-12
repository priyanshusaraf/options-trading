"""Read-only execution-plane port used to validate ledger manual-fill claims."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Trade
from app.db.session import SessionLocal


def scoped_trade_exists(trade_id: str, owner_id: str, broker_account_id: str) -> bool:
    """Prove a claimed trade belongs to this owner/account before the ledger writes."""
    try:
        numeric_id = int(trade_id)
    except (TypeError, ValueError):
        return False
    with SessionLocal() as session:
        return bool(session.scalar(select(Trade.id).where(
            Trade.id == numeric_id,
            Trade.owner_id == owner_id,
            Trade.broker_account_id == broker_account_id,
        ).exists().select()))
