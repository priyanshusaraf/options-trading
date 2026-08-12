"""Real two-session races against SQLite and the optional live PostgreSQL gate."""
from __future__ import annotations

import datetime as dt
import os
import threading
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.backtest import repository, sweep
from app.core import paper_authority
from app.core.execution_book import PAPER, capital_for_book
from app.db.concurrency import begin_reservation
from app.db.engine import configure_connection_profile
from app.db.models import (Base, BacktestRun, BrokerAccount, CapitalState,
                           BrokerConnection, Deployment, IrPaperDeployment,
                           Membership, OAuthCallbackState, Organization, Project,
                           User, UserSession)
from app.ledger import service as ledger_service
from app.ledger.db import LedgerBase
from app.ledger.models import LedgerManualFill
from research.domain.models import ResearchOperation, ResearchOperationEvent
from research.domain import operations as research_operations
from research.domain.operations import ResearchOperationRepository

OWNER = "task2-owner"
ACCOUNT = "task2-account"


@pytest.fixture(params=("sqlite", "postgresql"))
def portable_database(request, tmp_path):
    schema = None
    admin = None
    if request.param == "sqlite":
        engine = configure_connection_profile(sa.create_engine(
            f"sqlite:///{tmp_path / 'portable-races.db'}", future=True,
            connect_args={"check_same_thread": False}))
    else:
        url = os.environ.get("PT_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("PT_TEST_POSTGRES_URL is not configured")
        schema = f"task2_{uuid.uuid4().hex}"
        admin = sa.create_engine(url, future=True)
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        engine = sa.create_engine(
            url, future=True,
            connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        LedgerBase.metadata.create_all(engine)
        ResearchOperation.__table__.create(engine)
        ResearchOperationEvent.__table__.create(engine)
        with engine.begin() as connection:
            connection.execute(sa.text("""
                CREATE TABLE research_operation_item (
                    owner_id VARCHAR(64) NOT NULL,
                    operation_id VARCHAR(64) NOT NULL,
                    item_key VARCHAR(128) NOT NULL,
                    ordinal INTEGER NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    run_id INTEGER NULL,
                    completed_at TIMESTAMP NULL,
                    PRIMARY KEY (owner_id, operation_id, item_key)
                )
            """))
        sessions = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with sessions() as session, session.begin():
            session.add(Organization(organization_id=OWNER, name="Task 2"))
            session.add(BrokerAccount(
                broker_account_id=ACCOUNT, owner_id=OWNER, broker="paper",
                external_account_id="task2", display_name="Task 2"))
        yield request.param, engine, sessions
    finally:
        engine.dispose()
        if admin is not None and schema is not None:
            with admin.begin() as connection:
                connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def _pending_run(sessions, *, total: int = 1) -> int:
    with sessions() as session, session.begin():
        run = repository.enqueue_run(
            session, owner_id=OWNER, scope="liquid", intervals="day",
            capital=1.0, total=total)
        return run.id


def _race(function):
    barrier = threading.Barrier(2)
    outcomes = []

    def invoke(label):
        try:
            barrier.wait(timeout=5)
            outcomes.append(("ok", function(label)))
        except Exception as exc:
            outcomes.append(("error", exc))

    threads = [threading.Thread(target=invoke, args=(label,))
               for label in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    return outcomes


def test_two_sessions_have_one_claim_winner(portable_database):
    _dialect, _engine, sessions = portable_database
    run_id = _pending_run(sessions)
    now = dt.datetime(2026, 8, 12, 10)

    def claim(label):
        with sessions() as session:
            begin_reservation(session, scope="backtest:admission")
            row = repository.claim_run(
                session, owner_id=OWNER, run_id=run_id, claimed_by=label,
                now=now, lease_seconds=30)
            session.commit()
            return None if row is None else row.claim_token

    outcomes = _race(claim)
    assert [kind for kind, _ in outcomes].count("error") == 0
    assert sum(value is not None for _, value in outcomes) == 1
    assert len({value for _, value in outcomes if value is not None}) == 1


def test_takeover_fences_old_token_and_cancellation_fences_new_token(portable_database):
    _dialect, _engine, sessions = portable_database
    run_id = _pending_run(sessions)
    started = dt.datetime(2026, 8, 12, 10)
    with sessions() as session:
        begin_reservation(session, scope="backtest:admission")
        old = repository.claim_run(
            session, owner_id=OWNER, run_id=run_id, claimed_by="old",
            now=started, lease_seconds=1)
        session.commit()
    assert old is not None

    def takeover(label):
        with sessions() as session:
            begin_reservation(session, scope="backtest:admission")
            row = repository.claim_run(
                session, owner_id=OWNER, run_id=run_id, claimed_by=label,
                now=started + dt.timedelta(seconds=2), lease_seconds=30)
            session.commit()
            return None if row is None else row.claim_token

    outcomes = _race(takeover)
    new_tokens = [value for kind, value in outcomes if kind == "ok" and value]
    assert len(new_tokens) == 1 and new_tokens[0] != old.claim_token
    new_token = new_tokens[0]

    with sessions() as stale:
        assert not repository.append_claimed_result_batch(
            stale, owner_id=OWNER, run_id=run_id, claim_token=old.claim_token,
            values=[], now=started + dt.timedelta(seconds=3))
        stale.rollback()
    with sessions() as canceller, canceller.begin():
        assert repository.request_cancel(
            canceller, owner_id=OWNER, run_id=run_id,
            now=started + dt.timedelta(seconds=3))
    with sessions() as claimant:
        assert not repository.append_claimed_result_batch(
            claimant, owner_id=OWNER, run_id=run_id, claim_token=new_token,
            values=[], now=started + dt.timedelta(seconds=4))
        assert repository.complete_claim(
            claimant, owner_id=OWNER, run_id=run_id, claim_token=new_token,
            status="cancelled", now=started + dt.timedelta(seconds=4))
        claimant.commit()
    with sessions() as session:
        row = session.get(BacktestRun, run_id)
        assert row.status == "cancelled" and row.attempt_count == 2


def test_research_claim_has_one_winner_and_cancellation_fences_it(portable_database):
    _dialect, _engine, sessions = portable_database
    with sessions() as session:
        ResearchOperationRepository(session).enqueue(
            owner_id=OWNER, trigger="manual", plan={}, build="test",
            provider_mode="mock", operation_id="research-race",
            now=dt.datetime(2026, 8, 12, 10))

    def claim(label):
        with sessions() as session:
            row = ResearchOperationRepository(session).claim_next(
                owner_id=OWNER, worker_id=label,
                now=dt.datetime(2026, 8, 12, 10), lease_seconds=30)
            return None if row is None else row.claim_token

    outcomes = _race(claim)
    tokens = [value for kind, value in outcomes if kind == "ok" and value]
    assert len(tokens) == 1
    token = tokens[0]
    with sessions() as canceller:
        assert ResearchOperationRepository(canceller).request_cancel(
            "research-race", owner_id=OWNER,
            now=dt.datetime(2026, 8, 12, 10, 0, 1))
    with sessions() as stale:
        assert not ResearchOperationRepository(stale).transition(
            "research-race", owner_id=OWNER, token=token, stage="planning",
            now=dt.datetime(2026, 8, 12, 10, 0, 2))


def test_research_expired_takeover_fences_old_token_and_completes(portable_database):
    _dialect, _engine, sessions = portable_database
    operation_id = "research-takeover"
    now = dt.datetime(2026, 8, 12, 10)
    with sessions() as session:
        ResearchOperationRepository(session).enqueue(
            owner_id=OWNER, trigger="manual", plan={}, build="test",
            provider_mode="mock", operation_id=operation_id, now=now)
    with sessions() as session:
        old = ResearchOperationRepository(session).claim_operation(
            operation_id, owner_id=OWNER, worker_id="old",
            now=now, lease_seconds=1)
    assert old is not None

    def takeover(label):
        with sessions() as session:
            row = ResearchOperationRepository(session).claim_operation(
                operation_id, owner_id=OWNER, worker_id=label,
                now=now + dt.timedelta(seconds=2), lease_seconds=30)
            return None if row is None else row.claim_token

    outcomes = _race(takeover)
    tokens = [value for kind, value in outcomes if kind == "ok" and value]
    assert len(tokens) == 1 and tokens[0] != old.claim_token
    with sessions() as stale:
        assert not ResearchOperationRepository(stale).transition(
            operation_id, owner_id=OWNER, token=old.claim_token,
            stage="planning", now=now + dt.timedelta(seconds=3))
    with sessions() as current:
        assert ResearchOperationRepository(current).complete(
            operation_id, owner_id=OWNER, token=tokens[0],
            now=now + dt.timedelta(seconds=3))


def test_research_active_item_admission_is_bounded(portable_database, monkeypatch):
    _dialect, _engine, sessions = portable_database
    now = dt.datetime(2026, 8, 12, 10)
    for operation_id in ("research-bounded-a", "research-bounded-b"):
        with sessions() as session:
            ResearchOperationRepository(session).enqueue(
                owner_id=OWNER, trigger="manual", plan={}, build="test",
                provider_mode="mock", operation_id=operation_id, now=now)
        with sessions() as session, session.begin():
            session.execute(sa.text("""
                INSERT INTO research_operation_item
                    (owner_id, operation_id, item_key, ordinal, status)
                VALUES (:owner_id, :operation_id, 'item-1', 0, 'pending')
            """), {"owner_id": OWNER, "operation_id": operation_id})
    monkeypatch.setattr(research_operations, "_MAX_RUNNING_PER_OWNER", 10)
    monkeypatch.setattr(research_operations, "_MAX_RUNNING_HOST", 10)
    monkeypatch.setattr(research_operations, "_MAX_RUNNING_ITEMS_PER_OWNER", 1)
    monkeypatch.setattr(research_operations, "_MAX_RUNNING_ITEMS_HOST", 10)

    def claim(label):
        operation_id = f"research-bounded-{label}"
        with sessions() as session:
            row = ResearchOperationRepository(session).claim_operation(
                operation_id, owner_id=OWNER, worker_id=label,
                now=now, lease_seconds=30)
            return row is not None

    outcomes = _race(claim)
    assert sorted(value for kind, value in outcomes if kind == "ok") == [False, True]


def _claimed_research_operation(sessions, operation_id: str):
    now = dt.datetime(2026, 8, 12, 10)
    with sessions() as session:
        ResearchOperationRepository(session).enqueue(
            owner_id=OWNER, trigger="manual", plan={}, build="test",
            provider_mode="mock", operation_id=operation_id, now=now)
    with sessions() as session:
        claim = ResearchOperationRepository(session).claim_operation(
            operation_id, owner_id=OWNER, worker_id="worker",
            now=now, lease_seconds=30)
        assert claim is not None
        return claim.claim_token, now


def test_research_completed_run_append_is_portable_and_idempotent(portable_database):
    _dialect, _engine, sessions = portable_database
    token, now = _claimed_research_operation(sessions, "research-completed-run")
    with sessions() as session:
        repository_ = ResearchOperationRepository(session)
        assert repository_.add_completed_run(
            "research-completed-run", owner_id=OWNER, token=token,
            run_id=41, now=now + dt.timedelta(seconds=1))
        assert repository_.add_completed_run(
            "research-completed-run", owner_id=OWNER, token=token,
            run_id=41, now=now + dt.timedelta(seconds=2))
    with sessions() as session:
        row = session.get(ResearchOperation, (OWNER, "research-completed-run"))
        assert row.completed_run_ids_json == "[41]"


def test_research_transactional_receipt_append_is_portable(portable_database):
    _dialect, _engine, sessions = portable_database
    operation_id = "research-transactional-receipt"
    token, now = _claimed_research_operation(sessions, operation_id)
    with sessions() as session, session.begin():
        session.execute(sa.text("""
            INSERT INTO research_operation_item
                (owner_id, operation_id, item_key, ordinal, status, run_id)
            VALUES (:owner_id, :operation_id, 'item-1', 0, 'running', 42)
        """), {"owner_id": OWNER, "operation_id": operation_id})
    with sessions() as session, session.begin():
        assert ResearchOperationRepository(session).finalize_item_in_transaction(
            operation_id, owner_id=OWNER, token=token,
            item_key="item-1", run_id=42,
            now=now + dt.timedelta(seconds=1))
    with sessions() as session:
        row = session.get(ResearchOperation, (OWNER, operation_id))
        assert row.completed_run_ids_json == "[42]"


def test_bounded_admission_has_one_winner(portable_database, monkeypatch):
    _dialect, _engine, sessions = portable_database
    limits = SimpleNamespace(
        backtest_host_active_jobs=10, backtest_owner_active_jobs=10,
        backtest_owner_queued_jobs=1, backtest_host_requested_cells=10,
        backtest_host_worker_slots=10)
    monkeypatch.setattr(sweep, "get_settings", lambda: limits)

    def admit(label):
        with sessions() as session:
            begin_reservation(session, scope="backtest:admission")
            sweep._admit_workload(
                owner_id=OWNER, total=1, workers=1, session=session)
            repository.enqueue_run(
                session, owner_id=OWNER, scope="liquid", intervals="day",
                capital=1.0, total=1, note=label)
            session.commit()
            return True

    outcomes = _race(admit)
    assert sum(kind == "ok" and value is True for kind, value in outcomes) == 1
    errors = [value for kind, value in outcomes if kind == "error"]
    assert len(errors) == 1 and isinstance(errors[0], sweep.WorkloadAdmissionError)
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(BacktestRun)) == 1


def test_capital_bootstrap_race_creates_one_money_row(portable_database):
    _dialect, _engine, sessions = portable_database

    def bootstrap(_label):
        with sessions() as session:
            return capital_for_book(
                session, PAPER, broker_account_id=ACCOUNT).cash

    outcomes = _race(bootstrap)
    assert [kind for kind, _ in outcomes] == ["ok", "ok"]
    assert outcomes[0][1] == outcomes[1][1]
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(CapitalState).where(
            CapitalState.broker_account_id == ACCOUNT,
            CapitalState.book == PAPER)) == 1


def test_capital_bootstrap_preserves_an_executed_core_update(portable_database):
    _dialect, _engine, sessions = portable_database
    with sessions() as session:
        session.execute(sa.update(Organization).where(
            Organization.organization_id == OWNER).values(name="core-write-must-survive"))

        with pytest.raises(RuntimeError, match="pending writes"):
            capital_for_book(session, PAPER, broker_account_id=ACCOUNT)

        session.commit()
    with sessions() as session:
        assert session.get(Organization, OWNER).name == "core-write-must-survive"
        assert session.get(CapitalState, (ACCOUNT, PAPER)) is None


def test_manual_fill_evidence_has_one_claim_winner(portable_database):
    _dialect, _engine, sessions = portable_database
    with sessions() as session, session.begin():
        session.add(LedgerManualFill(
            owner_id=OWNER, broker_account_id=ACCOUNT, order_id="order-race",
            tradingsymbol="X", exchange="NFO", product="NRML", side="BUY", qty=1,
            avg_price=1.0, order_ts=dt.datetime(2026, 8, 12), fill_ts=None,
            verdict="MANUAL", raw="{}", seen_at=dt.datetime(2026, 8, 12)))
    read_barrier = threading.Barrier(2)

    def claim(label):
        try:
            return ledger_service.claim_manual_fill(
                sessions, "order-race", f"trade-{label}", owner_id=OWNER,
                broker_account_id=ACCOUNT,
                trade_exists=lambda *_: read_barrier.wait(timeout=5) is not None)
        except ledger_service.AlreadyClaimed as exc:
            return exc

    outcomes = _race(claim)
    values = [value for kind, value in outcomes if kind == "ok"]
    assert sum(value is True for value in values) == 1
    assert sum(isinstance(value, ledger_service.AlreadyClaimed) for value in values) == 1


def test_snapshot_compare_and_set_has_one_version_winner(portable_database):
    _dialect, engine, sessions = portable_database
    assert ledger_service.write_snapshot(
        sessions, '{"value":0}', None, owner_id=OWNER,
        broker_account_id=ACCOUNT) == 1
    read_barrier = threading.Barrier(2)

    def synchronize_updates(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("UPDATE") and "ledger_snapshot" in statement:
            read_barrier.wait(timeout=5)

    sa.event.listen(engine, "before_cursor_execute", synchronize_updates)
    try:
        def write(label):
            try:
                return ledger_service.write_snapshot(
                    sessions, f'{{"value":"{label}"}}', 1,
                    owner_id=OWNER, broker_account_id=ACCOUNT)
            except ledger_service.VersionConflict as exc:
                return exc

        outcomes = _race(write)
    finally:
        sa.event.remove(engine, "before_cursor_execute", synchronize_updates)
    values = [value for kind, value in outcomes if kind == "ok"]
    assert sum(value == 2 for value in values) == 1
    assert sum(isinstance(value, ledger_service.VersionConflict) for value in values) == 1
    assert ledger_service.read_snapshot(
        sessions, owner_id=OWNER, broker_account_id=ACCOUNT)[0] == 2


def test_snapshot_first_insert_race_maps_loser_to_version_conflict(portable_database):
    _dialect, _engine, sessions = portable_database

    def write(label):
        try:
            return ledger_service.write_snapshot(
                sessions, f'{{"value":"{label}"}}', None,
                owner_id=OWNER, broker_account_id=ACCOUNT)
        except ledger_service.VersionConflict as exc:
            return exc

    outcomes = _race(write)
    values = [value for kind, value in outcomes if kind == "ok"]
    assert sum(value == 1 for value in values) == 1
    assert sum(isinstance(value, ledger_service.VersionConflict) for value in values) == 1


def test_oauth_callback_state_has_one_consumer(portable_database):
    from app.api.connection_routes import _consume_callback_state

    _dialect, _engine, sessions = portable_database
    now = dt.datetime(2026, 8, 12, 10)
    digest = "a" * 64
    with sessions() as session, session.begin():
        session.add(User(
            user_id="task2-user", email_normalized="task2@example.test",
            display_name="Task 2"))
        session.flush()
        session.add(Membership(
            organization_id=OWNER, user_id="task2-user", role="owner"))
        session.flush()
        session.add(UserSession(
            session_id="task2-session", token_digest="b" * 64,
            user_id="task2-user", organization_id=OWNER,
            issued_at=now, expires_at=now + dt.timedelta(hours=1)))
        connection = BrokerConnection(
            owner_id=OWNER, broker_account_id=ACCOUNT, broker="kite",
            scope="kite:task2")
        session.add(connection)
        session.flush()
        session.add(OAuthCallbackState(
            state_digest=digest, connection_id=connection.id,
            session_id="task2-session", user_id="task2-user",
            organization_id=OWNER, created_at=now,
            expires_at=now + dt.timedelta(minutes=5)))

    def consume(_label):
        with sessions() as session, session.begin():
            return _consume_callback_state(session, digest=digest, now=now)

    outcomes = _race(consume)
    assert sorted(value for kind, value in outcomes if kind == "ok") == [False, True]


def test_oauth_callback_revoke_linearizes_before_credential_write(
        portable_database, monkeypatch):
    """A revoke that commits before credential UPDATE must make callback refuse."""
    from fastapi import HTTPException

    import app.api.connection_routes as routes
    from app.core import credential_vault
    from app.providers import connection_store

    _dialect, engine, sessions = portable_database
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    raw_state = "oauth-linearizable-state"
    digest = routes._digest_state(raw_state)
    user_id = "oauth-linearizable-user"
    session_id = "oauth-linearizable-session"
    with sessions() as session, session.begin():
        session.add(User(
            user_id=user_id, email_normalized="linearizable@example.test",
            display_name="Linearizable"))
        session.flush()
        session.add(Membership(
            organization_id=OWNER, user_id=user_id, role="owner"))
        session.flush()
        session.add(UserSession(
            session_id=session_id, token_digest="c" * 64,
            user_id=user_id, organization_id=OWNER, issued_at=now,
            expires_at=now + dt.timedelta(hours=1)))
        connection = BrokerConnection(
            owner_id=OWNER, broker_account_id=ACCOUNT, broker="kite",
            scope="kite:linearizable")
        session.add(connection)
        session.flush()
        connection_id = connection.id
        session.add(OAuthCallbackState(
            state_digest=digest, connection_id=connection_id,
            session_id=session_id, user_id=user_id, organization_id=OWNER,
            created_at=now, expires_at=now + dt.timedelta(minutes=5)))

    monkeypatch.setenv(
        credential_vault.ENV_KEY,
        "cnJycnJycnJycnJycnJycnJycnJycnJycnJycnJycnI=")
    monkeypatch.setattr(routes, "SessionLocal", sessions)
    monkeypatch.setattr(connection_store, "_default_session_factory", sessions)
    exchanged = threading.Event()
    at_credential_update = threading.Event()
    release_update = threading.Event()

    class Authenticator:
        def exchange(self, _secrets, _request_token):
            exchanged.set()
            return {"access_token": "must-not-survive-revoke"}

    monkeypatch.setattr(routes, "_authenticator", lambda _broker: Authenticator())

    def pause_callback_update(
            _connection, _cursor, statement, _parameters, _context, _many):
        if (threading.current_thread().name == "oauth-callback" and exchanged.is_set()
                and statement.lstrip().upper().startswith("UPDATE BROKER_CONNECTIONS")):
            at_credential_update.set()
            assert release_update.wait(timeout=5)

    sa.event.listen(engine, "before_cursor_execute", pause_callback_update)
    result = {}

    def callback():
        try:
            routes.oauth_callback(state=raw_state, request_token="one-time-token")
            result["status"] = 200
        except HTTPException as exc:
            result["status"] = exc.status_code
        except Exception as exc:  # the old SQLite path raises a stale-snapshot error
            result["error"] = exc

    worker = threading.Thread(target=callback, name="oauth-callback")
    try:
        worker.start()
        assert at_credential_update.wait(timeout=5)
        with sessions() as session, session.begin():
            session.execute(sa.update(BrokerConnection).where(
                BrokerConnection.id == connection_id).values(
                    status="revoked", credential_ciphertext=None,
                    credential_key_id=None, revoked_at=now))
        release_update.set()
        worker.join(timeout=10)
    finally:
        release_update.set()
        worker.join(timeout=10)
        sa.event.remove(engine, "before_cursor_execute", pause_callback_update)

    assert not worker.is_alive()
    assert result == {"status": 400}
    with sessions() as session:
        row = session.get(BrokerConnection, connection_id)
        assert row.status == "revoked"
        assert row.credential_ciphertext is None


def test_paper_authority_revision_race_has_one_transition_winner(portable_database):
    _dialect, _engine, sessions = portable_database
    with sessions() as session, session.begin():
        session.add(Project(project_id="task2-project", owner_id=OWNER, name="Task 2"))
        session.add(Deployment(
            id=712, owner_id=OWNER, broker_account_id=ACCOUNT, name="Task 2"))
        session.flush()
        session.add(IrPaperDeployment(
            id=812, owner_id=OWNER, broker_account_id=ACCOUNT,
            project_id="task2-project", graph_identifier="task2-graph",
            graph_version=1, graph_content_address="sha256:" + "a" * 64,
            deployment_id=712, instrument_key="NIFTY", interval="day",
            strategy_key="ir.task2", state="staged", revision=0))

    def transition(label):
        with sessions() as session, session.begin():
            row = paper_authority._for_update(
                session, 812, 0, owner_id=OWNER, broker_account_id=ACCOUNT)
            paper_authority._transition(session, row, f"paused")
            return label

    outcomes = _race(transition)
    assert sum(kind == "ok" for kind, _ in outcomes) == 1, outcomes
    errors = [value for kind, value in outcomes if kind == "error"]
    assert len(errors) == 1 and isinstance(errors[0], paper_authority.RevisionConflict)
    with sessions() as session:
        row = session.get(IrPaperDeployment, 812)
        assert row.revision == 1 and row.state == "paused"
