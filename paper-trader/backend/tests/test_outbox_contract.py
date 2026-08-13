"""Behavioral contract for the portable plane-local durable outbox."""
from __future__ import annotations

import datetime as dt
import importlib.util

import pytest
from sqlalchemy import Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def test_portable_outbox_repository_is_available():
    """Removing the shared repository must break every plane's delivery path."""
    assert importlib.util.find_spec("app.events.outbox") is not None


from app.events.outbox import (  # noqa: E402
    ClaimUnavailable,
    DuplicateProducerConflict,
    OutboxRepository,
    OutboxValidationError,
    PrincipalScope,
    StaleClaim,
    define_outbox_models,
)


class ContractBase(DeclarativeBase):
    pass


class Projection(ContractBase):
    __tablename__ = "test_projection"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(32), nullable=False)


MODELS = define_outbox_models(ContractBase, "test")


@pytest.fixture
def store():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    ContractBase.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    repo = OutboxRepository(
        MODELS,
        plane="test",
        allowed_event_types={"projection.changed", "owner.changed", "public.invalidate"},
        market_public_event_types={"public.invalidate"},
    )
    try:
        yield sm, repo
    finally:
        engine.dispose()


def _private(repo, session, *, producer="producer:1", owner="org-a", account="account-1",
             aggregate="position-1", payload=None):
    return repo.append(
        session,
        classification="private",
        owner_id=owner,
        broker_account_id=account,
        aggregate_type="position",
        aggregate_id=aggregate,
        event_type="projection.changed",
        schema_version=1,
        payload=payload or {"projection": "position", "version": 1},
        producer_key=producer,
    )


def test_append_refuses_an_unowned_ambient_transaction(store):
    """Removing explicit transaction ownership must not permit orphan events."""
    sm, repo = store
    with sm() as session:
        session.add(Projection(id=1, value="pending"))
        with pytest.raises(OutboxValidationError, match="transaction owner"):
            _private(repo, session)


def test_state_and_event_commit_or_rollback_together(store):
    """Moving append outside the writer transaction must make this fail."""
    sm, repo = store
    with pytest.raises(RuntimeError, match="abort"):
        with sm() as session, repo.writer(session):
            session.add(Projection(id=1, value="rolled-back"))
            _private(repo, session)
            raise RuntimeError("abort")
    with sm() as session:
        assert session.scalar(select(func.count()).select_from(Projection)) == 0
        assert session.scalar(select(func.count()).select_from(MODELS.Event)) == 0

    with sm() as session, repo.writer(session):
        session.add(Projection(id=2, value="committed"))
        identity = _private(repo, session)
    with sm() as session:
        assert session.get(Projection, 2).value == "committed"
        event = session.scalar(select(MODELS.Event))
        assert event.event_id == identity.event_id
        assert event.aggregate_sequence == 1
        assert event.content_address.startswith("sha256:")


def test_duplicate_producer_is_exact_retry_or_refusal(store):
    """Changing immutable fields under one producer key must fail closed."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        original = _private(repo, session)
    with sm() as session, repo.writer(session):
        duplicate = _private(repo, session)
        assert duplicate == original
    with sm() as session, repo.writer(session):
        with pytest.raises(DuplicateProducerConflict):
            _private(repo, session, payload={"projection": "position", "version": 2})


@pytest.mark.parametrize("payload", [
    {"access_token": "secret"},
    {"value": float("nan")},
    {"blob": "x" * 9000},
])
def test_payload_rejects_secrets_nonfinite_numbers_and_oversize(store, payload):
    """Weakening bounded canonical payload validation must make this fail."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        with pytest.raises(OutboxValidationError):
            _private(repo, session, payload=payload)


def test_scope_and_public_classification_are_closed(store):
    """Private owner scope and the public allowlist may not be caller-defined."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        with pytest.raises(OutboxValidationError, match="owner"):
            _private(repo, session, owner="")
        with pytest.raises(OutboxValidationError, match="allowlist"):
            repo.append(
                session, classification="market_public", owner_id=None,
                broker_account_id=None, aggregate_type="position", aggregate_id="1",
                event_type="projection.changed", schema_version=1, payload={},
                producer_key="public:bad",
            )


def test_scoped_read_filters_in_sql_and_never_reads_foreign_counts(store):
    """Dropping either owner/account SQL predicate must expose the sentinel event."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        _private(repo, session, producer="a", owner="org-a", account="account-1")
        _private(repo, session, producer="b", owner="org-b", account="account-1",
                 payload={"projection": "NEVER-RETURN"})
        _private(repo, session, producer="c", owner="org-a", account="account-2",
                 payload={"projection": "NEVER-RETURN"})
    with sm() as session:
        result = repo.read_scoped_after(
            session, PrincipalScope("org-a", "account-1"), offset=0, limit=10,
            resume_cursor_present=True)
        assert len(result.events) == 1
        assert result.events[0].owner_id == "org-a"
        assert result.events[0].broker_account_id == "account-1"


def test_claim_lease_repeats_after_crash_and_stale_token_cannot_ack(store):
    """Removing lease-token fencing must let a dead dispatcher advance the cursor."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        _private(repo, session)
    now = dt.datetime(2026, 8, 13, 1, 0, 0)
    with sm() as session, session.begin():
        first = repo.claim_batch(session, consumer_id="replica-a", lease_owner="worker-1",
                                 limit=10, lease_seconds=5, now=now)
        assert len(first.events) == 1
    with sm() as session, session.begin():
        with pytest.raises(ClaimUnavailable):
            repo.claim_batch(session, consumer_id="replica-a", lease_owner="worker-2",
                             limit=10, lease_seconds=5, now=now + dt.timedelta(seconds=1))
    with sm() as session, session.begin():
        second = repo.claim_batch(session, consumer_id="replica-a", lease_owner="worker-2",
                                  limit=10, lease_seconds=5,
                                  now=now + dt.timedelta(seconds=6))
        assert [event.event_id for event in second.events] == [first.events[0].event_id]
    with sm() as session, session.begin():
        with pytest.raises(StaleClaim):
            repo.ack(session, first.claim_token, first.events[0].event_id,
                     effect_key="refresh:1", now=now + dt.timedelta(seconds=6))
        assert repo.ack(session, second.claim_token, second.events[0].event_id,
                        effect_key="refresh:1", now=now + dt.timedelta(seconds=6)) is True
    with sm() as session, session.begin():
        empty = repo.claim_batch(session, consumer_id="replica-a", lease_owner="worker-3",
                                 limit=10, lease_seconds=5,
                                 now=now + dt.timedelta(seconds=12))
        assert empty.events == ()


def test_retention_reports_resync_and_healthy_cursor_pins_needed_events(store):
    """Cleanup may not remove an event before a healthy consumer has advanced."""
    sm, repo = store
    old = dt.datetime(2026, 7, 1)
    with sm() as session, repo.writer(session):
        _private(repo, session, producer="one", aggregate="one")
        _private(repo, session, producer="two", aggregate="two")
        for event in session.scalars(select(MODELS.Event)):
            event.created_at = old
    now = dt.datetime(2026, 8, 13)
    with sm() as session, session.begin():
        claim = repo.claim_batch(session, consumer_id="healthy", lease_owner="worker",
                                 limit=1, lease_seconds=30, now=now)
    with sm() as session, session.begin():
        assert repo.cleanup(session, older_than=now - dt.timedelta(days=7), now=now,
                            abandoned_after_seconds=60, limit=100) == 0
        repo.ack(session, claim.claim_token, claim.events[0].event_id,
                 effect_key="one", now=now)
    with sm() as session, session.begin():
        assert repo.cleanup(session, older_than=now - dt.timedelta(days=7), now=now,
                            abandoned_after_seconds=60, limit=100) == 1
    with sm() as session:
        result = repo.read_scoped_after(
            session, PrincipalScope("org-a", "account-1"), offset=0, limit=10,
            resume_cursor_present=True)
        assert result.resync_required is True
        assert len(result.events) == 1


def test_sqlite_offset_never_reuses_after_retention(store):
    """Dropping SQLite AUTOINCREMENT must let a new event hide behind an acked cursor."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        first = _private(repo, session)
    with sm() as session, session.begin():
        session.execute(MODELS.Event.__table__.delete())
    with sm() as session, repo.writer(session):
        second = _private(repo, session, producer="producer:2", aggregate="position-2")
    assert second.plane_offset > first.plane_offset


def test_expired_claim_cannot_ack_and_heartbeat_renews_exact_token(store):
    """Removing expiry fencing must let a dead worker advance a cursor."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        identity = _private(repo, session)
    now = dt.datetime(2026, 8, 13)
    with sm() as session, session.begin():
        claim = repo.claim_batch(session, consumer_id="replica", lease_owner="worker",
                                 limit=10, lease_seconds=5, now=now)
    with sm() as session, session.begin():
        with pytest.raises(StaleClaim, match="expired"):
            repo.ack(session, claim.claim_token, identity.event_id,
                     effect_key="effect", now=now + dt.timedelta(seconds=6))
    with sm() as session, session.begin():
        takeover = repo.claim_batch(session, consumer_id="replica", lease_owner="replacement",
                                    limit=10, lease_seconds=5,
                                    now=now + dt.timedelta(seconds=6))
        expires = repo.heartbeat(session, takeover.claim_token, lease_seconds=20,
                                 now=now + dt.timedelta(seconds=7))
        assert expires == now + dt.timedelta(seconds=27)
    with sm() as session, session.begin():
        assert repo.ack(session, takeover.claim_token, identity.event_id,
                        effect_key="effect", now=now + dt.timedelta(seconds=20))


def test_resync_metadata_is_scope_local(store):
    """A foreign tenant's retained offset must not change this tenant's resume verdict."""
    sm, repo = store
    with sm() as session, repo.writer(session):
        _private(repo, session, producer="b1", owner="org-b", account="account-1",
                 aggregate="b1")
        _private(repo, session, producer="a1", owner="org-a", account="account-1",
                 aggregate="a1")
    with sm() as session, session.begin():
        foreign = session.scalar(select(MODELS.Event).where(MODELS.Event.owner_id == "org-b"))
        session.delete(foreign)
    with sm() as session:
        result = repo.read_scoped_after(
            session, PrincipalScope("org-a", "account-1"), offset=1, limit=10,
            resume_cursor_present=True)
        assert result.resync_required is False
        assert [event.plane_offset for event in result.events] == [2]


def test_account_resume_considers_retained_owner_wide_events(store):
    """An account reader sees owner-wide events, so their prune marker must also resync it."""
    sm, repo = store
    old = dt.datetime(2026, 7, 1)
    with sm() as session, repo.writer(session):
        _private(repo, session, producer="owner-wide", owner="org-a", account=None,
                 aggregate="owner-wide")
        event = session.scalar(select(MODELS.Event))
        event.created_at = old
    now = dt.datetime(2026, 8, 13)
    with sm() as session, session.begin():
        assert repo.cleanup(session, older_than=now - dt.timedelta(days=7), now=now,
                            abandoned_after_seconds=60, limit=100) == 1
    with sm() as session:
        own = repo.read_scoped_after(
            session, PrincipalScope("org-a", "account-1"), offset=0, limit=10,
            resume_cursor_present=True)
        foreign = repo.read_scoped_after(
            session, PrincipalScope("org-b", "account-1"), offset=0, limit=10,
            resume_cursor_present=True)
    assert own.events == () and own.resync_required is True
    assert own.high_water == 1
    assert foreign.events == () and foreign.resync_required is False


def test_interleaved_foreign_offsets_do_not_create_a_scope_gap(store):
    """Global offset gaps are not evidence that this tenant lost an event."""
    sm, repo = store
    old = dt.datetime(2026, 7, 1)
    with sm() as session, repo.writer(session):
        first = _private(repo, session, producer="a1", owner="org-a",
                         account="account-1", aggregate="a1")
        _private(repo, session, producer="b1", owner="org-b",
                 account="account-1", aggregate="b1")
        last = _private(repo, session, producer="a2", owner="org-a",
                        account="account-1", aggregate="a2")
        first_row = session.get(MODELS.Event, first.plane_offset)
        first_row.created_at = old
    now = dt.datetime(2026, 8, 13)
    with sm() as session, session.begin():
        assert repo.cleanup(session, older_than=now - dt.timedelta(days=7), now=now,
                            abandoned_after_seconds=60, limit=100) == 1
    with sm() as session:
        result = repo.read_scoped_after(
            session, PrincipalScope("org-a", "account-1"),
            offset=first.plane_offset, limit=10, resume_cursor_present=True)
    assert [event.plane_offset for event in result.events] == [last.plane_offset]
    assert result.resync_required is False
