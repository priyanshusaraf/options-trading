from __future__ import annotations

import concurrent.futures
import os
import threading
import time
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.db.models import BacktestRun, Base, BrokerAccount, CapitalState, Organization
from app.execution.leases import LeaseRepository, LeaseUnavailable, RecoveryRequired, StaleLease
from app.core.execution_book import capital_for_book
from app.backtest import repository as backtest_repository
from app.events.planes import execution_outbox


@pytest.fixture()
def postgres_leases():
    base_url = os.environ.get("PT_TEST_POSTGRES_URL")
    if not base_url:
        pytest.skip("PT_TEST_POSTGRES_URL is not configured")
    schema = f"task5_leases_{uuid.uuid4().hex}"
    admin = sa.create_engine(base_url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = str(sa.engine.make_url(base_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}))
    engine = sa.create_engine(url, future=True, pool_size=5, max_overflow=2)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions.begin() as session:
        session.add(Organization(organization_id="tenant", name="Tenant"))
        session.add_all([
            BrokerAccount(broker_account_id="account-a", owner_id="tenant", broker="kite",
                          external_account_id="a", display_name="A"),
            BrokerAccount(broker_account_id="account-b", owner_id="tenant", broker="kite",
                          external_account_id="b", display_name="B"),
        ])
    try:
        yield LeaseRepository(sessions), sessions
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_postgres_two_session_claim_takeover_and_control_are_exactly_once(postgres_leases):
    repo, sessions = postgres_leases

    def claim(worker):
        try:
            return repo.claim(owner_id="tenant", broker_account_id="account-a",
                              cell_id=f"cell-{worker}", worker_id=f"boot-{worker}")
        except LeaseUnavailable as exc:
            return exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, (1, 2)))
    winners = [outcome for outcome in outcomes if hasattr(outcome, "fence_epoch")]
    assert len(winners) == 1
    assert sum(isinstance(outcome, LeaseUnavailable) for outcome in outcomes) == 1
    old = winners[0]
    repo.activate(old, reconciliation_evidence="live postgres clean")
    accepted = repo.request_control(
        owner_id="tenant", broker_account_id="account-a", kind="kill",
        idempotency_key="pg-kill", actor_user_id="operator")

    # Database time, not a host sleep, expires the row.
    with sessions.begin() as session:
        session.execute(sa.text("""
            UPDATE account_execution_leases
            SET heartbeat_at = CURRENT_TIMESTAMP - INTERVAL '2 minutes',
                expires_at = CURRENT_TIMESTAMP - INTERVAL '1 minute'
            WHERE owner_id = 'tenant' AND broker_account_id = 'account-a'
        """))
    new = repo.claim(owner_id="tenant", broker_account_id="account-a",
                     cell_id="new-cell", worker_id="new-boot")
    assert new.fence_epoch == old.fence_epoch + 1
    with pytest.raises(StaleLease):
        repo.heartbeat(old)
    def controls():
        return repo.claim_controls(new, limit=1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: controls(), (1, 2)))
    claimed = [row for rows in claims for row in rows]
    assert [row.command_id for row in claimed] == [accepted["request_id"]]
    assert claimed[0].fence_epoch == new.fence_epoch

    # A different account is not serialized behind account-a's recovery.
    independent = repo.claim(owner_id="tenant", broker_account_id="account-b",
                             cell_id="cell-b", worker_id="boot-b")
    assert independent.fence_epoch == 1


def test_postgres_backtest_state_and_typed_event_commit_or_rollback_together(postgres_leases):
    """The real producer uses the same PostgreSQL transaction as its durable run."""
    _repo, sessions = postgres_leases
    with sessions() as session:
        rolled_back = backtest_repository.enqueue_run(
            session, owner_id="tenant", scope="liquid", intervals="day",
            capital=10_000, total=1,
        )
        rolled_back_id = rolled_back.id
        session.rollback()
    with sessions() as session:
        assert session.get(BacktestRun, rolled_back_id) is None
        assert session.scalar(sa.select(sa.func.count()).select_from(
            execution_outbox().models.Event)) == 0

    with sessions.begin() as session:
        committed = backtest_repository.enqueue_run(
            session, owner_id="tenant", scope="liquid", intervals="day",
            capital=10_000, total=1,
        )
        committed_id = committed.id
    with sessions() as session:
        event = session.scalar(sa.select(execution_outbox().models.Event))
        assert event.aggregate_id == str(committed_id)
        assert (event.owner_id, event.broker_account_id) == ("tenant", None)


def test_postgres_money_commit_linearizes_before_takeover(postgres_leases):
    repo, sessions = postgres_leases
    old = repo.claim(owner_id="tenant", broker_account_id="account-a",
                     cell_id="old", worker_id="old-boot", ttl_seconds=2)
    repo.activate(old, reconciliation_evidence="clean")
    with sessions.begin() as session:
        session.add(CapitalState(broker_account_id="account-a", book="live",
                                 initial_capital=100, cash=100, realized_pnl=0,
                                 updated_at=sa.func.current_timestamp()))
    writer = sessions()
    repo.bind_money_session(writer, old)
    writer.execute(sa.update(CapitalState).where(
        CapitalState.broker_account_id == "account-a").values(cash=90))
    # The DML listener now holds the exact lease row lock through writer commit. Let DB
    # time pass the short expiry while that lock is held, then race takeover.
    time.sleep(2.1)

    outcome = []
    started = threading.Event()
    def takeover():
        started.set()
        outcome.append(repo.claim(owner_id="tenant", broker_account_id="account-a",
                                  cell_id="new", worker_id="new-boot"))
    thread = threading.Thread(target=takeover)
    thread.start()
    started.wait(2)
    time.sleep(0.1)
    assert thread.is_alive(), "takeover did not wait on bound money transaction's lease lock"
    writer.commit()
    writer.close()
    thread.join(5)
    assert not thread.is_alive()
    assert outcome[0].fence_epoch == old.fence_epoch + 1
    with sessions() as session:
        assert session.scalar(sa.select(CapitalState.cash)) == 90


def test_postgres_stale_epoch_cannot_bootstrap_capital(postgres_leases):
    repo, sessions = postgres_leases
    stale = repo.claim(owner_id="tenant", broker_account_id="account-a",
                       cell_id="old-bootstrap", worker_id="old-bootstrap")
    repo.release(stale)
    repo.claim(owner_id="tenant", broker_account_id="account-a",
               cell_id="new-bootstrap", worker_id="new-bootstrap")
    with sessions() as session:
        repo.bind_money_session(session, stale)
        with pytest.raises(StaleLease):
            capital_for_book(session, "live", broker_account_id="account-a")
    with sessions() as session:
        assert session.get(CapitalState, ("account-a", "live")) is None
