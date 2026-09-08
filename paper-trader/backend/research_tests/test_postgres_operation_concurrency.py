"""PostgreSQL portability contracts for the durable research scheduler."""
from __future__ import annotations

from research.domain.operations import ResearchOperationRepository


class _PostgresConnection:
    class _Dialect:
        name = "postgresql"

    dialect = _Dialect()

    def exec_driver_sql(self, statement, _parameters=None):
        if statement == "BEGIN IMMEDIATE":
            raise AssertionError("SQLite BEGIN IMMEDIATE reached PostgreSQL")


class _AdmissionSession:
    """Small SQL boundary fake; the repository behavior is the assertion target."""

    def __init__(self):
        self._connection = _PostgresConnection()
        self.bind = self._connection
        self.added = []
        self.committed = False
        self.info = {}

    def connection(self):
        return self._connection

    def get_bind(self):
        return self._connection

    def get_transaction(self):
        return None

    def in_transaction(self):
        # Admission already owns the transaction established by its first SQL read.
        # Mirror SQLAlchemy Session's interface used by the transactional outbox.
        return True

    def execute(self, _statement, _parameters=None):
        return None

    def scalar(self, statement):
        # Admission counts are zero; typed outbox identity/head lookups are absent.
        return 0 if "count(" in str(statement).lower() else None

    def add(self, row):
        self.added.append(row)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        return None


def test_postgresql_research_admission_never_executes_sqlite_begin_immediate():
    """A PostgreSQL research deployment must reach admission without SQLite SQL."""
    session = _AdmissionSession()

    result = ResearchOperationRepository(session).enqueue(
        owner_id="owner-a", trigger="manual", plan={}, build="test",
        provider_mode="mock", operation_id="operation-a",
    )

    assert result.operation_id == "operation-a"
    assert session.committed


# Actual PostgreSQL transactions below supplement, rather than replace, the
# historical dialect fake above.
import concurrent.futures
import threading

import pytest
from sqlalchemy import select, func

from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import ResearchOperation


@pytest.mark.parametrize("boundary", ["enqueue", "claim", "same_job"])
def test_real_postgresql_competing_workers_reserve_one_slot(pg_sandbox, boundary):
    engine = make_engine(pg_sandbox.research_url)
    init_research_db(engine)
    sessions = make_sessionmaker(engine)
    try:
        with sessions() as session:
            repo = ResearchOperationRepository(session)
            number = 15 if boundary == "enqueue" else 5 if boundary == "claim" else 1
            for i in range(number):
                repo.enqueue(owner_id="owner", operation_id=f"job-{i}", trigger="manual",
                             plan={}, build="b", provider_mode="mock")
            if boundary == "claim":
                for i in range(3):
                    assert repo.claim_operation(f"job-{i}", owner_id="owner", worker_id="seed")
        barrier = threading.Barrier(2)

        def compete(i):
            with sessions() as session:
                repo = ResearchOperationRepository(session)
                barrier.wait(timeout=10)
                if boundary == "enqueue":
                    try:
                        repo.enqueue(owner_id="owner", operation_id=f"extra-{i}", trigger="manual",
                                     plan={}, build="b", provider_mode="mock")
                        return "admitted"
                    except RuntimeError as exc:
                        assert "admission capacity" in str(exc)
                        return "refused"
                if boundary == "same_job":
                    result = repo.claim_operation("job-0", owner_id="owner", worker_id=f"worker-{i}")
                else:
                    result = repo.claim_next(owner_id="owner", worker_id=f"worker-{i}")
                return "admitted" if result is not None else "refused"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(compete, i) for i in range(2)]
            assert sorted(f.result(timeout=30) for f in futures) == ["admitted", "refused"]
        with sessions() as session:
            state = "pending" if boundary == "enqueue" else "running"
            assert session.scalar(select(func.count()).select_from(ResearchOperation).where(
                ResearchOperation.status == state)) == (16 if boundary == "enqueue" else 4 if boundary == "claim" else 1)
    finally:
        engine.dispose()
