"""Live PostgreSQL outbox concurrency and transaction notification proofs."""
from __future__ import annotations

import concurrent.futures
import asyncio
import os
import select as select_io
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.events.delivery import PostgresNotificationListener
from app.events.delivery import ManagedOutboxDelivery, OutboxDispatcher
from app.events.outbox import OutboxRepository, define_outbox_models


class PGBase(DeclarativeBase):
    pass


MODELS = define_outbox_models(PGBase, "pgtest")


@pytest.fixture
def pgstore():
    base = os.environ.get("PT_TEST_POSTGRES_URL")
    if not base:
        pytest.skip("PT_TEST_POSTGRES_URL is not configured")
    schema = f"task6_outbox_{uuid.uuid4().hex}"
    admin = sa.create_engine(base, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = str(sa.engine.make_url(base).update_query_dict(
        {"options": f"-csearch_path={schema}"}))
    engine = sa.create_engine(url, future=True, pool_size=6, max_overflow=2)
    PGBase.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    repo = OutboxRepository(MODELS, plane="pgtest", allowed_event_types={"projection.changed"})
    try:
        yield engine, sm, repo
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def _append(sm, repo, producer, *, aggregate="same-new-aggregate", payload=None):
    with sm() as session, repo.writer(session):
        return repo.append(
            session, classification="private", owner_id="org-a",
            broker_account_id="account-1", aggregate_type="position",
            aggregate_id=aggregate, event_type="projection.changed",
            schema_version=1, payload=payload or {"projection": "position", "producer": producer},
            producer_key=producer,
        )


def test_two_postgres_writers_allocate_first_aggregate_sequences(pgstore):
    """Removing insert-on-conflict plus head lock must lose one first writer."""
    _engine, sm, repo = pgstore
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        identities = list(pool.map(lambda value: _append(sm, repo, value), ("p1", "p2")))
    assert sorted(value.aggregate_sequence for value in identities) == [1, 2]
    assert len({value.plane_offset for value in identities}) == 2


def test_concurrent_exact_producer_retry_returns_original_identity(pgstore):
    """A producer-key race may not leak the database unique violation."""
    _engine, sm, repo = pgstore
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        identities = list(pool.map(
            lambda _: _append(sm, repo, "same-producer", aggregate="aggregate-a"),
            (1, 2)))
    assert identities[0] == identities[1]
    next_identity = _append(sm, repo, "next", aggregate="aggregate-a")
    assert next_identity.aggregate_sequence == 2


def test_concurrent_producer_retry_with_changed_content_fails_closed(pgstore):
    _engine, sm, repo = pgstore

    def attempt(value):
        try:
            return _append(sm, repo, "same-key", aggregate=f"aggregate-{value}",
                           payload={"projection": "position", "value": value})
        except Exception as exc:
            return exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (1, 2)))
    assert sum(hasattr(result, "event_id") for result in results) == 1
    assert sum(type(result).__name__ == "DuplicateProducerConflict" for result in results) == 1


def test_concurrent_initial_consumer_claim_has_one_fenced_winner(pgstore):
    """A missing cursor-row race must resolve to one claim rather than IntegrityError."""
    _engine, sm, repo = pgstore
    _append(sm, repo, "event")

    def claim(worker):
        try:
            with sm() as session, session.begin():
                return repo.claim_batch(session, consumer_id="new-consumer",
                                        lease_owner=worker, limit=10, lease_seconds=30)
        except Exception as exc:
            return exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("one", "two")))
    assert sum(hasattr(result, "claim_token") for result in results) == 1
    assert sum(type(result).__name__ == "ClaimUnavailable" for result in results) == 1


def test_postgres_notify_is_after_commit_and_absent_after_rollback(pgstore):
    """Moving pg_notify outside the transaction must publish rolled-back state."""
    engine, sm, repo = pgstore
    listener = PostgresNotificationListener(plane="pgtest")
    connection = listener.connect(engine)
    try:
        with sm() as session:
            with repo.writer(session):
                repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id="account-1", aggregate_type="position",
                    aggregate_id="commit", event_type="projection.changed",
                    schema_version=1, payload={"projection": "position"},
                    producer_key="commit")
                assert not select_io.select([connection], [], [], 0.05)[0]
        assert select_io.select([connection], [], [], 1.0)[0]
        notifications = list(connection.notifies(timeout=0.1, stop_after=1))
        assert listener.parse_hint(notifications[0].payload) == 1

        with pytest.raises(RuntimeError):
            with sm() as session, repo.writer(session):
                repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id="account-1", aggregate_type="position",
                    aggregate_id="rollback", event_type="projection.changed",
                    schema_version=1, payload={"projection": "position"},
                    producer_key="rollback")
                raise RuntimeError("rollback")
        assert not select_io.select([connection], [], [], 0.1)[0]
    finally:
        connection.close()


def test_managed_postgres_delivery_wakes_well_before_poll_interval(pgstore):
    """If LISTEN stops waking the service, this waits for the five-second fallback."""
    engine, sm, repo = pgstore

    async def run():
        delivered = asyncio.Event()
        dispatcher = OutboxDispatcher(
            sm, repo, consumer_id="managed", lease_owner="boot",
            effect=lambda _event: delivered.set())
        service = ManagedOutboxDelivery(
            dispatcher, engine=engine, plane="pgtest", poll_seconds=5)
        task = asyncio.create_task(service.run())
        try:
            await asyncio.sleep(0.1)
            await asyncio.to_thread(_append, sm, repo, "managed-event")
            await asyncio.wait_for(delivered.wait(), timeout=1.0)
        finally:
            await service.stop()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
