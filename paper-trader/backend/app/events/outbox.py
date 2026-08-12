"""Portable transaction-bound durable outbox for the three private planes.

The repository owns delivery order, consumer fencing and payload validation.  It
does not own a projection: producers append a bounded change fact in the same
transaction as their domain mutation, and consumers reload durable state.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import math
import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Any, Iterator

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

MAX_PAYLOAD_BYTES = 8192
_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_SECRET_PARTS = frozenset({
    "access_token", "refresh_token", "token", "password", "secret", "api_key",
    "authorization", "cookie", "credential", "oauth", "session_token",
})


class OutboxValidationError(ValueError):
    """The event cannot be represented by the bounded delivery contract."""


class DuplicateProducerConflict(OutboxValidationError):
    """A producer identity was reused for different immutable event content."""


class ClaimUnavailable(RuntimeError):
    """Another healthy dispatcher owns this consumer cursor."""


class StaleClaim(RuntimeError):
    """A former dispatcher attempted to advance a cursor after takeover."""


@dataclass(frozen=True)
class PrincipalScope:
    owner_id: str
    broker_account_id: str | None = None


@dataclass(frozen=True)
class EventIdentity:
    event_id: str
    plane_offset: int
    aggregate_sequence: int
    content_address: str


@dataclass(frozen=True)
class OutboxModels:
    StreamHead: type
    Event: type
    ConsumerCursor: type
    ConsumerReceipt: type
    RetentionWatermark: type
    prefix: str


@dataclass(frozen=True)
class ClaimedBatch:
    consumer_id: str
    claim_token: str
    events: tuple[Any, ...]


@dataclass(frozen=True)
class ScopedRead:
    events: tuple[Any, ...]
    resync_required: bool
    high_water: int


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def define_outbox_models(base: type, prefix: str) -> OutboxModels:
    """Register the same relational contract on one plane's own metadata."""
    if not _NAME.fullmatch(prefix):
        raise ValueError("outbox table prefix must be a bounded lowercase name")

    class StreamHead(base):
        __tablename__ = f"{prefix}_outbox_stream_head"
        aggregate_type: Mapped[str] = mapped_column(String(64), primary_key=True)
        aggregate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
        last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                    server_default=text("0"))
        updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=_now)
        __table_args__ = (
            CheckConstraint("last_sequence >= 0", name=f"ck_{prefix}_outbox_head_sequence"),
        )

    class Event(base):
        __tablename__ = f"{prefix}_outbox_event"
        plane_offset: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
        classification: Mapped[str] = mapped_column(String(16), nullable=False)
        scope_key: Mapped[str] = mapped_column(String(160), nullable=False)
        owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
        broker_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
        aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
        aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False)
        aggregate_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
        event_type: Mapped[str] = mapped_column(String(96), nullable=False)
        schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
        payload_json: Mapped[str] = mapped_column(Text, nullable=False)
        content_address: Mapped[str] = mapped_column(String(71), nullable=False)
        producer_key: Mapped[str] = mapped_column(String(128), nullable=False)
        created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=_now)
        retention_class: Mapped[str] = mapped_column(String(24), nullable=False,
                                                      default="projection",
                                                      server_default=text("'projection'"))
        __table_args__ = (
            UniqueConstraint("aggregate_type", "aggregate_id", "aggregate_sequence",
                             name=f"uq_{prefix}_outbox_aggregate_sequence"),
            UniqueConstraint("producer_key", name=f"uq_{prefix}_outbox_producer"),
            CheckConstraint("plane_offset > 0", name=f"ck_{prefix}_outbox_offset"),
            CheckConstraint("aggregate_sequence > 0", name=f"ck_{prefix}_outbox_sequence"),
            CheckConstraint("schema_version > 0", name=f"ck_{prefix}_outbox_schema_version"),
            CheckConstraint("classification IN ('private', 'market_public')",
                            name=f"ck_{prefix}_outbox_classification"),
            CheckConstraint(
                "(classification = 'private' AND owner_id IS NOT NULL) OR "
                "(classification = 'market_public' AND owner_id IS NULL "
                "AND broker_account_id IS NULL)",
                name=f"ck_{prefix}_outbox_scope_shape",
            ),
            Index(f"ix_{prefix}_outbox_offset", "plane_offset"),
            Index(f"ix_{prefix}_outbox_scope_offset", "scope_key", "plane_offset"),
            Index(f"ix_{prefix}_outbox_retention", "retention_class", "created_at", "plane_offset"),
            {"sqlite_autoincrement": True},
        )

    class ConsumerCursor(base):
        __tablename__ = f"{prefix}_outbox_consumer_cursor"
        consumer_id: Mapped[str] = mapped_column(String(96), primary_key=True)
        last_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                  server_default=text("0"))
        lease_owner: Mapped[str | None] = mapped_column(String(96), nullable=True)
        lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
        lease_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
        heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
        last_error: Mapped[str] = mapped_column(String(200), nullable=False, default="",
                                                server_default=text("''"))
        updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=_now)
        __table_args__ = (
            CheckConstraint("last_offset >= 0", name=f"ck_{prefix}_outbox_cursor_offset"),
            CheckConstraint(
                "(lease_token IS NULL AND lease_owner IS NULL AND lease_expires_at IS NULL) OR "
                "(lease_token IS NOT NULL AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
                name=f"ck_{prefix}_outbox_cursor_lease_shape",
            ),
            Index(f"ix_{prefix}_outbox_cursor_expiry", "lease_expires_at"),
        )

    class ConsumerReceipt(base):
        __tablename__ = f"{prefix}_outbox_consumer_receipt"
        consumer_id: Mapped[str] = mapped_column(String(96), primary_key=True)
        event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
        effect_key: Mapped[str] = mapped_column(String(128), nullable=False)
        created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=_now)
        __table_args__ = (
            UniqueConstraint("consumer_id", "effect_key",
                             name=f"uq_{prefix}_outbox_consumer_effect"),
            Index(f"ix_{prefix}_outbox_receipt_created", "created_at"),
        )

    class RetentionWatermark(base):
        __tablename__ = f"{prefix}_outbox_retention_watermark"
        scope_key: Mapped[str] = mapped_column(String(160), primary_key=True)
        pruned_through_offset: Mapped[int] = mapped_column(Integer, nullable=False)
        updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=_now)
        __table_args__ = (
            CheckConstraint("pruned_through_offset > 0",
                            name=f"ck_{prefix}_outbox_watermark_offset"),
        )

    for cls, suffix in ((StreamHead, "StreamHead"), (Event, "Event"),
                        (ConsumerCursor, "ConsumerCursor"),
                        (ConsumerReceipt, "ConsumerReceipt"),
                        (RetentionWatermark, "RetentionWatermark")):
        cls.__name__ = f"{prefix.title().replace('_', '')}Outbox{suffix}"
        cls.__qualname__ = cls.__name__
    return OutboxModels(StreamHead, Event, ConsumerCursor, ConsumerReceipt,
                        RetentionWatermark, prefix)


def _bounded_name(value: str, label: str, *, limit: int = 96) -> str:
    value = str(value or "").strip()
    if len(value) > limit or not _NAME.fullmatch(value):
        raise OutboxValidationError(f"{label} must be a bounded lowercase name")
    return value


def _scope_part(value: str | None, label: str, *, required: bool = True,
                limit: int = 160) -> str | None:
    if value is None:
        if required:
            raise OutboxValidationError(f"{label} is required")
        return None
    value = value.strip()
    if not value or len(value) > limit or not _SCOPE.fullmatch(value):
        raise OutboxValidationError(f"{label} must be a non-empty bounded scope")
    return value


def _reject_unsafe_json(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if key_text in _SECRET_PARTS or any(
                part in _SECRET_PARTS for part in re.split(r"[^a-z0-9]+", key_text) if part
            ):
                raise OutboxValidationError(f"secret-like payload key at {path}.{key}")
            _reject_unsafe_json(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_unsafe_json(child, path=f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise OutboxValidationError(f"non-finite JSON number at {path}")
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise OutboxValidationError(f"non-JSON value at {path}")


class OutboxRepository:
    """Shared semantics over one injected plane-specific model bundle."""

    def __init__(self, models: OutboxModels, *, plane: str,
                 allowed_event_types: set[str] | frozenset[str],
                 market_public_event_types: set[str] | frozenset[str] = frozenset()):
        self.models = models
        self.plane = _bounded_name(plane, "plane", limit=32)
        self.allowed_event_types = frozenset(
            _bounded_name(value, "event_type") for value in allowed_event_types)
        self.market_public_event_types = frozenset(
            _bounded_name(value, "public event_type") for value in market_public_event_types)
        if not self.market_public_event_types <= self.allowed_event_types:
            raise ValueError("public event types must be part of the closed event allowlist")

    @contextlib.contextmanager
    def writer(self, session: Session) -> Iterator[Session]:
        """Declare one caller-owned transaction as an outbox unit of work."""
        marker = f"outbox_writer:{id(self)}"
        previous = session.info.get(marker, 0)
        session.info[marker] = previous + 1
        try:
            if session.in_transaction():
                yield session
            else:
                with session.begin():
                    yield session
        finally:
            if previous:
                session.info[marker] = previous
            else:
                session.info.pop(marker, None)

    def _owns_transaction(self, session: Session) -> bool:
        return bool(session.info.get(f"outbox_writer:{id(self)}")) and session.in_transaction()

    def _immutable(self, *, classification: str, owner_id: str | None,
                   broker_account_id: str | None, aggregate_type: str, aggregate_id: str,
                   event_type: str, schema_version: int, payload_json: str,
                   retention_class: str) -> dict[str, Any]:
        return {
            "classification": classification,
            "owner_id": owner_id,
            "broker_account_id": broker_account_id,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "schema_version": schema_version,
            "payload_json": payload_json,
            "retention_class": retention_class,
        }

    def append(self, session: Session, *, classification: str, owner_id: str | None,
               broker_account_id: str | None, aggregate_type: str, aggregate_id: str,
               event_type: str, schema_version: int, payload: dict[str, Any],
               producer_key: str, retention_class: str = "projection") -> EventIdentity:
        if not self._owns_transaction(session):
            raise OutboxValidationError("append requires an explicit outbox transaction owner")
        if classification not in {"private", "market_public"}:
            raise OutboxValidationError("classification must be private or market_public")
        event_type = _bounded_name(event_type, "event_type")
        if event_type not in self.allowed_event_types:
            raise OutboxValidationError("event_type is outside the closed allowlist")
        aggregate_type = _bounded_name(aggregate_type, "aggregate_type", limit=64)
        aggregate_id = _scope_part(aggregate_id, "aggregate_id", limit=128) or ""
        producer_key = _scope_part(producer_key, "producer_key", limit=128) or ""
        retention_class = _bounded_name(retention_class, "retention_class", limit=24)
        if not isinstance(schema_version, int) or schema_version <= 0:
            raise OutboxValidationError("schema_version must be positive")
        if classification == "private":
            owner_id = _scope_part(owner_id, "owner_id", limit=64)
            broker_account_id = _scope_part(
                broker_account_id, "broker_account_id", required=False, limit=64)
            scope_key = f"private:{owner_id}:{broker_account_id or '*'}"
        else:
            if event_type not in self.market_public_event_types:
                raise OutboxValidationError("market_public event_type is outside the public allowlist")
            if owner_id is not None or broker_account_id is not None:
                raise OutboxValidationError("market_public events cannot carry private scope")
            scope_key = "market_public"
        if not isinstance(payload, dict):
            raise OutboxValidationError("payload must be a JSON object")
        _reject_unsafe_json(payload)
        try:
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise OutboxValidationError("payload is not canonical finite JSON") from exc
        if len(payload_json.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise OutboxValidationError("payload exceeds the bounded outbox size")

        immutable = self._immutable(
            classification=classification, owner_id=owner_id,
            broker_account_id=broker_account_id, aggregate_type=aggregate_type,
            aggregate_id=aggregate_id, event_type=event_type,
            schema_version=schema_version, payload_json=payload_json,
            retention_class=retention_class,
        )
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            # Producer identity is global within a plane, while stream-head locks are
            # aggregate-local. Serialize the small identity namespace before either
            # lookup so same-key writers on different aggregates cannot race into the
            # unique constraint. The lock is transaction-scoped and releases on rollback.
            session.execute(select(func.pg_advisory_xact_lock(
                func.hashtextextended(producer_key, 0))))
        existing = session.scalar(select(self.models.Event).where(
            self.models.Event.producer_key == producer_key))
        if existing is not None:
            actual = self._immutable(**{
                key: getattr(existing, key) for key in immutable
            })
            if actual != immutable:
                raise DuplicateProducerConflict(
                    "producer_key retry changed immutable event content")
            return EventIdentity(existing.event_id, existing.plane_offset,
                                 existing.aggregate_sequence, existing.content_address)

        head = None
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            session.execute(postgresql_insert(self.models.StreamHead).values(
                aggregate_type=aggregate_type, aggregate_id=aggregate_id,
                last_sequence=0, updated_at=_now(),
            ).on_conflict_do_nothing(index_elements=("aggregate_type", "aggregate_id")))
            head = session.scalar(select(self.models.StreamHead).where(
                self.models.StreamHead.aggregate_type == aggregate_type,
                self.models.StreamHead.aggregate_id == aggregate_id,
            ).with_for_update())
        else:
            head = session.get(self.models.StreamHead, (aggregate_type, aggregate_id))
        if head is None:
            head = self.models.StreamHead(aggregate_type=aggregate_type,
                                          aggregate_id=aggregate_id,
                                          last_sequence=0, updated_at=_now())
            session.add(head)
            session.flush()
        head.last_sequence += 1
        head.updated_at = _now()
        # The head lock serializes every producer targeting this aggregate. Re-read
        # the producer identity after acquiring it so an exact concurrent retry
        # observes the committed original rather than leaking its unique violation.
        existing = session.scalar(select(self.models.Event).where(
            self.models.Event.producer_key == producer_key))
        if existing is not None:
            actual = self._immutable(**{
                key: getattr(existing, key) for key in immutable
            })
            if actual != immutable:
                raise DuplicateProducerConflict(
                    "producer_key retry changed immutable event content")
            head.last_sequence -= 1
            return EventIdentity(existing.event_id, existing.plane_offset,
                                 existing.aggregate_sequence, existing.content_address)
        digest_doc = dict(immutable, aggregate_sequence=head.last_sequence)
        digest = "sha256:" + hashlib.sha256(json.dumps(
            digest_doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        event = self.models.Event(
            event_id=str(uuid.uuid4()), scope_key=scope_key,
            aggregate_sequence=head.last_sequence, producer_key=producer_key,
            content_address=digest, created_at=_now(), **immutable,
        )
        session.add(event)
        session.flush()
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            # pg_notify is transactional: delivery occurs only after commit.
            session.execute(select(func.pg_notify(
                f"strategy_os_{self.plane}_outbox",
                json.dumps({"plane": self.plane, "high_water": event.plane_offset},
                           separators=(",", ":")),
            )))
        return EventIdentity(event.event_id, event.plane_offset,
                             event.aggregate_sequence, event.content_address)

    def read_scoped_after(self, session: Session, principal_scope: PrincipalScope, *,
                          offset: int, limit: int,
                          resume_cursor_present: bool = False) -> ScopedRead:
        if offset < 0 or limit < 1 or limit > 500:
            raise OutboxValidationError("invalid scoped read bounds")
        owner_id = _scope_part(principal_scope.owner_id, "owner_id", limit=64)
        account_id = _scope_part(principal_scope.broker_account_id,
                                 "broker_account_id", required=False, limit=64)
        scope_conditions = [
            self.models.Event.classification == "private",
            self.models.Event.owner_id == owner_id,
        ]
        if account_id is None:
            scope_conditions.append(self.models.Event.broker_account_id.is_(None))
        else:
            scope_conditions.append(or_(
                self.models.Event.broker_account_id == account_id,
                self.models.Event.broker_account_id.is_(None),
            ))
        rows = tuple(session.scalars(select(self.models.Event).where(
            *scope_conditions, self.models.Event.plane_offset > offset,
        ).order_by(self.models.Event.plane_offset).limit(limit)))
        # Plane offsets are intentionally global and therefore sparse inside one
        # tenant scope. Only a scope-local prune marker proves that a resume
        # cursor lost data; gaps between visible offsets may belong to anyone.
        relevant_scope_keys = [f"private:{owner_id}:*"]
        if account_id is not None:
            relevant_scope_keys.append(f"private:{owner_id}:{account_id}")
        pruned_through = session.scalar(select(func.max(
            self.models.RetentionWatermark.pruned_through_offset)).where(
                self.models.RetentionWatermark.scope_key.in_(relevant_scope_keys))) or 0
        surviving_high_water = session.scalar(select(func.max(
            self.models.Event.plane_offset)).where(*scope_conditions)) or 0
        high_water = max(int(surviving_high_water), int(pruned_through))
        resync = bool(resume_cursor_present and pruned_through > offset)
        return ScopedRead(rows, resync, int(high_water))

    def claim_batch(self, session: Session, *, consumer_id: str, lease_owner: str,
                    limit: int, lease_seconds: int, now: dt.datetime | None = None) -> ClaimedBatch:
        consumer_id = _bounded_name(consumer_id, "consumer_id")
        lease_owner = _scope_part(lease_owner, "lease_owner", limit=96) or ""
        if limit < 1 or limit > 500 or lease_seconds < 1 or lease_seconds > 300:
            raise OutboxValidationError("invalid claim bounds")
        now = now or _now()
        query = select(self.models.ConsumerCursor).where(
            self.models.ConsumerCursor.consumer_id == consumer_id)
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            session.execute(postgresql_insert(self.models.ConsumerCursor).values(
                consumer_id=consumer_id, last_offset=0, updated_at=now,
            ).on_conflict_do_nothing(index_elements=("consumer_id",)))
            query = query.with_for_update(skip_locked=True)
        cursor = session.scalar(query)
        if cursor is None:
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                raise ClaimUnavailable(f"consumer {consumer_id!r} is being claimed")
            cursor = self.models.ConsumerCursor(consumer_id=consumer_id, last_offset=0,
                                                 updated_at=now)
            session.add(cursor)
            session.flush()
        if cursor.lease_token and cursor.lease_expires_at and cursor.lease_expires_at > now:
            raise ClaimUnavailable(f"consumer {consumer_id!r} has a healthy lease")
        token = secrets.token_hex(24)
        cursor.lease_owner = lease_owner
        cursor.lease_token = token
        cursor.lease_expires_at = now + dt.timedelta(seconds=lease_seconds)
        cursor.heartbeat_at = now
        cursor.updated_at = now
        events = tuple(session.scalars(select(self.models.Event).where(
            self.models.Event.plane_offset > cursor.last_offset,
        ).order_by(self.models.Event.plane_offset).limit(limit)))
        return ClaimedBatch(consumer_id, token, events)

    def ack(self, session: Session, claim_token: str, event_id: str, *, effect_key: str,
            now: dt.datetime | None = None) -> bool:
        cursor = session.scalar(select(self.models.ConsumerCursor).where(
            self.models.ConsumerCursor.lease_token == claim_token).with_for_update())
        if cursor is None:
            raise StaleClaim("claim token no longer owns a cursor")
        now = now or _now()
        if cursor.lease_expires_at is None or cursor.lease_expires_at <= now:
            raise StaleClaim("claim token is expired")
        event = session.scalar(select(self.models.Event).where(
            self.models.Event.event_id == event_id))
        if event is None:
            raise OutboxValidationError("cannot acknowledge an unknown event")
        if event.plane_offset <= cursor.last_offset:
            return False
        next_offset = session.scalar(select(func.min(self.models.Event.plane_offset)).where(
            self.models.Event.plane_offset > cursor.last_offset))
        if next_offset != event.plane_offset:
            raise OutboxValidationError("cursor acknowledgements must advance in plane order")
        effect_key = _scope_part(effect_key, "effect_key", limit=128) or ""
        existing = session.get(self.models.ConsumerReceipt, (cursor.consumer_id, event_id))
        if existing is None:
            session.add(self.models.ConsumerReceipt(
                consumer_id=cursor.consumer_id, event_id=event_id,
                effect_key=effect_key, created_at=_now()))
        elif existing.effect_key != effect_key:
            raise OutboxValidationError("event receipt effect identity changed")
        cursor.last_offset = event.plane_offset
        cursor.heartbeat_at = now
        cursor.updated_at = cursor.heartbeat_at
        return True

    def heartbeat(self, session: Session, claim_token: str, *, lease_seconds: int,
                  now: dt.datetime | None = None) -> dt.datetime:
        if lease_seconds < 1 or lease_seconds > 300:
            raise OutboxValidationError("invalid lease heartbeat bounds")
        now = now or _now()
        cursor = session.scalar(select(self.models.ConsumerCursor).where(
            self.models.ConsumerCursor.lease_token == claim_token).with_for_update())
        if (cursor is None or cursor.lease_expires_at is None
                or cursor.lease_expires_at <= now):
            raise StaleClaim("claim token is stale or expired")
        cursor.heartbeat_at = now
        cursor.lease_expires_at = now + dt.timedelta(seconds=lease_seconds)
        cursor.updated_at = now
        return cursor.lease_expires_at

    def release(self, session: Session, claim_token: str, *, error: str = "") -> None:
        cursor = session.scalar(select(self.models.ConsumerCursor).where(
            self.models.ConsumerCursor.lease_token == claim_token).with_for_update())
        if cursor is None:
            raise StaleClaim("claim token no longer owns a cursor")
        cursor.lease_owner = cursor.lease_token = cursor.lease_expires_at = None
        cursor.last_error = str(error)[:200]
        cursor.updated_at = _now()

    def cleanup(self, session: Session, *, older_than: dt.datetime, now: dt.datetime,
                abandoned_after_seconds: int, limit: int) -> int:
        if limit < 1 or limit > 10_000 or abandoned_after_seconds < 1:
            raise OutboxValidationError("invalid cleanup bounds")
        healthy_after = now - dt.timedelta(seconds=abandoned_after_seconds)
        pin = session.scalar(select(func.min(self.models.ConsumerCursor.last_offset)).where(
            self.models.ConsumerCursor.heartbeat_at >= healthy_after))
        query = select(self.models.Event.plane_offset).where(
            self.models.Event.created_at < older_than)
        if pin is not None:
            query = query.where(self.models.Event.plane_offset <= pin)
        offsets = tuple(session.scalars(query.order_by(
            self.models.Event.plane_offset).limit(limit)))
        if not offsets:
            return 0
        removed = tuple(session.scalars(select(self.models.Event).where(
            self.models.Event.plane_offset.in_(offsets))))
        for scope_key in {event.scope_key for event in removed}:
            highest = max(event.plane_offset for event in removed
                          if event.scope_key == scope_key)
            watermark = session.get(self.models.RetentionWatermark, scope_key)
            if watermark is None:
                session.add(self.models.RetentionWatermark(
                    scope_key=scope_key, pruned_through_offset=highest, updated_at=now))
            elif highest > watermark.pruned_through_offset:
                watermark.pruned_through_offset = highest
                watermark.updated_at = now
        result = session.execute(delete(self.models.Event).where(
            self.models.Event.plane_offset.in_(offsets)))
        return int(result.rowcount or 0)

    def metrics(self, session: Session, *, now: dt.datetime | None = None) -> dict[str, Any]:
        """Bounded plane/host aggregates with no scope or identifier labels."""
        now = now or _now()
        high_water = int(session.scalar(select(func.max(
            self.models.Event.plane_offset))) or 0)
        oldest = session.scalar(select(func.min(self.models.Event.created_at)))
        cursors = list(session.execute(select(
            self.models.ConsumerCursor.last_offset,
            self.models.ConsumerCursor.lease_expires_at,
        )))
        return {
            "plane": self.plane,
            "event_count": int(session.scalar(select(func.count()).select_from(
                self.models.Event)) or 0),
            "high_water_offset": high_water,
            "oldest_event_age_seconds": max(0.0, (now - oldest).total_seconds())
            if oldest else None,
            "max_cursor_lag": max((high_water - int(row[0]) for row in cursors), default=0),
            "active_consumer_leases": sum(
                1 for row in cursors if row[1] is not None and row[1] > now),
        }
