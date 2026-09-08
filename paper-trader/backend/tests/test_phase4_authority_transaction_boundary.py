"""Current-byte transaction ownership guards for the execution-plane seams."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

import app.db.concurrency as concurrency
from app.db.concurrency import caller_owned_savepoint

pytest_plugins = ("tests.test_portable_concurrency_integration",)


def _sqlite_session() -> tuple[sa.Engine, Session]:
    engine = sa.create_engine("sqlite://", future=True)
    return engine, Session(engine)


def _sqlite_probe_session() -> tuple[sa.Engine, Session]:
    """Create the probe schema without giving the tested Session prior SQL."""
    engine = sa.create_engine("sqlite://", future=True)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE boundary_probe (value TEXT NOT NULL)"))
    return engine, Session(engine)


def _probe_count(session: Session) -> int:
    return int(session.scalar(sa.text("SELECT count(*) FROM boundary_probe")) or 0)


def test_caller_owned_savepoint_creates_a_physical_root_from_a_clean_sqlite_session() -> None:
    engine, session = _sqlite_probe_session()
    try:
        assert session.get_transaction() is None
        with caller_owned_savepoint(session, scope="clean"):
            assert session.connection().connection.driver_connection.in_transaction
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        session.rollback()
        assert _probe_count(session) == 0
    finally:
        session.close()
        engine.dispose()


def test_caller_owned_savepoint_creates_a_physical_root_after_a_prior_read() -> None:
    engine, session = _sqlite_probe_session()
    try:
        session.execute(sa.text("SELECT 1"))
        assert not session.connection().connection.driver_connection.in_transaction
        with caller_owned_savepoint(session, scope="prior-read"):
            assert session.connection().connection.driver_connection.in_transaction
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        session.rollback()
        assert _probe_count(session) == 0
    finally:
        session.close()
        engine.dispose()


def test_caller_owned_savepoint_keeps_rows_pending_until_caller_finishes() -> None:
    engine, session = _sqlite_session()
    try:
        session.execute(sa.text("CREATE TABLE boundary_probe (value TEXT NOT NULL)"))
        session.commit()
        with caller_owned_savepoint(session, scope="test"):
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        assert session.connection().connection.driver_connection.in_transaction
        session.rollback()
        assert session.scalar(sa.text("SELECT count(*) FROM boundary_probe")) == 0
    finally:
        session.close()
        engine.dispose()


def test_caller_owned_savepoint_preserves_unrelated_caller_work() -> None:
    engine, session = _sqlite_session()
    try:
        session.execute(sa.text("CREATE TABLE boundary_probe (value TEXT NOT NULL)"))
        session.commit()
        session.execute(sa.text("INSERT INTO boundary_probe VALUES ('caller')"))
        with caller_owned_savepoint(session, scope="test"):
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        session.commit()
        assert session.scalars(sa.text("SELECT value FROM boundary_probe ORDER BY value")).all() == [
            "caller", "nested",
        ]
    finally:
        session.close()
        engine.dispose()


def test_explicit_caller_transaction_retains_commit_ownership() -> None:
    engine, session = _sqlite_probe_session()
    try:
        with session.begin():
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('caller')"))
            with caller_owned_savepoint(session, scope="explicit-caller"):
                session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        assert session.scalars(sa.text("SELECT value FROM boundary_probe ORDER BY value")).all() == [
            "caller", "nested",
        ]
    finally:
        session.close()
        engine.dispose()


def test_unproved_external_nested_sqlite_transaction_refuses_before_write() -> None:
    engine, session = _sqlite_session()
    try:
        session.execute(sa.text("SELECT 1"))
        with session.begin_nested():
            with pytest.raises(RuntimeError, match="unproved external nested"):
                with caller_owned_savepoint(session, scope="test"):
                    pass
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_recursive_helper_calls_share_the_proven_root_and_marker_clears_at_root_end() -> None:
    engine, session = _sqlite_probe_session()
    try:
        with caller_owned_savepoint(session, scope="outer"):
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('outer')"))
            with caller_owned_savepoint(session, scope="inner"):
                session.execute(sa.text("INSERT INTO boundary_probe VALUES ('inner')"))
        assert "caller_owned_savepoint_root" in session.info
        session.rollback()
        assert "caller_owned_savepoint_root" not in session.info
        assert _probe_count(session) == 0
    finally:
        session.close()
        engine.dispose()


def test_helper_does_not_finish_the_callers_transaction_when_commit_refuses() -> None:
    engine, session = _sqlite_probe_session()

    def refuse_commit(connection):
        if connection.engine is engine:
            raise sa.exc.DBAPIError.instance(
                "COMMIT", {}, RuntimeError("commit refusal"), RuntimeError
            )

    event.listen(engine, "commit", refuse_commit)
    try:
        with caller_owned_savepoint(session, scope="commit-refusal"):
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
            session.commit()
        # The failed outer finish must never make the still-live helper marker
        # borrowable.  The caller alone performs the recovery below.
        with pytest.raises(concurrency.TransactionBoundaryError,
                           match="failed Session|root proof became stale"):
            with caller_owned_savepoint(session, scope="after-commit-refusal"):
                pass
        session.rollback()
        assert _probe_count(session) == 0
    finally:
        event.remove(engine, "commit", refuse_commit)
        session.close()
        engine.dispose()


def test_unsupported_dialect_refuses_without_writing_and_allows_caller_rollback(
        monkeypatch) -> None:
    engine, session = _sqlite_probe_session()
    try:
        connection = session.connection()
        monkeypatch.setattr(connection.dialect, "name", "phase4_unsupported")
        with pytest.raises(concurrency.TransactionBoundaryError, match="unsupported database dialect"):
            with caller_owned_savepoint(session, scope="unsupported"):
                session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nope')"))
        session.rollback()
        assert _probe_count(session) == 0
    finally:
        session.close()
        engine.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_caller_owned_savepoint_keeps_postgresql_rows_pending_until_caller_finishes() -> None:
    url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"phase4_transaction_{uuid.uuid4().hex}"
    admin = sa.create_engine(url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, future=True,
                              connect_args={"options": f"-csearch_path={schema}"})
    session = Session(engine)
    try:
        session.execute(sa.text("CREATE TABLE boundary_probe (value TEXT NOT NULL)"))
        session.commit()
        with caller_owned_savepoint(session, scope="test"):
            session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        session.rollback()
        assert session.scalar(sa.text("SELECT count(*) FROM boundary_probe")) == 0
    finally:
        session.close()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_postgresql_external_nested_caller_is_accepted_with_a_physical_root() -> None:
    """PostgreSQL driver state proves a physical root before this savepoint."""
    url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"phase4_nested_{uuid.uuid4().hex}"
    admin = sa.create_engine(url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, future=True,
                              connect_args={"options": f"-csearch_path={schema}"})
    session = Session(engine)
    try:
        session.execute(sa.text("CREATE TABLE boundary_probe (value TEXT NOT NULL)"))
        session.commit()
        with session.begin_nested():
            with caller_owned_savepoint(session, scope="postgres-external-nested"):
                session.execute(sa.text("INSERT INTO boundary_probe VALUES ('nested')"))
        session.rollback()
        assert session.scalar(sa.text("SELECT count(*) FROM boundary_probe")) == 0
    finally:
        session.close()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_public_computation_seam_leaves_no_postgresql_row_after_caller_rollback() -> None:
    """Exercise the real non-authoritative seam on a fresh PostgreSQL schema."""
    from app.backtest import public_computation
    from app.db.models import Base, BacktestComputation
    from tests.test_public_backtest_computation import _payload

    url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"phase4_public_{uuid.uuid4().hex}"
    admin = sa.create_engine(url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, future=True,
                              connect_args={"options": f"-csearch_path={schema}"})
    session = Session(engine)
    address = "a" * 64
    try:
        Base.metadata.create_all(engine)
        public_computation.put_immutable(
            session, execution_address=address, dataset_address="c" * 64,
            strategy_key="trend_impulse_v3",
            strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG[
                "trend_impulse_v3"]["version"],
            policy_address=address, payload=_payload(address))
        session.rollback()
        assert session.scalar(sa.select(sa.func.count()).select_from(BacktestComputation)) == 0
    finally:
        session.close()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.parametrize("outcome", ["rollback", "commit-refusal"])
def test_public_computation_real_writer_leaves_no_sqlite_row_after_caller_failure(outcome: str) -> None:
    """The actual immutable writer remains inside the SQLite caller outcome."""
    from app.backtest import public_computation
    from app.db.models import Base, BacktestComputation
    from tests.test_public_backtest_computation import _payload

    engine = sa.create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    address = "d" * 64
    def refuse_commit(connection):
        if connection.engine is engine:
            raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
    if outcome == "commit-refusal":
        event.listen(engine, "commit", refuse_commit)
    try:
        with Session(engine) as session:
            public_computation.put_immutable(
                session, execution_address=address, dataset_address="e" * 64,
                strategy_key="trend_impulse_v3",
                strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG[
                    "trend_impulse_v3"]["version"], policy_address=address,
                payload=_payload(address))
            if outcome == "rollback":
                session.rollback()
            else:
                with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                    session.commit()
                session.rollback()
        with Session(engine) as observer:
            assert observer.get(BacktestComputation, address) is None
    finally:
        if outcome == "commit-refusal":
            event.remove(engine, "commit", refuse_commit)
        engine.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_public_computation_real_writer_postgresql_commit_refusal_has_no_fresh_row() -> None:
    from app.backtest import public_computation
    from app.db.models import Base, BacktestComputation
    from tests.test_public_backtest_computation import _payload

    url = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"phase4_public_refusal_{uuid.uuid4().hex}"
    admin = sa.create_engine(url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, future=True,
                              connect_args={"options": f"-csearch_path={schema}"})
    address = "f" * 64
    def refuse_commit(connection):
        if connection.engine is engine:
            raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
    try:
        Base.metadata.create_all(engine)
        event.listen(engine, "commit", refuse_commit)
        with Session(engine) as session:
            public_computation.put_immutable(
                session, execution_address=address, dataset_address="e" * 64,
                strategy_key="trend_impulse_v3",
                strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG[
                    "trend_impulse_v3"]["version"], policy_address=address,
                payload=_payload(address))
            with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                session.commit()
            session.rollback()
        with Session(engine) as observer:
            assert observer.get(BacktestComputation, address) is None
    finally:
        event.remove(engine, "commit", refuse_commit)
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_every_classified_execution_seam_uses_the_shared_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        "app/core/strategy_admissions.py": "execution_strategy_admission",
        "app/backtest/repository.py": "backtest_claimed_result_batch",
        "app/backtest/public_computation.py": "public_backtest_computation",
        "app/ledger/service.py": "ledger_snapshot",
    }
    for relative, scope in expected.items():
        source = (root / relative).read_text()
        assert (
            f'caller_owned_savepoint(session, scope="{scope}")' in source
            or f'caller_owned_savepoint(s, scope="{scope}")' in source
        )


def test_helper_contains_no_caller_lifecycle_operation() -> None:
    source = Path(concurrency.__file__).read_text()
    helper = source[source.index("def caller_owned_savepoint"):source.index("\ndef has_pending_writes")]
    for forbidden in (
        "session.commit(", "session.rollback(", "session.close(",
        "session.invalidate(", "Session(", "create_engine(", "retry",
    ):
        assert forbidden not in helper


def test_public_computation_refuses_invalid_unrelated_orm_work_before_its_savepoint() -> None:
    from app.backtest import public_computation
    from app.db.models import Base, BacktestComputation
    from tests.test_public_backtest_computation import _payload

    engine = sa.create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    address = "b" * 64
    try:
        with Session(engine) as session:
            session.add(BacktestComputation())
            with pytest.raises(concurrency.TransactionBoundaryError,
                               match="pre-savepoint caller flush failure"):
                public_computation.put_immutable(
                    session, execution_address=address, dataset_address="c" * 64,
                    strategy_key="trend_impulse_v3",
                    strategy_version=public_computation.PUBLIC_STRATEGY_CATALOG[
                        "trend_impulse_v3"]["version"],
                    policy_address=address, payload=_payload(address))
            session.rollback()
        with Session(engine) as observer:
            assert observer.get(BacktestComputation, address) is None
    finally:
        engine.dispose()


def _claimed_run(sessions, admitted_backtest_receipt):
    """Seed one fenced run through the public repository path."""
    import datetime as dt
    from app.backtest import repository
    from tests.test_portable_concurrency_integration import OWNER, _pending_run

    run_id = _pending_run(sessions, admitted_backtest_receipt)
    with sessions() as session:
        claim = repository.claim_run(
            session, owner_id=OWNER, run_id=run_id, claimed_by="phase4-boundary",
            now=dt.datetime(2026, 8, 12, 10), lease_seconds=60)
        session.commit()
    assert claim is not None
    return run_id, claim.claim_token


@pytest.mark.parametrize("outcome", ["rollback", "commit-refusal", "commit-replay"])
def test_append_claimed_result_batch_is_a_real_caller_owned_boundary(
        portable_database, admitted_backtest_receipt, outcome: str) -> None:
    """Actual claimed-batch writer: run state and result rows share caller fate."""
    import datetime as dt
    from app.backtest import repository
    from app.db.models import BacktestResult, BacktestRun
    from tests.test_portable_concurrency_integration import OWNER

    _dialect, engine, sessions = portable_database
    run_id, token = _claimed_run(sessions, admitted_backtest_receipt)
    with sessions() as seed_observer:
        admission_address = seed_observer.get(BacktestRun, run_id).admission_address
        admitted = repository.load_verified_admission(
            seed_observer, owner_id=OWNER, admission_address=admission_address)
    cell_key = f"phase4-batch-{uuid.uuid4().hex}"
    value = {
        "instrument_key": cell_key, "name": cell_key, "segment": "nse_delivery",
        "strategy_key": admitted.strategy_key, "interval": "day", "bars": 1,
        "strategy_version": admitted.strategy_version,
        "graph_address": admitted.graph_address,
        "attribution_state": admitted.attribution_state,
        "params_hash": "strategy-version-and-params-v1", "error": "",
        "admission_address": admission_address,
    }
    if outcome == "commit-refusal":
        def refuse_commit(connection):
            if connection.engine is engine:
                raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
        event.listen(engine, "commit", refuse_commit)
    try:
        with sessions() as session:
            assert repository.append_claimed_result_batch(
                session, owner_id=OWNER, run_id=run_id, claim_token=token,
                values=[value], now=dt.datetime(2026, 8, 12, 10, 0, 1))
            if outcome == "rollback":
                session.rollback()
            elif outcome == "commit-refusal":
                with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                    session.commit()
                session.rollback()
            else:
                session.commit()
        with sessions() as observer:
            result_count = observer.scalar(sa.select(sa.func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == OWNER, BacktestResult.run_id == run_id))
            run = observer.get(BacktestRun, run_id)
            if outcome == "commit-replay":
                assert result_count == 1 and run.done == 1
                assert repository.append_claimed_result_batch(
                    observer, owner_id=OWNER, run_id=run_id, claim_token=token,
                    values=[value], now=dt.datetime(2026, 8, 12, 10, 0, 2))
                observer.commit()
                assert observer.scalar(sa.select(sa.func.count()).select_from(BacktestResult).where(
                    BacktestResult.owner_id == OWNER, BacktestResult.run_id == run_id)) == 1
            else:
                assert result_count == 0 and run.done == 0 and run.status == "running"
    finally:
        if outcome == "commit-refusal":
            event.remove(engine, "commit", refuse_commit)


@pytest.mark.parametrize("outcome", ["rollback", "commit-refusal", "commit-replay"])
def test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary(
        portable_database, admitted_backtest_receipt, outcome: str) -> None:
    """Actual terminal writer keeps run state and terminal outbox event atomic."""
    import datetime as dt
    from app.backtest import repository
    from app.db.models import BacktestRun
    from app.events.planes import execution_outbox
    from tests.test_portable_concurrency_integration import OWNER

    _dialect, engine, sessions = portable_database
    run_id, token = _claimed_run(sessions, admitted_backtest_receipt)
    producer_key = f"backtest:{OWNER}:{run_id}:terminal:done"
    if outcome == "commit-refusal":
        def refuse_commit(connection):
            if connection.engine is engine:
                raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
        event.listen(engine, "commit", refuse_commit)
    try:
        with sessions() as session:
            assert repository.complete_claim(
                session, owner_id=OWNER, run_id=run_id, claim_token=token, status="done",
                now=dt.datetime(2026, 8, 12, 10, 0, 1))
            if outcome == "rollback":
                session.rollback()
            elif outcome == "commit-refusal":
                with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                    session.commit()
                session.rollback()
            else:
                session.commit()
        event_model = execution_outbox().models.Event
        with sessions() as observer:
            run = observer.get(BacktestRun, run_id)
            terminal_events = observer.scalar(sa.select(sa.func.count()).select_from(event_model).where(
                event_model.producer_key == producer_key))
            if outcome == "commit-replay":
                assert run.status == "done" and terminal_events == 1
                assert not repository.complete_claim(
                    observer, owner_id=OWNER, run_id=run_id, claim_token=token, status="done",
                    now=dt.datetime(2026, 8, 12, 10, 0, 2))
                observer.rollback()
            else:
                assert run.status == "running" and terminal_events == 0
    finally:
        if outcome == "commit-refusal":
            event.remove(engine, "commit", refuse_commit)


@pytest.mark.parametrize("outcome", ["commit", "commit-refusal"])
def test_ledger_snapshot_real_seam_commits_snapshot_and_outbox_together(
        portable_database, outcome: str) -> None:
    from app.events.planes import ledger_outbox
    from app.ledger import service as ledger_service
    from app.ledger.models import LedgerSnapshot
    from tests.test_portable_concurrency_integration import ACCOUNT, OWNER

    _dialect, engine, sessions = portable_database
    producer_key = f"snapshot:{OWNER}:{ACCOUNT}:1"
    if outcome == "commit-refusal":
        def refuse_commit(connection):
            if connection.engine is engine:
                raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
        event.listen(engine, "commit", refuse_commit)
    try:
        if outcome == "commit":
            assert ledger_service.write_snapshot(
                sessions, '{"phase4":1}', None, owner_id=OWNER,
                broker_account_id=ACCOUNT) == 1
        else:
            with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                ledger_service.write_snapshot(
                    sessions, '{"phase4":1}', None, owner_id=OWNER,
                    broker_account_id=ACCOUNT)
        event_model = ledger_outbox().models.Event
        with sessions() as observer:
            snapshot = observer.get(LedgerSnapshot, (OWNER, ACCOUNT, 1))
            events = observer.scalar(sa.select(sa.func.count()).select_from(event_model).where(
                event_model.producer_key == producer_key))
            if outcome == "commit":
                assert snapshot is not None and snapshot.payload == '{"phase4":1}' and events == 1
            else:
                assert snapshot is None and events == 0
    finally:
        if outcome == "commit-refusal":
            event.remove(engine, "commit", refuse_commit)
