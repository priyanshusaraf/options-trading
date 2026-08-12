"""Portable locking contracts for account-scoped money state."""
from __future__ import annotations

from types import SimpleNamespace
from contextlib import nullcontext

from sqlalchemy.dialects import postgresql

from app.core import paper_authority
from app.core.execution_book import PAPER, capital_for_book
from app.db.models import BrokerAccount, CapitalState


class _PostgresMoneySession:
    class _Connection:
        class _Dialect:
            name = "postgresql"

        dialect = _Dialect()

    def __init__(self):
        self.locked = False
        self.capital = object()
        self.no_autoflush = nullcontext()

    def connection(self):
        return self._Connection()

    def execute(self, statement, parameters=None):
        if "pg_advisory_xact_lock" in str(statement):
            raise AssertionError("existing money read acquired a bootstrap reservation")
        return None

    def get(self, model, identity):
        if model is BrokerAccount:
            return BrokerAccount(
                broker_account_id=identity, owner_id="owner-a", broker="paper",
                external_account_id="a", display_name="A")
        if model is CapitalState and identity == ("account-a", PAPER):
            return self.capital
        return None


def test_postgresql_existing_capital_read_does_not_acquire_bootstrap_reservation():
    """Routine cash reads must not retain a transaction-scoped advisory lock."""
    session = _PostgresMoneySession()

    assert capital_for_book(session, PAPER, broker_account_id="account-a") is session.capital


class _PostgresAuthoritySession:
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
        return SimpleNamespace(revision=3)


def test_postgresql_paper_authority_revision_read_locks_the_mutated_row():
    """Without a row lock two revision-3 transitions can both publish revision 4."""
    session = _PostgresAuthoritySession()

    paper_authority._for_update(
        session, 7, 3, owner_id="owner-a", broker_account_id="account-a")

    sql = str(session.statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in sql
