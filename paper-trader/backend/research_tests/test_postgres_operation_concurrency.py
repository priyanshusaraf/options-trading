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
        self.added = []
        self.committed = False
        self.info = {}

    def connection(self):
        return self._connection

    def get_bind(self):
        return self._connection

    def get_transaction(self):
        return None

    def execute(self, _statement, _parameters=None):
        return None

    def scalar(self, _statement):
        return 0

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
