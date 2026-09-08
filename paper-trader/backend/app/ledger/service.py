"""Snapshot and artifact persistence.

No FastAPI here — the routes layer owns HTTP status codes, this layer owns the
concurrency rule.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.concurrency import caller_owned_savepoint
from app.ledger.models import LedgerArtifact, LedgerManualFill, LedgerSnapshot
from app.events.planes import ledger_outbox


class VersionConflict(Exception):
    """The caller's base_version does not match what is stored."""

    def __init__(self, current: int):
        super().__init__(f"version conflict: stored is {current}")
        self.current = current


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def read_snapshot(sm, *, owner_id: str, broker_account_id: str) -> tuple[int, str] | None:
    with sm() as s:
        row = s.get(LedgerSnapshot, (owner_id, broker_account_id, 1))
        return None if row is None else (row.version, row.payload)


def write_snapshot(sm, payload: str, base_version: int | None, *, owner_id: str,
                   broker_account_id: str) -> int:
    """Compare-and-set. `base_version=None` asserts "no snapshot exists yet",
    which is what makes a first write racing two devices safe.

    Returns the new version. Raises VersionConflict on a mismatch, leaving the
    stored payload untouched."""
    outbox = ledger_outbox()
    with sm() as s, outbox.writer(s):
        key = (LedgerSnapshot.owner_id == owner_id,
               LedgerSnapshot.broker_account_id == broker_account_id,
               LedgerSnapshot.id == 1)
        if base_version is None:
            try:
                with caller_owned_savepoint(s, scope="ledger_snapshot"):
                    s.add(LedgerSnapshot(
                        owner_id=owner_id, broker_account_id=broker_account_id,
                        id=1, version=1, payload=payload, updated_at=_now()))
                    s.flush()
                    outbox.append(
                        s, classification="private", owner_id=owner_id,
                        broker_account_id=broker_account_id, aggregate_type="snapshot",
                        aggregate_id="1", event_type="ledger.snapshot.changed",
                        schema_version=1, payload={"projection": "ledger_snapshot", "version": 1},
                        producer_key=f"snapshot:{owner_id}:{broker_account_id}:1")
                return 1
            except IntegrityError:
                current = s.scalar(select(LedgerSnapshot.version).where(*key))
                if current is None:
                    raise
                raise VersionConflict(int(current))

        changed = s.execute(update(LedgerSnapshot).where(
            *key, LedgerSnapshot.version == base_version).values(
                version=base_version + 1, payload=payload, updated_at=_now()))
        if changed.rowcount == 1:
            outbox.append(
                s, classification="private", owner_id=owner_id,
                broker_account_id=broker_account_id, aggregate_type="snapshot",
                aggregate_id="1", event_type="ledger.snapshot.changed",
                schema_version=1,
                payload={"projection": "ledger_snapshot", "version": base_version + 1},
                producer_key=f"snapshot:{owner_id}:{broker_account_id}:{base_version + 1}")
            return base_version + 1
        current = s.scalar(select(LedgerSnapshot.version).where(*key))
        raise VersionConflict(int(current or 0))


def put_artifact(sm, artifact_id: str, mime: str, data: bytes, *, owner_id: str,
                 broker_account_id: str) -> str:
    outbox = ledger_outbox()
    with sm() as s, outbox.writer(s):
        row = s.get(LedgerArtifact, (owner_id, broker_account_id, artifact_id))
        if row is None:
            s.add(LedgerArtifact(owner_id=owner_id, broker_account_id=broker_account_id,
                                 id=artifact_id, mime=mime, bytes=data,
                                 created_at=_now()))
        else:
            row.mime, row.bytes = mime, data
        content = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
        outbox.append(
            s, classification="private", owner_id=owner_id,
            broker_account_id=broker_account_id, aggregate_type="artifact",
            aggregate_id=artifact_id, event_type="ledger.artifact.changed",
            schema_version=1,
            payload={"projection": "ledger_artifact", "content_address": content,
                     "mime": mime[:64]},
            producer_key=f"artifact:{artifact_id}:{uuid.uuid4().hex}")
    return artifact_id


def get_artifact(sm, artifact_id: str, *, owner_id: str,
                 broker_account_id: str) -> tuple[str, bytes] | None:
    with sm() as s:
        row = s.get(LedgerArtifact, (owner_id, broker_account_id, artifact_id))
        return None if row is None else (row.mime, row.bytes)


def delete_artifact(sm, artifact_id: str, *, owner_id: str, broker_account_id: str) -> bool:
    outbox = ledger_outbox()
    with sm() as s, outbox.writer(s):
        row = s.get(LedgerArtifact, (owner_id, broker_account_id, artifact_id))
        if row is None:
            return False
        s.delete(row)
        outbox.append(
            s, classification="private", owner_id=owner_id,
            broker_account_id=broker_account_id, aggregate_type="artifact",
            aggregate_id=artifact_id, event_type="ledger.artifact.changed",
            schema_version=1, payload={"projection": "ledger_artifact", "state": "deleted"},
            producer_key=f"artifact-delete:{artifact_id}:{uuid.uuid4().hex}")
        return True


# ── Manual fills ──────────────────────────────────────────────────────────


class AlreadyClaimed(Exception):
    """This fill has already been reasoned about. Never silently reassign it."""

    def __init__(self, trade_id: str):
        super().__init__(f"already claimed by {trade_id}")
        self.trade_id = trade_id


def list_manual_fills(sm, unclaimed: bool = True, *, owner_id: str,
                      broker_account_id: str) -> list[dict]:
    with sm() as s:
        q = select(LedgerManualFill).where(
            LedgerManualFill.owner_id == owner_id,
            LedgerManualFill.broker_account_id == broker_account_id)
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


def claim_manual_fill(sm, order_id: str, trade_id: str, *, owner_id: str,
                      broker_account_id: str, trade_exists) -> bool:
    """Returns False if there is no such fill. Raises AlreadyClaimed if the
    owner has already supplied reasoning for it."""
    outbox = ledger_outbox()
    with sm() as s, outbox.writer(s):
        if not trade_exists(trade_id, owner_id, broker_account_id):
            return False
        claimed = s.execute(update(LedgerManualFill).where(
            LedgerManualFill.owner_id == owner_id,
            LedgerManualFill.broker_account_id == broker_account_id,
            LedgerManualFill.order_id == order_id,
            LedgerManualFill.claimed_trade.is_(None),
        ).values(claimed_trade=trade_id))
        if claimed.rowcount == 1:
            outbox.append(
                s, classification="private", owner_id=owner_id,
                broker_account_id=broker_account_id, aggregate_type="manual_fill",
                aggregate_id=order_id, event_type="ledger.manual_fill.changed",
                schema_version=1,
                payload={"projection": "manual_fill", "state": "claimed"},
                producer_key=f"manual-fill:{owner_id}:{broker_account_id}:{order_id}:claimed")
            return True
        existing = s.scalar(select(LedgerManualFill.claimed_trade).where(
            LedgerManualFill.owner_id == owner_id,
            LedgerManualFill.broker_account_id == broker_account_id,
            LedgerManualFill.order_id == order_id))
        if existing:
            raise AlreadyClaimed(existing)
        return False
