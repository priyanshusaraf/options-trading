"""Replica delivery stays polling-authoritative, scoped and idempotent."""
import asyncio
import datetime as dt
import importlib.util

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.events.delivery import (
    CacheInvalidator,
    DurableReplicaGateway,
    OutboxDispatcher,
    PostgresNotificationListener,
    ResumeCursorCodec,
)
from app.events.outbox import OutboxRepository, PrincipalScope, define_outbox_models
from app.ws.manager import WSManager


def test_replica_delivery_module_is_available():
    assert importlib.util.find_spec("app.events.delivery") is not None


class DeliveryBase(DeclarativeBase):
    pass


MODELS = define_outbox_models(DeliveryBase, "delivery")


def _store():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    DeliveryBase.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    repo = OutboxRepository(
        MODELS, plane="delivery",
        allowed_event_types={"projection.changed"},
    )
    return engine, sm, repo


def _append(sm, repo, *, producer="p:1", owner="org-a", account="account-1",
            sequence_version=1):
    with sm() as session, repo.writer(session):
        return repo.append(
            session, classification="private", owner_id=owner,
            broker_account_id=account, aggregate_type="position",
            aggregate_id="position-1", event_type="projection.changed",
            schema_version=1,
            payload={"projection": "position", "version": sequence_version},
            producer_key=producer,
        )


def test_dispatcher_polls_without_notifications_and_retries_after_crash():
    """Removing the periodic query must make a lost notification stall delivery."""
    engine, sm, repo = _store()
    try:
        identity = _append(sm, repo)
        effects = []
        dispatcher = OutboxDispatcher(
            sm, repo, consumer_id="replica-a", lease_owner="worker-a",
            effect=lambda event: effects.append(event.event_id),
        )
        assert dispatcher.poll_once() == 1
        assert effects == [identity.event_id]

        # Simulate a process death after the local idempotent effect and before ack.
        identity2 = _append(sm, repo, producer="p:2", sequence_version=2)
        dispatcher = OutboxDispatcher(
            sm, repo, consumer_id="replica-a", lease_owner="worker-b",
            effect=lambda event: effects.append(event.event_id),
            crash_after_effect=True,
        )
        assert dispatcher.poll_once(now=dt.datetime(2026, 8, 13)) == 0
        replacement = OutboxDispatcher(
            sm, repo, consumer_id="replica-a", lease_owner="worker-c",
            effect=lambda event: effects.append(event.event_id),
        )
        assert replacement.poll_once(now=dt.datetime(2026, 8, 13, 0, 0, 31)) == 1
        assert effects.count(identity2.event_id) == 2  # at-least-once delivery
    finally:
        engine.dispose()


def test_resume_cursor_is_scope_bound_and_tamper_evident():
    """Removing the owner/account binding must let a foreign principal resume."""
    codec = ResumeCursorCodec(b"0123456789abcdef0123456789abcdef")
    scope = PrincipalScope("org-a", "account-1")
    token = codec.encode(plane="execution", scope=scope, offset=42)
    assert codec.decode(token, plane="execution", scope=scope) == 42
    assert codec.decode(token, plane="execution",
                        scope=PrincipalScope("org-b", "account-1")) is None
    assert codec.decode(token[:-1] + ("a" if token[-1] != "a" else "b"),
                        plane="execution", scope=scope) is None


def test_cache_invalidation_is_tenant_scoped_and_sequence_idempotent():
    """A tenantless cache key or sequence rollback must expose/rewind another owner."""
    invalidator = CacheInvalidator()
    a = PrincipalScope("org-a", "account-1")
    b = PrincipalScope("org-b", "account-1")
    assert invalidator.apply(scope=a, namespace="positions", aggregate_type="position",
                             aggregate_id="p1",
                             aggregate_sequence=2, durable_version=7) is True
    assert invalidator.apply(scope=a, namespace="positions", aggregate_type="position",
                             aggregate_id="p1",
                             aggregate_sequence=1, durable_version=8) is False
    assert invalidator.version(scope=a, namespace="positions") == 7
    assert invalidator.version(scope=b, namespace="positions") is None


def test_replica_gateway_reloads_scoped_projection_and_latest_wins():
    """Using payload as state or an unscoped channel must make this fail."""
    class Socket:
        def __init__(self): self.sent = []
        async def accept(self): pass
        async def send_text(self, text): self.sent.append(text)
        async def close(self): pass

    async def run():
        manager = WSManager()
        manager.bind(asyncio.get_running_loop())
        socket = Socket()
        await manager.connect(socket, channel=("org-a", "account-1"))
        reads = []

        def reload(scope, projection):
            reads.append((scope, projection))
            return {"source": "database", "version": len(reads)}

        gateway = DurableReplicaGateway(manager, reload_projection=reload)
        event = type("Event", (), {
            "classification": "private", "owner_id": "org-a",
            "broker_account_id": "account-1", "event_type": "projection.changed",
            "payload_json": '{"projection":"position","secret_state":"event"}',
            "aggregate_sequence": 1, "aggregate_type": "position", "aggregate_id": "p1",
        })()
        gateway.apply(event)
        await asyncio.sleep(0.02)
        manager.disconnect(socket)
        return socket.sent, reads

    sent, reads = asyncio.run(run())
    assert reads == [(PrincipalScope("org-a", "account-1"), "position")]
    assert len(sent) == 1
    assert "database" in sent[0]
    assert "secret_state" not in sent[0]
    assert '"type":"projection_event"' in sent[0]


def test_postgres_listener_wakeup_is_only_a_bounded_hint():
    """Accepting arbitrary notification payloads must affect dispatcher state."""
    listener = PostgresNotificationListener(plane="execution")
    assert listener.parse_hint('{"plane":"execution","high_water":42}') == 42
    assert listener.parse_hint('{"plane":"ledger","high_water":999}') is None
    assert listener.parse_hint('{"plane":"execution","high_water":"secret"}') is None
    assert listener.parse_hint("not-json") is None


def test_dispatcher_heartbeat_precedes_each_effect():
    """A slow effect may not run under a cursor lease that has already expired."""
    engine, sm, repo = _store()
    try:
        _append(sm, repo)
        called = []
        dispatcher = OutboxDispatcher(
            sm, repo, consumer_id="replica", lease_owner="worker",
            effect=lambda event: called.append(event.event_id), lease_seconds=5,
        )
        assert dispatcher.poll_once(now=dt.datetime(2026, 8, 13)) == 1
        assert len(called) == 1
    finally:
        engine.dispose()


def test_two_same_host_replica_consumers_each_receive_the_event():
    """Sharing a hostname-only consumer cursor must starve one replica."""
    engine, sm, repo = _store()
    try:
        identity = _append(sm, repo)
        effects_a, effects_b = [], []
        a = OutboxDispatcher(sm, repo, consumer_id="host-boot-a", lease_owner="boot-a",
                             effect=lambda event: effects_a.append(event.event_id))
        b = OutboxDispatcher(sm, repo, consumer_id="host-boot-b", lease_owner="boot-b",
                             effect=lambda event: effects_b.append(event.event_id))
        assert a.poll_once() == b.poll_once() == 1
        assert effects_a == effects_b == [identity.event_id]
    finally:
        engine.dispose()
