"""SQL boundary proofs for PostgreSQL durable-work claims."""
from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.backtest import repository


class _PostgresSession:
    class _Connection:
        class _Dialect:
            name = "postgresql"

        dialect = _Dialect()

    def __init__(self):
        self.statement = None

    def connection(self):
        return self._Connection()

    def get_bind(self):
        return self._Connection()

    def scalar(self, statement):
        self.statement = statement
        return None


def test_postgresql_backtest_candidate_claim_skips_rows_locked_by_other_workers():
    """Removing SKIP LOCKED would serialize independent dispatcher workers."""
    session = _PostgresSession()

    assert repository.claim_next_run(
        session, owner_id="owner-a", claimed_by="worker-a") is None

    sql = str(session.statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE SKIP LOCKED" in sql
