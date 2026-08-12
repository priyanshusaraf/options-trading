"""Polling-authoritative replica delivery and scoped resume helpers."""
from __future__ import annotations

import base64
import asyncio
import datetime as dt
import hashlib
import hmac
import json
import select as select_io
from dataclasses import dataclass
from typing import Callable

from app.events.outbox import ClaimUnavailable, OutboxRepository, PrincipalScope
from app.ws.manager import PUBLIC_MARKET, WSManager


class NotificationConnection:
    def __init__(self, raw):
        self._raw = raw
        self.driver = raw.driver_connection

    def fileno(self):
        return self.driver.fileno()

    def notifies(self, *args, **kwargs):
        return self.driver.notifies(*args, **kwargs)

    def wait_hint(self, listener, timeout: float) -> int | None:
        if not select_io.select([self.driver], [], [], timeout)[0]:
            return None
        notifications = list(self.driver.notifies(timeout=0, stop_after=1))
        return listener.parse_hint(notifications[0].payload) if notifications else None

    def close(self):
        self._raw.close()


class PostgresNotificationListener:
    """Validate bounded LISTEN payloads; callers still poll after every hint."""

    def __init__(self, *, plane: str):
        if not isinstance(plane, str) or not plane.isidentifier() or len(plane) > 32:
            raise ValueError("notification plane must be a bounded identifier")
        self.plane = plane
        self.channel = f"strategy_os_{plane}_outbox"

    def parse_hint(self, payload: str) -> int | None:
        if not isinstance(payload, str) or len(payload) > 256:
            return None
        try:
            value = json.loads(payload)
            high_water = value.get("high_water")
            if (value.get("plane") != self.plane or not isinstance(high_water, int)
                    or high_water < 1):
                return None
            return high_water
        except Exception:
            return None

    def connect(self, engine):
        """Return a dedicated DBAPI AUTOCOMMIT connection subscribed to one plane."""
        if engine.dialect.name != "postgresql":
            return None
        raw = engine.raw_connection()
        connection = raw.driver_connection
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(f'LISTEN "{self.channel}"')
        cursor.close()
        # Keep SQLAlchemy's pool wrapper alive until the dedicated connection closes.
        return NotificationConnection(raw)


class ResumeCursorCodec:
    """Opaque HMAC cursor bound to the resolved plane and principal scope."""

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("resume cursor secret must contain at least 32 bytes")
        self.secret = secret

    @staticmethod
    def _scope(scope: PrincipalScope) -> list[str | None]:
        return [scope.owner_id, scope.broker_account_id]

    def encode(self, *, plane: str, scope: PrincipalScope, offset: int) -> str:
        body = json.dumps({"v": 1, "p": plane, "s": self._scope(scope), "o": int(offset)},
                          sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self.secret, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body + signature).decode().rstrip("=")

    def decode(self, token: str | None, *, plane: str,
               scope: PrincipalScope) -> int | None:
        if not token or len(token) > 512:
            return None
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            canonical = base64.urlsafe_b64encode(raw).decode().rstrip("=")
            if not hmac.compare_digest(token, canonical):
                return None
            body, signature = raw[:-32], raw[-32:]
            if not hmac.compare_digest(
                signature, hmac.new(self.secret, body, hashlib.sha256).digest()
            ):
                return None
            value = json.loads(body)
            if value != {"o": value.get("o"), "p": plane,
                         "s": self._scope(scope), "v": 1}:
                return None
            offset = value["o"]
            return offset if isinstance(offset, int) and offset >= 0 else None
        except Exception:
            return None


class CacheInvalidator:
    """Replica-local, tenant-scoped monotonic durable version invalidation."""

    def __init__(self):
        self._sequences: dict[tuple[str, str | None, str, str], int] = {}
        self._versions: dict[tuple[str, str | None, str], int] = {}

    @staticmethod
    def _namespace_key(scope: PrincipalScope, namespace: str):
        return scope.owner_id, scope.broker_account_id, namespace

    def apply(self, *, scope: PrincipalScope, namespace: str, aggregate_type: str,
              aggregate_id: str,
              aggregate_sequence: int, durable_version: int) -> bool:
        aggregate_key = (*self._namespace_key(scope, namespace), aggregate_type, aggregate_id)
        if aggregate_sequence <= self._sequences.get(aggregate_key, 0):
            return False
        self._sequences[aggregate_key] = aggregate_sequence
        key = self._namespace_key(scope, namespace)
        self._versions[key] = max(durable_version, self._versions.get(key, durable_version))
        return True

    def version(self, *, scope: PrincipalScope, namespace: str) -> int | None:
        return self._versions.get(self._namespace_key(scope, namespace))


class DurableReplicaGateway:
    """Authorize one event's durable scope, reload state and enqueue locally."""

    def __init__(self, manager: WSManager, *, reload_projection: Callable,
                 cache_invalidator: CacheInvalidator | None = None):
        self.manager = manager
        self.reload_projection = reload_projection
        self.cache_invalidator = cache_invalidator or CacheInvalidator()
        self._sequences: dict[tuple, int] = {}

    def apply(self, event) -> str:
        if event.classification == "private":
            if not event.owner_id:
                raise ValueError("private event has no owner scope")
            scope = PrincipalScope(event.owner_id, event.broker_account_id)
            channel = ((event.owner_id, event.broker_account_id)
                       if event.broker_account_id else f"OWNER:{event.owner_id}")
        elif event.classification == "market_public":
            scope = None
            channel = PUBLIC_MARKET
        else:
            raise ValueError("unknown event classification")
        payload = json.loads(event.payload_json)
        projection = payload.get("projection")
        if not isinstance(projection, str):
            raise ValueError("projection event lacks a bounded projection name")
        sequence_key = (event.classification, event.owner_id, event.broker_account_id,
                        event.aggregate_type, event.aggregate_id)
        if event.aggregate_sequence <= self._sequences.get(sequence_key, 0):
            return "duplicate"
        if scope is not None and not self.cache_invalidator.apply(
            scope=scope, namespace=projection,
            aggregate_type=event.aggregate_type, aggregate_id=event.aggregate_id,
            aggregate_sequence=event.aggregate_sequence,
            durable_version=int(payload.get("version") or payload.get("revision")
                                or payload.get("audit_sequence")
                                or payload.get("fence_epoch")
                                or event.aggregate_sequence),
        ):
            return "duplicate"
        # Event payload is a change fact, never the current projection value.
        fresh = self.reload_projection(scope, projection)
        self._sequences[sequence_key] = event.aggregate_sequence
        self.manager.push(channel, {
            "type": "projection_event",
            "data": {"projection": projection, "snapshot": fresh},
        })
        return "applied"


@dataclass
class OutboxDispatcher:
    """One bounded poll. A surrounding task decides wakeups and cadence."""

    sessionmaker: object
    repository: OutboxRepository
    consumer_id: str
    lease_owner: str
    effect: Callable
    batch_size: int = 100
    lease_seconds: int = 30
    crash_after_effect: bool = False
    clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(
        dt.timezone.utc).replace(tzinfo=None)

    def poll_once(self, *, now: dt.datetime | None = None) -> int:
        claim_now = now or self.clock()
        try:
            with self.sessionmaker() as session, session.begin():
                batch = self.repository.claim_batch(
                    session, consumer_id=self.consumer_id, lease_owner=self.lease_owner,
                    limit=self.batch_size, lease_seconds=self.lease_seconds, now=claim_now)
        except ClaimUnavailable:
            return 0
        delivered = 0
        for event in batch.events:
            operation_now = now or self.clock()
            with self.sessionmaker() as session, session.begin():
                self.repository.heartbeat(
                    session, batch.claim_token, lease_seconds=self.lease_seconds,
                    now=operation_now)
            self.effect(event)
            if self.crash_after_effect:
                return delivered
            with self.sessionmaker() as session, session.begin():
                ack_now = now or self.clock()
                self.repository.ack(
                    session, batch.claim_token, event.event_id,
                    effect_key=f"projection:{event.event_id}", now=ack_now)
            delivered += 1
        with self.sessionmaker() as session, session.begin():
            self.repository.release(session, batch.claim_token)
        return delivered


class ManagedOutboxDelivery:
    """Notification-assisted loop whose periodic poll remains authoritative."""

    def __init__(self, dispatcher: OutboxDispatcher, *, engine, plane: str,
                 poll_seconds: float = 1.0, max_backoff_seconds: float = 30.0):
        self.dispatcher = dispatcher
        self.engine = engine
        self.listener = PostgresNotificationListener(plane=plane)
        self.poll_seconds = max(0.05, min(float(poll_seconds), 60.0))
        self.max_backoff_seconds = max(1.0, min(float(max_backoff_seconds), 60.0))
        self._stop = asyncio.Event()
        self._connection = None

    async def stop(self):
        self._stop.set()
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    async def run(self):
        backoff = 0.25
        while not self._stop.is_set():
            try:
                if self.engine.dialect.name == "postgresql" and self._connection is None:
                    self._connection = await asyncio.to_thread(self.listener.connect, self.engine)
                    await asyncio.to_thread(self.dispatcher.poll_once)  # reconnect catch-up
                    backoff = 0.25
                # Poll is always authority. A notification only shortens this wait;
                # DB readiness integration remains isolated from effect execution.
                await asyncio.to_thread(self.dispatcher.poll_once)
                if self._connection is not None:
                    # Valid, invalid and duplicate payloads all end in the same
                    # authoritative bounded poll. The hint only shortens the wait.
                    await asyncio.to_thread(
                        self._connection.wait_hint, self.listener, self.poll_seconds)
                else:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception:
                if self._connection is not None:
                    self._connection.close()
                    self._connection = None
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, self.max_backoff_seconds)
