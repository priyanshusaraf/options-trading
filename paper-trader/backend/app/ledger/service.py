"""Snapshot and artifact persistence.

No FastAPI here — the routes layer owns HTTP status codes, this layer owns the
concurrency rule.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.ledger.models import LedgerArtifact, LedgerManualFill, LedgerSnapshot


class VersionConflict(Exception):
    """The caller's base_version does not match what is stored."""

    def __init__(self, current: int):
        super().__init__(f"version conflict: stored is {current}")
        self.current = current


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def read_snapshot(sm) -> tuple[int, str] | None:
    with sm() as s:
        row = s.get(LedgerSnapshot, 1)
        return None if row is None else (row.version, row.payload)


def write_snapshot(sm, payload: str, base_version: int | None) -> int:
    """Compare-and-set. `base_version=None` asserts "no snapshot exists yet",
    which is what makes a first write racing two devices safe.

    Returns the new version. Raises VersionConflict on a mismatch, leaving the
    stored payload untouched."""
    with sm() as s, s.begin():
        row = s.get(LedgerSnapshot, 1)
        if row is None:
            if base_version is not None:
                raise VersionConflict(0)
            s.add(LedgerSnapshot(id=1, version=1, payload=payload, updated_at=_now()))
            return 1
        if base_version != row.version:
            raise VersionConflict(row.version)
        row.version += 1
        row.payload = payload
        row.updated_at = _now()
        return row.version


def put_artifact(sm, artifact_id: str, mime: str, data: bytes) -> str:
    with sm() as s, s.begin():
        row = s.get(LedgerArtifact, artifact_id)
        if row is None:
            s.add(LedgerArtifact(id=artifact_id, mime=mime, bytes=data,
                                 created_at=_now()))
        else:
            row.mime, row.bytes = mime, data
    return artifact_id


def get_artifact(sm, artifact_id: str) -> tuple[str, bytes] | None:
    with sm() as s:
        row = s.get(LedgerArtifact, artifact_id)
        return None if row is None else (row.mime, row.bytes)


def delete_artifact(sm, artifact_id: str) -> bool:
    with sm() as s, s.begin():
        row = s.get(LedgerArtifact, artifact_id)
        if row is None:
            return False
        s.delete(row)
        return True


# ── Manual fills ──────────────────────────────────────────────────────────


class AlreadyClaimed(Exception):
    """This fill has already been reasoned about. Never silently reassign it."""

    def __init__(self, trade_id: str):
        super().__init__(f"already claimed by {trade_id}")
        self.trade_id = trade_id


def list_manual_fills(sm, unclaimed: bool = True) -> list[dict]:
    with sm() as s:
        q = select(LedgerManualFill)
        if unclaimed:
            q = q.where(LedgerManualFill.claimed_trade.is_(None))
        return [{
            "order_id": r.order_id,
            "tradingsymbol": r.tradingsymbol,
            "exchange": r.exchange,
            "product": r.product,
            "side": r.side,
            "qty": r.qty,
            "avg_price": r.avg_price,
            "order_ts": r.order_ts.isoformat() if r.order_ts else None,
            "verdict": r.verdict,
            "claimed_trade": r.claimed_trade,
        } for r in s.scalars(q.order_by(LedgerManualFill.order_ts))]


def claim_manual_fill(sm, order_id: str, trade_id: str) -> bool:
    """Returns False if there is no such fill. Raises AlreadyClaimed if the
    owner has already supplied reasoning for it."""
    with sm() as s, s.begin():
        row = s.get(LedgerManualFill, order_id)
        if row is None:
            return False
        if row.claimed_trade:
            raise AlreadyClaimed(row.claimed_trade)
        row.claimed_trade = trade_id
        return True
